from players_mapping import REPLACEMENT_PLAYERS
from structs import Game
from structs import PlayerStats
from structs import RatingModel


def calc_ratings(games: list[Game], rating_model: RatingModel) -> dict[str, PlayerStats]:
    print(f"Start calc ratings for model {rating_model.__class__.__name__}")
    player_stats_map: dict[str, PlayerStats] = {}
    for game in games:
        for player in game.players:
            if player not in REPLACEMENT_PLAYERS:
                player_stats_map[player] = PlayerStats.create(rating_model=rating_model)
    print(f"Start ratings initialized for {len(player_stats_map)} players")

    for game in games:
        players_with_scores = []
        for i in range(4):
            if game.players[i] not in REPLACEMENT_PLAYERS:
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
            if player not in REPLACEMENT_PLAYERS:
                place = game.places[i]
                player_stats_map[player].places[place - 1] += 1
    print("All games are processed")

    for player_stats in player_stats_map.values():
        player_stats.rating_for_sorting = rating_model.get_rating_for_sorting(rating=player_stats.rating)

    return player_stats_map
