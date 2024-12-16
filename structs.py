from datetime import datetime
from typing import Any
from typing import Optional
from typing import TypeVar

import ujson

from players_mapping import REPLACEMENT_PLAYERS

R = TypeVar("R")


class Player:
    def __init__(self, name: str, old_id: Optional[int], new_id: Optional[int]):
        self.name = name
        self.old_id = old_id
        self.new_id = new_id
        self.is_replacement_player: bool = (name in REPLACEMENT_PLAYERS)

    @staticmethod
    def create_old(name: str, player_id: int) -> 'Player':
        return Player(name=name, old_id=player_id, new_id=None)

    @staticmethod
    def create_new(name: str, player_id: int) -> 'Player':
        return Player(name=name, old_id=None, new_id=player_id)

    def to_json(self) -> dict[str, Any]:
        data = {"name": self.name}
        if self.old_id is not None:
            data["old_id"] = self.old_id
        if self.new_id is not None:
            data["new_id"] = self.new_id
        if self.is_replacement_player:
            data["is_replacement_player"] = True
        return data

    @staticmethod
    def from_json(data: dict[str, Any]) -> 'Player':
        player = Player(
            name=data["name"],
            old_id=data.get("old_id"),
            new_id=data.get("new_id"),
        )
        if data.get("is_replacement_player", False) is True:
            assert player.is_replacement_player
        return player

    def key(self):
        return self.old_id, self.new_id

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
