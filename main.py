#!/usr/bin/env python3
import sys
from datetime import datetime
from datetime import timedelta

from db_load import load_games
from rating_calc import calc_ratings
from rating_impl import *
from structs import Game


def main():
    if len(sys.argv) != 2:
        print("Usage: ./main.py [rating_model_name]")
        print("rating_model_name can be one of: elo, trueskill, openskill_pl, openskill_bt")
        return

    rating_model_name = sys.argv[1]
    print(f"Rating model name: {rating_model_name}")
    match rating_model_name:
        case "elo":
            rating_model = EloModel()
        case "trueskill":
            rating_model = TrueSkillModel()
        case "openskill_pl":
            rating_model = OpenSkillPLModel()
        case "openskill_bt":
            rating_model = OpenSkillBTModel()
        case _:
            print("Unknown rating model name. Use one of above.")
            return
    print("Rating model chosen")

    old_games: list[Game] = load_games(db_name="mimir_old",
                                       player_names_file=None,
                                       whitelist_event_ids=None)
    print(f"{len(old_games)} old games loaded from DB")

    new_games: list[Game] = load_games(db_name="mimir_new_2024_10_15",
                                       player_names_file="/home/dergunov/test/mimir_2024_10_15/data-1729000499739.csv",
                                       whitelist_event_ids=[400, 430])
    print(f"{len(new_games)} new games loaded from DB")

    today_date = datetime.now()
    player_stats_map = calc_ratings(games=old_games + new_games, rating_model=rating_model)
    for player, player_stats in sorted(player_stats_map.items(), key=lambda x: -x[1].rating_for_sorting):
        total_games = sum(player_stats.places)
        if total_games < 20:
            continue
        if today_date - player_stats.last_game_date > timedelta(days=365 * 2):
            continue
        rating_for_sorting = player_stats.rating_for_sorting
        mean, stddev = player_stats.mean_and_stddev
        print(f"Player {player}: confirmed rating {rating_for_sorting:.3f} ({mean:.3f} +/- {stddev:.3f}) in {total_games} games ({player_stats.places})")


if __name__ == "__main__":
    main()
