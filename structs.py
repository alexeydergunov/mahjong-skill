from datetime import datetime
from typing import Optional
from typing import TypeVar

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
    def __init__(self, event_id: int, session_id: int, session_date: datetime, players: list[str], places: list[int], scores: list[float]):
        assert len(players) == 4
        assert len(places) == 4
        assert len(scores) == 4
        self.event_id = event_id
        self.session_id = session_id
        self.session_date = session_date
        self.players = players
        self.places = places
        self.scores = scores
