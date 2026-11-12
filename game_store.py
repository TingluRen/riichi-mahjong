"""Versioned local JSON saves with validation, atomic replacement and quarantine."""
from tile_utils import normalize_tiles, RED_TILES
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from hand_evaluator import VALID_TILES as SHAPE_TILES
VALID_TILES = SHAPE_TILES | RED_TILES

# The envelope version identifies the save format; required fields describe one complete game.
SAVE_VERSION = 1
REQUIRED = set("""wall dead_wall dora_indicator_count rinshan_draw_count hands discards
melds discard_history dealer_index round_wind hand_number honba match_ended
match_end_reason final_riichi_award final_riichi_recipient seat_winds human_player_index
current_player_index phase winner_index end_reason abort_reason last_discard
temporary_furiten winner_indices scores riichi_declared riichi_sticks double_riichi
ippatsu_eligible pending_double_riichi calls_made ordinary_draw_counts ordinary_draw_player
last_live_draw_player last_discard_is_houtei is_closed riichi_min_wall_tiles pending_riichi
pending_kakan robbed_kan_tile riichi_furiten rinshan_player_index after_call
forbidden_discard_tiles settlement winning_discarder_index""".split())


class InvalidSaveError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise InvalidSaveError(message)


def _integer(value, minimum=None, maximum=None):
    return (type(value) is int and (minimum is None or value >= minimum)
            and (maximum is None or value <= maximum))


def _index(value):
    return _integer(value, 0, 3)


def _tiles(value):
    return isinstance(value, list) and all(isinstance(t, str) and t in VALID_TILES for t in value)


def validate_game(game):
    """Validate a complete snapshot without changing it or invoking gameplay."""
    _require(isinstance(game, dict) and REQUIRED <= game.keys(), "Missing game fields.")
    # Validate player references before using them as list indices.
    for field in ("dealer_index", "human_player_index", "current_player_index"):
        _require(_index(game[field]), f"Invalid {field}.")
    for field in ("winner_index", "pending_riichi", "ordinary_draw_player", "last_live_draw_player",
                  "rinshan_player_index", "winning_discarder_index", "final_riichi_recipient"):
        _require(game[field] is None or _index(game[field]), f"Invalid {field}.")
    # Counters must be whole numbers and cannot be negative.
    for field in ("honba", "riichi_sticks", "riichi_min_wall_tiles", "final_riichi_award"):
        _require(_integer(game[field], 0), f"Invalid {field}.")
    _require(_integer(game["hand_number"], 1, 4), "Invalid hand number.")
    _require(game["round_wind"] in ("1z", "2z"), "Invalid round wind.")
    # Seat winds rotate with the dealer, while player indices stay fixed.
    _require(game["seat_winds"] == [
        f"{(player - game['dealer_index']) % 4 + 1}z" for player in range(4)
    ], "Seat winds do not match dealer.")
    _require(_integer(game["rinshan_draw_count"], 0, 4), "Invalid Rinshan count.")
    _require(_integer(game["dora_indicator_count"], 1, 5)
             and game["dora_indicator_count"] == game["rinshan_draw_count"] + 1,
             "Invalid Dora indicator count.")
    # Check scalar flags separately from the four-player flag lists.
    for field in ("match_ended", "pending_double_riichi", "calls_made",
                  "last_discard_is_houtei", "after_call"):
        _require(type(game[field]) is bool, f"Invalid {field}.")
    for field in ("temporary_furiten", "riichi_declared", "double_riichi",
                  "ippatsu_eligible", "is_closed", "riichi_furiten"):
        _require(isinstance(game[field], list) and len(game[field]) == 4
                 and all(type(v) is bool for v in game[field]), f"Invalid {field}.")
    _require(isinstance(game["ordinary_draw_counts"], list) and len(game["ordinary_draw_counts"]) == 4
             and all(_integer(v, 0) for v in game["ordinary_draw_counts"]), "Invalid draw counts.")
    _require(isinstance(game["scores"], list) and len(game["scores"]) == 4
             and all(_integer(v) for v in game["scores"]), "Invalid scores.")
    # Points on the table and in Riichi deposits must still total 100000.
    _require(sum(game["scores"]) + 1000 * game["riichi_sticks"] == 100000,
             "Scores and deposits must total 100000 points.")
    # Build a physical inventory; display data and discard history must not add extra tiles.
    physical = []
    for field in ("wall", "dead_wall", "forbidden_discard_tiles"):
        _require(_tiles(game[field]), f"Invalid {field} tiles.")
    _require(len(game["dead_wall"]) == 14, "Dead wall must contain 14 tiles.")
    physical.extend(game["wall"] + game["dead_wall"])
    # Every player needs a hand, a current river and a complete discard history.
    for field in ("hands", "discards", "discard_history"):
        _require(isinstance(game[field], list) and len(game[field]) == 4
                 and all(_tiles(pile) for pile in game[field]), f"Invalid {field}.")
    for piles in (game["hands"], game["discards"]):
        for pile in piles: physical.extend(pile)
    _require(isinstance(game["melds"], list) and len(game["melds"]) == 4, "Invalid melds.")
    # Validate meld shapes and their source players before counting their physical tiles.
    for player, melds in enumerate(game["melds"]):
        _require(isinstance(melds, list) and len(melds) <= 4, "Invalid meld list.")
        for meld in melds:
            _require(isinstance(meld, dict) and meld.get("type") in
                     ("chi", "pon", "ankan", "daiminkan", "kakan"), "Invalid meld type.")
            kind = meld["type"]; cards = meld.get("tiles")
            _require(_tiles(cards) and len(cards) == (3 if kind in ("chi", "pon") else 4), "Invalid meld tiles.")
            # Use ordinary fives for shape checks while leaving saved red tiles unchanged.
            shape_cards = normalize_tiles(cards)
            if kind == "chi":
                _require(len({t[1] for t in shape_cards}) == 1 and shape_cards[0][1] != "z"
                         and sorted(int(t[0]) for t in shape_cards) == list(range(min(int(t[0]) for t in shape_cards), min(int(t[0]) for t in shape_cards) + 3)), "Invalid Chi.")
            else:
                _require(len(set(shape_cards)) == 1, "Invalid triplet / Kan.")
            if kind != "ankan":
                _require(_index(meld.get("from_player_index")) and meld["from_player_index"] != player, "Invalid meld source.")
            physical.extend(cards)
        # Cross-check derived flags instead of trusting saved flags on their own.
        _require(game["is_closed"][player] == all(meld["type"] == "ankan" for meld in melds), "Invalid closed-hand flag.")
        _require(not game["riichi_declared"][player] or game["is_closed"][player], "Open Riichi is unsupported.")
        _require(not game["double_riichi"][player] or game["riichi_declared"][player], "Invalid Double Riichi.")
        _require(not game["ippatsu_eligible"][player] or game["riichi_declared"][player], "Invalid Ippatsu.")
        # Rivers are ordered subsequences of the complete history; calls remove tiles.
        history = iter(game["discard_history"][player])
        _require(all(any(old == tile for old in history) for tile in game["discards"][player]), "River conflicts with discard history.")
    # A tile taken by robbing a Kan is no longer in the declarer's hand.
    robbed = game["robbed_kan_tile"]
    _require(robbed is None or isinstance(robbed, str) and robbed in VALID_TILES, "Invalid robbed tile.")
    if robbed is not None: physical.append(robbed)
    _require(len(physical) == 136 and Counter(normalize_tiles(physical)) == Counter({tile: 4 for tile in SHAPE_TILES}) and (not any(t in RED_TILES for t in physical) or all(physical.count("0" + suit) == 1 and physical.count("5" + suit) == 3 for suit in ("m", "p", "s"))), "Physical tile counts are invalid.")
    # Check the phase and ending labels before validating their dependent fields.
    phase = game["phase"]; reason = game["end_reason"]
    _require(phase in ("draw", "discard", "response", "kakan_response", "ended"), "Invalid phase.")
    _require(reason in (None, "tsumo", "ron", "chankan", "exhaustive_draw", "abortive_draw", "nagashi_mangan"), "Invalid ending.")
    _require(game["match_end_reason"] in (None, "bankruptcy", "south_round_complete"), "Invalid match ending.")
    _require(game["abort_reason"] in (None, "kyuushu_kyuuhai", "suufon_renda", "suucha_riichi", "suukaikan"), "Invalid abort reason.")
    winners = game["winner_indices"]
    _require(isinstance(winners, list) and all(_index(v) for v in winners) and len(winners) == len(set(winners)), "Invalid winners.")
    # A response must refer to the actual last tile in the discarder's river.
    last = game["last_discard"]
    if last is not None:
        _require(isinstance(last, dict) and _index(last.get("player_index"))
                 and isinstance(last.get("tile"), str) and last["tile"] in VALID_TILES, "Invalid last discard.")
        pile = game["discards"][last["player_index"]]
        _require(bool(pile) and pile[-1] == last["tile"], "Last discard is absent from river.")
    # An added Kan remains a Pon until the robbery window closes.
    pending = game["pending_kakan"]
    if pending is not None:
        _require(isinstance(pending, dict) and _index(pending.get("player_index"))
                 and _integer(pending.get("meld_index"), 0, 3)
                 and isinstance(pending.get("tile"), str) and pending["tile"] in VALID_TILES, "Invalid pending Kakan.")
        groups = game["melds"][pending["player_index"]]
        _require(pending["meld_index"] < len(groups), "Missing pending Pon.")
        meld = groups[pending["meld_index"]]
        _require(meld["type"] == "pon" and normalize_tiles(meld["tiles"]) == [normalize_tiles(pending["tile"])] * 3
                 and pending["tile"] in game["hands"][pending["player_index"]], "Invalid Kakan context.")
    _require((phase == "kakan_response") == (pending is not None), "Kakan phase mismatch.")
    if phase == "response": _require(last is not None, "Discard response is missing its tile.")
    _require(not game["after_call"] or phase == "discard", "Invalid call-discard state.")
    # An ended hand needs a consistent settlement, not just an ending label.
    if phase == "ended":
        _require(reason is not None and isinstance(game["settlement"], dict), "Missing result settlement.")
        settlement = game["settlement"]
        for field in ("score_deltas", "scores_before", "scores_after"):
            _require(isinstance(settlement.get(field), list) and len(settlement[field]) == 4
                     and all(_integer(v) for v in settlement[field]), "Invalid settlement scores.")
        _require(settlement["scores_after"] == game["scores"] and
                 [a+b for a,b in zip(settlement["scores_before"], settlement["score_deltas"])] == game["scores"], "Settlement does not match balances.")
        _require(_integer(settlement.get("riichi_award"), 0)
                 and (settlement.get("riichi_recipient") is None or _index(settlement["riichi_recipient"])), "Invalid settlement deposits.")
        if reason == "exhaustive_draw":
            _require(isinstance(settlement.get("tenpai_flags"), list) and len(settlement["tenpai_flags"]) == 4
                     and all(type(v) is bool for v in settlement["tenpai_flags"]), "Missing Tenpai flags.")
        if reason in ("tsumo", "ron", "chankan", "nagashi_mangan"):
            _require(bool(winners) and game["winner_index"] == winners[0], "Winning result is missing winners.")
            if reason == "tsumo": _require(len(winners) == 1, "Tsumo must have one winner.")
            if reason in ("ron", "chankan"):
                _require(_index(game["winning_discarder_index"]) and game["winning_discarder_index"] not in winners, "Invalid winning discarder.")
            if reason == "ron": _require(last is not None, "Ron is missing its tile.")
            if reason == "chankan": _require(robbed is not None, "Chankan is missing its tile.")
        else: _require(not winners and game["winner_index"] is None, "Draw has winners.")
    else:
        _require(reason is None and game["settlement"] is None and not winners
                 and game["winner_index"] is None and not game["match_ended"], "Live game has finished-result state.")
    _require(not game["match_ended"] or game["match_end_reason"] is not None, "Missing match-end reason.")
    if game["final_riichi_award"]:
        _require(game["match_ended"] and _index(game["final_riichi_recipient"]), "Invalid final deposit recipient.")
    if phase == "ended" and reason in ("tsumo", "ron", "chankan"):
        from main import get_winner_score
        _require(all(get_winner_score(game, player) is not None for player in winners), "Saved winning hand cannot be scored.")
    for player, hand in enumerate(game["hands"]):
        expected = 13 - 3 * len(game["melds"][player])
        if phase in ("discard", "kakan_response") and player == game["current_player_index"]:
            expected += 1
        elif phase == "ended" and reason == "tsumo" and player == game["winner_index"]:
            expected += 1
        elif phase == "ended" and game["abort_reason"] == "kyuushu_kyuuhai" and player == game["current_player_index"]:
            expected += 1
        _require(len(hand) == expected, "Hand size does not match phase and melds.")
    return game


class GameStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        """Read and validate the save; return None when no save exists."""
        try:
            if self.path.stat().st_size > 2_000_000:
                raise InvalidSaveError("Save file is too large.")
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except UnicodeError as error:
            raise InvalidSaveError("Save file is not valid UTF-8.") from error
        try:
            # Validate the file format before handing the snapshot to the game engine.
            envelope = json.loads(raw)
            _require(isinstance(envelope, dict) and type(envelope.get("version")) is int
                     and envelope["version"] == SAVE_VERSION, "Unsupported save version.")
            return validate_game(envelope.get("game"))
        except (ValueError, TypeError, KeyError, IndexError, AssertionError) as error:
            raise InvalidSaveError(f"Saved game is invalid: {error}") from error

    def save(self, game):
        """Validate first, then replace the save with a fully written temporary file."""
        validate_game(game)
        try:
            text = json.dumps({"version": SAVE_VERSION,
                               "saved_at": datetime.now(timezone.utc).isoformat(),
                               "game": game}, ensure_ascii=False, allow_nan=False)
        except (ValueError, TypeError) as error:
            raise InvalidSaveError("Game cannot be serialized as JSON.") from error
        # Create the save folder only when a validated game is ready to write.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            # Close the temporary file before replacing: Windows cannot rename an open file.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".mahjong-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(text)
                stream.flush()
                # Flush the file before replacing the last usable save.
                os.fsync(stream.fileno())
            # A completed file replaces the old save in one filesystem operation.
            os.replace(temporary, self.path)
        # Remove any leftover temporary file whether saving succeeds or fails.
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def quarantine(self):
        """Preserve the original bytes; never overwrite a damaged save."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self.path.with_name(f"{self.path.stem}.corrupt-{stamp}-{uuid4().hex[:8]}{self.path.suffix}")
        self.path.replace(backup)
        return backup
