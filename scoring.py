from tile_utils import normalize_tiles, count_aka_dora
from tile_utils import normalized_inputs
from yaku import YAKUMAN_NAMES, get_yakuman_count, get_opening_yakuman
from yaku import get_situational_yaku
from hand_evaluator import get_wait_type
from yaku import (
    get_yaku_candidates,
    count_supported_yaku_han,
)

@normalized_inputs('group')
def get_group_fu(group, *, concealed):
    """Return Fu for one validated group."""
    group_type = group["type"]

    # Sequences add no Fu; triplets and Kans depend on whether they are concealed.
    if group_type in ("sequence", "chi"):
        return 0

    if group_type in ("triplet", "pon"):
        fu = 4 if concealed else 2
    elif group_type in ("ankan", "daiminkan", "kakan"):
        fu = 16 if concealed else 8
    else:
        raise ValueError(f"Unsupported group type: {group_type}")

    tile = group["tiles"][0]

    # Terminal and honor groups earn twice the Fu of simple groups.
    if tile[1] == "z" or tile[0] in ("1", "9"):
        fu *= 2

    return fu


@normalized_inputs('candidate', 'winning_tile')
def calculate_candidate_fu(
    candidate,
    winning_tile,
    *,
    is_tsumo=False,
    is_closed=True,
    seat_wind="1z",
    round_wind="1z",
    double_wind_pair_fu=4,
):
    """Calculate Fu for one candidate produced by the yaku evaluator."""
    if double_wind_pair_fu not in (2, 4):
        raise ValueError("Double wind pair Fu must be 2 or 4.")

    kind = candidate["kind"]

    # Yakuman does not use ordinary Fu scoring.
    if get_yakuman_count(candidate["yaku"]):
        return {
            "fu": None,
            "raw_fu": None,
            "details": [],
        }

    # Seven Pairs always uses 25 Fu and skips normal group scoring.
    if kind == "chiitoitsu":
        return {
            "fu": 25,
            "raw_fu": 25,
            "details": [
                {"reason": "Seven pairs", "fu": 25}
            ],
        }

    if kind != "standard":
        raise ValueError("Unsupported candidate kind.")

    decomposition = candidate["decomposition"]
    winning_group = candidate.get("winning_group")

    if winning_group is None:
        raise ValueError("Winning tile placement is required.")

    # A concealed Kan keeps the hand closed; other declared groups open it.
    closed = is_closed and all(
        group["type"] == "ankan"
        for group in decomposition["declared_groups"]
    )

    # Keep a breakdown for the result screen while adding Fu.
    details = [{"reason": "Base", "fu": 20}]

    def add(reason, fu):
        if fu:
            details.append({"reason": reason, "fu": fu})

    # Closed Ron adds 10 Fu, even when Ron completes a triplet.
    if not is_tsumo and closed:
        add("Closed Ron", 10)

    # Dragon and value-wind pairs add Fu; a double wind uses the configured amount.
    pair_tile = decomposition["pair"][0]

    if pair_tile in ("5z", "6z", "7z"):
        add("Dragon pair", 2)
    elif pair_tile == seat_wind == round_wind:
        add("Double wind pair", double_wind_pair_fu)
    elif pair_tile in (seat_wind, round_wind):
        add("Value wind pair", 2)

    # A Ron-completed triplet counts as open for group Fu.
    for index, group in enumerate(
        decomposition["concealed_groups"]
    ):
        concealed = True

        if (
            not is_tsumo
            and winning_group["type"] == "triplet"
            and winning_group["index"] == index
        ):
            concealed = False

        add(
            f"Concealed-hand group {index + 1}",
            get_group_fu(group, concealed=concealed),
        )

    # Score fixed melds separately, treating only Ankan as concealed.
    for index, group in enumerate(
        decomposition["declared_groups"]
    ):
        add(
            f"Declared group {index + 1}",
            get_group_fu(
                group,
                concealed=group["type"] == "ankan",
            ),
        )

    # Closed, edge and single-pair waits add two Fu.
    wait_type = get_wait_type(candidate, winning_tile)

    if wait_type in ("kanchan", "penchan", "tanki"):
        add(f"Wait: {wait_type}", 2)

    # Pinfu Tsumo keeps its special 20 Fu.
    if is_tsumo and "Pinfu" not in candidate["yaku"]:
        add("Tsumo", 2)

    raw_fu = sum(item["fu"] for item in details)

    # An open Ron with no other Fu is still scored as 30 Fu.
    if not closed and not is_tsumo and raw_fu == 20:
        add("Open Ron minimum", 10)
        raw_fu = 30

    # Round ordinary Fu upward to the next ten after applying minimums.
    rounded_fu = ((raw_fu + 9) // 10) * 10

    return {
        "fu": rounded_fu,
        "raw_fu": raw_fu,
        "details": details,
    }


@normalized_inputs('hand', 'winning_tile', 'melds')
def get_fu_candidates(
    hand,
    winning_tile,
    melds=None,
    *,
    is_tsumo=False,
    is_closed=True,
    seat_wind="1z",
    round_wind="1z",
    double_wind_pair_fu=4,
):
    """Calculate Fu separately for every supported interpretation."""
    candidates = get_yaku_candidates(
        hand,
        seat_wind=seat_wind,
        round_wind=round_wind,
        melds=melds,
        is_closed=is_closed,
        winning_tile=winning_tile,
        is_tsumo=is_tsumo,
    )

    if winning_tile not in hand:
        return []

    results = []

    for candidate in candidates:
        fu_result = calculate_candidate_fu(
            candidate,
            winning_tile,
            is_tsumo=is_tsumo,
            is_closed=is_closed,
            seat_wind=seat_wind,
            round_wind=round_wind,
            double_wind_pair_fu=double_wind_pair_fu,
        )

        results.append({
            **candidate,
            **fu_result,
        })

    return results



def round_up_to_100(points):
    """Round a payment up to the next hundred."""
    # Round each payment upward, rather than rounding only the final total.
    return ((points + 99) // 100) * 100


def calculate_points(
    han,
    fu,
    *,
    is_dealer=False,
    is_tsumo=False,
    yakuman_count=0,
    kazoe_limit="yakuman",
    kiriage_mangan=False,
):
    """Calculate payments without changing game scores."""
    if type(han) is not int or han < 0:
        raise ValueError("Han must be a non-negative integer.")

    if type(yakuman_count) is not int or yakuman_count < 0:
        raise ValueError("Yakuman count must be a non-negative integer.")

    if type(is_dealer) is not bool or type(is_tsumo) is not bool:
        raise ValueError("Dealer and Tsumo flags must be booleans.")

    if type(kiriage_mangan) is not bool:
        raise ValueError("Kiriage Mangan must be a boolean.")

    if kazoe_limit not in ("yakuman", "sanbaiman"):
        raise ValueError("Unsupported Kazoe limit.")

    if yakuman_count:
        # Actual Yakuman ignores ordinary Han, Fu and Dora.
        basic_points = 8000 * yakuman_count
        limit = "Yakuman"
    else:
        if han < 1:
            raise ValueError("Ordinary scoring requires at least one Han.")

        valid_fu = (
            type(fu) is int
            and (
                fu in (20, 25)
                or (fu >= 30 and fu % 10 == 0)
            )
        )

        if not valid_fu:
            raise ValueError("Fu must already be calculated and rounded.")

        if han >= 13:
            if kazoe_limit == "yakuman":
                basic_points = 8000
                limit = "Kazoe Yakuman"
            else:
                basic_points = 6000
                limit = "Sanbaiman"
        elif han >= 11:
            basic_points = 6000
            limit = "Sanbaiman"
        elif han >= 8:
            basic_points = 4000
            limit = "Baiman"
        elif han >= 6:
            basic_points = 3000
            limit = "Haneman"
        elif han >= 5:
            basic_points = 2000
            limit = "Mangan"
        else:
            basic_points = fu * (2 ** (han + 2))
            limit = None

            if basic_points >= 2000:
                basic_points = 2000
                limit = "Mangan"
            elif kiriage_mangan and (
                (han == 4 and fu == 30)
                or (han == 3 and fu == 60)
            ):
                basic_points = 2000
                limit = "Mangan"

        # These combinations cannot represent ordinary legal wins.
        if not is_tsumo and fu == 20:
            raise ValueError("A Ron hand cannot have 20 Fu.")

        if fu in (20, 25) and han < 2:
            raise ValueError("20 or 25 Fu requires at least two Han.")

    result = {
        "han": han,
        "fu": fu,
        "yakuman_count": yakuman_count,
        "basic_points": basic_points,
        "limit": limit,
        "is_dealer": is_dealer,
        "is_tsumo": is_tsumo,
        "ron_payment": None,
        "dealer_payment": None,
        "non_dealer_payment": None,
        "total": 0,
    }

    if not is_tsumo:
        multiplier = 6 if is_dealer else 4

        payment = round_up_to_100(
            basic_points * multiplier
        )

        result["ron_payment"] = payment
        result["total"] = payment

    elif is_dealer:
        payment = round_up_to_100(basic_points * 2)

        result["non_dealer_payment"] = payment
        result["total"] = payment * 3

    else:
        dealer_payment = round_up_to_100(
            basic_points * 2
        )
        non_dealer_payment = round_up_to_100(
            basic_points
        )

        result["dealer_payment"] = dealer_payment
        result["non_dealer_payment"] = non_dealer_payment
        result["total"] = (
            dealer_payment + non_dealer_payment * 2
        )

    return result


def evaluate_hand_score(
    hand,
    winning_tile,
    melds=None,
    *,
    is_closed=True,
    is_tsumo=False,
    tenhou=False,
    chiihou=False,
    is_dealer=False,
    seat_wind="1z",
    round_wind="1z",
    riichi=False,
    double_riichi=False,
    ippatsu=False,
    haitei=False,
    houtei=False,
    rinshan=False,
    chankan=False,
    dora_count=0,
    ura_dora_count=0,
    double_wind_pair_fu=4,
    kazoe_limit="yakuman",
    kiriage_mangan=False,
):
    """Select the highest-paying supported winning interpretation."""
    aka_dora_count = count_aka_dora(hand, melds)
    hand = normalize_tiles(hand)
    winning_tile = normalize_tiles(winning_tile)
    melds = normalize_tiles(melds)
    for name, value in (
        ("Dora count", dora_count),
        ("Ura Dora count", ura_dora_count),
    ):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer.")

    if is_tsumo and chankan:
        raise ValueError("Chankan cannot be a Tsumo win.")

    if rinshan and not is_tsumo:
        raise ValueError("Rinshan requires a Tsumo win.")

    melds = [] if melds is None else list(melds)

    closed = is_closed and all(
        meld["type"] == "ankan"
        for meld in melds
    )

    opening_yakuman = get_opening_yakuman(
        is_closed=closed, is_tsumo=is_tsumo, tenhou=tenhou, chiihou=chiihou,
    )
    if tenhou and not is_dealer:
        raise ValueError("Tenhou requires the dealer.")
    if chiihou and is_dealer:
        raise ValueError("Chiihou requires a non-dealer.")
    accepted_riichi = riichi and closed
    event_yaku = get_situational_yaku(
        is_closed=closed, is_tsumo=is_tsumo, riichi=riichi,
        double_riichi=double_riichi, ippatsu=ippatsu,
        rinshan=rinshan, chankan=chankan, haitei=haitei, houtei=houtei,
    )

    candidates = get_fu_candidates(
        hand,
        winning_tile,
        melds,
        is_tsumo=is_tsumo,
        is_closed=is_closed,
        seat_wind=seat_wind,
        round_wind=round_wind,
        double_wind_pair_fu=double_wind_pair_fu,
    )

    scored_candidates = []

    for candidate in candidates:
        yaku = list(candidate["yaku"])

        yakuman = [name for name in yaku if name in YAKUMAN_NAMES] + opening_yakuman
        if yakuman:
            # Actual Yakuman ignores ordinary yaku, Fu, Dora and Ura Dora.
            yaku = list(dict.fromkeys(yakuman))
            yakuman_count = get_yakuman_count(yaku)
            candidate = {**candidate, "fu": None, "raw_fu": None, "details": []}
            yaku_han = 0
            counted_dora = 0
            counted_ura = 0
        else:
            yakuman_count = 0

            yaku.extend(event_yaku)

            # Dora cannot supply the required yaku.
            if not yaku:
                continue

            yaku_han = count_supported_yaku_han(
                yaku,
                is_closed=closed,
            )
            counted_dora = dora_count
            counted_ura = (
                ura_dora_count if accepted_riichi else 0
            )

        counted_aka = aka_dora_count if not yakuman_count else 0
        bonus_han = counted_dora + counted_ura + counted_aka
        total_han = yaku_han + bonus_han

        payments = calculate_points(
            total_han,
            candidate["fu"],
            is_dealer=is_dealer,
            is_tsumo=is_tsumo,
            yakuman_count=yakuman_count,
            kazoe_limit=kazoe_limit,
            kiriage_mangan=kiriage_mangan,
        )

        scored_candidates.append({
            **candidate,
            "yaku": yaku,
            "yaku_han": yaku_han,
            "dora_count": counted_dora,
            "aka_dora_count": counted_aka,
            "ura_dora_count": counted_ura,
            "bonus_han": bonus_han,
            "han": total_han,
            "yakuman_count": yakuman_count,
            "payments": payments,
        })

    if not scored_candidates:
        return None

    return max(
        scored_candidates,
        key=lambda result: result["payments"]["total"],
    )