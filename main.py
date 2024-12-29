#!/usr/bin/env python3
import argparse
from collections import defaultdict
from typing import Any
from typing import Optional

import requests
import ujson
from datetime import datetime
# from datetime import timedelta

import db_load
from players_work import merge_old_and_new_player_ids
from players_work import replace_names
from rating_calc import calc_ratings
from rating_impl import *
from structs import Game
from structs import Player
from structs import PlayerStats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["elo", "trueskill", "openskill_pl", "openskill_bt"],
                        required=True)
    parser.add_argument("--load-from-portal", action="store_true", default=False, required=False)
    parser.add_argument("--event-list-file", type=str, required=False)
    parser.add_argument("--date-to", type=str, required=False)
    parser.add_argument("--online", action="store_true", default=False, required=False)
    parser.add_argument("--old-pantheon-games-load-file", type=str, required=False)
    parser.add_argument("--new-pantheon-games-load-file", type=str, required=False)
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

    online: bool = args.online
    print(f"Online: {online}")

    # db_load.log_tournaments_info(pantheon_type="old", online=online)
    # db_load.log_tournaments_info(pantheon_type="new", online=online)

    if args.old_pantheon_games_load_file is not None:
        old_games: list[Game] = Game.load_list(filename=args.old_pantheon_games_load_file)
        print(f"{len(old_games)} old games loaded from file {args.old_pantheon_games_load_file}")
    else:
        old_games: list[Game] = db_load.load_games(pantheon_type="old",
                                                   online=online,
                                                   player_names_file=None,
                                                   force_event_ids_to_load=None if online else [142, 236])
        print(f"{len(old_games)} old games loaded from DB")
    if args.old_pantheon_games_dump_file is not None:
        Game.dump_list(games=old_games, filename=args.old_pantheon_games_dump_file)
        print(f"Old games saved to file {args.old_pantheon_games_dump_file}")
    replace_names(games=old_games, pantheon_type="old")
    if old_portal_event_ids is not None:
        old_games = [g for g in old_games if g.event_id in old_portal_event_ids]
        print(f"{len(old_games)} old games remaining after filtering by portal event ids")

    if args.new_pantheon_games_load_file is not None:
        new_games: list[Game] = Game.load_list(filename=args.new_pantheon_games_load_file)
        print(f"{len(new_games)} new games loaded from file {args.new_pantheon_games_load_file}")
    else:
        new_games: list[Game] = db_load.load_games(pantheon_type="new",
                                                   online=online,
                                                   player_names_file="shared/players-data.csv",
                                                   force_event_ids_to_load=None if online else [215, 400, 430, 467])
        print(f"{len(new_games)} new games loaded from DB")
    if args.new_pantheon_games_dump_file is not None:
        Game.dump_list(games=new_games, filename=args.new_pantheon_games_dump_file)
        print(f"New games saved to file {args.new_pantheon_games_dump_file}")
    replace_names(games=new_games, pantheon_type="new")
    if new_portal_event_ids is not None:
        new_games = [g for g in new_games if g.event_id in new_portal_event_ids]
        print(f"{len(new_games)} new games remaining after filtering by portal event ids")

    all_games = old_games + new_games
    merge_old_and_new_player_ids(games=all_games)
    player_stats_map: dict[Player, PlayerStats] = calc_ratings(games=all_games, rating_model=rating_model, date_to=date_to)

    export_results = []
    for player, player_stats in sorted(player_stats_map.items(), key=lambda x: -x[1].rating_for_sorting):
        places = player_stats.places
        total_games = sum(places)
        if total_games < 10:
            continue
        # if date_to - player_stats.last_game_date.date() > timedelta(days=365 * 2):
        #     continue
        rating_for_sorting = player_stats.rating_for_sorting
        mean, stddev = player_stats.mean_and_stddev
        print(f"Player {player.name} (old ids {player.old_ids}, new ids {player.new_ids}): confirmed rating {rating_for_sorting:.3f} ({mean:.3f} +/- {stddev:.3f}) in {total_games} games ({places})")
        sorted_events: list[tuple[str, int]] = sorted(player_stats.event_game_counts.keys(), key=lambda x: (x[0][2], x[1]))  # 'ol[d]' < 'ne[w]'
        export_element = {
            "player": player.name,
            "rating": round(rating_for_sorting, 3),
            "mean": round(mean, 3),
            "stddev": round(stddev, 3),
            "game_count": total_games,
            "places": str(places),
            "last_game_date": player_stats.last_game_date.strftime("%Y-%m-%d"),
            "event_game_counts": [t + "_" + str(i) + " -> " + str(player_stats.event_game_counts[(t, i)]) for (t, i) in sorted_events],
        }
        if len(player.old_ids) > 0:
            export_element["old_ids"] = str(player.old_ids)
        if len(player.new_ids) > 0:
            export_element["new_ids"] = str(player.new_ids)
        export_results.append(export_element)

    if args.output_file is not None:
        export_to_file(
            rating_model_name=rating_model_name,
            all_games=all_games,
            export_results=export_results,
            filename=args.output_file,
        )


def export_to_file(rating_model_name: str, all_games: list[Game], export_results: list[dict[str, str]], filename: str):
    games_by_event: dict[tuple[str, int], int] = defaultdict(int)
    for game in all_games:
        games_by_event[(game.pantheon_type, game.event_id)] += 1

    ts_rating = {
        "tournament_ids": [{"pantheon_type": et, "pantheon_id": eid, "game_count": cnt} for (et, eid), cnt in sorted(games_by_event.items())],
        rating_model_name: export_results,
    }

    with open(filename, "w") as f:
        # noinspection PyTypeChecker
        ujson.dump(ts_rating, f, ensure_ascii=False, indent=2)
    print(f"Rating by model '{rating_model_name}' exported to file {filename}")


if __name__ == "__main__":
    main()
