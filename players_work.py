from collections import defaultdict

from shared.players_mapping import TEMPORARY_REPLACEMENTS
from structs import Game
from structs import Player


def replace_temporary_replacement_players(games: list[Game]):
    games_for_player_and_event: dict[tuple[Player, str, int], list[Game]] = defaultdict(list)
    for game in games:
        for player in game.players:
            games_for_player_and_event[(player, game.pantheon_type, game.event_id)].append(game)

    for (player, pantheon_type, event_id), player_event_games in games_for_player_and_event.items():
        if player.name in TEMPORARY_REPLACEMENTS:
            if (pantheon_type, event_id) in TEMPORARY_REPLACEMENTS[player.name]:
                index_from, index_to = TEMPORARY_REPLACEMENTS[player.name][(pantheon_type, event_id)]
                # make 0-indexed
                index_from -= 1
                index_to -= 1
                for index, game in enumerate(player_event_games):
                    if index_from <= index <= index_to:
                        player.temporary_replacements.add((pantheon_type, event_id, game.session_id))
                        print(f"Added player {player.name} as a replacement player "
                              f"for event {event_id} in pantheon type {pantheon_type}, "
                              f"session {game.session_id} (index {index + 1} / {len(player_event_games)})")

    print("Temporary replacements processed")
