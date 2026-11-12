"""Strict post-Riichi Ankan: drawn fourth tile, unchanged waits and grouping."""
from tile_utils import normalized_inputs
from hand_evaluator import get_waiting_tiles, get_standard_hand_decompositions


def _group_signature(decomposition, groups):
    """Make a stable shape key so group order does not affect comparisons."""
    return (
        tuple(sorted(decomposition["pair"])),
        tuple(sorted((group["type"], tuple(sorted(group["tiles"]))) for group in groups)),
    )


@normalized_inputs('hand', 'melds', 'tile')
def is_riichi_ankan_legal(hand, melds, tile):
    """Read-only structural check. Phase, resources and draw context are checked by main.

    Under the strict rule used here, the three pre-draw tiles must be a
    triplet in EVERY winning interpretation for EVERY wait. Replacing it
    with a fixed concealed Kan must preserve all remaining interpretations.
    """
    if (not hand or hand[-1] != tile or hand.count(tile) != 4
            or len(melds) >= 4 or len(hand) != 14 - 3 * len(melds)
            or any(meld["type"] != "ankan" for meld in melds)):
        return False
    # The Riichi-locked hand excludes the fourth tile just drawn.
    locked_hand = list(hand[:-1])
    if locked_hand.count(tile) != 3:
        return False
    # A legal Kan must preserve the full set of waits.
    waits_before = set(get_waiting_tiles(locked_hand, melds))
    if not waits_before:
        return False
    remaining = [value for value in hand if value != tile]
    new_melds = list(melds) + [{"type": "ankan", "tiles": [tile] * 4}]
    if set(get_waiting_tiles(remaining, new_melds)) != waits_before:
        return False
    # Compare every winning interpretation, not just the wait names.
    for wait in waits_before:
        before = get_standard_hand_decompositions(locked_hand + [wait], melds)
        after = get_standard_hand_decompositions(remaining + [wait], new_melds)
        if not before or not after:
            return False
        # Remove the original triplet before comparing the remaining groups.
        old_shapes = set()
        for decomposition in before:
            groups = list(decomposition["concealed_groups"])
            index = next((index for index, group in enumerate(groups)
                          if group["type"] == "triplet" and group["tiles"] == [tile] * 3), None)
            if index is None:
                return False
            groups.pop(index)
            old_shapes.add(_group_signature(decomposition, groups))
        # The fixed Ankan must leave exactly the same remaining shapes.
        new_shapes = {
            _group_signature(decomposition, decomposition["concealed_groups"])
            for decomposition in after
        }
        if old_shapes != new_shapes:
            return False
    return True
