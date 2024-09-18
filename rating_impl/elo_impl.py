import math

from structs import RatingModel


class EloModel(RatingModel):
    def __init__(self):
        self.start_rating = 1500.0
        self.k = 10.0
        self.max_rating_diff = 400.0

    def new_rating(self) -> float:
        return self.start_rating

    @classmethod
    def get_outcome(cls, score1: float, score2: float) -> float:
        if score1 > score2:
            return 1.0
        if score1 < score2:
            return 0.0
        return 0.5

    def process_game(self, old_ratings: list[float], scores: list[float]) -> list[float]:
        n = len(old_ratings)
        assert len(scores) == n
        deltas = [0.0] * n
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                r1 = old_ratings[i]
                r2 = old_ratings[j]
                expected = 1.0 / (1.0 + math.pow(10.0, min(r2 - r1, self.max_rating_diff) / self.max_rating_diff))
                actual = self.get_outcome(score1=scores[i], score2=scores[j])
                deltas[i] += self.k * (actual - expected)
        new_ratings = old_ratings.copy()
        for i in range(n):
            new_ratings[i] += deltas[i]
        return new_ratings

    def get_rating_for_sorting(self, rating: float) -> float:
        return rating

    def get_mean_and_stddev(self, rating: float) -> tuple[float, float]:
        return rating, 0.0  # not sure how to calculate stddev
