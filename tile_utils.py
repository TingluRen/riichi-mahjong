"""Physical red fives use 0m/0p/0s; shape analysis uses ordinary fives."""
from functools import wraps
from inspect import signature
RED_TILES = frozenset(("0m", "0p", "0s"))
def normalize_tile(tile):
    """Treat a red five as an ordinary five for rule checks."""
    return "5" + tile[1] if isinstance(tile, str) and tile in RED_TILES else tile

def normalize_tiles(value):
    """Copy nested tile data while converting red fives for analysis."""
    if isinstance(value, str):
        return normalize_tile(value)
    if isinstance(value, list):
        return [normalize_tiles(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_tiles(item) for item in value)
    if isinstance(value, dict):
        return {key: normalize_tiles(item) for key, item in value.items()}
    return value

def normalized_inputs(*names):
    """Use ordinary fives for analysis without changing the original tiles."""
    # Bind arguments by name so positional and keyword calls normalize the same inputs.
    def decorate(function):
        sig = signature(function)
        @wraps(function)
        def wrapped(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            for name in names:
                if name in bound.arguments:
                    bound.arguments[name] = normalize_tiles(bound.arguments[name])
            return function(*bound.args, **bound.kwargs)
        return wrapped
    return decorate

def count_aka_dora(hand, melds=None):
    """Count physical red fives in the hand and declared melds."""
    return sum(tile in RED_TILES for tile in list(hand) +
               [tile for meld in (melds or []) for tile in meld["tiles"]])

def take_matching(hand, tile, count):
    """Remove matching tiles, using ordinary fives before red fives."""
    # Choose physical copies without turning a red five into an ordinary tile.
    matches = sorted((t for t in hand if normalize_tile(t) == normalize_tile(tile)),
                     key=lambda t: t in RED_TILES)
    if len(matches) < count:
        raise ValueError("Required tiles are missing.")
    # Check enough copies exist before removing anything from the hand.
    chosen = matches[:count]
    for value in chosen:
        hand.remove(value)
    return chosen
