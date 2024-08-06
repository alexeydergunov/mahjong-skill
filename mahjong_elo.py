import math
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

START_RATING = 1500.0
ELO_K = 10.0
MAX_RATING_DIFF = 400.0


def get_delta(player_rating_map: dict[int, float], id1: int, id2: int, first_win: bool):
    assert id1 in player_rating_map
    assert id2 in player_rating_map
    r1 = player_rating_map[id1]
    r2 = player_rating_map[id2]
    expected = 1.0 / (1.0 + math.pow(10.0, min(r2 - r1, MAX_RATING_DIFF) / MAX_RATING_DIFF))
    actual = 1.0 if first_win else 0.0
    return ELO_K * (actual - expected)


def process_game(session_id: int, player_rating_map: dict[int, float], place_player_map: dict[int, int], replacement_player_ids: set[int]):
    delta_map = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    pvp_matches_count = 0
    for place_1, player_1 in place_player_map.items():
        for place_2, player_2 in place_player_map.items():
            if player_1 == player_2:
                continue
            assert place_1 != place_2
            pvp_matches_count += 1
            if player_1 in replacement_player_ids or player_2 in replacement_player_ids:
                # print(f"Player {player_1} or {player_2} is replacement player")
                continue
            delta_map[place_1] += get_delta(player_rating_map=player_rating_map, id1=player_1, id2=player_2, first_win=place_1 < place_2)
    if pvp_matches_count != 12:
        print(f"Session {session_id} is broken: pvp_matches_count = {pvp_matches_count}, probably same players played from different accounts")
        return
    for place, delta in delta_map.items():
        player_id = place_player_map[place]
        player_rating_map[player_id] += delta


class DbData:
    def __init__(self,
                 session_date_map: dict[int, datetime],
                 session_results: dict[int, dict[int, int]],
                 player_names: dict[int, str],
                 replacement_player_ids: set[int]):
        self.session_date_map = session_date_map
        self.session_results = session_results
        self.player_names = player_names
        self.replacement_player_ids = replacement_player_ids
        self.player_place_stats: Optional[dict[int, list[int]]] = None
        self.player_rating_map: Optional[dict[int, float]] = None

    # noinspection SqlDialectInspection,SqlNoDataSourceInspection
    @staticmethod
    def create(is_new: bool, without_clubs: bool, without_online: bool) -> 'DbData':
        # db_name = "mimir_new_2024_02_15" if is_new else "mimir_old"
        # db_name = "mimir_new_2024_05_14" if is_new else "mimir_old"
        db_name = "mimir_new_2024_08_05" if is_new else "mimir_old"

        def creator():
            c = psycopg2.connect(user="mimir", password="mimir", host="localhost", port=5432, dbname=db_name)
            return c

        engine = sqlalchemy.create_engine(url="postgresql+psycopg2://", creator=creator)
        session_maker = sessionmaker(bind=engine)
        session: Session = session_maker()

        good_event_ids: set[int] = set()
        auto_seating_statement = "auto_seating = 1" if without_clubs is True else "auto_seating in (0, 1)"
        online_statement = "is_online = 0" if without_online is True else "is_online in (0, 1)"
        result = session.execute(text(f"select id from event where {auto_seating_statement} and {online_statement}"))
        for row in result.all():
            event_id = int(row[0])
            good_event_ids.add(event_id)

        session_date_map: dict[int, datetime] = {}
        result = session.execute(text("select id, event_id, end_date from session where status = 'finished'"))
        for row in result.all():
            session_id = int(row[0])
            event_id = int(row[1])
            session_date = row[2]
            if event_id not in good_event_ids:
                continue
            assert session_id not in session_date_map
            session_date_map[session_id] = session_date
        print(f"{len(session_date_map)} sessions loaded")

        session_results: dict[int, dict[int, int]] = defaultdict(dict)
        result = session.execute(text("select session_id, player_id, place from session_results"))
        for row in result.all():
            session_id = int(row[0])
            player_id = int(row[1])
            place = int(row[2])
            if session_id not in session_date_map:
                continue
            assert 1 <= place <= 4
            assert player_id not in session_results[session_id].values()
            session_results[session_id][place] = player_id
        print(f"{len(session_results)} sessions with results loaded")

        broken_session_ids = []
        for session_id, place_player_map in session_results.items():
            if len(place_player_map) != 4:
                print(f"Session {session_id} is broken, places are: {set(place_player_map.keys())}")
                broken_session_ids.append(session_id)
        print(f"There are {len(broken_session_ids)} broken sessions")

        for session_id in broken_session_ids:
            session_date_map.pop(session_id)
            session_results.pop(session_id)

        player_names: dict[int, str] = {}
        if is_new:
            # with open("/home/dergunov/test/mimir_2024_02_15/data-1707938621941.csv") as fd:
            # with open("/home/dergunov/test/mimir_2024_05_14/data-1715691561372.csv") as fd:
            with open("/home/dergunov/test/mimir_2024_08_05/data-1722873805934.csv") as fd:
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
            result = session.execute(text("select id, display_name from player"))
            for row in result.all():
                player_id = int(row[0])
                player_name = row[1].strip()
                assert player_id not in player_names
                player_names[player_id] = player_name
            print(f"{len(player_names)} players loaded from old DB")

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

        for place_player_map in session_results.values():
            assert set(place_player_map.keys()) == {1, 2, 3, 4}
            for place in range(1, 5):
                place_player_map[place] = canonical_player_ids_map[place_player_map[place]]
        print("Player ids replaced")

        player_ids_to_forget = set(player_names.keys()) - set(canonical_player_ids_map.values())
        for player_id in player_ids_to_forget:
            player_names.pop(player_id)

        session.close()

        return DbData(session_date_map=session_date_map,
                      session_results=session_results,
                      player_names=player_names,
                      replacement_player_ids=replacement_player_ids)

    def build_rating_map(self,
                         old_player_rating_map: dict[int, float],
                         old_player_stats_map: dict[int, list[int]],
                         old_player_names_map: dict[int, str]) -> tuple[dict[int, float], dict[int, list[int]]]:
        old_rating_by_name: dict[str, float] = {}
        old_stats_by_name: dict[str, list[int]] = {}
        for old_player_id, old_player_rating in old_player_rating_map.items():
            assert old_player_id in old_player_stats_map
            assert old_player_id in old_player_names_map
            old_player_stats = old_player_stats_map[old_player_id]
            old_player_name = old_player_names_map[old_player_id]
            assert old_player_name not in old_rating_by_name
            assert old_player_name not in old_stats_by_name
            old_rating_by_name[old_player_name] = old_player_rating
            old_stats_by_name[old_player_name] = old_player_stats
        print("Finished building old -> new rating map")

        new_player_rating_map: dict[int, float] = {}
        new_player_stats_map: dict[int, list[int]] = {}
        new_players_appearing_in_old: set[str] = set()
        for new_player_id, new_player_name in self.player_names.items():
            old_player_rating: Optional[float] = old_rating_by_name.get(new_player_name)
            if old_player_rating is None:
                new_player_rating_map[new_player_id] = START_RATING
                new_player_stats_map[new_player_id] = [0, 0, 0, 0]
            else:
                assert new_player_name in old_stats_by_name
                new_player_rating_map[new_player_id] = old_player_rating
                new_player_stats_map[new_player_id] = list(old_stats_by_name[new_player_name])
                new_players_appearing_in_old.add(new_player_name)
        print(f"{len(new_players_appearing_in_old)} players appearing in both pantheon instances")

        # fill old ratings for players who don't appear in new version
        for old_player_id, old_player_rating in old_player_rating_map.items():
            old_player_name = old_player_names_map[old_player_id]
            if old_player_name not in new_players_appearing_in_old:
                # negative ids
                new_player_rating_map[-old_player_id] = old_player_rating
                new_player_stats_map[-old_player_id] = list(old_player_stats_map[old_player_id])
                self.player_names[-old_player_id] = old_player_name

        return new_player_rating_map, new_player_stats_map

    def process(self,
                old_player_rating_map: Optional[dict[int, float]] = None,
                old_player_stats_map: Optional[dict[int, list[int]]] = None,
                old_player_names_map: Optional[dict[int, str]] = None):
        assert (old_player_rating_map is None) == (old_player_stats_map is None) == (old_player_names_map is None)

        self.player_rating_map: dict[int, float] = {}
        self.player_place_stats: dict[int, list[int]] = {}
        if (old_player_rating_map is not None) and (old_player_stats_map is not None) and (old_player_names_map is not None):
            player_rating_map, player_stats_map = self.build_rating_map(old_player_rating_map=old_player_rating_map,
                                                                        old_player_stats_map=old_player_stats_map,
                                                                        old_player_names_map=old_player_names_map)
            self.player_rating_map.update(player_rating_map)
            self.player_place_stats.update(player_stats_map)
            print(f"{len(player_rating_map)} players ratings and stats loaded from old instance")

        sessions_by_date: list[int] = list(self.session_results.keys())
        sessions_by_date.sort(key=lambda s: self.session_date_map[s])

        new_player_rating_count = 0
        for place_player_map in self.session_results.values():
            assert len(place_player_map) == 4
            assert set(place_player_map.keys()) == {1, 2, 3, 4}
            for place, player_id in place_player_map.items():
                if player_id not in self.player_rating_map:
                    new_player_rating_count += 1
                    self.player_rating_map[player_id] = START_RATING
        print(f"{new_player_rating_count} players ratings initialized with start value {START_RATING}")

        new_player_stats_count = 0
        for place_player_map in self.session_results.values():
            assert len(place_player_map) == 4
            assert set(place_player_map.keys()) == {1, 2, 3, 4}
            for place, player_id in place_player_map.items():
                if player_id not in self.player_place_stats:
                    self.player_place_stats[player_id] = [0, 0, 0, 0]
                    new_player_stats_count += 1
                self.player_place_stats[player_id][place - 1] += 1
        print(f"{new_player_stats_count} new players place stats loaded")

        for session_id in sessions_by_date:
            place_player_map = self.session_results[session_id]
            process_game(session_id=session_id,
                         player_rating_map=self.player_rating_map,
                         place_player_map=place_player_map,
                         replacement_player_ids=self.replacement_player_ids)
        print(f"{len(sessions_by_date)} games processed")
        print("Remembered ratings and place stats")

    def log_ratings(self):
        print(f"Elo k = {ELO_K}")
        players_with_rating = list(self.player_rating_map.items())
        players_with_rating.sort(key=lambda pr: (-pr[1], pr[0]))
        for player_id, rating in players_with_rating:
            places = self.player_place_stats[player_id]
            total_games = sum(places)
            player_name = self.player_names[player_id]
            if total_games < 20 or player_name in REPLACEMENT_PLAYERS:
                continue
            print(f"Player {player_id}: {player_name}, rating {rating:.2f} in {total_games} games ({places})")


def main():
    without_clubs = True
    without_online = True

    old_data = DbData.create(is_new=False, without_clubs=without_clubs, without_online=without_online)
    old_data.process()
    print(f"{len(old_data.player_rating_map)} in old instance")

    new_data = DbData.create(is_new=True, without_clubs=without_clubs, without_online=without_online)
    new_data.process(old_player_rating_map=old_data.player_rating_map,
                     old_player_stats_map=old_data.player_place_stats,
                     old_player_names_map=old_data.player_names)
    print(f"{len(new_data.player_rating_map)} in both instances combined")
    new_data.log_ratings()


if __name__ == "__main__":
    main()
