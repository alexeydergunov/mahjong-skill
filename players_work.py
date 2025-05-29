from collections import defaultdict

from shared.players_mapping import SAME_PLAYERS
from structs import Game
from structs import Player


def replace_names(games: list[Game], pantheon_type: str):
    players_by_id: dict[int, Player] = {}
    for game in games:
        for player in game.players:
            if pantheon_type == "old":
                assert len(player.old_ids) == 1
                assert len(player.new_ids) == 0
                player_id = player.old_ids[0]
            elif pantheon_type == "new":
                assert len(player.old_ids) == 0
                assert len(player.new_ids) == 1
                player_id = player.new_ids[0]
            else:
                raise Exception(f"Wrong pantheon_type: {pantheon_type}")
            assert isinstance(player_id, int)
            if player_id not in players_by_id:
                players_by_id[player_id] = player
            else:
                existing_player = players_by_id[player_id]
                assert player.name == existing_player.name
                assert player.old_ids == existing_player.old_ids
                assert player.new_ids == existing_player.new_ids
                assert player.is_replacement_player == existing_player.is_replacement_player
    print(f"Dict players_by_id built in for pantheon_type {pantheon_type}")
    print(f"Found {len(players_by_id)} raw players")

    canonical_player_names: dict[str, str] = {}
    for same_players_list in SAME_PLAYERS:
        canonical_name = same_players_list[0]
        for player_name in same_players_list:
            assert player_name not in canonical_player_names
            canonical_player_names[player_name] = canonical_name
    print(f"Dict canonical_player_names built for pantheon_type {pantheon_type}")

    replacement_player_ids: set[int] = set()
    for player_id, player in players_by_id.items():
        if player.is_replacement_player:
            replacement_player_ids.add(player_id)
            print(f"Found replacement player: {player_id} with name {player.name}")
        else:
            if player.name in canonical_player_names:
                player.name = canonical_player_names[player.name]
    print(f"All player names are replaced with canonical names for pantheon_type {pantheon_type}")

    ids_by_name_map: dict[str, list[int]] = defaultdict(list)
    for player_id, player in players_by_id.items():
        if not player.is_replacement_player:
            ids_by_name_map[player.name].append(player_id)
    print(f"Built ids_by_name_map for pantheon_type {pantheon_type}")

    canonical_player_ids_map: dict[int, int] = {}
    for player_name, player_ids in ids_by_name_map.items():
        player_ids.sort()
        canonical_id = player_ids[-1]  # choose newest
        if len(player_ids) > 1:
            print(f"There are several ids for player {player_name}: {player_ids}, choose {canonical_id}")
        for player_id in player_ids:
            canonical_player_ids_map[player_id] = canonical_id
        players_by_id[canonical_id].remember_other_ids(ids=player_ids)
    for player_id in replacement_player_ids:
        canonical_player_ids_map[player_id] = player_id
    assert len(canonical_player_ids_map) == len(players_by_id)
    print(f"Chosen canonical player ids for pantheon_type {pantheon_type}")

    player_ids_to_forget = set(players_by_id.keys()) - set(canonical_player_ids_map.values())
    for player_id in player_ids_to_forget:
        players_by_id.pop(player_id)
    print(f"Duplicate players deleted for pantheon_type {pantheon_type}")

    for game in games:
        for i in range(len(game.players)):
            if pantheon_type == "old":
                player_id = game.players[i].get_default_old_id()
            elif pantheon_type == "new":
                player_id = game.players[i].get_default_new_id()
            else:
                raise Exception(f"Wrong pantheon_type: {pantheon_type}")
            assert player_id is not None
            assert player_id in canonical_player_ids_map
            canonical_player_id = canonical_player_ids_map[player_id]
            game.players[i] = players_by_id[canonical_player_id]
    print(f"Player ids replaced in games for pantheon_type {pantheon_type}")


def merge_old_and_new_player_ids(games: list[Game]):
    old_ids_by_name: dict[str, list[int]] = {}
    new_ids_by_name: dict[str, list[int]] = {}
    for game in games:
        for player in game.players:
            if not player.is_replacement_player:
                if len(player.old_ids) > 0:
                    if player.name in old_ids_by_name:
                        assert old_ids_by_name[player.name] == player.old_ids
                    else:
                        old_ids_by_name[player.name] = player.old_ids
                if len(player.new_ids) > 0:
                    if player.name in new_ids_by_name:
                        assert new_ids_by_name[player.name] == player.new_ids
                    else:
                        new_ids_by_name[player.name] = player.new_ids
    print(f"Found {len(old_ids_by_name)} old names, {len(new_ids_by_name)} new names")

    for game in games:
        for player in game.players:
            if not player.is_replacement_player:
                old_ids: list[int] = old_ids_by_name.get(player.name, [])
                new_ids: list[int] = new_ids_by_name.get(player.name, [])
                if len(player.old_ids) > 0:
                    assert player.old_ids == old_ids
                else:
                    player.old_ids = old_ids
                if len(player.new_ids) > 0:
                    assert player.new_ids == new_ids
                else:
                    player.new_ids = new_ids
    print("Old and new player ids merged")
