"""Match-level bankruptcy and final Riichi-deposit handling."""
from copy import deepcopy


def finish_match(game, reason):
    """Finish once. Award leftover deposits to the raw-score leader.

    Equal leaders use initial player index as the deposit tiebreaker;
    the existing shared-rank display is otherwise retained.
    """
    # Make finalization safe to call again without paying deposits twice.
    if game["match_ended"]:
        return
    if game["phase"] != "ended" or game["settlement"] is None:
        raise ValueError("The hand must be settled before finishing the match.")
    if reason not in ("bankruptcy", "south_round_complete"):
        raise ValueError("Unsupported match ending.")
    scores = list(game["scores"])
    if len(scores) != 4 or any(type(score) is not int for score in scores):
        raise ValueError("Invalid player scores.")
    sticks = game["riichi_sticks"]
    if type(sticks) is not int or sticks < 0:
        raise ValueError("Invalid Riichi stick count.")
    # Prepare the final result on a copy before changing the stored settlement.
    settlement = deepcopy(game["settlement"])
    if len(settlement["score_deltas"]) != 4:
        raise ValueError("Invalid settlement deltas.")
    award = sticks * 1000
    # Award remaining deposits to the leader; initial player order breaks ties.
    recipient = min(range(4), key=lambda player: (-scores[player], player)) if award else None
    if recipient is not None:
        scores[recipient] += award
        settlement["score_deltas"][recipient] += award
    settlement["scores_after"] = list(scores)
    settlement["final_riichi_award"] = award
    settlement["final_riichi_recipient"] = recipient
    # Commit the final scores, deposit award and match-ending flags together.
    game["scores"] = scores
    game["settlement"] = settlement
    game["riichi_sticks"] = 0
    game["final_riichi_award"] = award
    game["final_riichi_recipient"] = recipient
    game["match_end_reason"] = reason
    game["match_ended"] = True


def finish_if_bankrupt(game):
    """Exactly zero remains playable; below zero ends after full settlement."""
    if any(score < 0 for score in game["scores"]):
        finish_match(game, "bankruptcy")
