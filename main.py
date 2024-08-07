from db_load import load_games
from rating_calc import calc_ratings
from rating_impl import *
from structs import Game


def main():
    without_clubs = True
    without_online = True

    old_games: list[Game] = load_games(db_name="mimir_old",
                                       player_names_file=None,
                                       without_clubs=without_clubs,
                                       without_online=without_online)
    print(f"{len(old_games)} old games loaded from DB")

    new_games: list[Game] = load_games(db_name="mimir_new_2024_08_05",
                                       player_names_file="/home/dergunov/test/mimir_2024_08_05/data-1722873805934.csv",
                                       without_clubs=without_clubs,
                                       without_online=without_online)
    print(f"{len(new_games)} new games loaded from DB")

    rating_model = OpenSkillPLModel()  # change here
    player_stats_map = calc_ratings(games=old_games + new_games, rating_model=rating_model)
    for player, player_stats in sorted(player_stats_map.items(), key=lambda x: -x[1].rating_for_sorting):
        total_games = sum(player_stats.places)
        if total_games < 20:
            continue
        print(f"Player {player}: rating {player_stats.rating_for_sorting:.3f} in {total_games} games ({player_stats.places})")


if __name__ == "__main__":
    main()
