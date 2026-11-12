from tile_utils import normalized_inputs
from collections import Counter
from copy import deepcopy

# All 34 tile types, ordered by suit and rank.
TILE_TYPES = tuple(
    f"{number}{suit}"
    for suit in ("m", "p", "s")
    for number in range(1, 10)
) + tuple(f"{number}z" for number in range(1, 8))

VALID_TILES = frozenset(TILE_TYPES)

# The 13 terminal/honor types used by Thirteen Orphans.
ORPHAN_TILES = frozenset({
    "1m", "9m",
    "1p", "9p",
    "1s", "9s",
    "1z", "2z", "3z", "4z", "5z", "6z", "7z"
})


@normalized_inputs('hand')
def _get_valid_counts(hand):
    """Return tile counts, or None for an invalid closed hand."""
    if not isinstance(hand, (list, tuple)) or len(hand) != 14:
        return None

    if any(
        not isinstance(tile, str) or tile not in VALID_TILES
        for tile in hand
    ):
        return None

    # Count copies only after tile codes and hand size have been checked.
    counts = Counter(hand)

    if any(count > 4 for count in counts.values()):
        return None

    return counts


def _can_form_melds(counts):
    """Check whether all remaining tiles can form melds."""
    # Always branch from the first remaining tile to avoid redundant group orders.
    first_index = next(
        (index for index, count in enumerate(counts) if count > 0),
        None
    )

    # No tiles remain: every tile was successfully grouped.
    if first_index is None:
        return True

    # Try a triplet.
    if counts[first_index] >= 3:
        counts[first_index] -= 3
        success = _can_form_melds(counts)
        counts[first_index] += 3

        if success:
            return True

    # Try a sequence within one numbered suit.
    if first_index < 27 and first_index % 9 <= 6:
        second_index = first_index + 1
        third_index = first_index + 2

        if counts[second_index] > 0 and counts[third_index] > 0:
            counts[first_index] -= 1
            counts[second_index] -= 1
            counts[third_index] -= 1

            success = _can_form_melds(counts)

            # Restore counts after recursion so other group choices see the original hand.
            counts[first_index] += 1
            counts[second_index] += 1
            counts[third_index] += 1

            if success:
                return True

    return False


@normalized_inputs('hand')
def is_standard_hand(hand):
    """Check for four melds and one pair."""
    tile_counts = _get_valid_counts(hand)

    if tile_counts is None:
        return False

    counts = [tile_counts[tile] for tile in TILE_TYPES]

    # Try every possible pair.
    for index in range(len(counts)):
        if counts[index] >= 2:
            counts[index] -= 2
            success = _can_form_melds(counts)
            counts[index] += 2

            if success:
                return True

    return False


@normalized_inputs('hand')
def is_seven_pairs(hand):
    """Check for seven distinct pairs."""
    counts = _get_valid_counts(hand)

    if counts is None:
        return False

    return (
        len(counts) == 7
        and all(count == 2 for count in counts.values())
    )


@normalized_inputs('hand')
def is_thirteen_orphans(hand):
    """Check for all 13 terminal/honor types and one duplicate."""
    counts = _get_valid_counts(hand)

    if counts is None:
        return False

    return (
        set(counts) == ORPHAN_TILES
        and sorted(counts.values()) == [1] * 12 + [2]
    )


@normalized_inputs('melds')
def _get_meld_tiles(melds):
    """Validate declared sequences, triplets and Kans."""
    if not isinstance(melds, (list, tuple)) or len(melds) > 4:
        return None

    tiles = []

    for meld in melds:
        if not isinstance(meld, dict):
            return None

        # Check each declared group before including its tiles in copy counts.
        meld_type = meld.get("type")
        # Keep the physical group size: a Kan contains four tiles.
        meld_tiles = meld.get("tiles")

        if meld_type not in (
            "pon", "chi", "ankan", "daiminkan", "kakan"
        ):
            return None

        if not isinstance(meld_tiles, (list, tuple)):
            return None

        expected_count = (
            4 if meld_type in ("ankan", "daiminkan", "kakan")
            else 3
        )

        if len(meld_tiles) != expected_count:
            return None

        if any(
            not isinstance(tile, str) or tile not in VALID_TILES
            for tile in meld_tiles
        ):
            return None

        if meld_type in ("pon", "ankan", "daiminkan", "kakan"):
            if len(set(meld_tiles)) != 1:
                return None

        else:
            suits = {tile[1] for tile in meld_tiles}

            if len(suits) != 1 or "z" in suits:
                return None

            numbers = sorted(int(tile[0]) for tile in meld_tiles)
            first = numbers[0]

            if numbers != [first, first + 1, first + 2]:
                return None

        tiles.extend(meld_tiles)

    return tiles


@normalized_inputs('hand', 'melds')
def is_complete_hand_with_melds(hand, melds):
    """Check a winning hand with fixed exposed melds."""
    exposed_tiles = _get_meld_tiles(melds)

    if exposed_tiles is None:
        return False

    if not isinstance(hand, (list, tuple)):
        return False

    expected_count = 14 - 3 * len(melds)

    if len(hand) != expected_count:
        return False

    if any(
        not isinstance(tile, str) or tile not in VALID_TILES
        for tile in hand
    ):
        return False

    all_counts = Counter(list(hand) + exposed_tiles)

    if any(count > 4 for count in all_counts.values()):
        return False

    # Special hands require no declared groups, including concealed Kans.
    if not melds:
        return (
            is_standard_hand(hand)
            or is_seven_pairs(hand)
            or is_thirteen_orphans(hand)
        )

    hand_counts = Counter(hand)
    counts = [hand_counts[tile] for tile in TILE_TYPES]

    # Exposed melds stay fixed. Group only the concealed tiles.
    for index in range(len(counts)):
        if counts[index] < 2:
            continue

        counts[index] -= 2
        success = _can_form_melds(counts)
        counts[index] += 2

        if success:
            return True

    return False


@normalized_inputs('hand', 'melds')
def is_complete_hand(hand, melds=None):
    """Check a winning hand, optionally including exposed melds."""
    if melds is None:
        melds = []

    return is_complete_hand_with_melds(hand, melds)


@normalized_inputs('hand', 'melds')
def get_waiting_tiles(hand, melds=None):
    """Return waits for concealed tiles plus fixed exposed melds."""
    if melds is None:
        melds = []

    exposed_tiles = _get_meld_tiles(melds)

    if exposed_tiles is None:
        return []

    expected_count = 13 - 3 * len(melds)

    if not isinstance(hand, (list, tuple)):
        return []

    if len(hand) != expected_count:
        return []

    if any(
        not isinstance(tile, str) or tile not in VALID_TILES
        for tile in hand
    ):
        return []

    counts = Counter(list(hand) + exposed_tiles)

    if any(count > 4 for count in counts.values()):
        return []

    # Try every tile type and keep additions that complete the hand.
    waiting_tiles = []

    for tile in TILE_TYPES:
        if counts[tile] >= 4:
            continue

        candidate_hand = list(hand) + [tile]

        if is_complete_hand(candidate_hand, melds):
            waiting_tiles.append(tile)

    return waiting_tiles


@normalized_inputs('hand', 'melds')
def get_tenpai_discards(hand, melds=None):
    """Return discards that leave the remaining hand in tenpai."""
    if melds is None:
        melds = []

    if _get_meld_tiles(melds) is None:
        raise ValueError("Invalid declared groups.")

    expected_count = 14 - 3 * len(melds)

    if not isinstance(hand, (list, tuple)) or len(hand) != expected_count:
        raise ValueError(
            f"Hand must contain exactly {expected_count} tiles."
        )

    # Collect separate results so alternative groupings are not lost.
    results = []

    for tile_index, tile in enumerate(hand):
        remaining_hand = list(hand)
        remaining_hand.pop(tile_index)

        waiting_tiles = get_waiting_tiles(remaining_hand, melds)

        if waiting_tiles:
            results.append({
                "tile_index": tile_index,
                "tile": tile,
                "waiting_tiles": waiting_tiles
            })

    return results


@normalized_inputs('hand', 'melds')
def get_standard_hand_decompositions(hand, melds=None):
    """Return every standard decomposition into groups and a pair."""
    declared_groups = [] if melds is None else list(melds)

    # Reuse the existing validation and completion checks.
    if not is_complete_hand(hand, declared_groups):
        return []

    required_groups = 4 - len(declared_groups)
    counts = Counter(hand)

    tile_types = [
        f"{number}{suit}"
        for suit in ("m", "p", "s")
        for number in range(1, 10)
    ] + [
        f"{number}z"
        for number in range(1, 8)
    ]

    results = []

    def search_groups(groups, pair):
        first_tile = next(
            (tile for tile in tile_types if counts[tile] > 0),
            None
        )

        # All concealed tiles have been assigned.
        if first_tile is None:
            if len(groups) == required_groups:
                results.append({
                    "pair": list(pair),
                    "concealed_groups": deepcopy(groups),
                    "declared_groups": deepcopy(declared_groups)
                })

            return

        if len(groups) >= required_groups:
            return

        # Try a triplet.
        if counts[first_tile] >= 3:
            counts[first_tile] -= 3
            groups.append({
                "type": "triplet",
                "tiles": [first_tile] * 3
            })

            search_groups(groups, pair)

            groups.pop()
            counts[first_tile] += 3

        # Honors cannot form sequences.
        number = int(first_tile[0])
        suit = first_tile[1]

        if suit == "z" or number > 7:
            return

        sequence = [
            first_tile,
            f"{number + 1}{suit}",
            f"{number + 2}{suit}"
        ]

        # Try a sequence.
        if all(counts[tile] > 0 for tile in sequence):
            for tile in sequence:
                counts[tile] -= 1

            groups.append({
                "type": "sequence",
                "tiles": sequence
            })

            search_groups(groups, pair)

            groups.pop()

            for tile in sequence:
                counts[tile] += 1

    # Try each possible pair.
    for tile in tile_types:
        if counts[tile] < 2:
            continue

        counts[tile] -= 2
        search_groups([], [tile, tile])
        counts[tile] += 2

    return results


@normalized_inputs('hand', 'winning_tile', 'melds')
def get_winning_tile_placements(hand, winning_tile, melds=None):
    """Locate the winning tile in each standard decomposition."""
    if not isinstance(winning_tile, str):
        return []

    if winning_tile not in hand:
        return []

    decompositions = get_standard_hand_decompositions(hand, melds)
    placements = []

    for decomposition in decompositions:
        # The winning tile may complete the pair.
        if winning_tile in decomposition["pair"]:
            placements.append({
                "decomposition": deepcopy(decomposition),
                "winning_group": {
                    "type": "pair",
                    "index": None,
                    "tiles": list(decomposition["pair"]),
                },
            })

        # It may instead complete a concealed sequence or triplet.
        for index, group in enumerate(
            decomposition["concealed_groups"]
        ):
            if winning_tile not in group["tiles"]:
                continue

            placements.append({
                "decomposition": deepcopy(decomposition),
                "winning_group": {
                    "type": group["type"],
                    "index": index,
                    "tiles": list(group["tiles"]),
                },
            })

    return placements


@normalized_inputs('placement', 'winning_tile')
def get_wait_type(placement, winning_tile):
    """Classify the wait for one standard winning-tile placement."""
    group = placement["winning_group"]
    group_type = group["type"]
    tiles = group["tiles"]

    if winning_tile not in tiles:
        raise ValueError("Winning tile is not in the selected group.")

    if group_type == "pair":
        return "tanki"

    if group_type == "triplet":
        return "shanpon"

    if group_type != "sequence":
        raise ValueError("Unsupported winning group type.")

    numbers = sorted(int(tile[0]) for tile in tiles)
    winning_number = int(winning_tile[0])

    # The winning tile fills the middle of the sequence.
    if winning_number == numbers[1]:
        return "kanchan"

    # 12 waiting on 3, or 89 waiting on 7.
    if (
        numbers == [1, 2, 3] and winning_number == 3
    ) or (
        numbers == [7, 8, 9] and winning_number == 7
    ):
        return "penchan"

    return "ryanmen"


@normalized_inputs('hand', 'winning_tile', 'melds')
def get_winning_waits(hand, winning_tile, melds=None):
    """Return standard placements together with their wait types."""
    placements = get_winning_tile_placements(
        hand,
        winning_tile,
        melds,
    )

    for placement in placements:
        placement["wait_type"] = get_wait_type(
            placement,
            winning_tile,
        )

    return placements
