from tile_utils import normalized_inputs
from collections import Counter
from functools import lru_cache

from hand_evaluator import (
    TILE_TYPES,
    VALID_TILES,
    ORPHAN_TILES,
    _get_meld_tiles,
)


# Use a fixed 34-slot count array for the hand search.
TILE_INDEX = {
    tile: index
    for index, tile in enumerate(TILE_TYPES)
}


def _standard_shanten(counts, fixed_groups):
    return _search_shanten(tuple(counts), 0, 0, 0, fixed_groups)


# Reuse structural subproblems across draws/calls; bounded for small hosts.
@lru_cache(maxsize=32768)
def _search_shanten(state, groups, partial_groups, has_pair, fixed_groups):
    # Start with the first remaining tile to avoid exploring group order permutations.
    first = next(
        (index for index, count in enumerate(state) if count),
        None,
    )

    # At the end of a branch, count only partial groups that still fit the hand.
    if first is None:
        usable_partials = min(
            partial_groups,
            4 - fixed_groups - groups,
        )

        return (
            8
            - 2 * (fixed_groups + groups)
            - usable_partials
            - has_pair
        )

    remaining = list(state)

    # Remove a candidate group, recurse, then restore counts for the next choice.
    def branch(indices, new_groups, new_partials, new_pair):
        for index in indices:
            remaining[index] -= 1

        result = _search_shanten(
            tuple(remaining),
            new_groups,
            new_partials,
            new_pair,
            fixed_groups,
        )

        for index in indices:
            remaining[index] += 1

        return result

    # Leave this tile unused in the chosen interpretation.
    best = branch(
        [first],
        groups,
        partial_groups,
        has_pair,
    )

    can_add_group = fixed_groups + groups < 4

    # Try using three copies as a complete triplet.
    if can_add_group and state[first] >= 3:
        best = min(
            best,
            branch(
                [first] * 3,
                groups + 1,
                partial_groups,
                has_pair,
            ),
        )

    # Try a complete sequence without crossing a suit boundary.
    if (
        can_add_group
        and first < 27
        and first % 9 <= 6
        and state[first + 1]
        and state[first + 2]
    ):
        best = min(
            best,
            branch(
                [first, first + 1, first + 2],
                groups + 1,
                partial_groups,
                has_pair,
            ),
        )

    # A pair can be the head or an incomplete group; explore both uses.
    if state[first] >= 2:
        if not has_pair:
            best = min(
                best,
                branch(
                    [first, first],
                    groups,
                    partial_groups,
                    1,
                ),
            )

        if partial_groups < 4 - fixed_groups:
            best = min(
                best,
                branch(
                    [first, first],
                    groups,
                    partial_groups + 1,
                    has_pair,
                ),
            )

    if first < 27 and partial_groups < 4 - fixed_groups:
        # Adjacent tiles, such as 45m.
        if first % 9 <= 7 and state[first + 1]:
            best = min(
                best,
                branch(
                    [first, first + 1],
                    groups,
                    partial_groups + 1,
                    has_pair,
                ),
            )

        # Gapped tiles, such as 46m.
        if first % 9 <= 6 and state[first + 2]:
            best = min(
                best,
                branch(
                    [first, first + 2],
                    groups,
                    partial_groups + 1,
                    has_pair,
                ),
            )

    return best

@normalized_inputs('hand', 'melds')
def calculate_shanten(hand, melds=None):
    """Return the lowest supported structural Shanten."""
    melds = [] if melds is None else melds
    meld_tiles = _get_meld_tiles(melds)

    if meld_tiles is None:
        raise ValueError("Invalid declared groups.")

    if not isinstance(hand, (list, tuple)):
        raise ValueError("Hand must be a list or tuple.")

    # Declared groups reduce the concealed hand size by three each.
    expected_count = 13 - 3 * len(melds)

    if len(hand) not in (expected_count, expected_count + 1):
        raise ValueError("Invalid concealed hand length.")

    if any(
        not isinstance(tile, str) or tile not in VALID_TILES
        for tile in hand
    ):
        raise ValueError("Invalid tile.")

    # Reject impossible copy counts before searching the hand.
    combined_counts = Counter(list(hand) + meld_tiles)

    if any(count > 4 for count in combined_counts.values()):
        raise ValueError("A tile cannot have more than four copies.")

    # Convert tile codes to counts for the recursive search.
    counts = [0] * 34

    for tile in hand:
        counts[TILE_INDEX[tile]] += 1

    best = _standard_shanten(counts, len(melds))

    # Special hands require no declared groups, including Ankan.
    if not melds:
        distinct_count = sum(count > 0 for count in counts)
        pair_count = sum(count >= 2 for count in counts)

        # Seven Pairs needs seven distinct tile types, not just seven pairs of copies.
        seven_pairs = (
            6 - pair_count + max(0, 7 - distinct_count)
        )

        # Thirteen Orphans needs each terminal/honor type and one duplicate.
        orphan_counts = [
            counts[TILE_INDEX[tile]]
            for tile in ORPHAN_TILES
        ]

        thirteen_orphans = (
            13
            - sum(count > 0 for count in orphan_counts)
            - int(any(count >= 2 for count in orphan_counts))
        )

        best = min(best, seven_pairs, thirteen_orphans)

    return best


@normalized_inputs('hand', 'melds', 'visible_tiles')
def analyze_discards(
    hand,
    melds=None,
    *,
    visible_tiles=None,
    allowed_indices=None,
):
    """Analyze legal discards using only known tile information."""
    melds = [] if melds is None else melds
    visible_tiles = [] if visible_tiles is None else visible_tiles

    # Validate the hand before evaluating its possible discards.
    calculate_shanten(hand, melds)

    if len(hand) != 14 - 3 * len(melds):
        raise ValueError("Discard analysis requires a post-draw hand.")

    if not isinstance(visible_tiles, (list, tuple)):
        raise ValueError("Visible tiles must be a list or tuple.")

    if any(
        not isinstance(tile, str) or tile not in VALID_TILES
        for tile in visible_tiles
    ):
        raise ValueError("Invalid visible tile.")

    own_meld_tiles = _get_meld_tiles(melds)

    # Hidden opponents' hands and the wall must not influence the AI choice.
    # Visible tiles must exclude this player's hand and own melds.
    known_counts = Counter(
        list(hand) + own_meld_tiles + list(visible_tiles)
    )

    if any(count > 4 for count in known_counts.values()):
        raise ValueError("Known tiles contain more than four copies.")

    # Honor turn restrictions such as Riichi and forbidden post-call discards.
    if allowed_indices is None:
        indices = list(range(len(hand)))
    else:
        indices = list(allowed_indices)

        if any(
            type(index) is not int
            or not 0 <= index < len(hand)
            for index in indices
        ):
            raise ValueError("Invalid allowed discard index.")

        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate allowed discard indices.")

    # Cache repeated hands within this analysis.
    @lru_cache(maxsize=None)
    def cached_shanten(tiles):
        return calculate_shanten(list(tiles), melds)

    results = []
    analyzed_tiles = {}

    for tile_index in indices:
        discarded_tile = hand[tile_index]

        # Discarding identical copies produces the same tile counts.
        if discarded_tile not in analyzed_tiles:
            remaining_hand = list(hand)
            remaining_hand.pop(tile_index)

            base_shanten = cached_shanten(
                tuple(sorted(remaining_hand))
            )

            improving_tiles = []

            # Try each possible next draw and count only unseen copies that improve Shanten.
            for tile in TILE_TYPES:
                unseen_count = 4 - known_counts[tile]

                if unseen_count <= 0:
                    continue

                next_shanten = cached_shanten(
                    tuple(sorted(remaining_hand + [tile]))
                )

                if next_shanten < base_shanten:
                    improving_tiles.append({
                        "tile": tile,
                        "remaining": unseen_count,
                        "shanten": next_shanten,
                    })

            # Ukeire is the total number of remaining improving tiles.
            analyzed_tiles[discarded_tile] = {
                "shanten": base_shanten,
                "improving_tiles": improving_tiles,
                "ukeire": sum(
                    item["remaining"]
                    for item in improving_tiles
                ),
            }

        analysis = analyzed_tiles[discarded_tile]

        # Keep an entry for every legal hand index, even for identical tiles.
        results.append({
            "tile_index": tile_index,
            "tile": discarded_tile,
            "shanten": analysis["shanten"],
            "improving_tiles": [
                dict(item)
                for item in analysis["improving_tiles"]
            ],
            "ukeire": analysis["ukeire"],
        })

    return results


@normalized_inputs('hand', 'melds', 'visible_tiles')
def choose_discard(
    hand,
    melds=None,
    *,
    visible_tiles=None,
    allowed_indices=None,
):
    """Choose the lowest-Shanten, highest-Ukeire legal discard."""
    options = analyze_discards(
        hand,
        melds,
        visible_tiles=visible_tiles,
        allowed_indices=allowed_indices,
    )

    if not options:
        raise ValueError("No legal discard is available.")

    # Prefer lower Shanten, then more improving tiles; use the remaining keys to break ties.
    best = min(
        options,
        key=lambda option: (
            option["shanten"],
            -option["ukeire"],
            option["tile_index"],
        ),
    )

    return best["tile_index"]
