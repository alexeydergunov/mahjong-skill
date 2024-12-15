from datetime import datetime
from typing import Any
from typing import NewType
from typing import Optional
from typing import TypeVar

import ujson

Player = NewType("Player", str)

R = TypeVar("R")


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
            "players": self.players,
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
            players=data["players"],
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
