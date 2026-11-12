from tile_utils import normalize_tile, normalize_tiles, take_matching
from match_rules import finish_match, finish_if_bankrupt
from riichi_kan import is_riichi_ankan_legal
from nagashi import get_nagashi_winners, get_nagashi_score
import random
from collections import Counter
from hand_evaluator import (
    is_complete_hand,
    get_tenpai_discards,
    get_waiting_tiles,
)
from win_rules import is_discard_furiten
from yaku import get_win_yaku
from scoring import evaluate_hand_score
from copy import deepcopy
from ai import choose_discard, calculate_shanten
from ai_calls import yaku_plan_costs, safe_discard_indices, score_call

def create_tiles(include_red=True):
    """Build 136 tiles, with one red five per suit by default."""
    tiles = []

    for suit in ['m', 'p', 's']:
        for number in range(1, 10):
            tile = f"{number}{suit}"
            tiles.extend([tile] * 4)

    # Four winds and three dragons.
    for number in range(1, 8):
        tile = f"{number}z"
        tiles.extend([tile] * 4)

    # Replace one ordinary five per suit; the total stays at 136 tiles.
    if include_red:
        for suit in ("m", "p", "s"):
            tiles[tiles.index("5" + suit)] = "0" + suit
    return tiles

def create_game():
    """Deal a new hand and initialize the round state."""
    wall = create_tiles()
    random.shuffle(wall)

    # Reserve 14 tiles for replacement draws and indicators.
    dead_wall = wall[-14:]
    del wall[-14:]

    hands = [[] for _ in range(4)]

    discards = [[] for _ in range(4)]

    # Deal 13 tiles to each player.
    for _ in range(13):
        for hand in hands:
            draw_tile(wall, hand)

    for hand in hands:
        sort_tiles(hand)

    # Keep all hand state together so it can be saved and restored.
    return {
        "wall": wall,
        "dead_wall": dead_wall,
        "dora_indicator_count": 1,
        "rinshan_draw_count": 0,
        "hands": hands,
        "discards": discards,
        "melds": [[] for _ in range(4)],
        # History keeps called-away discards too, for furiten and Nagashi checks.
        "discard_history": [[] for _ in range(4)],
        "dealer_index": 0,

        "round_wind": "1z",
        "hand_number": 1,
        "honba": 0,
        "match_ended": False,
        "match_end_reason": None,
        "final_riichi_award": 0,
        "final_riichi_recipient": None,
        "seat_winds": ["1z", "2z", "3z", "4z"],

        "human_player_index": 0,
        "current_player_index": 0,
        # Phases separate drawing, discarding, responses and settlement.
        "phase": "draw",
        "winner_index": None,
        "end_reason": None,
        "abort_reason": None,

        "last_discard": None,
        "temporary_furiten": [False, False, False, False],
        "winner_indices": [],

        # Riichi state and point balances.
        # Scores and accepted Riichi declarations carry across hands.
        "scores": [25000, 25000, 25000, 25000],
        "riichi_declared": [False, False, False, False],
        "riichi_sticks": 0,
        "double_riichi": [False] * 4,
        "ippatsu_eligible": [False] * 4,
        "pending_double_riichi": False,
        "calls_made": False,
        "ordinary_draw_counts": [0] * 4,
        "ordinary_draw_player": None,
        "last_live_draw_player": None,
        "last_discard_is_houtei": False,
        "is_closed": [True, True, True, True],
        "riichi_min_wall_tiles": 4,
        # Pending declarations wait for responses before taking effect.
        "pending_riichi": None,
        "pending_kakan": None,
        "robbed_kan_tile": None,
        "riichi_furiten": [False, False, False, False],
        "rinshan_player_index": None,

        "after_call": False,
        "forbidden_discard_tiles": [],

        "settlement": None,
        "winning_discarder_index": None,
    }


def interrupt_ippatsu(game):
    """A committed Chi, Pon or Kan interrupts all first-turn/Ippatsu windows."""
    game["calls_made"] = True
    game["ordinary_draw_player"] = None
    game["ippatsu_eligible"] = [False] * 4
    game["last_live_draw_player"] = None
    game["last_discard_is_houtei"] = False


def get_event_yaku_flags(game, player_index, *, is_tsumo, chankan=False):
    """Share event context between legal-win checks and final scoring."""
    riichi = game["riichi_declared"][player_index]
    opening_draw = (
        is_tsumo and not chankan
        and game["ordinary_draw_player"] == player_index
        and game["ordinary_draw_counts"][player_index] == 1
        and not game["calls_made"]
        and not game["discard_history"][player_index]
        and not game["melds"][player_index]
        and game["rinshan_player_index"] is None
        and not game["after_call"]
    )
    dealer = player_index == game["dealer_index"]
    return {
        "tenhou": opening_draw and dealer and not any(game["discard_history"]),
        "chiihou": opening_draw and not dealer,
        "double_riichi": riichi and game["double_riichi"][player_index],
        "ippatsu": riichi and game["ippatsu_eligible"][player_index],
        "haitei": (is_tsumo and game["last_live_draw_player"] == player_index
                   and game["rinshan_player_index"] is None and not game["wall"]),
        "houtei": (not is_tsumo and not chankan
                   and game["last_discard_is_houtei"] and not game["wall"]),
    }


ABORT_REASONS = {
    "kyuushu_kyuuhai", "suufon_renda", "suucha_riichi", "suukaikan",
}


def can_kyuushu_kyuuhai(game, player_index):
    """Check for nine terminal/honor types on an uninterrupted first draw."""
    if type(player_index) is not int or player_index not in range(4):
        return False
    if (game["phase"] != "discard"
            or game["current_player_index"] != player_index
            or game["ordinary_draw_player"] != player_index
            or game["ordinary_draw_counts"][player_index] != 1
            or game["calls_made"] or game["after_call"]
            or game["riichi_declared"][player_index]
            or game["discard_history"][player_index]
            or game["melds"][player_index]
            or game["rinshan_player_index"] is not None):
        return False
    hand = game["hands"][player_index]
    return len(hand) == 14 and len({
        tile for tile in hand if tile[1] == "z" or tile[0] in ("1", "9")
    }) >= 9


def get_automatic_abort_reason(game):
    """Inspect a discard response; Ron always resolves before any draw abort."""
    if game["phase"] != "response":
        return None
    history = game["discard_history"]
    if not game["calls_made"] and all(len(pile) == 1 for pile in history):
        first = [pile[0] for pile in history]
        if first[0] in ("1z", "2z", "3z", "4z") and len(set(first)) == 1:
            return "suufon_renda"
    if all(game["riichi_declared"]):
        return "suucha_riichi"
    kan_counts = [
        sum(meld["type"] in ("ankan", "daiminkan", "kakan") for meld in melds)
        for melds in game["melds"]
    ]
    # Fourth replacement draw and its discard are allowed; one owner's four Kans continue.
    if sum(kan_counts) == 4 and max(kan_counts) < 4:
        return "suukaikan"
    return None


def _end_abortive_draw(game, reason):
    """No Noten payments; existing scores and all deposits carry forward."""
    if reason not in ABORT_REASONS:
        raise ValueError("Unknown abortive draw reason.")
    before = list(game["scores"])
    game["phase"] = "ended"
    game["end_reason"] = "abortive_draw"
    game["abort_reason"] = reason
    game["winner_index"] = None
    game["winner_indices"] = []
    game["winning_discarder_index"] = None
    game["pending_riichi"] = None
    game["pending_double_riichi"] = False
    game["settlement"] = {
        "score_deltas": [0] * 4,
        "scores_before": before,
        "scores_after": list(before),
        "riichi_award": 0,
        "riichi_recipient": None,
        "honba": game["honba"],
        "honba_awards": [0] * 4,
        "abort_reason": reason,
    }

    finish_if_bankrupt(game)


def declare_kyuushu_kyuuhai(game, player_index):
    """End the hand only if the first-draw abort is legal."""
    if not can_kyuushu_kyuuhai(game, player_index):
        raise ValueError("Nine terminals/honors abort is not available.")
    _end_abortive_draw(game, "kyuushu_kyuuhai")


def get_ankan_options(game, player_index):
    """Return tile types available for concealed Kan."""
    if type(player_index) is not int or player_index not in range(4):
        return []

    if game["phase"] != "discard":
        return []

    if game["current_player_index"] != player_index:
        return []

    # A call must be followed by a discard, not another call.
    if game["after_call"]:
        return []

    if not game["wall"] or len(game["dead_wall"]) != 14:
        return []

    if game["rinshan_draw_count"] >= 4:
        return []

    if game["dora_indicator_count"] >= 5:
        return []

    hand = game["hands"][player_index]
    melds = game["melds"][player_index]

    if len(melds) >= 4:
        return []

    if len(hand) != 14 - 3 * len(melds):
        return []

    counts = Counter(normalize_tiles(hand))

    options = sorted(tile for tile, count in counts.items() if count == 4)
    if not game["riichi_declared"][player_index]:
        return options

    if not game["is_closed"][player_index]:
        return []
    # The final hand slot is always the latest normal or replacement draw.
    if (game["ordinary_draw_player"] != player_index
            and game["rinshan_player_index"] != player_index):
        return []
    return [tile for tile in options if is_riichi_ankan_legal(hand, melds, tile)]


def get_kakan_options(game, player_index):
    """Return Pon groups that can be upgraded with a concealed tile."""
    if player_index not in range(4):
        return []

    if game["phase"] != "discard":
        return []

    if game["current_player_index"] != player_index:
        return []

    if game["after_call"]:
        return []

    if game["riichi_declared"][player_index]:
        return []

    if not game["wall"]:
        return []

    if game["rinshan_draw_count"] >= 4:
        return []

    if game["dora_indicator_count"] >= 5:
        return []

    if len(game["dead_wall"]) != 14:
        return []

    hand = game["hands"][player_index]
    melds = game["melds"][player_index]

    if len(hand) != 14 - 3 * len(melds):
        return []

    options = []

    for meld_index, meld in enumerate(melds):
        if meld["type"] != "pon":
            continue

        tile = meld["tiles"][0]

        if any(normalize_tile(t) == normalize_tile(tile) for t in hand):
            physical_tile = next(t for t in hand if normalize_tile(t) == normalize_tile(tile))
            options.append({
                "meld_index": meld_index,
                "tile": physical_tile
            })

    return options


def can_kakan(game, player_index):
    """Check whether any Pon can be upgraded to a Kan."""
    return bool(get_kakan_options(game, player_index))

def declare_kakan(game, player_index, meld_index):
    """Request a Pon upgrade and wait for robbery responses."""
    if type(meld_index) is not int:
        raise ValueError("Invalid meld index.")

    options = get_kakan_options(game, player_index)

    option = next(
        (
            option
            for option in options
            if option["meld_index"] == meld_index
        ),
        None
    )

    if option is None:
        raise ValueError("This group cannot be upgraded to Kakan.")

    if game["pending_kakan"] is not None:
        raise ValueError("A Kakan declaration is already pending.")

    interrupt_ippatsu(game)
    game["pending_kakan"] = {
        "player_index": player_index,
        "meld_index": meld_index,
        "tile": option["tile"]
    }

    game["last_discard"] = None
    game["phase"] = "kakan_response"


def can_ankan(game, player_index):
    """Check whether a concealed Kan is available this turn."""
    return bool(get_ankan_options(game, player_index))

def declare_ankan(game, player_index, tile):
    """Declare a concealed Kan and draw its replacement tile."""
    if tile not in get_ankan_options(game, player_index):
        raise ValueError("This tile cannot be declared as Ankan.")

    # Validate before moving any physical tiles.
    if len(game["dead_wall"]) != 14:
        raise ValueError("The dead wall must contain 14 tiles.")

    interrupt_ippatsu(game)
    hand = game["hands"][player_index]

    kan_tiles = take_matching(hand, tile, 4)

    game["melds"][player_index].append({
        "type": "ankan",
        "tiles": kan_tiles
    })

    # Sort the remaining hand before appending the replacement.
    sort_tiles(hand)

    drawn_tile = draw_rinshan_tile(game, player_index)
    game["dora_indicator_count"] += 1

    return drawn_tile

def get_riichi_options(game, player_index):
    """Return legal declaration discards for the current player."""
    if player_index not in range(4):
        return []

    if game["phase"] != "discard":
        return []

    if game["current_player_index"] != player_index:
        return []

    if game["riichi_declared"][player_index]:
        return []

    if not game["is_closed"][player_index]:
        return []

    if game["scores"][player_index] < 1000:
        return []

    if len(game["wall"]) < game["riichi_min_wall_tiles"]:
        return []

    return get_tenpai_discards(
        game["hands"][player_index],
        game["melds"][player_index]
    )


def can_riichi(game, player_index):
    """Check whether the player has any legal riichi discard."""
    return bool(get_riichi_options(game, player_index))


def declare_riichi(game, player_index, tile_index):
    """Discard a declaration tile and wait for Ron responses."""
    options = get_riichi_options(game, player_index)

    if type(tile_index) is not int:
        raise ValueError("Invalid tile index.")

    if not any(
        option["tile_index"] == tile_index
        for option in options
    ):
        raise ValueError("This tile cannot be used to declare Riichi.")

    double_riichi = (
        not game["discard_history"][player_index]
        and not game["calls_made"]
    )
    # Finish the discard before recording the pending declaration.
    discarded_tile = finish_turn(game, player_index, tile_index)
    game["pending_riichi"] = player_index
    game["pending_double_riichi"] = double_riichi

    return discarded_tile


def sort_tiles(tiles):
    """Sort in place by suit and rank, treating red fives as fives."""
    # Order suits as man, pin, sou, then winds and dragons.
    tile_order = {
        '1m': 1, '2m': 2, '3m': 3, '4m': 4, '5m': 5, '6m': 6, '7m': 7, '8m': 8, '9m': 9,
        '1p': 10, '2p': 11, '3p': 12, '4p': 13, '5p': 14, '6p': 15, '7p': 16, '8p': 17, '9p': 18,
        '1s': 19, '2s': 20, '3s': 21, '4s': 22, '5s': 23, '6s': 24, '7s': 25, '8s': 26, '9s': 27,
        '1z': 28, '2z': 29, '3z': 30, '4z': 31, '5z': 32, '6z': 33, '7z': 34
    }

    tiles.sort(key=lambda x: tile_order.get(normalize_tile(x), float('inf')))

def draw_tile(wall, hand):
    """Append the draw last so it stays separate from the sorted hand."""
    # The end of the list is the next draw; keep it last in the hand.
    tile = wall.pop()
    hand.append(tile)

    return tile

def draw_rinshan_tile(game, player_index):
    """Draw a replacement tile while keeping the dead wall at 14."""
    if player_index not in range(4):
        raise ValueError("Invalid player index.")

    if game["phase"] != "discard":
        raise ValueError("Cannot draw a replacement in this phase.")

    if game["current_player_index"] != player_index:
        raise ValueError("It is not this player's turn.")

    draw_count = game["rinshan_draw_count"]

    if not 0 <= draw_count < 4:
        raise ValueError("No replacement tiles remain.")

    if len(game["dead_wall"]) != 14:
        raise ValueError("The dead wall must contain 14 tiles.")

    if not game["wall"]:
        raise ValueError("The wall cannot replenish the dead wall.")

    # These four positions are consumed in order.
    tile = game["dead_wall"][draw_count]

    # Ordinary draws use pop(), so index 0 is the far end.
    game["dead_wall"][draw_count] = game["wall"].pop(0)

    game["ordinary_draw_player"] = None
    game["last_live_draw_player"] = None
    game["last_discard_is_houtei"] = False
    game["hands"][player_index].append(tile)
    game["rinshan_draw_count"] += 1
    game["rinshan_player_index"] = player_index

    game["temporary_furiten"][player_index] = False
    game["last_discard"] = None
    game["after_call"] = False
    game["forbidden_discard_tiles"] = []

    return tile

def discard_tile(hand, discard_pile, tile_index):
    """Remove a tile by index, record it and sort the remaining hand."""
    if not 0<= tile_index < len(hand):
        raise ValueError("Invalid tile index for discard.")

    tile = hand.pop(tile_index)
    discard_pile.append(tile)

    sort_tiles(hand)

    return tile

def start_turn(game):
    """Draw a tile or settle the hand if the live wall is empty."""
    if game["phase"] != "draw":
        raise ValueError("Cannot draw in the current phase.")

    if not game["wall"]:
        game["phase"] = "ended"
        game["end_reason"] = "exhaustive_draw"

        settle_exhaustive_draw(game)
        return None

    player_index = game["current_player_index"]

    drawn_tile = draw_tile(
        game["wall"],
        game["hands"][player_index]
    )

    game["ordinary_draw_counts"][player_index] += 1
    game["ordinary_draw_player"] = player_index
    game["last_live_draw_player"] = player_index if not game["wall"] else None
    game["last_discard_is_houtei"] = False
    # Temporary furiten ends when this player draws.
    game["temporary_furiten"][player_index] = False
    game["last_discard"] = None
    game["rinshan_player_index"] = None
    game["phase"] = "discard"

    return drawn_tile


def finish_turn(game, player_index, tile_index):
    """Validate the discard and open the response window."""
    if game["phase"] != "discard":
        raise ValueError("Cannot discard in the current phase.")

    if player_index != game["current_player_index"]:
        raise ValueError("It is not this player's turn.")

    hand = game["hands"][player_index]

    if type(tile_index) is not int or not 0 <= tile_index < len(hand):
        raise ValueError("Invalid tile index for discard.")

    # After Riichi, only the newly drawn tile may be discarded.
    if game["riichi_declared"][player_index]:
        if tile_index != len(hand) - 1:
            raise ValueError(
                "After Riichi, you must discard the drawn tile."
            )

    if normalize_tile(hand[tile_index]) in normalize_tiles(game["forbidden_discard_tiles"]):
        raise ValueError(
            "This tile cannot be discarded immediately after a call."
        )

    # Validate all inputs first; only a successful discard expires Ippatsu.
    game["ippatsu_eligible"][player_index] = False
    game["last_discard_is_houtei"] = (
        game["last_live_draw_player"] == player_index
        and game["rinshan_player_index"] is None
        and not game["after_call"]
        and not game["wall"]
    )
    game["ordinary_draw_player"] = None
    game["last_live_draw_player"] = None
    discarded_tile = discard_tile(
        hand,
        game["discards"][player_index],
        tile_index
    )

    game["discard_history"][player_index].append(discarded_tile)
    game["rinshan_player_index"] = None

    game["last_discard"] = {
        "player_index": player_index,
        "tile": discarded_tile
    }

    game["after_call"] = False
    game["forbidden_discard_tiles"] = []
    game["phase"] = "response"

    return discarded_tile


def get_ai_visible_tiles(game, player_index):
    """Collect public tiles outside this player's hand and melds."""
    if type(player_index) is not int or player_index not in range(4):
        raise ValueError("Invalid player index.")

    visible_tiles = []

    # Only current discard piles, not historical records.
    for pile in game["discards"]:
        visible_tiles.extend(pile)

    # Own melds are already counted inside analyze_discards().
    for index, melds in enumerate(game["melds"]):
        if index == player_index:
            continue

        for meld in melds:
            visible_tiles.extend(meld["tiles"])

    visible_tiles.extend(get_dora_indicators(game))

    return visible_tiles


def get_ai_discard_index(game, player_index):
    """Choose a discard while preserving current game restrictions."""
    if type(player_index) is not int or player_index not in range(4):
        raise ValueError("Invalid player index.")

    if (
        game["phase"] != "discard"
        or game["current_player_index"] != player_index
    ):
        raise ValueError("It is not this player's discard phase.")

    hand = game["hands"][player_index]

    allowed_indices = [
        index
        for index, tile in enumerate(hand)
        if normalize_tile(tile) not in normalize_tiles(game["forbidden_discard_tiles"])
    ]

    if game["riichi_declared"][player_index]:
        drawn_index = len(hand) - 1

        if drawn_index not in allowed_indices:
            raise ValueError("The drawn tile cannot be discarded.")

        return drawn_index

    # Keep secured yaku or continue clearing tiles that do not fit the chosen route.
    if not game["is_closed"][player_index]:
        safe = safe_discard_indices(hand, game["melds"][player_index], allowed_indices,
                                    game["seat_winds"][player_index], game["round_wind"],
                                    get_ai_visible_tiles(game, player_index))
        if safe:
            allowed_indices = safe

    return choose_discard(
        hand,
        game["melds"][player_index],
        visible_tiles=get_ai_visible_tiles(game, player_index),
        allowed_indices=allowed_indices,
    )


def perform_ai_discard(game, player_index):
    """Discard normally or attempt Riichi with the selected tile."""
    if player_index == game["human_player_index"]:
        raise ValueError("This operation is for computer players.")

    tile_index = get_ai_discard_index(game, player_index)

    riichi_options = (
        get_riichi_options(game, player_index)
        if not game["after_call"]
        else []
    )

    can_declare_with_selected_tile = any(
        option["tile_index"] == tile_index
        for option in riichi_options
    )

    if can_declare_with_selected_tile:
        tile = declare_riichi(
            game,
            player_index,
            tile_index,
        )

        return {
            "tile": tile,
            "riichi_attempted": True,
        }

    tile = finish_turn(
        game,
        player_index,
        tile_index,
    )

    return {
        "tile": tile,
        "riichi_attempted": False,
    }


def advance_until_human(game, observer=None, max_steps=None):
    """Run computer turns until the human has a decision or the hand ends."""
    steps = 0
    while game["phase"] != "ended":
        if max_steps is not None and steps >= max_steps:
            return True
        steps += 1
        # Record public turn boundaries for browser playback, without delaying saves.
        if observer is not None:
            observer(game)
        if game["phase"] == "kakan_response":
            human_index = game["human_player_index"]

            if can_chankan(game, human_index):
                return

            computer_winners = [
                index
                for index in range(4)
                if index != human_index and can_chankan(game, index)
            ]

            # Complete the Kan only after every robbery claim has been checked.
            resolve_kakan_responses(game, computer_winners)
            continue

        # Resolve wins before calls, and compare human and AI call priorities.
        if game["phase"] == "response":
            human_index = game["human_player_index"]
            if can_ron(game, human_index):
                return
            computer_winners = [index for index in range(4)
                                if index != human_index and can_ron(game, index)]
            if computer_winners:
                resolve_ron_responses(game, computer_winners)
                continue
            human_calls = []
            if can_pon(game, human_index):
                human_calls.append(_make_call(game, human_index, "pon"))
            if can_daiminkan(game, human_index):
                human_calls.append(_make_call(game, human_index, "daiminkan"))
            human_calls.extend(_make_call(game, human_index, "chi", option)
                               for option in get_chi_options(game, human_index))
            if human_calls:
                rival = get_ai_discard_claim(game)
                if rival is None or min(map(_call_priority, human_calls)) < _call_priority(rival):
                    return
            resolve_ron_responses(game, [])
            continue

        if game["phase"] == "draw":
            start_turn(game)

        if game["phase"] == "ended":
            return

        if observer is not None:
            observer(game)
        player_index = game["current_player_index"]

        if player_index == game["human_player_index"]:
            return

        # A computer takes a legal win before choosing a discard.
        if can_tsumo(game, player_index):
            declare_tsumo(game, player_index)
            return

        if can_kyuushu_kyuuhai(game, player_index):
            declare_kyuushu_kyuuhai(game, player_index)
            return

        kan = get_ai_turn_kan(game, player_index) if not game["after_call"] else None
        if kan is not None:
            if kan["type"] == "ankan":
                declare_ankan(game, player_index, kan["tile"])
            else:
                declare_kakan(game, player_index, kan["meld_index"])
            continue
        perform_ai_discard(game, player_index)

def check_tile_counts(game):
    """Check that every physical tile still has exactly one location."""
    # Count physical locations only; history and indicators refer to existing tiles.
    all_tiles = game["wall"] + game["dead_wall"]

    for hand in game["hands"]:
        all_tiles.extend(hand)

    for pile in game["discards"]:
        all_tiles.extend(pile)

    for player_melds in game["melds"]:
        for meld in player_melds:
            all_tiles.extend(meld["tiles"])

    # A robbed added-Kan tile is stored separately after leaving the hand.
    if game["robbed_kan_tile"] is not None:
        all_tiles.append(game["robbed_kan_tile"])

    assert len(all_tiles) == 136
    # Old saves may use the original set without red fives.
    assert Counter(all_tiles) in (Counter(create_tiles()), Counter(create_tiles(False)))
    assert len(game["dead_wall"]) == 14

def get_dora_indicators(game):
    """Read the revealed indicator slots from the dead wall."""
    # Replacement tiles occupy slots 0-3; visible and hidden indicators alternate.
    indicator_indices = [4, 6, 8, 10, 12]
    visible_count = game["dora_indicator_count"]

    return [
        game["dead_wall"][index]
        for index in indicator_indices[:visible_count]
    ]

def get_ura_dora_indicators(game):
    """Return Ura Dora indicators from the dead wall."""
    count = game["dora_indicator_count"]

    # Ura indicators sit beside the corresponding visible indicators.
    return [
        game["dead_wall"][5 + index * 2]
        for index in range(count)
    ]


def get_winner_ura_dora_indicators(game, player_index):
    """Reveal Ura Dora only for a winner with accepted Riichi."""
    if game["end_reason"] == "nagashi_mangan":
        return []

    if game["phase"] != "ended":
        return []

    if player_index not in game["winner_indices"]:
        return []

    if not game["riichi_declared"][player_index]:
        return []

    return get_ura_dora_indicators(game)

def indicator_to_dora(indicator):
    # Validate the tile code.
    """Find the next tile in the numbered, wind or dragon cycle."""
    if not isinstance(indicator, str) or len(indicator) != 2:
        raise ValueError("Invalid dora indicator.")

    indicator = normalize_tile(indicator)
    number_text, suit = indicator

    # Numbered suits: 1 -> 2 -> ... -> 9 -> 1.
    if suit in ("m", "p", "s") and number_text in "123456789":
        number = int(number_text)
        next_number = number % 9 + 1

        return f"{next_number}{suit}"

    # Winds and dragons form two separate cycles.
    honor_dora = {
        "1z": "2z",  # East -> South
        "2z": "3z",  # South -> West
        "3z": "4z",  # West -> North
        "4z": "1z",  # North -> East
        "5z": "6z",  # White -> Green
        "6z": "7z",  # Green -> Red
        "7z": "5z",  # Red -> White
    }

    if indicator in honor_dora:
        return honor_dora[indicator]

    raise ValueError("Invalid dora indicator.")

def count_dora(hand, melds, indicators):
    """Count Dora in concealed tiles and declared groups."""
    all_tiles = list(hand)

    for meld in melds:
        all_tiles.extend(meld["tiles"])

    total = 0

    for indicator in indicators:
        dora_tile = indicator_to_dora(indicator)
        total += normalize_tiles(all_tiles).count(dora_tile)

    return total

def get_dora_tiles(game):
    """Convert visible indicators into the tile types that earn Dora."""
    indicators = get_dora_indicators(game)

    return [
        indicator_to_dora(indicator)
        for indicator in indicators
    ]

def can_tsumo(game, player_index):
    """Check the turn, hand shape and required yaku for a self-drawn win."""
    if player_index not in range(4):
        return False

    if game["phase"] != "discard":
        return False

    if player_index != game["current_player_index"]:
        return False

    if game["after_call"]:
        return False

    hand = game["hands"][player_index]

    return bool(get_win_yaku(
        hand,
        seat_wind=game["seat_winds"][player_index],
        round_wind=game["round_wind"],
        melds=game["melds"][player_index],
        is_closed=game["is_closed"][player_index],
        is_tsumo=True,
        riichi=game["riichi_declared"][player_index],
        **get_event_yaku_flags(game, player_index, is_tsumo=True),
        rinshan=game["rinshan_player_index"] == player_index,
        winning_tile=hand[-1],
    ))

def declare_tsumo(game, player_index):
    """Record a legal self-drawn win and settle its payments."""
    if not can_tsumo(game, player_index):
        raise ValueError("Tsumo is not allowed.")

    game["winner_index"] = player_index
    game["winner_indices"] = [player_index]
    game["end_reason"] = "tsumo"
    game["phase"] = "ended"
    settle_win(game)

def get_chi_candidates(game, player_index):
    """Return possible Chi combinations before response priority checks."""
    if get_automatic_abort_reason(game):
        return []

    if player_index not in range(4):
        return []

    if game["phase"] != "response":
        return []

    discard = game["last_discard"]

    if discard is None:
        return []

    # Only the previous player in turn order can supply Chi.
    previous_player = (player_index - 1) % 4

    if discard["player_index"] != previous_player:
        return []

    if game["riichi_declared"][player_index]:
        return []

    if not game["wall"]:
        return []

    melds = game["melds"][player_index]
    hand = game["hands"][player_index]

    if len(melds) >= 4:
        return []

    if len(hand) != 13 - 3 * len(melds):
        return []

    tile = normalize_tile(discard["tile"])
    suit = tile[1]

    if suit == "z":
        return []

    number = int(tile[0])
    candidates = []

    # The claimed tile can be the first, middle, or last tile.
    for start in range(max(1, number - 2), min(number, 7) + 1):
        sequence = [
            f"{start}{suit}",
            f"{start + 1}{suit}",
            f"{start + 2}{suit}"
        ]

        hand_tiles = sequence.copy()
        hand_tiles.remove(tile)

        if all(
            normalize_tiles(hand).count(required) >= count
            for required, count in Counter(hand_tiles).items()
        ):
            from itertools import product
            choices = [[value for value in dict.fromkeys(hand)
                        if normalize_tile(value) == required] for required in hand_tiles]
            for selected in product(*choices):
                physical = list(selected)
                candidates.append({
                    "tiles": sorted(physical + [discard["tile"]], key=normalize_tile),
                    "hand_tiles": physical,
                })

    return candidates

def get_chi_forbidden_tiles(called_tile, sequence):
    """Return tile types forbidden immediately after this Chi."""
    called_tile = normalize_tile(called_tile)
    sequence = normalize_tiles(sequence)
    suit = called_tile[1]
    number = int(called_tile[0])
    start = min(int(tile[0]) for tile in sequence)

    forbidden = {called_tile}

    # Calling the low end can swap out the opposite high end.
    if number == start and start + 3 <= 9:
        forbidden.add(f"{start + 3}{suit}")

    # Calling the high end can swap out the opposite low end.
    if number == start + 2 and start - 1 >= 1:
        forbidden.add(f"{start - 1}{suit}")

    return sorted(forbidden)

def get_chi_options(game, player_index):
    """Keep Chi candidates that leave at least one legal discard."""
    candidates = get_chi_candidates(game, player_index)

    if not candidates:
        return []

    called_tile = game["last_discard"]["tile"]
    options = []

    for candidate in candidates:
        remaining_hand = list(game["hands"][player_index])

        for tile in candidate["hand_tiles"]:
            remaining_hand.remove(tile)

        forbidden_tiles = get_chi_forbidden_tiles(
            called_tile,
            candidate["tiles"]
        )

        # The player must be able to discard after calling.
        if not any(
            normalize_tile(tile) not in forbidden_tiles
            for tile in remaining_hand
        ):
            continue

        options.append({
            "tiles": candidate["tiles"].copy(),
            "hand_tiles": candidate["hand_tiles"].copy(),
            "forbidden_discard_tiles": forbidden_tiles
        })

    return options


def can_chi(game, player_index):
    """Check whether at least one legal Chi option remains."""
    return bool(get_chi_options(game, player_index))


def can_daiminkan(game, player_index):
    """Check whether the current discard can complete an open Kan."""
    if get_automatic_abort_reason(game):
        return False

    if player_index not in range(4):
        return False

    if game["phase"] != "response":
        return False

    discard = game["last_discard"]

    if discard is None:
        return False

    if discard["player_index"] == player_index:
        return False

    if game["riichi_declared"][player_index]:
        return False

    if not game["wall"]:
        return False

    if game["rinshan_draw_count"] >= 4:
        return False

    if game["dora_indicator_count"] >= 5:
        return False

    if len(game["dead_wall"]) != 14:
        return False

    melds = game["melds"][player_index]
    hand = game["hands"][player_index]

    if len(melds) >= 4:
        return False

    if len(hand) != 13 - 3 * len(melds):
        return False

    return normalize_tiles(hand).count(normalize_tile(discard["tile"])) == 3


def declare_daiminkan(game, player_index):
    """Declare an open Kan after resolving wins and competing calls."""
    if not can_daiminkan(game, player_index):
        raise ValueError("Daiminkan is not allowed.")
    return _declare_discard_call(game, _make_call(game, player_index, "daiminkan"))


def can_pon(game, player_index):
    """Check whether a player can claim the current discard for Pon."""
    if get_automatic_abort_reason(game):
        return False

    if player_index not in range(4):
        return False

    if game["phase"] != "response":
        return False

    discard = game["last_discard"]

    if discard is None:
        return False

    if discard["player_index"] == player_index:
        return False

    if game["riichi_declared"][player_index]:
        return False

    # Do not allow calls on the final discard.
    if not game["wall"]:
        return False

    melds = game["melds"][player_index]
    hand = game["hands"][player_index]

    if len(melds) >= 4:
        return False

    if len(hand) != 13 - 3 * len(melds):
        return False

    tile = discard["tile"]

    if normalize_tiles(hand).count(normalize_tile(tile)) < 2:
        return False

    # At least one legal discard must remain after the call.
    return any(normalize_tile(hand_tile) != normalize_tile(tile) for hand_tile in hand)

def declare_pon(game, player_index):
    """Declare Pon after resolving wins and competing calls."""
    if not can_pon(game, player_index):
        raise ValueError("Pon is not allowed.")
    return _declare_discard_call(game, _make_call(game, player_index, "pon"))


def declare_chi(game, player_index, option_index):
    """Declare the selected Chi, preserving its immediate discard restrictions."""
    options = get_chi_options(game, player_index)
    if type(option_index) is not int or not 0 <= option_index < len(options):
        raise ValueError("Invalid Chi option.")
    return _declare_discard_call(game, _make_call(game, player_index, "chi", options[option_index]))


def _make_call(game, player, kind, option=None):
    """Keep physical red tiles intact while preparing a call without changing state."""
    discard = game["last_discard"]
    tile = discard["tile"]
    if kind == "chi":
        hand_tiles = list(option["hand_tiles"])
        tiles = list(option["tiles"])
        forbidden = list(option["forbidden_discard_tiles"])
    else:
        copy = list(game["hands"][player])
        hand_tiles = take_matching(copy, tile, 3 if kind == "daiminkan" else 2)
        tiles = hand_tiles + [tile]
        forbidden = [normalize_tile(tile)] if kind == "pon" else []
    return {"player_index": player, "type": kind, "tile": tile,
            "hand_tiles": hand_tiles, "tiles": tiles,
            "forbidden_discard_tiles": forbidden,
            "from_player_index": discard["player_index"]}


def _call_priority(claim):
    """Pon and open Kan precede Chi; nearer players win equal-priority claims."""
    return (1 if claim["type"] == "chi" else 0,
            (claim["player_index"] - claim["from_player_index"]) % 4)


def get_ai_discard_claim(game):
    """Choose a useful call with a concrete yaku plan, using only visible tiles."""
    if game["phase"] != "response" or not game["wall"] or get_automatic_abort_reason(game):
        return None
    discard = game["last_discard"]
    if discard is None:
        return None
    pile = game["discards"][discard["player_index"]]
    # A call needs a physical river tile, not just a response label.
    if not pile or pile[-1] != discard["tile"]:
        return None
    claims = []
    for player in range(4):
        if player == game["human_player_index"]:
            continue
        candidates = []
        if can_pon(game, player):
            candidates.append(_make_call(game, player, "pon"))
        if can_daiminkan(game, player):
            candidates.append(_make_call(game, player, "daiminkan"))
        candidates.extend(_make_call(game, player, "chi", option)
                          for option in get_chi_options(game, player))
        if not candidates:
            continue
        visible = get_ai_visible_tiles(game, player)
        choices = []
        for claim in candidates:
            quality = score_call(game["hands"][player], game["melds"][player], claim,
                                 visible, game["seat_winds"][player], game["round_wind"])
            if quality is not None:
                choices.append((quality, claim))
        if choices:
            # Each player proposes one action; table priority is applied afterwards.
            claims.append(min(choices, key=lambda item: (item[0],
                          item[1]["type"] != "daiminkan"))[1])
    return min(claims, key=_call_priority) if claims else None


def _declare_discard_call(game, requested):
    """Resolve Ron first, then choose between the requested call and AI claims."""
    player = requested["player_index"]
    winners = [index for index in range(4) if index != player and can_ron(game, index)]
    if winners:
        resolve_ron_responses(game, winners)
        return False
    selected = requested
    if player == game["human_player_index"]:
        rival = get_ai_discard_claim(game)
        if rival is not None and _call_priority(rival) < _call_priority(requested):
            selected = rival
    _apply_discard_call(game, selected)
    return selected is requested


def _apply_discard_call(game, claim, *, responses_resolved=False):
    """Move one claimed discard and the exact concealed copies into a fixed meld."""
    player = claim["player_index"]
    discarder = claim["from_player_index"]
    tile = claim["tile"]
    pile = game["discards"][discarder]
    if not pile or pile[-1] != tile:
        raise ValueError("The current discard is missing.")
    hand = game["hands"][player]
    remaining = list(hand)
    for value in claim["hand_tiles"]:
        remaining.remove(value)
    # Accept pending Riichi and record passed wins without drawing an ordinary tile.
    if not responses_resolved:
        resolve_ron_responses(game, [], allow_ai_calls=False)
    interrupt_ippatsu(game)
    hand[:] = remaining
    pile.pop()
    game["melds"][player].append({"type": claim["type"], "tiles": list(claim["tiles"]),
                                   "from_player_index": discarder})
    game["is_closed"][player] = False
    game["temporary_furiten"][player] = False
    game["current_player_index"] = player
    game["phase"] = "discard"
    game["last_discard"] = None
    game["after_call"] = claim["type"] != "daiminkan"
    game["forbidden_discard_tiles"] = list(claim["forbidden_discard_tiles"])
    sort_tiles(hand)
    if claim["type"] == "daiminkan":
        draw_rinshan_tile(game, player)
        game["dora_indicator_count"] += 1


def get_ai_turn_kan(game, player):
    """Consider self-Kans without inspecting the replacement tile or losing a yaku."""
    hand = game["hands"][player]
    melds = game["melds"][player]
    candidates = []
    for tile in get_ankan_options(game, player):
        copy = list(hand)
        removed = take_matching(copy, tile, 4)
        groups = deepcopy(melds) + [{"type": "ankan", "tiles": removed}]
        candidates.append(({"type": "ankan", "tile": tile}, copy, groups))
    for option in get_kakan_options(game, player):
        copy = list(hand)
        copy.remove(option["tile"])
        groups = deepcopy(melds)
        groups[option["meld_index"]]["type"] = "kakan"
        groups[option["meld_index"]]["tiles"].append(option["tile"])
        candidates.append(({"type": "kakan", **option}, copy, groups))
    if not candidates:
        return None
    baseline = calculate_shanten(hand, melds)
    for action, remaining, groups in candidates:
        if (not game["is_closed"][player] and not yaku_plan_costs(
                remaining, groups, game["seat_winds"][player], game["round_wind"],
                get_ai_visible_tiles(game, player))):
            continue
        if calculate_shanten(remaining, groups) <= baseline:
            return action
    return None


def resolve_kakan_responses(game, winners):
    """Resolve robbery claims or complete the pending added Kan."""
    if game["phase"] != "kakan_response":
        raise ValueError("There is no Kakan to respond to.")

    pending = game["pending_kakan"]

    if pending is None:
        raise ValueError("The pending Kakan is missing.")

    winners = list(winners)

    if len(winners) != len(set(winners)):
        raise ValueError("Duplicate winners.")

    # Validate all claims before changing the game.
    for winner_index in winners:
        if not can_chankan(game, winner_index):
            raise ValueError("Chankan is not allowed for this player.")

    player_index = pending["player_index"]
    meld_index = pending["meld_index"]
    tile = pending["tile"]

    hand = game["hands"][player_index]
    melds = game["melds"][player_index]

    if not 0 <= meld_index < len(melds):
        raise ValueError("The original Pon is missing.")

    meld = melds[meld_index]

    if (
        meld["type"] != "pon"
        or normalize_tiles(meld["tiles"]) != [normalize_tile(tile)] * 3
        or tile not in hand
    ):
        raise ValueError("The pending Kakan is invalid.")

    if winners:
        # The original Pon stays unchanged.
        hand.remove(tile)
        sort_tiles(hand)

        game["robbed_kan_tile"] = tile
        game["winner_indices"] = winners
        game["winner_index"] = winners[0]
        game["winning_discarder_index"] = player_index
        game["end_reason"] = "chankan"
        game["phase"] = "ended"
        game["pending_kakan"] = None

        settle_win(game)
        return

    # Validate replacement resources before committing the upgrade.
    if (
        not game["wall"]
        or len(game["dead_wall"]) != 14
        or not 0 <= game["rinshan_draw_count"] < 4
        or not 1 <= game["dora_indicator_count"] < 5
    ):
        raise ValueError("A replacement draw is unavailable.")

    # Passing a completion opportunity causes furiten.
    for index in range(4):
        if index == player_index:
            continue

        completed_hand = game["hands"][index] + [tile]

        if is_complete_hand(completed_hand, game["melds"][index]):
            if game["riichi_declared"][index]:
                game["riichi_furiten"][index] = True
            else:
                game["temporary_furiten"][index] = True

    hand.remove(tile)

    # Preserve the original source player.
    meld["type"] = "kakan"
    meld["tiles"].append(tile)

    sort_tiles(hand)

    game["pending_kakan"] = None
    game["current_player_index"] = player_index
    game["phase"] = "discard"

    draw_rinshan_tile(game, player_index)
    game["dora_indicator_count"] += 1


def can_chankan(game, player_index):
    """Check whether a player can rob the pending added Kan."""
    if player_index not in range(4):
        return False

    if game["phase"] != "kakan_response":
        return False

    pending = game["pending_kakan"]

    if pending is None:
        return False

    if player_index == pending["player_index"]:
        return False

    if game["temporary_furiten"][player_index]:
        return False

    if game["riichi_furiten"][player_index]:
        return False

    hand = game["hands"][player_index]
    melds = game["melds"][player_index]

    if is_discard_furiten(
        hand,
        game["discard_history"][player_index],
        melds
    ):
        return False

    # The added tile still physically belongs to the declarer.
    # Build a separate list for structural evaluation.
    completed_hand = list(hand) + [pending["tile"]]

    return is_complete_hand(completed_hand, melds)


def can_ron(game, player_index):
    """Check whether the discard wins the hand without violating furiten."""
    if player_index not in range(4):
        return False

    if game["phase"] != "response":
        return False

    last_discard = game["last_discard"]

    if last_discard is None:
        return False

    # A player cannot win from their own discard.
    if player_index == last_discard["player_index"]:
        return False

    if game["temporary_furiten"][player_index]:
        return False

    if game["riichi_furiten"][player_index]:
        return False

    hand = game["hands"][player_index]
    melds = game["melds"][player_index]

    if is_discard_furiten(
        hand,
        game["discard_history"][player_index],
        melds
    ):
        return False

    # This creates a new list without moving the discarded tile.
    completed_hand = hand + [last_discard["tile"]]

    if not is_complete_hand(completed_hand, melds):
        return False

    # Riichi itself supplies a yaku.
    if game["riichi_declared"][player_index]:
        return True

    yaku = get_win_yaku(
        completed_hand,
        seat_wind=game["seat_winds"][player_index],
        round_wind=game["round_wind"],
        melds=melds,
        is_closed=game["is_closed"][player_index],
        winning_tile=last_discard["tile"],
        is_tsumo=False,
        **get_event_yaku_flags(game, player_index, is_tsumo=False),
    )

    return bool(yaku)


def resolve_ron_responses(game, winners, *, allow_ai_calls=True):
    """Resolve all wins before accepting Riichi or starting the next turn."""
    if game["phase"] != "response":
        raise ValueError("There is no discard to respond to.")

    winners = list(winners)

    if len(winners) != len(set(winners)):
        raise ValueError("Duplicate winners.")

    # Validate every winner before changing the game.
    for player_index in winners:
        if not can_ron(game, player_index):
            raise ValueError("Ron is not allowed for this player.")

    last_discard = game["last_discard"]
    discarder = last_discard["player_index"]

    if winners:
        # A declaration tile was won on: Riichi does not take effect.
        game["pending_riichi"] = None
        game["pending_double_riichi"] = False

        game["winner_indices"] = winners
        game["winner_index"] = winners[0]
        game["winning_discarder_index"] = discarder
        game["end_reason"] = "ron"
        game["phase"] = "ended"

        settle_win(game)
        return

    # Nobody won. Record passed completion opportunities.
    for player_index in range(4):
        if player_index == discarder:
            continue

        completed_hand = (
            game["hands"][player_index] + [last_discard["tile"]]
        )

        if is_complete_hand(
            completed_hand,
            game["melds"][player_index]
        ):
            if game["riichi_declared"][player_index]:
                game["riichi_furiten"][player_index] = True
            else:
                game["temporary_furiten"][player_index] = True

    # Accept Riichi only after the declaration tile survives.
    pending_player = game["pending_riichi"]

    if pending_player is not None:
        game["scores"][pending_player] -= 1000
        game["riichi_sticks"] += 1
        game["riichi_declared"][pending_player] = True
        game["double_riichi"][pending_player] = game["pending_double_riichi"]
        game["ippatsu_eligible"][pending_player] = True
        game["pending_double_riichi"] = False

        # Existing temporary furiten cannot be escaped after Riichi.
        if game["temporary_furiten"][pending_player]:
            game["riichi_furiten"][pending_player] = True

        game["pending_riichi"] = None

    abort_reason = get_automatic_abort_reason(game)
    if abort_reason is not None:
        _end_abortive_draw(game, abort_reason)
        return

    # Calls resolve only after every win, deposit and abortive-draw check.
    if allow_ai_calls and game["wall"]:
        claim = get_ai_discard_claim(game)
        if claim is not None:
            _apply_discard_call(game, claim, responses_resolved=True)
            return

    if not game["wall"]:
        game["phase"] = "ended"
        game["end_reason"] = "exhaustive_draw"

        settle_exhaustive_draw(game)
    else:
        game["current_player_index"] = (discarder + 1) % 4
        game["phase"] = "draw"
        game["last_discard"] = None


def declare_ron(game, player_index):
    """Accept the human win together with any eligible computer wins."""
    if player_index != game["human_player_index"]:
        raise ValueError("This operation is for the human player.")

    if not can_ron(game, player_index):
        raise ValueError("Ron is not allowed.")

    # Computers always accept a valid Ron in this prototype.
    winners = [
        index
        for index in range(4)
        if can_ron(game, index)
    ]

    resolve_ron_responses(game, winners)

def pass_ron(game, player_index):
    """Record the passed win and let other players respond."""
    if player_index != game["human_player_index"]:
        raise ValueError("This operation is for the human player.")

    if not can_ron(game, player_index):
        raise ValueError("There is no Ron option to pass.")

    if game["riichi_declared"][player_index]:
        game["riichi_furiten"][player_index] = True
    else:
        game["temporary_furiten"][player_index] = True

    # Other eligible players may still win.
    winners = [
        index
        for index in range(4)
        if index != player_index and can_ron(game, index)
    ]

    resolve_ron_responses(game, winners)

def pass_response(game, player_index):
    """Pass all currently available human discard responses."""
    if player_index != game["human_player_index"]:
        raise ValueError("This operation is for the human player.")

    if not (
        can_ron(game, player_index)
        or can_pon(game, player_index)
        or can_chi(game, player_index)
        or can_daiminkan(game, player_index)
    ):
        raise ValueError("There is no response option to pass.")

    if can_ron(game, player_index):
        pass_ron(game, player_index)
        return

    # Computers still take priority if they can win.
    winners = [
        index
        for index in range(4)
        if index != player_index and can_ron(game, index)
    ]

    resolve_ron_responses(game, winners)


def declare_chankan(game, player_index):
    """Accept a human robbery win, including eligible computer winners."""
    if player_index != game["human_player_index"]:
        raise ValueError("This operation is for the human player.")

    if not can_chankan(game, player_index):
        raise ValueError("Chankan is not allowed.")

    winners = [
        index
        for index in range(4)
        if can_chankan(game, index)
    ]

    resolve_kakan_responses(game, winners)


def pass_chankan(game, player_index):
    """Pass a human robbery opportunity."""
    if player_index != game["human_player_index"]:
        raise ValueError("This operation is for the human player.")

    if not can_chankan(game, player_index):
        raise ValueError("There is no Chankan option to pass.")

    if game["riichi_declared"][player_index]:
        game["riichi_furiten"][player_index] = True
    else:
        game["temporary_furiten"][player_index] = True

    winners = [
        index
        for index in range(4)
        if index != player_index and can_chankan(game, index)
    ]

    resolve_kakan_responses(game, winners)


def get_winner_score(game, player_index):
    """Read the best supported score without changing the game."""
    if game["phase"] != "ended":
        return None

    if player_index not in game["winner_indices"]:
        return None

    reason = game["end_reason"]
    if reason == "nagashi_mangan":
        return get_nagashi_score(is_dealer=player_index == game["dealer_index"])
    hand = list(game["hands"][player_index])
    melds = game["melds"][player_index]

    if reason == "ron":
        winning_tile = game["last_discard"]["tile"]
        hand.append(winning_tile)
    elif reason == "chankan":
        winning_tile = game["robbed_kan_tile"]
        hand.append(winning_tile)
    elif reason == "tsumo":
        winning_tile = hand[-1]
    else:
        return None

    ura_indicators = get_winner_ura_dora_indicators(
        game,
        player_index,
    )

    return evaluate_hand_score(
        hand,
        winning_tile,
        melds,
        is_closed=game["is_closed"][player_index],
        is_tsumo=reason == "tsumo",
        is_dealer=player_index == game["dealer_index"],
        seat_wind=game["seat_winds"][player_index],
        round_wind=game["round_wind"],
        riichi=game["riichi_declared"][player_index],
        rinshan=(
            reason == "tsumo"
            and game["rinshan_player_index"] == player_index
        ),
        chankan=reason == "chankan",
        **get_event_yaku_flags(game, player_index, is_tsumo=reason == "tsumo",
                              chankan=reason == "chankan"),
        dora_count=count_dora(
            hand,
            melds,
            get_dora_indicators(game),
        ),
        ura_dora_count=count_dora(
            hand,
            melds,
            ura_indicators,
        ),
    )


def settle_win(game):
    """Apply winning payments exactly once."""
    if game["phase"] != "ended":
        raise ValueError("The round has not ended.")

    reason = game["end_reason"]

    if reason not in ("tsumo", "ron", "chankan", "nagashi_mangan"):
        raise ValueError("This function only settles wins.")

    if game["settlement"] is not None:
        return deepcopy(game["settlement"])

    # Reject duplicate winners before calculating payments.
    winners = list(game["winner_indices"])

    if (
        not winners
        or len(winners) != len(set(winners))
        or any(type(index) is not int or index not in range(4)
               for index in winners)
    ):
        raise ValueError("Invalid winners.")

    if reason == "tsumo" and len(winners) != 1:
        raise ValueError("Tsumo must have exactly one winner.")

    # Ron and Chankan charge the source player; Tsumo charges the other three.
    discarder = None

    if reason in ("ron", "chankan"):
        discarder = game["winning_discarder_index"]

        if (
            type(discarder) is not int
            or discarder not in range(4)
            or discarder in winners
        ):
            raise ValueError("Invalid paying player.")

    honba = game["honba"]

    if type(honba) is not int or honba < 0:
        raise ValueError("Invalid Honba count.")

    sticks = game["riichi_sticks"]

    if type(sticks) is not int or sticks < 0:
        raise ValueError("Invalid Riichi stick count.")

    # Calculate every winner before changing any balances.
    winner_scores = {}

    for winner in winners:
        score = get_winner_score(game, winner)

        if score is None:
            raise ValueError("A winner has no supported score.")

        winner_scores[winner] = score

    # Accumulate net changes first, then update balances after all winners are scored.
    deltas = [0, 0, 0, 0]
    honba_awards = [0, 0, 0, 0]

    for winner in winners:
        payments = winner_scores[winner]["payments"]

        if reason in ("ron", "chankan"):
            # For Ron, the discarder pays the full Honba bonus to each winner.
            honba_bonus = honba * 300
            amount = payments["ron_payment"] + honba_bonus

            deltas[discarder] -= amount
            deltas[winner] += amount
            honba_awards[winner] += honba_bonus

        else:
            for payer in range(4):
                if payer == winner:
                    continue

                if winner == game["dealer_index"]:
                    base_payment = payments["non_dealer_payment"]
                elif payer == game["dealer_index"]:
                    base_payment = payments["dealer_payment"]
                else:
                    base_payment = payments["non_dealer_payment"]

                # For Tsumo, each other player pays 100 points per Honba.
                honba_bonus = honba * 100
                amount = base_payment + honba_bonus

                deltas[payer] -= amount
                deltas[winner] += amount
                honba_awards[winner] += honba_bonus

    # Award the existing deposit pool once.
    if reason == "tsumo":
        stick_recipient = winners[0]
    elif reason == "nagashi_mangan":
        stick_recipient = min(winners, key=lambda winner: (winner - game["dealer_index"]) % 4)
    else:
        stick_recipient = min(
            winners,
            key=lambda winner: (winner - discarder) % 4,
        )

    riichi_award = sticks * 1000
    deltas[stick_recipient] += riichi_award

    before = list(game["scores"])
    after = [
        score + delta
        for score, delta in zip(before, deltas)
    ]

    settlement = {
        "score_deltas": deltas,
        "scores_before": before,
        "scores_after": after,
        "riichi_award": riichi_award,
        "riichi_recipient": (
            stick_recipient if riichi_award else None
        ),
        "honba": honba,
        "honba_awards": honba_awards,
    }

    # Commit only after the complete calculation succeeds.
    game["scores"] = after
    game["riichi_sticks"] = 0
    game["settlement"] = settlement
    finish_if_bankrupt(game)

    return deepcopy(game["settlement"])


def settle_exhaustive_draw(game):
    """Apply Tenpai/Noten payments exactly once."""
    if (game["phase"] == "ended" and game["end_reason"] == "nagashi_mangan"
            and game["settlement"] is not None):
        return deepcopy(game["settlement"])

    if (
        game["phase"] != "ended"
        or game["end_reason"] != "exhaustive_draw"
    ):
        raise ValueError("The round has not ended in an exhaustive draw.")

    if game["settlement"] is not None:
        return deepcopy(game["settlement"])

    if game["wall"]:
        raise ValueError("The live wall is not empty.")

    if game["winner_indices"]:
        raise ValueError("An exhaustive draw cannot have winners.")

    nagashi_winners = get_nagashi_winners(game)
    if nagashi_winners:
        # Validate every payment on a copy before committing any state.
        candidate = deepcopy(game)
        candidate["end_reason"] = "nagashi_mangan"
        candidate["winner_indices"] = nagashi_winners
        candidate["winner_index"] = nagashi_winners[0]
        candidate["winning_discarder_index"] = None
        settlement = settle_win(candidate)
        for key in ("end_reason", "winner_indices", "winner_index",
                    "winning_discarder_index", "scores", "riichi_sticks", "settlement",
                    "match_ended", "match_end_reason", "final_riichi_award", "final_riichi_recipient"):
            game[key] = candidate[key]
        return settlement

    # Structural Tenpai does not require a yaku or a legal Ron.
    tenpai_flags = [
        bool(get_waiting_tiles(
            game["hands"][index],
            game["melds"][index],
        ))
        for index in range(4)
    ]

    # Split the 3000-point draw payment between Tenpai and Noten players.
    tenpai_count = sum(tenpai_flags)
    deltas = [0, 0, 0, 0]

    if 0 < tenpai_count < 4:
        gain = 3000 // tenpai_count
        loss = 3000 // (4 - tenpai_count)

        deltas = [
            gain if tenpai else -loss
            for tenpai in tenpai_flags
        ]

    before = list(game["scores"])
    after = [
        score + delta
        for score, delta in zip(before, deltas)
    ]

    settlement = {
        "score_deltas": deltas,
        "scores_before": before,
        "scores_after": after,
        "tenpai_flags": tenpai_flags,
        "riichi_award": 0,
        "riichi_recipient": None,
    }

    game["scores"] = after
    game["settlement"] = settlement
    finish_if_bankrupt(game)

    # Deposits carry forward unless bankruptcy has ended the match.
    return deepcopy(game["settlement"])


def create_next_hand(game):
    """Create the next hand without modifying the previous hand."""
    if game["phase"] != "ended":
        raise ValueError("The current hand has not ended.")

    if game["match_ended"]:
        raise ValueError("The match has already ended.")

    if game["settlement"] is None:
        raise ValueError("The current hand has not been settled.")

    if any(score < 0 for score in game["scores"]):
        finished_game = deepcopy(game)
        finish_match(finished_game, "bankruptcy")
        return finished_game

    dealer = game["dealer_index"]
    reason = game["end_reason"]

    # A dealer win repeats the hand; a non-dealer win resets Honba.
    if reason in ("tsumo", "ron", "chankan", "nagashi_mangan"):
        dealer_continues = dealer in game["winner_indices"]

        next_honba = (
            game["honba"] + 1
            if dealer_continues
            else 0
        )

    # Abortive draws repeat the dealer and add one Honba.
    elif reason == "abortive_draw":
        dealer_continues = True
        next_honba = game["honba"] + 1

    # An exhaustive draw always adds Honba; only a Tenpai dealer stays.
    elif reason == "exhaustive_draw":
        dealer_continues = game["settlement"]["tenpai_flags"][dealer]
        next_honba = game["honba"] + 1

    else:
        raise ValueError("Unsupported hand ending.")

    next_dealer = dealer
    next_number = game["hand_number"]
    next_wind = game["round_wind"]

    # Rotate the dealer and advance East/South hand numbers only when needed.
    if not dealer_continues:
        next_dealer = (dealer + 1) % 4
        next_number += 1

        if next_number > 4:
            if next_wind == "1z":
                next_wind = "2z"
                next_number = 1
            elif next_wind == "2z":
                # Keep the final hand and its result available.
                finished_game = deepcopy(game)
                finish_match(finished_game, "south_round_complete")
                return finished_game
            else:
                raise ValueError("Unsupported round wind.")

    # Rebuild all hand-specific state through the existing initializer.
    next_game = create_game()

    # Carry match-level balances and settings into the fresh hand.
    next_game["scores"] = list(game["scores"])
    next_game["riichi_sticks"] = game["riichi_sticks"]
    next_game["human_player_index"] = game["human_player_index"]
    next_game["riichi_min_wall_tiles"] = game["riichi_min_wall_tiles"]

    # Apply the next hand position after resetting per-hand flags.
    next_game["dealer_index"] = next_dealer
    next_game["current_player_index"] = next_dealer
    next_game["round_wind"] = next_wind
    next_game["hand_number"] = next_number
    next_game["honba"] = next_honba

    winds = ["1z", "2z", "3z", "4z"]

    # Recalculate each seat wind relative to the new dealer.
    next_game["seat_winds"] = [
        winds[(player_index - next_dealer) % 4]
        for player_index in range(4)
    ]

    return next_game


def get_winner_yaku(game, player_index):
    """Read yaku from the selected scoring interpretation."""
    score = get_winner_score(game, player_index)

    if score is None:
        return []

    return list(score["yaku"])


if __name__ == "__main__":
    game = create_game()
    advance_until_human(game)

    # Player indices stay fixed even when the dealer changes.
    human_index = game["human_player_index"]

    print(f"Phase: {game['phase']}")
    print(f"Current player: {game['current_player_index'] + 1}")
    print(f"Your hand: {game['hands'][human_index]}")
    print(f"Hand count: {len(game['hands'][human_index])}")
    print(f"Wall remaining: {len(game['wall'])}")

    # Debug: simulate the human discarding the first tile.
    discarded_tile = finish_turn(game, human_index, 0)

    # Advance through computer turns to the next human turn.
    advance_until_human(game)

    print(f"\nYou discarded: {discarded_tile}")
    print(f"Phase: {game['phase']}")
    print(f"Current player: {game['current_player_index'] + 1}")
    print(f"Hand count: {len(game['hands'][human_index])}")
    print(f"Discard counts: {[len(pile) for pile in game['discards']]}")
    print(f"Wall remaining: {len(game['wall'])}")
