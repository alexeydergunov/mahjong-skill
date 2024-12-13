from collections import defaultdict
from datetime import datetime
from typing import Optional

import psycopg2
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from players_mapping import REPLACEMENT_PLAYERS
from players_mapping import SAME_PLAYERS
from structs import Game


def log_tournaments_info(db_name: str):
    def creator():
        c = psycopg2.connect(user="mimir", password="mimir", host="localhost", port=5432, dbname=db_name)
        return c

    engine = sqlalchemy.create_engine(url="postgresql+psycopg2://", creator=creator)
    session_maker = sessionmaker(bind=engine)
    db_session: Session = session_maker()

    result = db_session.execute(text(f"select e.id, e.title, min(s.start_date), max(s.end_date)"
                                     f" from event e"
                                     f" join session s on (e.id = s.event_id)"
                                     f" where (e.is_online = 0) and (e.sync_start != 0)"
                                     f" group by e.id"
                                     f" order by e.id"))
    print(f"Tournaments from db {db_name}:")
    count = 0
    for row in result.all():
        event_id = int(row[0])
        title = row[1].strip()
        start_time: datetime = row[2]
        end_time: datetime = row[3]
        print(f"{event_id} - from {start_time} to {end_time} - '{title}'")
        count += 1
    print(f"Found {count} tournaments in db {db_name}")
    db_session.close()


# noinspection SqlDialectInspection,SqlNoDataSourceInspection
def load_games(pantheon_type: str, db_name: str, player_names_file: Optional[str], force_event_ids_to_load: Optional[list[int]]) -> list[Game]:
    def creator():
        c = psycopg2.connect(user="mimir", password="mimir", host="localhost", port=5432, dbname=db_name)
        return c

    engine = sqlalchemy.create_engine(url="postgresql+psycopg2://", creator=creator)
    session_maker = sessionmaker(bind=engine)
    db_session: Session = session_maker()

    # https://github.com/MahjongPantheon/pantheon/blob/7a3c326d7fc8339e4a874371c5c2ae543712b36d/Mimir/src/models/Event.php#L478-L480
    good_event_ids: set[int] = set()
    result = db_session.execute(text(f"select id from event where (is_online = 0) and (sync_start != 0)"))
    for row in result.all():
        event_id = int(row[0])
        good_event_ids.add(event_id)

    if force_event_ids_to_load is not None:
        good_event_ids.update(force_event_ids_to_load)

    session_date_map: dict[int, datetime] = {}
    session_event_map: dict[int, int] = {}
    total_game_count: dict[int, int] = defaultdict(int)
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
    result = db_session.execute(text("select session_id, player_id, place, rating_delta from session_results"))
    for row in result.all():
        session_id = int(row[0])
        player_id = int(row[1])
        place = int(row[2])
        score = float(row[3])
        if session_id not in session_date_map:
            continue
        event_game_count = total_game_count[session_event_map[session_id]]
        if event_game_count < 6:  # there are some legal events with 8 players and 3 rounds
            continue
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

    player_names: dict[int, str] = {}
    if player_names_file is not None:
        # new pantheon, no sensitive data
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
                assert player_id not in player_names
                player_names[player_id] = player_name
        print(f"{len(player_names)} players loaded from csv file")
    else:
        # old pantheon
        result = db_session.execute(text("select id, display_name from player"))
        for row in result.all():
            player_id = int(row[0])
            player_name = row[1].strip()
            assert player_id not in player_names
            player_names[player_id] = player_name
        print(f"{len(player_names)} players loaded from old DB")

    db_session.close()

    canonical_player_names: dict[str, str] = {}
    for same_players_list in SAME_PLAYERS:
        canonical_name = same_players_list[0]
        for player_name in same_players_list:
            assert player_name not in canonical_player_names
            canonical_player_names[player_name] = canonical_name
    for player_id in player_names.keys():
        if player_names[player_id] in canonical_player_names:
            player_names[player_id] = canonical_player_names[player_names[player_id]]

    replacement_player_ids: set[int] = set()
    for player_id, player_name in player_names.items():
        if player_name in REPLACEMENT_PLAYERS:
            replacement_player_ids.add(player_id)
            print(f"Found replacement player: {player_id} with name {player_name}")

    ids_by_name_map: dict[str, list[int]] = defaultdict(list)
    for player_id, player_name in player_names.items():
        ids_by_name_map[player_name].append(player_id)
    print("Replaced same players with a canonical name")

    canonical_player_ids_map: dict[int, int] = {}
    for player_name, player_ids in ids_by_name_map.items():
        player_ids.sort()
        canonical_id = player_ids[0]
        if len(player_ids) > 1:
            print(f"There are several ids for player {player_name}: {player_ids}, choose {canonical_id}")
        for player_id in player_ids:
            canonical_player_ids_map[player_id] = canonical_id
    assert len(canonical_player_ids_map) == len(player_names)
    print("Chosen canonical player ids")

    for session_id in session_results.keys():
        player_results_map: dict[int, tuple[int, float]] = session_results[session_id]
        places: set[int] = {v[0] for v in player_results_map.values()}
        assert places == {1, 2, 3, 4}
        new_player_results_map: dict[int, tuple[int, float]] = {}
        for player_id, player_results in player_results_map.items():
            new_player_id = canonical_player_ids_map[player_id]
            new_player_results_map[new_player_id] = player_results
        session_results[session_id] = new_player_results_map
    print("Player ids replaced")

    player_ids_to_forget = set(player_names.keys()) - set(canonical_player_ids_map.values())
    for player_id in player_ids_to_forget:
        player_names.pop(player_id)
    print("Duplicate player names deleted")

    sessions_by_date: list[int] = list(session_results.keys())
    sessions_by_date.sort(key=lambda s: session_date_map[s])
    print("Sessions sorted by date")

    games: list[Game] = []
    for session_id in sessions_by_date:
        session_date = session_date_map[session_id]
        event_id = session_event_map[session_id]
        player_results_map = session_results[session_id]
        players: list[str] = []
        places: list[int] = []
        scores: list[float] = []
        for player_id, (place, score) in player_results_map.items():
            players.append(player_names[player_id])
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
