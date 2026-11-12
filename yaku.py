from tile_utils import normalized_inputs
from collections import Counter

from hand_evaluator import (
    is_complete_hand,
    is_seven_pairs,
    is_thirteen_orphans,
    get_standard_hand_decompositions,
    get_winning_tile_placements,
    get_wait_type,
)

WINDS = ("1z", "2z", "3z", "4z")


# Names in this set use Yakuman payments instead of ordinary Han scoring.
YAKUMAN_NAMES = frozenset({
    "Kokushi Musou", "Suuankou", "Daisangen", "Tsuuiisou", "Ryuuiisou",
    "Chinroutou", "Shousuushii", "Daisuushii", "Suukantsu", "Chuuren Poutou",
    "Tenhou", "Chiihou",
})


def get_yakuman_count(yaku):
    """Each distinct supported Yakuman counts once; compatible Yakuman stack."""
    return len(set(yaku) & YAKUMAN_NAMES)


def _tile_yakuman(hand, melds, *, closed):
    """Check Yakuman determined by the tiles alone."""
    # Tile-composition Yakuman include both concealed tiles and fixed melds.
    all_tiles = list(hand) + [tile for meld in melds for tile in meld["tiles"]]
    result = []
    # Check all honors, all green and all terminals independently; compatible Yakuman stack.
    if all(tile[1] == "z" for tile in all_tiles):
        result.append("Tsuuiisou")
    if all(tile in {"2s", "3s", "4s", "6s", "8s", "6z"} for tile in all_tiles):
        result.append("Ryuuiisou")
    if all(tile[1] != "z" and tile[0] in ("1", "9") for tile in all_tiles):
        result.append("Chinroutou")
    # Nine Gates requires a closed, single-suit hand with no declared groups.
    if closed and not melds and len(hand) == 14:
        suit = hand[0][1]
        if suit in ("m", "p", "s") and all(tile[1] == suit for tile in hand):
            counts = Counter(tile[0] for tile in hand)
            if counts["1"] >= 3 and counts["9"] >= 3 and all(counts[str(n)] >= 1 for n in range(2, 9)):
                result.append("Chuuren Poutou")
    return result


def _standard_yakuman(decomposition, winning_group, *, closed, is_tsumo):
    """Check Yakuman that depend on a particular grouping."""
    groups = decomposition["concealed_groups"] + decomposition["declared_groups"]
    # Treat declared Kans as triplet shapes for dragon and wind Yakuman.
    triplet_types = {"triplet", "pon", "ankan", "daiminkan", "kakan"}
    triplets = {g["tiles"][0] for g in groups if g["type"] in triplet_types}
    result = []
    if {"5z", "6z", "7z"} <= triplets:
        result.append("Daisangen")
    # Four wind triplets and three wind triplets plus a wind pair are different Yakuman.
    winds = {"1z", "2z", "3z", "4z"}
    if winds <= triplets:
        result.append("Daisuushii")
    elif len(winds & triplets) == 3 and decomposition["pair"][0] in winds - triplets:
        result.append("Shousuushii")
    if sum(g["type"] in ("ankan", "daiminkan", "kakan") for g in groups) == 4:
        result.append("Suukantsu")
    # Count concealed triplets and Kans, then account for the winning tile.
    concealed = sum(g["type"] == "triplet" for g in decomposition["concealed_groups"])
    concealed += sum(g["type"] == "ankan" for g in decomposition["declared_groups"])
    if winning_group is not None and not is_tsumo and winning_group["type"] == "triplet":
        concealed -= 1
    # Ron on the pair preserves four concealed triplets; Ron on a triplet does not.
    if closed and concealed == 4 and winning_group is not None:
        result.append("Suuankou")
    return result


def _get_base_yaku(
    hand,
    seat_wind="1z",
    round_wind="1z",
    melds=None
):
    """Identify supported yaku with optional declared melds."""
    if melds is None:
        melds = []

    if seat_wind not in WINDS or round_wind not in WINDS:
        raise ValueError("Invalid seat wind or round wind.")

    # A tile pattern is scored only after the whole hand is complete.
    if not is_complete_hand(hand, melds):
        return []

    # Special hands require no exposed melds.
    if not melds and is_thirteen_orphans(hand):
        return ["Kokushi Musou"]

    all_tiles = list(hand)

    for meld in melds:
        all_tiles.extend(meld["tiles"])

    # Include declared tiles when checking suit and honor composition.
    counts = Counter(all_tiles)
    yaku = []

    # Tanyao: only numbered tiles from 2 to 8.
    if all(
        tile[1] in ("m", "p", "s")
        and 2 <= int(tile[0]) <= 8
        for tile in all_tiles
    ):
        yaku.append("Tanyao")

    # Applies to both standard hands and Seven Pairs.
    if all(tile[1] == "z" or tile[0] in ("1", "9") for tile in all_tiles):
        yaku.append("Honroutou")

    # Dragon triplets.
    dragon_names = {
        "5z": "Yakuhai: White Dragon",
        "6z": "Yakuhai: Green Dragon",
        "7z": "Yakuhai: Red Dragon"
    }

    for tile, name in dragon_names.items():
        if counts[tile] >= 3:
            yaku.append(name)

    # Seat wind and round wind are separate yaku.
    if counts[seat_wind] >= 3:
        yaku.append("Yakuhai: Seat Wind")

    if counts[round_wind] >= 3:
        yaku.append("Yakuhai: Round Wind")

    # Collect numbered suits and check for honors.
    numbered_suits = {
        tile[1]
        for tile in all_tiles
        if tile[1] in ("m", "p", "s")
    }
    has_honors = any(tile[1] == "z" for tile in all_tiles)

    # One numbered suit with honors is Honitsu; without honors it is Chinitsu.
    if len(numbered_suits) == 1:
        if has_honors:
            yaku.append("Honitsu")
        else:
            yaku.append("Chinitsu")

    return yaku

@normalized_inputs('hand', 'winning_tile', 'melds')
def get_yaku_candidates(
    hand,
    seat_wind="1z",
    round_wind="1z",
    melds=None,
    *,
    is_closed=True,
    winning_tile=None,
    is_tsumo=False,
):
    """Return separate yaku candidates for each interpretation."""
    melds = [] if melds is None else list(melds)

    base_yaku = _get_base_yaku(
        hand,
        seat_wind=seat_wind,
        round_wind=round_wind,
        melds=melds,
    )

    if not is_complete_hand(hand, melds):
        return []

    if "Kokushi Musou" in base_yaku:
        return [{
            "kind": "kokushi",
            "decomposition": None,
            "yaku": ["Kokushi Musou"],
        }]

    closed = is_closed and all(
        meld["type"] == "ankan"
        for meld in melds
    )

    tile_yakuman = _tile_yakuman(hand, melds, closed=closed)
    candidates = []

    # Seven pairs is a separate interpretation.
    if not melds and is_seven_pairs(hand):
        candidates.append({
            "kind": "chiitoitsu",
            "decomposition": None,
            "yaku": tile_yakuman or base_yaku + ["Chiitoitsu"],
        })

    if winning_tile is None:
        standard_options = [
            {
                "decomposition": decomposition,
                "winning_group": None,
            }
            for decomposition in get_standard_hand_decompositions(
                hand, melds
            )
        ]
    else:
        if winning_tile not in hand:
            return []

        standard_options = get_winning_tile_placements(
            hand,
            winning_tile,
            melds,
        )

    for option in standard_options:
        decomposition = option["decomposition"]
        winning_group = option["winning_group"]
        yaku = list(base_yaku)

        # Include concealed sequences and fixed declared Chi groups.
        sequence_starts = set()

        groups = (
            decomposition["concealed_groups"]
            + decomposition["declared_groups"]
        )

        # Sanankou requires the actual winning tile context.
        if winning_group is not None:
            concealed_triplets = sum(
                group["type"] == "triplet"
                for group in decomposition["concealed_groups"]
            )

            concealed_triplets += sum(
                group["type"] == "ankan"
                for group in decomposition["declared_groups"]
            )

            # A triplet completed by Ron is not concealed.
            if (
                not is_tsumo
                and winning_group["type"] == "triplet"
            ):
                concealed_triplets -= 1

            if concealed_triplets >= 3:
                yaku.append("Sanankou")

        # Toitoi: all four groups are triplets or Kans.
        triplet_types = {"triplet", "pon", "ankan", "daiminkan", "kakan"}

        if len(groups) == 4 and all(
            group["type"] in triplet_types
            for group in groups
        ):
            yaku.append("Toitoi")

        # Each interpretation is checked independently, including fixed melds.
        has_sequence = any(group["type"] in ("sequence", "chi") for group in groups)
        all_groups_and_pair = [group["tiles"] for group in groups] + [decomposition["pair"]]
        outside_groups = all(
            any(tile[1] == "z" or tile[0] in ("1", "9") for tile in tiles)
            for tiles in all_groups_and_pair
        )
        if has_sequence and outside_groups:
            if any(tile[1] == "z" for tiles in all_groups_and_pair for tile in tiles):
                yaku.append("Chanta")
            else:
                yaku.append("Junchan")

        triplet_tiles = {
            group["tiles"][0]
            for group in groups if group["type"] in triplet_types
        }
        if any(all(f"{number}{suit}" in triplet_tiles for suit in ("m", "p", "s"))
               for number in range(1, 10)):
            yaku.append("Sanshoku Doukou")

        dragons = {"5z", "6z", "7z"}
        dragon_pair = decomposition["pair"][0]
        if dragon_pair in dragons and dragons - {dragon_pair} <= triplet_tiles:
            yaku.append("Shousangen")

        if sum(group["type"] in ("ankan", "daiminkan", "kakan") for group in groups) == 3:
            yaku.append("Sankantsu")

        for group in groups:
            if group["type"] not in ("sequence", "chi"):
                continue

            first_tile = min(
                group["tiles"],
                key=lambda tile: int(tile[0])
            )

            sequence_starts.add((
                first_tile[1],
                int(first_tile[0])
            ))

        # Same sequence in all three suits.
        if any(
            all(
                (suit, number) in sequence_starts
                for suit in ("m", "p", "s")
            )
            for number in range(1, 8)
        ):
            yaku.append("Sanshoku Doujun")

        # 123, 456 and 789 in one suit.
        if any(
            all(
                (suit, number) in sequence_starts
                for number in (1, 4, 7)
            )
            for suit in ("m", "p", "s")
        ):
            yaku.append("Ittsu")

        if closed:
            value_pair_tiles = {
                "5z", "6z", "7z",
                seat_wind,
                round_wind,
            }

            if (
                winning_group is not None
                and len(groups) == 4
                and all(
                    group["type"] == "sequence"
                    for group in groups
                )
                and decomposition["pair"][0] not in value_pair_tiles
                and get_wait_type(option, winning_tile) == "ryanmen"
            ):
                yaku.append("Pinfu")

            sequences = Counter(
                tuple(group["tiles"])
                for group in decomposition["concealed_groups"]
                if group["type"] == "sequence"
            )

            sequence_pairs = sum(
                count // 2
                for count in sequences.values()
            )

            if sequence_pairs >= 2:
                yaku.append("Ryanpeikou")
            elif sequence_pairs == 1:
                yaku.append("Iipeikou")

        yakuman = tile_yakuman + _standard_yakuman(
            decomposition, winning_group, closed=closed, is_tsumo=is_tsumo,
        )
        candidates.append({
            "kind": "standard",
            "decomposition": decomposition,
            "winning_group": winning_group,
            "yaku": yakuman or yaku,
        })

    return candidates


def count_supported_yaku_han(yaku, *, is_closed=True):
    """Count Han for the ordinary yaku currently supported."""
    fixed_han = {
        "Tanyao": 1,
        "Chiitoitsu": 2,
        "Iipeikou": 1,
        "Ryanpeikou": 3,
        "Riichi": 1,
        "Double Riichi": 2,
        "Ippatsu": 1,
        "Haitei Raoyue": 1,
        "Houtei Raoyui": 1,
        "Menzen Tsumo": 1,
        "Rinshan Kaihou": 1,
        "Chankan": 1,
        "Yakuhai: White Dragon": 1,
        "Yakuhai: Green Dragon": 1,
        "Yakuhai: Red Dragon": 1,
        "Yakuhai: Seat Wind": 1,
        "Yakuhai: Round Wind": 1,
        "Toitoi": 2,
        "Honroutou": 2,
        "Shousangen": 2,
        "Sanshoku Doukou": 2,
        "Sankantsu": 2,
        "Sanankou": 2,
        "Pinfu": 1,
    }

    variable_han = {
        "Honitsu": (3, 2),
        "Chinitsu": (6, 5),
        "Sanshoku Doujun": (2, 1),
        "Ittsu": (2, 1),
        "Chanta": (2, 1),
        "Junchan": (3, 2),
    }

    total = 0

    for name in yaku:
        if name in fixed_han:
            total += fixed_han[name]
        elif name in variable_han:
            closed_han, open_han = variable_han[name]
            total += closed_han if is_closed else open_han
        else:
            raise ValueError(f"Unsupported ordinary yaku: {name}")

    return total


def _current_candidate_priority(candidate, *, is_closed=True):
    """Compare Yakuman first, then supported ordinary yaku Han."""
    yaku = candidate["yaku"]

    yakuman_count = get_yakuman_count(yaku)
    if yakuman_count:
        return (1, yakuman_count)

    return (
        0,
        count_supported_yaku_han(yaku, is_closed=is_closed)
    )


@normalized_inputs('hand', 'winning_tile', 'melds')
def get_supported_yaku(
    hand,
    seat_wind="1z",
    round_wind="1z",
    melds=None,
    *,
    is_closed=True,
    winning_tile=None,
    is_tsumo=False,
):
    """Select one interpretation from the currently supported yaku."""
    candidates = get_yaku_candidates(
        hand,
        seat_wind=seat_wind,
        round_wind=round_wind,
        melds=melds,
        is_closed=is_closed,
        winning_tile=winning_tile,
        is_tsumo=is_tsumo,
    )

    if not candidates:
        return []

    declared_groups = [] if melds is None else melds

    closed = is_closed and all(
        meld["type"] == "ankan"
        for meld in declared_groups
    )

    best = max(
        candidates,
        key=lambda candidate: _current_candidate_priority(
            candidate,
            is_closed=closed,
        )
    )

    return list(best["yaku"])

def get_opening_yakuman(*, is_closed=True, is_tsumo=False, tenhou=False, chiihou=False):
    """Read the uninterrupted first-draw win flags."""
    if tenhou and chiihou:
        raise ValueError("Tenhou and Chiihou cannot coexist.")
    if (tenhou or chiihou) and not (is_closed and is_tsumo):
        raise ValueError("Opening Yakuman requires a closed Tsumo.")
    return ["Tenhou"] if tenhou else ["Chiihou"] if chiihou else []


def get_situational_yaku(*, is_closed=True, is_tsumo=False, riichi=False,
                         double_riichi=False, ippatsu=False, rinshan=False,
                         chankan=False, haitei=False, houtei=False):
    """Return compatible event yaku; Double Riichi replaces Riichi."""
    if is_tsumo and chankan:
        raise ValueError("Chankan cannot be a Tsumo win.")
    if rinshan and not is_tsumo:
        raise ValueError("Rinshan requires a Tsumo win.")
    if haitei and (not is_tsumo or rinshan or chankan):
        raise ValueError("Haitei requires an ordinary last-tile Tsumo.")
    if houtei and (is_tsumo or rinshan or chankan):
        raise ValueError("Houtei requires an ordinary last-discard Ron.")
    if double_riichi and not (riichi and is_closed):
        raise ValueError("Double Riichi requires accepted closed Riichi.")
    if ippatsu and not (riichi and is_closed):
        raise ValueError("Ippatsu requires accepted closed Riichi.")
    result = []
    if riichi and is_closed:
        result.append("Double Riichi" if double_riichi else "Riichi")
        if ippatsu:
            result.append("Ippatsu")
    if is_tsumo and is_closed:
        result.append("Menzen Tsumo")
    if rinshan:
        result.append("Rinshan Kaihou")
    if chankan:
        result.append("Chankan")
    if haitei:
        result.append("Haitei Raoyue")
    if houtei:
        result.append("Houtei Raoyui")
    return result


@normalized_inputs('hand', 'winning_tile', 'melds')
def get_win_yaku(
    hand,
    seat_wind="1z",
    round_wind="1z",
    melds=None,
    *,
    is_closed=True,
    is_tsumo=False,
    tenhou=False,
    chiihou=False,
    riichi=False,
    double_riichi=False,
    ippatsu=False,
    haitei=False,
    houtei=False,
    rinshan=False,
    chankan=False,
    winning_tile=None,
):
    """Collect supported tile-based and situational yaku."""
    if melds is None:
        melds = []

    yaku = get_supported_yaku(
        hand,
        seat_wind=seat_wind,
        round_wind=round_wind,
        melds=melds,
        is_closed=is_closed,
        winning_tile=winning_tile,
        is_tsumo=is_tsumo,
    )

    if not is_complete_hand(hand, melds):
        return []


    # Exposed groups prevent closed-hand yaku.
    closed = is_closed and all(
        meld["type"] == "ankan"
        for meld in melds
    )

    event_yakuman = get_opening_yakuman(
        is_closed=closed, is_tsumo=is_tsumo, tenhou=tenhou, chiihou=chiihou,
    )
    yakuman = [name for name in yaku if name in YAKUMAN_NAMES] + event_yakuman
    if yakuman:
        return yakuman

    yaku.extend(get_situational_yaku(
        is_closed=closed, is_tsumo=is_tsumo, riichi=riichi,
        double_riichi=double_riichi, ippatsu=ippatsu,
        rinshan=rinshan, chankan=chankan, haitei=haitei, houtei=houtei,
    ))

    return yaku
