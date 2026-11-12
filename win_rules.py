from tile_utils import normalized_inputs
from hand_evaluator import get_waiting_tiles


@normalized_inputs('hand', 'discard_pile', 'melds')
def is_discard_furiten(hand, discard_pile, melds=None):
    """Check whether any current wait appears in discard history."""
    waiting_tiles = set(get_waiting_tiles(hand, melds))

    return bool(waiting_tiles.intersection(discard_pile))