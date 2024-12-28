from collections import defaultdict
from datetime import datetime
from typing import Any
from typing import Optional
from typing import TypeVar

import ujson

from players_mapping import REPLACEMENT_PLAYERS

R = TypeVar("R")


class Player:
    def __init__(self, name: str, old_ids: list[int], new_ids: list[int]):
        self.name = name
        self.old_ids = old_ids
        self.new_ids = new_ids
        self.is_replacement_player: bool = (name in REPLACEMENT_PLAYERS)

    def remember_other_ids(self, ids: list[int]):
        if len(self.old_ids) > 0:
            assert len(self.new_ids) == 0
            assert len(self.old_ids) == 1
            assert self.old_ids[0] in ids
            self.old_ids = ids
        elif len(self.new_ids) > 0:
            assert len(self.old_ids) == 0
            assert len(self.new_ids) == 1
            assert self.new_ids[0] in ids
            self.new_ids = ids
        else:
            raise Exception("Incorrect state, all ids lists are empty")

    @staticmethod
    def create_old(name: str, player_id: int) -> 'Player':
        return Player(name=name, old_ids=[player_id], new_ids=[])

    @staticmethod
    def create_new(name: str, player_id: int) -> 'Player':
        return Player(name=name, old_ids=[], new_ids=[player_id])

    def to_json(self) -> dict[str, Any]:
        data = {"name": self.name}
        if len(self.old_ids) > 0:
            data["old_ids"] = self.old_ids
        if len(self.new_ids) > 0:
            data["new_ids"] = self.new_ids
        return data

    @staticmethod
    def from_json(data: dict[str, Any]) -> 'Player':
        player = Player(
            name=data["name"],
            old_ids=data.get("old_ids", []),
            new_ids=data.get("new_ids", []),
        )
        return player

    def get_default_old_id(self) -> Optional[int]:
        if len(self.old_ids) > 0:
            return self.old_ids[-1]
        return None

    def get_default_new_id(self) -> Optional[int]:
        if len(self.new_ids) > 0:
            return self.new_ids[-1]
        return None

    def key(self) -> tuple[Optional[int], Optional[int]]:
        return self.get_default_old_id(), self.get_default_new_id()

    def __hash__(self) -> int:
        return hash(self.key())

    def __eq__(self, other: 'Player') -> bool:
        return self.key() == other.key()


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
                 players: list[Player], places: list[int], scores: list[float]):
        assert len(players) == 4
        assert len(places) == 4
        assert len(scores) == 4
        self.pantheon_type = pantheon_type
        self.event_id = event_id
        self.session_id = session_id
        self.session_date = session_date
        self.players = players
        self.places = places
        self.scores = scores

    def to_json(self) -> dict[str, Any]:
        return {
            "pantheon_type": self.pantheon_type,
            "event_id": self.event_id,
            "session_id": self.session_id,
            "session_date": self.session_date.isoformat(),
            "players": [p.to_json() for p in self.players],
            "places": self.places,
            "scores": self.scores,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> 'Game':
        return Game(
            pantheon_type=data["pantheon_type"],
            event_id=data["event_id"],
            session_id=data["session_id"],
            session_date=datetime.fromisoformat(data["session_date"]),
            players=[Player.from_json(data=pd) for pd in data["players"]],
            places=data["places"],
            scores=data["scores"],
        )

    @staticmethod
    def dump_list(games: list['Game'], filename: str):
        with open(filename, "w") as f:
            for game in games:
                f.write(ujson.dumps(game.to_json(), ensure_ascii=False))
                f.write("\n")

    @staticmethod
    def load_list(filename: str) -> list['Game']:
        games = []
        with open(filename, "r") as f:
            for line in f:
                data = ujson.loads(line.strip())
                games.append(Game.from_json(data=data))
        return games
