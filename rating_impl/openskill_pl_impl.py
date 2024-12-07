from openskill.models import PlackettLuce
from openskill.models import PlackettLuceRating

from structs import RatingModel


class OpenSkillPLModel(RatingModel):
    def __init__(self):
        self.model = PlackettLuce()

    def new_rating(self) -> PlackettLuceRating:
        return self.model.rating()

    def process_game(self, old_ratings: list[PlackettLuceRating], scores: list[float]) -> list[PlackettLuceRating]:
        if len(old_ratings) <= 1:
            return old_ratings
        teams = [[r] for r in old_ratings]
        new_rating_groups = self.model.rate(teams=teams, scores=scores)
        return [rg[0] for rg in new_rating_groups]

    def get_rating_for_sorting(self, rating: PlackettLuceRating) -> float:
        return rating.ordinal()

    def get_mean_and_stddev(self, rating: PlackettLuceRating) -> tuple[float, float]:
        return rating.mu, rating.sigma

    def adjust(self, rating: PlackettLuceRating, days: int):
        return
        # if days <= 180:
        #     return
        # rating.sigma += 0.0015 * (days - 180)
