import os
from collections import defaultdict
from datetime import datetime
from typing import Optional

import psycopg2
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from structs import Game
from structs import Player


class DbConnectionProvider:
    def __init__(self, pantheon_type: str):
        assert pantheon_type in {"old", "new"}
        self.pantheon_type = pantheon_type

    def get_creator(self, db_type: str):
        if db_type == "mimir":
            user = os.getenv("MIMIR_USER") or "mimir"
            password = os.getenv("MIMIR_PASSWORD") or "mimir"
            db_name = os.getenv("MIMIR_DB_NAME") or ("mimir_new" if self.pantheon_type == "new" else "mimir_old")
            host = os.getenv("MIMIR_HOST") or "localhost"
            port = os.getenv("MIMIR_PORT") or 5432
            port = int(port)
        elif db_type == "frey":
            user = os.getenv("FREY_USER") or "frey"
            password = os.getenv("FREY_PASSWORD") or "frey"
            db_name = os.getenv("FREY_DB_NAME") or "frey"
            host = os.getenv("FREY_HOST") or "localhost"
            port = os.getenv("FREY_PORT") or 5432
            port = int(port)
        else:
            raise Exception(f"Wrong db_type {db_type}")
        return psycopg2.connect(user=user, password=password, host=host, port=port, dbname=db_name)

    def get_session(self, db_type: str) -> Session:
        engine = sqlalchemy.create_engine(url="postgresql+psycopg2://", creator=lambda: self.get_creator(db_type=db_type))
        session_maker = sessionmaker(bind=engine)
        db_session: Session = session_maker()
        return db_session


def log_tournaments_info(pantheon_type: str, online: bool):
    db_connection_provider = DbConnectionProvider(pantheon_type=pantheon_type)

    with db_connection_provider.get_session(db_type="mimir") as db_session:
        if online:
            where_condition = "(e.is_online != 0)"
        else:
            where_condition = "(e.is_online = 0) and (e.sync_start != 0)"
        result = db_session.execute(text(f"select e.id, e.title, min(s.start_date), max(s.end_date)"
                                         f" from event e"
                                         f" join session s on (e.id = s.event_id)"
                                         f" where {where_condition}"
                                         f" group by e.id"
                                         f" order by e.id"))
        print(f"Tournaments from pantheon type {pantheon_type}:")
        count = 0
        for row in result.all():
            event_id = int(row[0])
            title = row[1].strip()
            start_time: datetime = row[2]
            end_time: datetime = row[3]
            print(f"{event_id} - from {start_time} to {end_time} - '{title}'")
            count += 1
        print(f"Found {count} tournaments in pantheon type {pantheon_type}")


# noinspection SqlDialectInspection,SqlNoDataSourceInspection
def load_games(pantheon_type: str, online: bool, player_names_file: Optional[str], force_event_ids_to_load: Optional[list[int]]) -> list[Game]:
    db_connection_provider = DbConnectionProvider(pantheon_type=pantheon_type)

    good_event_ids: set[int] = set()
    with db_connection_provider.get_session(db_type="mimir") as db_session:
        # https://github.com/MahjongPantheon/pantheon/blob/7a3c326d7fc8339e4a874371c5c2ae543712b36d/Mimir/src/models/Event.php#L478-L480
        if online:
            where_condition = "(is_online != 0)"
        else:
            where_condition = "(is_online = 0) and (sync_start != 0)"
        result = db_session.execute(text(f"select id from event where {where_condition}"))
        for row in result.all():
            event_id = int(row[0])
            good_event_ids.add(event_id)

    if force_event_ids_to_load is not None:
        good_event_ids.update(force_event_ids_to_load)

    session_date_map: dict[int, datetime] = {}
    session_event_map: dict[int, int] = {}
    total_game_count: dict[int, int] = defaultdict(int)
    with db_connection_provider.get_session(db_type="mimir") as db_session:
        result = db_session.execute(text("select id, event_id, end_date from session where status = 'finished'"))
        for row in result.all():
            session_id = int(row[0])
            event_id = int(row[1])
            session_date = row[2]
            if event_id not in good_event_ids:
                continue
            assert session_id not in session_date_map
            session_date_map[session_id] = session_date
            session_event_map[session_id] = event_id
            total_game_count[event_id] += 1
    print(f"{len(session_date_map)} sessions loaded")

    session_results: dict[int, dict[int, tuple[int, float]]] = defaultdict(dict)
    with db_connection_provider.get_session(db_type="mimir") as db_session:
        result = db_session.execute(text("select session_id, player_id, place, rating_delta from session_results"))
        for row in result.all():
            session_id = int(row[0])
            player_id = int(row[1])
            place = int(row[2])
            score = float(row[3])
            if session_id not in session_date_map:
                continue
            event_game_count = total_game_count[session_event_map[session_id]]
            assert event_game_count > 0
            assert 1 <= place <= 4
            assert isinstance(score, (int, float))
            assert -1000000 <= score <= 1000000
            assert player_id not in session_results[session_id].values()
            session_results[session_id][player_id] = (place, score)
    print(f"{len(session_results)} sessions with results loaded")

    broken_session_ids = []
    for session_id, player_results_map in session_results.items():
        if len(player_results_map) != 4:
            print(f"Session {session_id} is broken, players are: {set(player_results_map.keys())}")
            broken_session_ids.append(session_id)
    print(f"There are {len(broken_session_ids)} broken sessions")

    for session_id in broken_session_ids:
        session_date_map.pop(session_id)
        session_results.pop(session_id)

    players_by_id: dict[int, Player] = {}
    if pantheon_type == "new":
        if player_names_file is not None and os.path.exists(player_names_file):
            print(f"Loading players from csv file {player_names_file}")
            with open(player_names_file) as fd:
                line: str
                for index, line in enumerate(fd):
                    if index == 0:
                        continue
                    line = line.strip()
                    if not line:
                        continue
                    i = 0
                    while line[i].isdigit():
                        i += 1
                    player_id = int(line[:i])
                    player_name = line[i + 1:]
                    if len(player_name) >= 2 and player_name.startswith("\"") and player_name.endswith("\""):
                        player_name = player_name[1:-1]
                    player_name = player_name.strip()
                    while "\"\"" in player_name:
                        player_name = player_name.replace("\"\"", "\"")
                    assert player_id not in players_by_id
                    players_by_id[player_id] = Player.create_new(name=player_name, player_id=player_id)
            print(f"{len(players_by_id)} players loaded from csv file")
        else:
            print("Loading players from Frey DB")
            with db_connection_provider.get_session(db_type="frey") as db_session:
                result = db_session.execute(text("select id, title from person"))
                for row in result.all():
                    player_id = int(row[0])
                    player_name = row[1].strip()
                    assert player_id not in players_by_id
                    players_by_id[player_id] = Player.create_new(name=player_name, player_id=player_id)
            print(f"{len(players_by_id)} players loaded from new DB")
    elif pantheon_type == "old":
        with db_connection_provider.get_session(db_type="mimir") as db_session:
            result = db_session.execute(text("select id, display_name from player"))
            for row in result.all():
                player_id = int(row[0])
                player_name = row[1].strip()
                assert player_id not in players_by_id
                players_by_id[player_id] = Player.create_old(name=player_name, player_id=player_id)
        print(f"{len(players_by_id)} players loaded from old DB")
    else:
        raise Exception(f"Wrong pantheon_type: {pantheon_type}")

    sessions_by_date: list[int] = list(session_results.keys())
    sessions_by_date.sort(key=lambda s: session_date_map[s])
    print("Sessions sorted by date")

    games: list[Game] = []
    for session_id in sessions_by_date:
        session_date = session_date_map[session_id]
        event_id = session_event_map[session_id]
        player_results_map = session_results[session_id]
        players: list[Player] = []
        places: list[int] = []
        scores: list[float] = []
        for player_id, (place, score) in player_results_map.items():
            players.append(players_by_id[player_id])
            places.append(place)
            scores.append(score)
        if -999.99 <= min(scores) or max(scores) <= 999.99:  # can be +42000 or +42.0
            for i in range(len(scores)):
                scores[i] *= 1000.0
        games.append(Game(pantheon_type=pantheon_type,
                          event_id=event_id,
                          session_id=session_id,
                          session_date=session_date,
                          players=players,
                          places=places,
                          scores=scores))
    print("Games built")
    return games
