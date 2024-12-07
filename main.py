#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from datetime import timedelta

from db_load import load_games
from rating_calc import calc_ratings
from rating_impl import *
from structs import Game


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["elo", "trueskill", "openskill_pl", "openskill_bt"],
                        required=True)
    parser.add_argument("--event-list-file", type=str, required=False)  # 1 line == {"type": "old" or "new", "id": number}
    parser.add_argument("--date-to", type=str, required=False)
    args = parser.parse_args()

    rating_model_name = args.model
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

    if args.event_list_file is not None:
        old_portal_event_ids = set()
        new_portal_event_ids = set()
        with open(args.event_list_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    event_desc = json.loads(line)
                    if event_desc["type"] == "old":
                        old_portal_event_ids.add(int(event_desc["id"]))
                    elif event_desc["type"] == "new":
                        new_portal_event_ids.add(int(event_desc["id"]))
        print(f"Loaded {len(old_portal_event_ids)} old events and {len(new_portal_event_ids)} new events from file {args.event_list_file}")
    else:
        old_portal_event_ids = None
        new_portal_event_ids = None
        print("No event ids file specified")

    if args.date_to is not None:
        date_to_str = args.date_to
        print(f"Date to = '{date_to_str}'")
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
    else:
        date_to = datetime.now().date()
        print(f"Date to = 'today'")

    old_games: list[Game] = load_games(db_name="mimir_old",
                                       player_names_file=None,
                                       force_event_ids_to_load=None)
    print(f"{len(old_games)} old games loaded from DB")
    if old_portal_event_ids is not None:
        old_games = [g for g in old_games if g.event_id in old_portal_event_ids]
        print(f"{len(old_games)} old games remaining after filtering by portal event ids")

    new_games: list[Game] = load_games(db_name="mimir_new",
                                       player_names_file="shared/players-data.csv",
                                       force_event_ids_to_load=[400, 430, 467])
    print(f"{len(new_games)} new games loaded from DB")
    if new_portal_event_ids is not None:
        new_games = [g for g in new_games if g.event_id in new_portal_event_ids]
        print(f"{len(new_games)} new games remaining after filtering by portal event ids")

    today_date = datetime.now()
    player_stats_map = calc_ratings(games=old_games + new_games, rating_model=rating_model, date_to=date_to)
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
