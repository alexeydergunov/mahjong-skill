from openskill.models import BradleyTerryFull
from openskill.models import BradleyTerryFullRating

from structs import RatingModel


class OpenSkillBTModel(RatingModel):
    def __init__(self):
        self.model = BradleyTerryFull()

    def new_rating(self) -> BradleyTerryFullRating:
        return self.model.rating()

    def process_game(self, old_ratings: list[BradleyTerryFullRating], scores: list[float]) -> list[BradleyTerryFullRating]:
        if len(old_ratings) <= 1:
            return old_ratings
        teams = [[r] for r in old_ratings]
        new_rating_groups = self.model.rate(teams=teams, scores=scores)
        return [rg[0] for rg in new_rating_groups]

    def get_rating_for_sorting(self, rating: BradleyTerryFullRating) -> float:
        return rating.ordinal()

    def get_mean_and_stddev(self, rating: BradleyTerryFullRating) -> tuple[float, float]:
        return rating.mu, rating.sigma

    def adjust(self, rating: BradleyTerryFullRating, days: int):
        return
        # if days <= 180:
        #     return
        # rating.sigma += 0.001 * (days - 180)
