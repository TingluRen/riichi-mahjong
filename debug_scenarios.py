from main import (
    create_game,
    create_tiles,
    sort_tiles,
    finish_turn,
    advance_until_human,
    check_tile_counts,
    can_ron
)


def create_ron_demo():
    game = create_game()

    # Rebuild the tile distribution from a complete set.
    pool = create_tiles(include_red=False)

    # Player 1 waits on White Dragon.
    # The East triplet provides Yakuhai.
    human_hand = [
        "1m", "2m", "3m",
        "4p", "5p", "6p",
        "7s", "8s", "9s",
        "1z", "1z", "1z",
        "5z"
    ]

    for tile in human_hand:
        pool.remove(tile)

    # Reserve the tile Player 2 will discard.
    pool.remove("5z")

    hands = [human_hand, [], [], []]

    # Give each computer 13 tiles.
    for player_index in (1, 2, 3):
        for _ in range(13):
            hands[player_index].append(pool.pop(0))

    for hand in hands:
        sort_tiles(hand)

    # Player 2 has drawn White Dragon.
    hands[1].append("5z")

    game["hands"] = hands
    game["discards"] = [[] for _ in range(4)]
    game["dead_wall"] = pool[:14]
    game["wall"] = pool[14:]
    game["current_player_index"] = 1
    game["phase"] = "discard"

    # Player 2 discards the newly drawn tile.
    finish_turn(game, 1, len(hands[1]) - 1)

    # Pause for the human's Ron / Pass decision.
    advance_until_human(game)

    check_tile_counts(game)

    if not can_ron(game, game["human_player_index"]):
        raise ValueError("The Ron demo was not set up correctly.")

    return game


def create_riichi_demo():
    from main import can_riichi

    game = create_game()
    pool = create_tiles(include_red=False)

    human_hand = [
        "1m", "2m", "3m",
        "4p", "5p", "6p",
        "7s", "8s", "9s",
        "1z", "1z", "1z",
        "5z", "9p"
    ]

    # Deliberately scattered computer hands.
    computer_hand = [
        "1m", "4m", "7m",
        "1p", "4p", "7p",
        "1s", "4s", "7s",
        "2z", "3z", "4z", "6z"
    ]

    hands = [
        human_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy()
    ]

    # Remove all dealt tiles from the physical tile pool.
    for hand in hands:
        for tile in hand:
            pool.remove(tile)

    # Players 2, 3, 4, then the human draw these tiles.
    next_draws = ["2p", "3p", "6p", "2s"]

    for tile in next_draws:
        pool.remove(tile)

    # Keep the human's simulated drawn tile, 9p, at the end.
    for hand in hands[1:]:
        sort_tiles(hand)

    game["hands"] = hands
    game["discards"] = [[] for _ in range(4)]
    game["dead_wall"] = pool[:14]
    game["wall"] = pool[14:]

    # draw_tile() uses pop(), so store draws in reverse order.
    game["wall"].extend(reversed(next_draws))

    game["current_player_index"] = 0
    game["phase"] = "discard"

    check_tile_counts(game)

    if not can_riichi(game, 0):
        raise ValueError("The Riichi demo must allow Riichi.")

    return game

def create_pon_demo():
    from main import can_pon

    game = create_game()
    pool = create_tiles(include_red=False)

    human_hand = [
        "1m", "2m", "4m", "5m", "7m", "8m",
        "1p", "4p", "7p", "1s", "4s",
        "5z", "5z"
    ]

    computer_hand = [
        "1m", "4m", "7m",
        "1p", "4p", "7p",
        "1s", "4s", "7s",
        "2z", "3z", "4z", "6z"
    ]

    hands = [
        human_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy()
    ]

    for hand in hands:
        for tile in hand:
            pool.remove(tile)

    # Reserve Player 2's declaration discard.
    pool.remove("5z")

    # Keep the next computer turns predictable.
    next_draws = ["2p", "3p", "6p", "2s"]

    for tile in next_draws:
        pool.remove(tile)

    for hand in hands:
        sort_tiles(hand)

    hands[1].append("5z")

    game["hands"] = hands
    game["dead_wall"] = pool[:14]
    game["wall"] = pool[14:]
    game["wall"].extend(reversed(next_draws))
    game["current_player_index"] = 1
    game["phase"] = "discard"

    finish_turn(game, 1, len(hands[1]) - 1)
    advance_until_human(game)

    check_tile_counts(game)

    if not can_pon(game, 0) or can_ron(game, 0):
        raise ValueError("The Pon demo was not set up correctly.")

    return game


def create_chi_demo():
    from main import get_chi_options

    game = create_game()
    pool = create_tiles(include_red=False)

    human_hand = [
        "1m", "2m", "4m", "5m", "6m",
        "1p", "4p", "7p",
        "1s", "4s",
        "1z", "2z", "3z"
    ]

    computer_hand = [
        "1m", "4m", "7m",
        "1p", "4p", "7p",
        "1s", "4s", "7s",
        "2z", "3z", "4z", "6z"
    ]

    hands = [
        human_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy()
    ]

    for hand in hands:
        for tile in hand:
            pool.remove(tile)

    # Reserve Player 4's discard.
    pool.remove("3m")

    # Draws after the human calls Chi and discards.
    next_draws = ["2p", "3p", "6p", "2s"]

    for tile in next_draws:
        pool.remove(tile)

    for hand in hands:
        sort_tiles(hand)

    hands[3].append("3m")

    game["hands"] = hands
    game["dead_wall"] = pool[:14]
    game["wall"] = pool[14:]
    game["wall"].extend(reversed(next_draws))
    game["current_player_index"] = 3
    game["phase"] = "discard"

    finish_turn(game, 3, len(hands[3]) - 1)
    advance_until_human(game)

    check_tile_counts(game)

    if len(get_chi_options(game, 0)) != 3:
        raise ValueError("The Chi demo must offer three combinations.")

    if can_ron(game, 0):
        raise ValueError("The Chi demo must not offer Ron.")

    return game


def create_ankan_demo():
    from main import get_ankan_options

    game = create_game()
    pool = create_tiles(include_red=False)

    human_hand = [
        "1m", "2m", "3m",
        "4p", "5p", "6p",
        "7s", "8s", "9s",
        "1z",
        "5z", "5z", "5z", "5z"
    ]

    for tile in human_hand:
        pool.remove(tile)

    # Reserve the first Rinshan tile.
    pool.remove("1z")

    hands = [human_hand.copy(), [], [], []]

    for player_index in (1, 2, 3):
        for _ in range(13):
            hands[player_index].append(pool.pop(0))

    # Keep one simulated drawn tile at the end.
    starting_hand = hands[0][:-1]
    sort_tiles(starting_hand)
    hands[0] = starting_hand + [hands[0][-1]]

    for hand in hands[1:]:
        sort_tiles(hand)

    game["hands"] = hands
    game["dead_wall"] = ["1z"] + pool[:13]
    game["wall"] = pool[13:]
    game["current_player_index"] = 0
    game["phase"] = "discard"

    check_tile_counts(game)

    if get_ankan_options(game, 0) != ["5z"]:
        raise ValueError("The Ankan demo was not set up correctly.")

    return game


def create_daiminkan_demo():
    from main import can_daiminkan, can_pon

    game = create_game()
    pool = create_tiles(include_red=False)

    human_hand = [
        "1m", "2m", "3m",
        "4p", "5p", "6p",
        "7s", "8s", "9s",
        "1z",
        "5z", "5z", "5z"
    ]

    computer_hand = [
        "1m", "4m", "7m",
        "1p", "4p", "7p",
        "1s", "4s", "7s",
        "2z", "3z", "4z", "6z"
    ]

    hands = [
        human_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy(),
        computer_hand.copy()
    ]

    for hand in hands:
        for tile in hand:
            pool.remove(tile)

    # Reserve the discard and the first replacement tile.
    pool.remove("5z")
    pool.remove("1z")

    for hand in hands:
        sort_tiles(hand)

    hands[1].append("5z")

    game["hands"] = hands
    game["dead_wall"] = ["1z"] + pool[:13]
    game["wall"] = pool[13:]
    game["current_player_index"] = 1
    game["phase"] = "discard"

    finish_turn(game, 1, len(hands[1]) - 1)
    advance_until_human(game)

    check_tile_counts(game)

    if not can_daiminkan(game, 0) or not can_pon(game, 0):
        raise ValueError("The Kan demo must allow Kan and Pon.")

    if can_ron(game, 0):
        raise ValueError("The Kan demo must not offer Ron.")

    return game


def _build_kakan_demo(human_hand, declaring_player):
    from main import can_kakan

    game = create_game()
    pool = create_tiles(include_red=False)

    scattered_hand = [
        "1m", "4m", "7m",
        "1p", "4p", "7p",
        "1s", "4s", "7s",
        "2z", "3z", "4z", "6z"
    ]

    hands = [
        human_hand.copy(),
        scattered_hand.copy(),
        scattered_hand.copy(),
        scattered_hand.copy()
    ]

    if declaring_player == 0:
        pon_tile = "5z"
        source_player = 1
    else:
        pon_tile = "6m"
        source_player = 2

        hands[declaring_player] = [
            "1m", "4m", "7m",
            "1p", "4p", "7p",
            "1s", "4s", "7s",
            "6m", "7z"
        ]

    for hand in hands:
        for tile in hand:
            pool.remove(tile)

    # The original Pon contains three physical tiles.
    for _ in range(3):
        pool.remove(pon_tile)

    # Reserve the first replacement tile.
    replacement_tile = "1z"
    pool.remove(replacement_tile)

    for hand in hands:
        sort_tiles(hand)

    # Keep a simulated drawn tile at the end.
    drawn_tile = (
        "5z" if declaring_player == 0 else "6m"
    )
    hands[declaring_player].remove(drawn_tile)
    hands[declaring_player].append(drawn_tile)

    game["hands"] = hands
    game["melds"][declaring_player] = [{
        "type": "pon",
        "tiles": [pon_tile] * 3,
        "from_player_index": source_player
    }]
    game["is_closed"][declaring_player] = False

    # The original called discard has left the physical discard pile,
    # but must remain in the source player's discard history.
    game["discard_history"][source_player].append(pon_tile)

    game["dead_wall"] = [replacement_tile] + pool[:13]
    game["wall"] = pool[13:]
    game["current_player_index"] = declaring_player
    game["phase"] = "discard"

    check_tile_counts(game)

    if not can_kakan(game, declaring_player):
        raise ValueError("The demo must allow a Kakan declaration.")

    return game


def create_kakan_demo():
    human_hand = [
        "1m", "2m", "3m",
        "4p", "5p", "6p",
        "7s", "8s", "9s",
        "1z", "5z"
    ]

    return _build_kakan_demo(human_hand, declaring_player=0)


def create_chankan_demo():
    from main import declare_kakan, can_chankan

    human_hand = [
        "1p", "2p", "3p",
        "4p", "5p", "6p",
        "7s", "8s", "9s",
        "4m", "5m",
        "2z", "2z"
    ]

    game = _build_kakan_demo(human_hand, declaring_player=1)

    declare_kakan(game, 1, 0)
    advance_until_human(game)

    check_tile_counts(game)

    if not can_chankan(game, 0):
        raise ValueError("The demo must offer human Chankan.")

    return game