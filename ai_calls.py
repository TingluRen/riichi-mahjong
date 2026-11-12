"""Call choices that improve the hand while keeping a concrete yaku plan."""
from ai import analyze_discards, calculate_shanten
from tile_utils import normalize_tiles
from collections import Counter
from functools import lru_cache
from hand_evaluator import TILE_TYPES


def open_yaku_routes(hand, melds, seat_wind, round_wind):
    """Recognize guaranteed open-hand routes, without counting Dora as a yaku."""
    hand = normalize_tiles(hand)
    melds = normalize_tiles(melds)
    tiles = hand + [tile for meld in melds for tile in meld["tiles"]]
    routes = set()
    values = {"5z", "6z", "7z", seat_wind, round_wind}
    # Keep value triplets, whether already declared or still concealed.
    # Later discard filtering protects a concealed triplet until another route exists.
    counts = Counter(hand)
    if (any(meld["type"] != "chi" and meld["tiles"][0] in values for meld in melds)
            or any(counts[tile] >= 3 for tile in values)):
        routes.add("yakuhai")
    if tiles and all(tile[1] != "z" and tile[0] in "2345678" for tile in tiles):
        routes.add("tanyao")
    suits = {tile[1] for tile in tiles if tile[1] != "z"}
    # Fixed numbered tiles keep a single-suit route from becoming ambiguous.
    if len(suits) == 1 and any(tile[1] != "z" for meld in melds for tile in meld["tiles"]):
        routes.add("flush")
    if tiles and all(tile[1] == "z" for tile in tiles):
        routes.add("honors")
    return routes


def yaku_plan_costs(hand, melds, seat_wind, round_wind, visible_tiles=()):
    """Count the few changes needed for a specific open-hand yaku; zero is secured."""
    hand = normalize_tiles(hand)
    melds = normalize_tiles(melds)
    fixed = [tile for meld in melds for tile in meld["tiles"]]
    costs = {name: 0 for name in open_yaku_routes(hand, melds, seat_wind, round_wind)}

    # A simple meld can be opened before the final one or two terminals/honors go.
    simple = lambda tile: tile[1] != "z" and tile[0] in "2345678"
    if fixed and all(simple(tile) for tile in fixed):
        unwanted = sum(not simple(tile) for tile in hand)
        if unwanted <= 2:
            costs["tanyao"] = unwanted

    # A value pair is a plan only while a third copy can still be acquired.
    counts = Counter(hand)
    known = Counter(hand + fixed + normalize_tiles(list(visible_tiles)))
    for value in {"5z", "6z", "7z", seat_wind, round_wind}:
        if counts[value] == 2 and known[value] < 4:
            costs["yakuhai:" + value] = 1

    # Fixed melds must already fit the target suit; allow at most two off-suit tiles.
    for suit in ("m", "p", "s"):
        if fixed and all(tile[1] in (suit, "z") for tile in fixed):
            unwanted = sum(tile[1] not in (suit, "z") for tile in hand)
            if unwanted <= 2 and any(tile[1] == suit for tile in hand + fixed):
                costs["flush:" + suit] = unwanted
    return costs


def safe_discard_indices(hand, melds, indices, seat_wind, round_wind, visible_tiles=()):
    """Secure a yaku when possible; otherwise move toward the closest concrete plan."""
    options = []
    for index in indices:
        # The discarded tile stays visible, so it cannot count as an available third copy.
        visible = list(visible_tiles) + [hand[index]]
        costs = yaku_plan_costs(hand[:index] + hand[index + 1:], melds,
                               seat_wind, round_wind, visible)
        if costs:
            options.append((index, min(costs.values())))
    if not options:
        return []
    closest = min(cost for _, cost in options)
    return [index for index, cost in options if cost == closest]


@lru_cache(maxsize=512)
def _cached_ukeire(hand, groups, visible):
    """Count improving draws for the no-call choice, without seeing the live wall."""
    melds = [{"type": kind, "tiles": list(tiles)} for kind, tiles in groups]
    baseline = calculate_shanten(list(hand), melds)
    known = Counter(hand + visible + tuple(tile for _, tiles in groups for tile in tiles))
    return sum(4 - known[tile] for tile in TILE_TYPES if known[tile] < 4
               and calculate_shanten(list(hand) + [tile], melds) < baseline)


def waiting_ukeire(hand, melds, visible_tiles):
    """Compare a call with passing on the same visible information."""
    hand = tuple(sorted(normalize_tiles(hand)))
    groups = tuple((meld["type"], tuple(sorted(normalize_tiles(meld["tiles"])))) for meld in melds)
    visible = tuple(sorted(normalize_tiles(list(visible_tiles))))
    return _cached_ukeire(hand, groups, visible)


def score_call(hand, melds, claim, visible_tiles, seat_wind, round_wind):
    """Accept faster calls with a concrete route to a real yaku, not just Dora."""
    remaining = list(hand)
    for tile in claim["hand_tiles"]:
        remaining.remove(tile)
    groups = list(melds) + [{"type": claim["type"], "tiles": claim["tiles"]}]
    baseline = calculate_shanten(hand, melds)
    # The claimed tile moves into our own meld; count it only once.
    visible = list(visible_tiles)
    visible.remove(claim["tile"])

    # A Kan draws later. Evaluate the pre-replacement shape, without peeking at the wall.
    if claim["type"] == "daiminkan":
        if not yaku_plan_costs(remaining, groups, seat_wind, round_wind, visible):
            return None
        shanten = calculate_shanten(remaining, groups)
        return (shanten, 0) if shanten <= baseline else None

    forbidden = claim["forbidden_discard_tiles"]
    indices = [i for i, tile in enumerate(normalize_tiles(remaining)) if tile not in forbidden]
    indices = safe_discard_indices(remaining, groups, indices, seat_wind, round_wind, visible)
    if not indices:
        return None

    options = analyze_discards(remaining, groups, visible_tiles=visible, allowed_indices=indices)
    best = min(options, key=lambda option: (option["shanten"], -option["ukeire"]))
    if best["shanten"] > baseline:
        return None
    # Equal-Shanten calls are worthwhile only when they add actual improving copies.
    if best["shanten"] == baseline and best["ukeire"] <= waiting_ukeire(hand, melds, visible_tiles):
        return None
    # Furiten and zero remaining copies do not invalidate a structural waiting shape.
    return best["shanten"], -best["ukeire"]
