import trueskill

from structs import RatingModel


class TrueSkillModel(RatingModel):
    def __init__(self):
        self.model = trueskill.TrueSkill(draw_probability=0.0)

    def new_rating(self) -> trueskill.Rating:
        return self.model.create_rating()

    def process_game(self, old_ratings: list[trueskill.Rating], scores: list[float]) -> list[trueskill.Rating]:
        if len(old_ratings) <= 1:
            return old_ratings
        rating_groups = [(r,) for r in old_ratings]
        ranks = [(-s) for s in scores]
        new_rating_groups = self.model.rate(rating_groups=rating_groups, ranks=ranks)
        return [rg[0] for rg in new_rating_groups]

    def get_rating_for_sorting(self, rating: trueskill.Rating) -> float:
        return self.model.expose(rating=rating)

    def get_mean_and_stddev(self, rating: trueskill.Rating) -> tuple[float, float]:
        return rating.mu, rating.sigma

    def adjust(self, rating: trueskill.Rating, days: int):
        return
        # if days <= 180:
        #     return
        #
        # old_pi = rating.pi
        # old_tau = rating.tau
        # old_sigma = 1.0 / (old_pi ** 0.5)
        # old_mu = old_tau / old_pi
        #
        # new_sigma = old_sigma + 0.0005 * (days - 180)  # here
        # new_pi = 1.0 / (new_sigma ** 2)
        # new_tau = new_pi * old_mu
        #
        # rating.pi = new_pi
        # rating.tau = new_tau
