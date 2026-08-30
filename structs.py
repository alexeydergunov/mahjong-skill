from collections import defaultdict
from datetime import datetime
from typing import Any
from typing import Optional
from typing import TypeVar

import ujson

from shared.players_mapping import REPLACEMENT_PLAYERS

R = TypeVar("R")


class Player:
    def __init__(self, slug: str | None, name: str, unknown_id: int | None, old_ids: list[int], new_ids: list[int]):
        if slug is None:
            assert unknown_id is not None
            assert old_ids + new_ids == [unknown_id]
        else:
            assert unknown_id is None
            assert len(old_ids) + len(new_ids) >= 1

        self.slug = slug
        self.name = name
        self.unknown_id = unknown_id
        self.old_ids = old_ids
        self.new_ids = new_ids
        self.is_replacement_player: bool = (name in REPLACEMENT_PLAYERS)
        self.temporary_replacements: set[tuple[str, int, int]] = set()  # pantheon_type, event_id, session_id

    @staticmethod
    def create_known(slug: str, name: str, old_ids: list[int], new_ids: list[int]) -> 'Player':
        return Player(slug=slug, name=name, unknown_id=None, old_ids=old_ids, new_ids=new_ids)

    @staticmethod
    def create_old_unknown(name: str, player_id: int) -> 'Player':
        return Player(slug=None, name=name, unknown_id=player_id, old_ids=[player_id], new_ids=[])

    @staticmethod
    def create_new_unknown(name: str, player_id: int) -> 'Player':
        return Player(slug=None, name=name, unknown_id=player_id, old_ids=[], new_ids=[player_id])

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name}
        if self.slug is not None:
            data["slug"] = self.slug
        if len(self.old_ids) > 0:
            data["old_ids"] = self.old_ids
        if len(self.new_ids) > 0:
            data["new_ids"] = self.new_ids
        return data

    @staticmethod
    def from_json(data: dict[str, Any]) -> 'Player':
        slug = data.get("slug")
        old_ids = data.get("old_ids", [])
        new_ids = data.get("new_ids", [])
        player = Player(
            slug=slug,
            name=data["name"],
            unknown_id=None if slug is not None else (old_ids + new_ids)[0],
            old_ids=old_ids,
            new_ids=new_ids,
        )
        return player

    def key(self) -> tuple[Optional[str], Optional[int]]:
        return self.slug, self.unknown_id

    def __hash__(self) -> int:
        return hash(self.key())

    def __eq__(self, other) -> bool:
        if not isinstance(other, Player):
            return False
        other: Player
        return self.key() == other.key()


class PlayerCreator:
    def __init__(self, portal_players_map: dict[tuple[str, int], Player]):
        self.portal_players_map: dict[tuple[str, int], Player] = portal_players_map
        self.unknown_players_map: dict[tuple[str, int], Player] = {}

        # to output all log lines after processing
        self.logged_accounts: set[tuple[str, int]] = set()
        self.log_lines: list[str] = []

    def get_or_create_player(self, pantheon_type: str, player_id: int, player_name: str) -> Player:
        if (pantheon_type, player_id) in self.portal_players_map:
            portal_player = self.portal_players_map[(pantheon_type, player_id)]
            if (pantheon_type, player_id) not in self.logged_accounts:
                self.logged_accounts.add((pantheon_type, player_id))
                self.log_lines.append(f"Use portal player {portal_player.name} instead of {player_name} "
                                      f"for type {pantheon_type}, id {player_id}")
            return portal_player
        elif (pantheon_type, player_id) in self.unknown_players_map:
            return self.unknown_players_map[(pantheon_type, player_id)]
        else:
            match pantheon_type:
                case "old":
                    player = Player.create_old_unknown(name=player_name, player_id=player_id)
                case "new":
                    player = Player.create_new_unknown(name=player_name, player_id=player_id)
                case _:
                    raise Exception(f"Wrong pantheon_type {pantheon_type}")
            if (pantheon_type, player_id) not in self.logged_accounts:
                self.logged_accounts.add((pantheon_type, player_id))
                self.log_lines.append(f"There is no portal player {player_name} "
                                      f"for type {pantheon_type}, id {player_id}")
            self.unknown_players_map[(pantheon_type, player_id)] = player
            return player

    def flush_log(self):
        print(f"PlayerCreator processed {len(self.logged_accounts)} unique players:")
        for line in self.log_lines:
            print(line)


class RatingModel:
    def new_rating(self) -> R:
        raise NotImplementedError()

    def process_game(self, old_ratings: list[R], scores: list[float]) -> list[R]:
        raise NotImplementedError()

    def get_rating_for_sorting(self, rating: R) -> float:
        raise NotImplementedError()

    def get_mean_and_stddev(self, rating: R) -> tuple[float, float]:
        raise NotImplementedError()

    def adjust(self, rating: R, days: int):
        raise NotImplementedError()


class PlayerStats:
    def __init__(self, rating: R):
        self.rating_for_sorting: Optional[float] = None
        self.mean_and_stddev: Optional[tuple[float, float]] = None
        self.rating = rating
        self.places = [0, 0, 0, 0]
        self.last_game_date: Optional[datetime] = None
        self.event_game_counts: dict[tuple[str, int], int] = defaultdict(int)

    @staticmethod
    def create(rating_model: RatingModel) -> 'PlayerStats':
        return PlayerStats(rating=rating_model.new_rating())


class Game:
    def __init__(self, pantheon_type: str, event_id: int, session_id: int, session_date: datetime,
                 player_ids: list[int], player_names: list[str], places: list[int], scores: list[float],
                 player_creator: PlayerCreator):
        assert len(places) == 4
        assert len(scores) == 4
        assert len(player_ids) == 4
        assert len(player_names) == 4
        self.pantheon_type = pantheon_type
        self.event_id = event_id
        self.session_id = session_id
        self.session_date = session_date
        self.player_ids = player_ids
        self.player_names = player_names
        self.places = places
        self.scores = scores

        self.players = []
        for player_id, player_name in zip(self.player_ids, self.player_names, strict=True):
            self.players.append(player_creator.get_or_create_player(
                pantheon_type=pantheon_type,
                player_id=player_id,
                player_name=player_name,
            ))

    def to_json(self) -> dict[str, Any]:
        return {
            "pantheon_type": self.pantheon_type,
            "event_id": self.event_id,
            "session_id": self.session_id,
            "session_date": self.session_date.isoformat(),
            "player_ids": self.player_ids,
            "player_names": self.player_names,
            "places": self.places,
            "scores": self.scores,
        }

    @staticmethod
    def from_json(data: dict[str, Any], player_creator: PlayerCreator) -> 'Game':
        return Game(
            pantheon_type=data["pantheon_type"],
            event_id=data["event_id"],
            session_id=data["session_id"],
            session_date=datetime.fromisoformat(data["session_date"]),
            player_ids=data["player_ids"],
            player_names=data["player_names"],
            places=data["places"],
            scores=data["scores"],
            player_creator=player_creator,
        )

    @staticmethod
    def dump_list(games: list['Game'], filename: str):
        with open(filename, "w") as f:
            for game in games:
                f.write(ujson.dumps(game.to_json(), ensure_ascii=False))
                f.write("\n")

    @staticmethod
    def load_list(filename: str, player_creator: PlayerCreator) -> list['Game']:
        games = []
        with open(filename, "r") as f:
            for line in f:
                data = ujson.loads(line.strip())
                games.append(Game.from_json(data=data, player_creator=player_creator))
        return games
