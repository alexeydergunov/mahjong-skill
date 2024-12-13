#!/usr/bin/env python3
import argparse
from typing import Any
from typing import Optional

import requests
import ujson
from datetime import datetime
from datetime import timedelta

import db_load
from rating_calc import calc_ratings
from rating_impl import *
from structs import Game


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["elo", "trueskill", "openskill_pl", "openskill_bt"],
                        required=True)
    parser.add_argument("--load-from-portal", action="store_true", default=False, required=False)
    parser.add_argument("--event-list-file", type=str, required=False)
    parser.add_argument("--date-to", type=str, required=False)
    parser.add_argument("--old-pantheon-games-dump-file", type=str, required=False)
    parser.add_argument("--new-pantheon-games-dump-file", type=str, required=False)
    parser.add_argument("--output-file", type=str, required=False)
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

    portal_data: Optional[list[dict[str, Any]]] = None
    if args.load_from_portal:
        portal_data = requests.get("https://mahjong.click/api/v0/tournaments/finished/").json()
        print("Loaded tournaments data from portal api")
    elif args.event_list_file is not None:
        with open(args.event_list_file, "r") as f:
            portal_data = ujson.load(f)
        print(f"Loaded tournaments data from file {args.event_list_file}")
    else:
        print("Neither of '--load-from-portal', '--event-list-file' options are specified")

    old_portal_event_ids = None
    new_portal_event_ids = None
    if portal_data is not None:
        old_portal_event_ids = set()
        new_portal_event_ids = set()
        for portal_event in portal_data:
            pantheon_type = portal_event["pantheon_type"]
            pantheon_id = int(portal_event["pantheon_id"])
            if pantheon_type == "old":
                old_portal_event_ids.add(pantheon_id)
            elif pantheon_type == "new":
                new_portal_event_ids.add(pantheon_id)
        print(f"Loaded {len(old_portal_event_ids)} old events and {len(new_portal_event_ids)} new events from tournaments data")

    if args.date_to is not None:
        date_to_str = args.date_to
        print(f"Date to = '{date_to_str}'")
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
    else:
        date_to = datetime.now().date()
        print(f"Date to = 'today'")

    # db_load.log_tournaments_info(pantheon_type="old")
    # db_load.log_tournaments_info(pantheon_type="new")

    old_games: list[Game] = db_load.load_games(pantheon_type="old",
                                               player_names_file=None,
                                               force_event_ids_to_load=None)
    print(f"{len(old_games)} old games loaded from DB")
    if args.old_pantheon_games_dump_file is not None:
        Game.dump_list(games=old_games, filename=args.old_pantheon_games_dump_file)
        print(f"Old games saved to file {args.old_pantheon_games_dump_file}")
    if old_portal_event_ids is not None:
        old_games = [g for g in old_games if g.event_id in old_portal_event_ids]
        print(f"{len(old_games)} old games remaining after filtering by portal event ids")

    new_games: list[Game] = db_load.load_games(pantheon_type="new",
                                               player_names_file="shared/players-data.csv",
                                               force_event_ids_to_load=[400, 430, 467])
    print(f"{len(new_games)} new games loaded from DB")
    if args.new_pantheon_games_dump_file is not None:
        Game.dump_list(games=new_games, filename=args.new_pantheon_games_dump_file)
        print(f"New games saved to file {args.new_pantheon_games_dump_file}")
    if new_portal_event_ids is not None:
        new_games = [g for g in new_games if g.event_id in new_portal_event_ids]
        print(f"{len(new_games)} new games remaining after filtering by portal event ids")

    today_date = datetime.now()
    all_games = old_games + new_games
    player_stats_map = calc_ratings(games=all_games, rating_model=rating_model, date_to=date_to)

    export_results = []
    for player, player_stats in sorted(player_stats_map.items(), key=lambda x: -x[1].rating_for_sorting):
        total_games = sum(player_stats.places)
        if total_games < 20:
            continue
        if today_date - player_stats.last_game_date > timedelta(days=365 * 2):
            continue
        rating_for_sorting = player_stats.rating_for_sorting
        mean, stddev = player_stats.mean_and_stddev
        print(f"Player {player}: confirmed rating {rating_for_sorting:.3f} ({mean:.3f} +/- {stddev:.3f}) in {total_games} games ({player_stats.places})")
        export_results.append({
            "player": player,
            "rating": f"{rating_for_sorting:.3f}",
            "game_count": str(total_games),
            "last_game_date": player_stats.last_game_date.strftime("%Y-%m-%d"),
        })

    if args.output_file is not None:
        export_to_file(all_games, export_results, args.output_file)


def export_to_file(all_games: list[Game], export_results: list[dict[str, str]], filename: str):
    unique_events: set[tuple[str, int]] = set()
    for game in all_games:
        unique_events.add((game.pantheon_type, game.event_id))

    ts_rating = {
        "tournament_ids": [{"pantheon_type": et, "pantheon_id": eid} for et, eid in sorted(unique_events)],
        "trueskill": export_results,
    }

    with open(filename, "w") as f:
        # noinspection PyTypeChecker
        ujson.dump(ts_rating, f, ensure_ascii=False, indent=2)
    print(f"Trueskill rating exported to file {filename}")


if __name__ == "__main__":
    main()
