from datetime import date

from players_mapping import REPLACEMENT_PLAYERS
from structs import Game
from structs import PlayerStats
from structs import RatingModel


def is_replacement_player(player_name: str) -> bool:
    # hack: we add "Replacement player (id NNN) to make sure names are unique
    # new hack: check that at least one replacement player is a prefix
    for replacement_player_name in REPLACEMENT_PLAYERS:
        if player_name.startswith(replacement_player_name):
            return True
    return False


def calc_ratings(games: list[Game], rating_model: RatingModel, date_to: date) -> dict[str, PlayerStats]:
    games.sort(key=lambda g: g.session_date)  # there were games in old pantheon played later than some games in new pantheon
    games = [g for g in games if g.session_date.date() <= date_to]

    print(f"Start calc ratings for model {rating_model.__class__.__name__}")
    player_stats_map: dict[str, PlayerStats] = {}
    for game in games:
        for player in game.players:
            if not is_replacement_player(player_name=player):
                player_stats_map[player] = PlayerStats.create(rating_model=rating_model)
    print(f"Start ratings initialized for {len(player_stats_map)} players")

    for game in games:
        for player in game.players:
            if not is_replacement_player(player_name=player):
                if player_stats_map[player].last_game_date is not None:
                    days_since_last_game = (game.session_date.date() - player_stats_map[player].last_game_date.date()).days
                    assert days_since_last_game >= 0
                    rating_model.adjust(rating=player_stats_map[player].rating, days=days_since_last_game)

        players_with_scores = []
        for i in range(4):
            if not is_replacement_player(player_name=game.players[i]):
                players_with_scores.append((game.players[i], game.scores[i]))
        players_with_scores.sort(key=lambda ps: (-ps[1], ps[0]))

        old_ratings = [player_stats_map[ps[0]].rating for ps in players_with_scores]
        scores = [ps[1] for ps in players_with_scores]
        new_ratings = rating_model.process_game(old_ratings=old_ratings, scores=scores)

        for i in range(len(players_with_scores)):
            player = players_with_scores[i][0]
            player_stats_map[player].rating = new_ratings[i]

        for i in range(4):
            player = game.players[i]
            if not is_replacement_player(player_name=player):
                place = game.places[i]
                player_stats_map[player].places[place - 1] += 1
                if player_stats_map[player].last_game_date is None or game.session_date > player_stats_map[player].last_game_date:
                    player_stats_map[player].last_game_date = game.session_date
    print(f"All games till date {date_to} are processed")

    for player_stats in player_stats_map.values():
        if player_stats.last_game_date is not None:
            days_since_last_game = (date_to - player_stats.last_game_date.date()).days
            assert days_since_last_game >= 0
            rating_model.adjust(rating=player_stats.rating, days=days_since_last_game)
    print(f"Ratings adjusted to the date {date_to}")

    for player_stats in player_stats_map.values():
        player_stats.rating_for_sorting = rating_model.get_rating_for_sorting(rating=player_stats.rating)
        player_stats.mean_and_stddev = rating_model.get_mean_and_stddev(rating=player_stats.rating)

    return player_stats_map
