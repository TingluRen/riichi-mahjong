"""Discard-based Nagashi Mangan, scored as a win in this project's rules."""
from scoring import calculate_points


def get_nagashi_winners(game):
    """Return qualifiers in dealer-first turn order; never mutate the game.

    A nonempty full discard history must contain only terminals/honors and
    still exactly match the physical river. Any called-away tile disqualifies
    the player even when the remaining river still looks valid. Own melds do
    not by themselves disqualify the player under this discard-only variant.
    """
    if (game["phase"] != "ended" or game["end_reason"] != "exhaustive_draw"
            or game["wall"] or game["winner_indices"]):
        return []
    # Check in dealer-first turn order so a shared win has a stable deposit recipient.
    winners = []
    for offset in range(4):
        player = (game["dealer_index"] + offset) % 4
        # A qualifying river must be nonempty and have no called-away discards.
        history = game["discard_history"][player]
        if (history and history == game["discards"][player]
                and all(tile[1] == "z" or tile[0] in ("1", "9") for tile in history)):
            winners.append(player)
    return winners


def get_nagashi_score(*, is_dealer):
    """A fixed Mangan: no hand completion, ordinary yaku, Fu or bonus Dora."""
    # 30 Fu is an input placeholder only; a 5-Han Mangan is Fu-independent.
    payments = calculate_points(5, 30, is_dealer=is_dealer, is_tsumo=True)
    payments["fu"] = None
    return {
        "kind": "nagashi", "decomposition": None, "winning_group": None,
        "yaku": ["Nagashi Mangan"], "yaku_han": 5, "han": 5,
        "dora_count": 0, "ura_dora_count": 0, "bonus_han": 0,
        "yakuman_count": 0, "fu": None, "raw_fu": None, "details": [],
        "payments": payments,
    }
