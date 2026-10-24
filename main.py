#!/usr/bin/env python3
import argparse
from collections import defaultdict
from datetime import date
from datetime import datetime
# from datetime import timedelta
from typing import Any
from typing import Optional

import requests
import ujson

import db_load
from players_work import replace_temporary_replacement_players
from rating_calc import calc_ratings
from rating_impl import *
from structs import Game
from structs import Player
from structs import PlayerCreator
from structs import PlayerStats

MODELS = ["elo", "trueskill", "openskill_pl", "openskill_bt"]


def is_suitable_tournament(online: bool, portal_event: dict[str, Any]) -> bool:
    if online:
        if portal_event["tournament_type"] == "online":
            return True
        if portal_event["tournament_type"] == "other" and portal_event["tournament_slug"].startswith("kawa-league"):
            return True
        if portal_event["tournament_type"] == "other" and portal_event["tournament_slug"] == "web-dragon-tournament":
            return True
        return False
    else:
        if portal_event["tournament_type"] in {"rr", "ema", "crr"}:
            return True
        if portal_event["tournament_type"] == "other" and portal_event["tournament_slug"] == "h8ful-eight":
            return True
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=MODELS, required=True)
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
            print(f"Unknown rating model name. Use one of: {MODELS}")
            return

    if args.date_to is not None:
        date_to_str = args.date_to
        print(f"Date to = '{date_to_str}'")
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
    else:
        date_to = datetime.now().date()
        print(f"Date to = 'today'")

    online: bool = args.online
    print(f"Online: {online}")

    portal_data: Optional[list[dict[str, Any]]] = None
    if args.load_from_portal:
        portal_data = requests.get("https://mahjong.click/api/v0/tournaments/finished/").json()
        print("Loaded tournaments data from portal api")
    elif args.event_list_file is not None:
        with open(args.event_list_file, "r") as f:
            portal_data = ujson.load(f)
        print(f"Loaded tournaments data from file {args.event_list_file}")
    else:
        print("Neither of '--load-from-portal', '--event-list-file' options are specified. "
              "Use one of them for correct work")

    portal_players_map: dict[tuple[str, int], Player] = {}
    slug_to_ids: dict[str, list[tuple[str, int]]] = defaultdict(list)
    slug_to_name: dict[str, str] = {}
    old_portal_event_ids = None
    new_portal_event_ids = None
    if portal_data is not None:
        old_portal_event_ids = set()
        new_portal_event_ids = set()
        for portal_event in portal_data:
            pantheon_type = portal_event["pantheon_type"]
            pantheon_id = int(portal_event["tournament_pantheon_id"])
            # remember portal players
            for player_data in portal_event.get("players", []):
                player_slug = player_data.get("player_slug")
                if player_slug is not None:
                    # player exists on portal
                    player_name = player_data["player_name"]
                    player_id = player_data.get("player_pantheon_id")
                    if player_id is not None:
                        slug_to_ids[player_slug].append((pantheon_type, player_id))
                        slug_to_name[player_slug] = player_name
            # skip not suitable tournaments, but players are already remembered
            if not is_suitable_tournament(online=online, portal_event=portal_event):
                continue
            if pantheon_type == "old":
                old_portal_event_ids.add(pantheon_id)
            elif pantheon_type == "new":
                new_portal_event_ids.add(pantheon_id)
        for player_slug, player_name in slug_to_name.items():
            old_ids = sorted(set(p_id for p_t, p_id in slug_to_ids[player_slug] if p_t == "old"))
            new_ids = sorted(set(p_id for p_t, p_id in slug_to_ids[player_slug] if p_t == "new"))
            for pantheon_type, player_id in slug_to_ids[player_slug]:
                portal_players_map[(pantheon_type, player_id)] = Player.create_known(
                    slug=player_slug,
                    name=player_name,
                    old_ids=old_ids,
                    new_ids=new_ids,
                )
        print(f"Loaded {len(old_portal_event_ids)} old events, "
              f"{len(new_portal_event_ids)} new events "
              f"and {len(portal_players_map)} portal players "
              f"from portal tournaments data")
    player_creator = PlayerCreator(portal_players_map=portal_players_map)

    # Yoroshiku League, Kawa S2 Div B tie-breaks - missing on portal
    if online and (new_portal_event_ids is not None):
        new_portal_event_ids.add(106)
        new_portal_event_ids.add(254)
        new_portal_event_ids.add(692)

    # db_load.log_tournaments_info(pantheon_type="old", online=online)
    # db_load.log_tournaments_info(pantheon_type="new", online=online)

    if args.old_pantheon_games_load_file is not None:
        old_games: list[Game] = Game.load_list(
            filename=args.old_pantheon_games_load_file,
            player_creator=player_creator,
        )
        print(f"{len(old_games)} old games loaded from file {args.old_pantheon_games_load_file}")
    else:
        if online:
            force_event_ids_to_load = None
        else:
            force_event_ids_to_load = [142, 236]  # created as club event
        old_games: list[Game] = db_load.load_games(
            pantheon_type="old",
            online=online,
            player_creator=player_creator,
            player_names_file=None,
            force_event_ids_to_load=force_event_ids_to_load,
        )
        print(f"{len(old_games)} old games loaded from DB")
    if args.old_pantheon_games_dump_file is not None:
        Game.dump_list(games=old_games, filename=args.old_pantheon_games_dump_file)
        print(f"Old games saved to file {args.old_pantheon_games_dump_file}")
    if old_portal_event_ids is not None:
        old_games = [g for g in old_games if g.event_id in old_portal_event_ids]
        print(f"{len(old_games)} old games remaining after filtering by portal event ids")

    if args.new_pantheon_games_load_file is not None:
        new_games: list[Game] = Game.load_list(
            filename=args.new_pantheon_games_load_file,
            player_creator=player_creator,
        )
        print(f"{len(new_games)} new games loaded from file {args.new_pantheon_games_load_file}")
    else:
        if online:
            force_event_ids_to_load = [
                106, 254,  # Yoroshiku League
                692,  # Kawa S2 Div B tie-breaks
            ]
        else:
            force_event_ids_to_load = [215]  # created as club event
        new_games: list[Game] = db_load.load_games(
            pantheon_type="new",
            online=online,
            player_creator=player_creator,
            player_names_file="shared/players-data.csv",
            force_event_ids_to_load=force_event_ids_to_load,
        )
        print(f"{len(new_games)} new games loaded from DB")
    if args.new_pantheon_games_dump_file is not None:
        Game.dump_list(games=new_games, filename=args.new_pantheon_games_dump_file)
        print(f"New games saved to file {args.new_pantheon_games_dump_file}")
    if new_portal_event_ids is not None:
        new_games = [g for g in new_games if g.event_id in new_portal_event_ids]
        print(f"{len(new_games)} new games remaining after filtering by portal event ids")
    player_creator.flush_log()

    all_games = old_games + new_games
    replace_temporary_replacement_players(games=all_games)
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
        assert rating_for_sorting is not None
        assert player_stats.mean_and_stddev is not None
        mean, stddev = player_stats.mean_and_stddev
        last_game_date_str = player_stats.last_game_date.strftime("%Y-%m-%d")
        print(f"Player {'*' if player.slug is None else ''}{player.name} "
              f"(old ids {player.old_ids}, new ids {player.new_ids}): "
              f"confirmed rating {rating_for_sorting:.3f} ({mean:.3f} +/- {stddev:.3f}) "
              f"in {total_games} games ({places}, last game at {last_game_date_str})")
        sorted_events: list[tuple[str, int]] = sorted(player_stats.event_game_counts.keys(), key=lambda x: (x[0][2], x[1]))  # 'ol[d]' < 'ne[w]'
        export_element: dict[str, Any] = {
            "player": player.name,
            "slug": player.slug,
            "rating": round(rating_for_sorting, 3),
            "mean": round(mean, 3),
            "stddev": round(stddev, 3),
            "game_count": total_games,
            "places": str(places),
            "last_game_date": last_game_date_str,
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
            date_to=date_to,
            online=online,
            all_games=all_games,
            export_results=export_results,
            filename=args.output_file,
        )


def export_to_file(rating_model_name: str,
                   date_to: date,
                   online: bool,
                   all_games: list[Game],
                   export_results: list[dict[str, Any]],
                   filename: str):
    games_by_event: dict[tuple[str, int], int] = defaultdict(int)
    for game in all_games:
        games_by_event[(game.pantheon_type, game.event_id)] += 1

    rating_type = rating_model_name.upper()
    if online:
        rating_type = "ONLINE_" + rating_type

    rating_data = {
        "tournament_ids": [{"pantheon_type": et, "pantheon_id": eid, "game_count": cnt} for (et, eid), cnt in sorted(games_by_event.items())],
        "ratings": export_results,
        "date": date_to.strftime("%Y-%m-%d"),
        "type": rating_type,
    }

    with open(filename, "w") as f:
        # noinspection PyTypeChecker
        ujson.dump(rating_data, f, ensure_ascii=False, indent=2)
    print(f"Rating for type '{rating_type}' exported to file {filename}")


if __name__ == "__main__":
    main()
