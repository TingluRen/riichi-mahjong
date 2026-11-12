from tile_utils import normalize_tile, normalize_tiles
from contextvars import ContextVar
from functools import wraps
from threading import RLock
import logging
import os
from contextlib import asynccontextmanager
from copy import deepcopy

from game_store import GameStore, InvalidSaveError
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from hand_evaluator import get_tenpai_discards

# Preset hands for the developer tools.
from debug_scenarios import (
    create_ron_demo,
    create_riichi_demo,
    create_pon_demo,
    create_chi_demo,
    create_ankan_demo,
    create_daiminkan_demo,
    create_kakan_demo,
    create_chankan_demo,
)

from main import (
    create_game,
    can_kyuushu_kyuuhai,
    declare_kyuushu_kyuuhai,
    advance_until_human as run_computer_turns,
    finish_turn,
    get_dora_indicators,
    can_tsumo,
    declare_tsumo,
    can_ron,
    declare_ron,
    get_riichi_options,
    declare_riichi,
    can_pon,
    declare_pon,
    pass_response as pass_discard_response,
    get_chi_options,
    declare_chi,
    get_ankan_options,
    declare_ankan,
    can_daiminkan,
    declare_daiminkan,
    get_kakan_options,
    declare_kakan,
    can_chankan,
    declare_chankan,
    pass_chankan,
    get_winner_score,
    get_winner_ura_dora_indicators,
    create_next_hand,
)

base_dir = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
game_store = GameStore(os.environ.get("MAHJONG_SAVE_PATH", str(base_dir / "data" / "saved_game.json")))
save_notice = None
save_blocked = False


# Online requests use their own state; local play keeps the original module state.
request_state = ContextVar("mahjong_request_state", default=None)


class _LocalState:
    """Keep direct engine calls and the local server compatible with existing tests."""
    def __getattr__(self, name):
        return globals()[name]

    def __setattr__(self, name, value):
        globals()[name] = value


local_state = _LocalState()


def current_state():
    """Use the visitor bound to this request, falling back to local play."""
    state = request_state.get()
    return state if state is not None else local_state


def initialize_saved_game():
    """Restore the saved hand, or start a new one while preserving a bad save."""
    # State comes from the visitor context, or the local game.
    current_state().save_notice = None
    current_state().save_blocked = False
    # Load and validate first; corrupt files are backed up before starting over.
    loaded = None
    try:
        loaded = current_state().game_store.load()
        if loaded is not None:
            advance_until_human(loaded)
    except (InvalidSaveError, ValueError, KeyError, TypeError) as error:
        logger.warning("Saved Mahjong game could not be restored: %s", error)
        try:
            backup = current_state().game_store.quarantine()
            current_state().save_notice = f"Saved game could not be restored. Original kept as {backup.name}. A new game was started."
        except OSError:
            current_state().save_blocked = True
            current_state().save_notice = "Saved game could not be restored or backed up. The original file was kept unchanged. Check the data folder permissions before playing."
        loaded = None
    except OSError:
        current_state().save_blocked = True
        current_state().save_notice = "Saved game could not be read. The original file was kept unchanged. Check the data folder permissions before playing."
    # Resume the loaded phase; a new game still needs its first turn advanced.
    current_state().game = loaded if loaded is not None else create_game()
    if loaded is None:
        advance_until_human(current_state().game)
    elif current_state().save_notice is None:
        current_state().save_notice = "Your saved game has been restored."
    # Write the initial snapshot only when the original save can safely be replaced.
    if not current_state().save_blocked:
        try:
            current_state().game_store.save(current_state().game)
        except (OSError, ValueError) as error:
            logger.warning("Initial Mahjong autosave failed: %s", error)
            current_state().save_notice = "Autosave is unavailable. Check disk space and data folder permissions. Actions will be cancelled if they cannot be saved."


@asynccontextmanager
async def lifespan(application):
    with game_lock:
        initialize_saved_game()
    yield


app = FastAPI(lifespan=lifespan)


game_lock = RLock()
# Track HTTP actions separately so direct engine calls do not trigger disk writes.
http_action = ContextVar("mahjong_http_action", default=False)


@app.middleware("http")
async def mark_http_actions(request, call_next):
    # Mark modifying API requests for the durable-action wrapper.
    token = http_action.set(request.method == "POST" and request.url.path.startswith("/api/"))
    incremental_token = incremental_turns.set(request.headers.get("x-mahjong-step") == "1")
    try:
        return await call_next(request)
    finally:
        http_action.reset(token)
        incremental_turns.reset(incremental_token)


incremental_turns = ContextVar("incremental_turns", default=False)
turns_pending = ContextVar("turns_pending", default=False)

playback_frames = ContextVar("mahjong_playback_frames", default=None)


def advance_until_human(game):
    """Collect sanitized views for replay while the engine completes atomically."""
    frames = playback_frames.get()
    if frames is None:
        return run_computer_turns(game)

    def observe(candidate):
        state = current_state()
        previous = state.game
        state.game = candidate
        try:
            view = deepcopy(get_player_view())
            if not frames or frames[-1] != view:
                frames.append(view)
        finally:
            state.game = previous

    pending = run_computer_turns(game, observer=observe,
                                 max_steps=1 if incremental_turns.get() else None)
    turns_pending.set(bool(pending))
    return pending


def durable_action(function):
    """Lock, apply and save an HTTP action; roll back if it fails.

    Direct calls skip persistence. A disconnected browser does not cancel a save.
    """
    @wraps(function)
    def wrapped(*args, **kwargs):
        # State comes from the visitor context, or the local game.
        # Direct function calls keep their in-memory behavior, which tests also rely on.
        if not http_action.get():
            return function(*args, **kwargs)
        with game_lock:
            if current_state().save_blocked:
                raise HTTPException(status_code=503, detail=current_state().save_notice)
            # Work on a copy so a failed action or save leaves the old hand intact.
            previous = current_state().game
            previous_notice = current_state().save_notice
            current_state().game = deepcopy(previous)
            if (function.__name__ == "new_game"
                    or current_state().save_notice and current_state().save_notice.startswith("Autosave is unavailable.")):
                current_state().save_notice = None
            try:
                # Playback contains public views only; never send concealed AI tiles.
                token = playback_frames.set([])
                pending_token = turns_pending.set(False)
                try:
                    result = function(*args, **kwargs)
                    frames = playback_frames.get()
                    target = result.get("game", result)
                    if incremental_turns.get():
                        target["turns_pending"] = turns_pending.get()
                    if frames and isinstance(target, dict):
                        target["playback_frames"] = frames
                finally:
                    playback_frames.reset(token)
                    turns_pending.reset(pending_token)
                try:
                    current_state().game_store.save(current_state().game)
                except (OSError, InvalidSaveError) as error:
                    logger.warning("Mahjong action cancelled because autosave failed: %s", error)
                    raise HTTPException(status_code=503, detail=
                        "Could not save the game. This action was cancelled. Check disk space and data folder permissions, then retry.") from error
                return result
            # Restore both game state and its notice if the transaction does not finish.
            except BaseException:
                current_state().game = previous
                current_state().save_notice = previous_notice
                raise
    return wrapped


def locked_view(function):
    """Keep reads from seeing a game halfway through an action."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with game_lock:
            return function(*args, **kwargs)
    return wrapped


app.mount(
    "/static",
    StaticFiles(directory=base_dir / "static"),
    name="static"
)

# Keep one local game in memory.
game = create_game()
advance_until_human(game)

class ChiRequest(BaseModel):
    option_index: int = Field(strict=True, ge=0)

class DiscardRequest(BaseModel):
    tile_index: int = Field(strict=True, ge=0)

class AnkanRequest(BaseModel):
    tile: str = Field(strict=True, pattern=r"^[1-9][mps]$|^[1-7]z$")

class KakanRequest(BaseModel):
    meld_index: int = Field(strict=True, ge=0)


def get_final_rankings(game):
    """Return raw-score rankings after the match has ended."""
    if not game["match_ended"]:
        return []

    scores = game["scores"]

    player_order = sorted(
        range(4),
        key=lambda index: (-scores[index], index),
    )

    # Keep shared ranks for tied scores while preserving a stable display order.
    return [
        {
            "player_index": index,
            "score": scores[index],
            "rank": 1 + sum(
                other_score > scores[index]
                for other_score in scores
            ),
        }
        for index in player_order
    ]

@locked_view
def get_player_view():
    """Build the browser response without exposing computer hands."""
    human_index = current_state().game["human_player_index"]
    hand = current_state().game["hands"][human_index]

    is_human_discard_phase = (
        current_state().game["phase"] == "discard"
        and current_state().game["current_player_index"] == human_index
    )

    human_melds = current_state().game["melds"][human_index]
    # Each declared group replaces three concealed tiles, including a Kan.
    expected_hand_count = 14 - 3 * len(human_melds)

    tenpai_discards = (
        get_tenpai_discards(hand, human_melds)
        if (
            is_human_discard_phase
            and current_state().game["is_closed"][human_index]
            and len(hand) == expected_hand_count
        )
        else []
    )

    # Send legal choices to the UI; action handlers still validate requests again.
    riichi_options = get_riichi_options(current_state().game, human_index)
    chi_options = get_chi_options(current_state().game, human_index)
    ankan_options = get_ankan_options(current_state().game, human_index)
    kakan_options = get_kakan_options(current_state().game, human_index)
    human_can_chankan = can_chankan(current_state().game, human_index)

    # Send exact legal hand indices so the browser can disable forbidden discards.
    allowed_discard_indices = []

    if is_human_discard_phase:
        if current_state().game["riichi_declared"][human_index]:
            allowed_discard_indices = [len(hand) - 1]
        else:
            allowed_discard_indices = [
                index
                for index, tile in enumerate(hand)
                if normalize_tile(tile) not in normalize_tiles(current_state().game["forbidden_discard_tiles"])
            ]

    # A call gives no drawn tile; otherwise the last slot is the latest draw.
    drawn_tile_index = (
        len(hand) - 1
        if is_human_discard_phase and not current_state().game["after_call"]
        else None
    )

    # Build display hands without moving physical tiles.
    winning_hands = []

    for winner_index in current_state().game["winner_indices"]:
        winning_hand = list(current_state().game["hands"][winner_index])

        if current_state().game["end_reason"] == "ron":
            winning_hand.append(current_state().game["last_discard"]["tile"])
        elif current_state().game["end_reason"] == "chankan":
            winning_hand.append(current_state().game["robbed_kan_tile"])

        ura_indicators = get_winner_ura_dora_indicators(
            current_state().game,
            winner_index
        )

        score = get_winner_score(current_state().game, winner_index)

        if score is None:
            raise ValueError("The winning hand has no supported score.")

        winning_hands.append({
            "player_index": winner_index,
            "hand": winning_hand,
            "yaku": score["yaku"],
            "dora_count": score["dora_count"],
            "aka_dora_count": score.get("aka_dora_count", 0),
            "ura_dora_indicators": ura_indicators,
            "ura_dora_count": score["ura_dora_count"],
            "score": score,
            "nagashi_discards": (
                list(current_state().game["discards"][winner_index])
                if current_state().game["end_reason"] == "nagashi_mangan" else []
            ),
        })

    return {
        "hand": hand,
        "save_notice": current_state().save_notice,
        "tenpai_discards": tenpai_discards,
        "drawn_tile_index": drawn_tile_index,
        "dora_indicators": get_dora_indicators(current_state().game),
        "discards": current_state().game["discards"],
        "hand_counts": [len(hand) for hand in current_state().game["hands"]],
        "current_player_index": current_state().game["current_player_index"],
        "human_player_index": human_index,
        "round_wind": current_state().game["round_wind"],
        "hand_number": current_state().game["hand_number"],
        "honba": current_state().game["honba"],
        "dealer_index": current_state().game["dealer_index"],
        "match_ended": current_state().game["match_ended"],
        "match_end_reason": current_state().game["match_end_reason"],
        "final_riichi_award": current_state().game["final_riichi_award"],
        "final_riichi_recipient": current_state().game["final_riichi_recipient"],
        "can_next_hand": (
            current_state().game["phase"] == "ended"
            and current_state().game["settlement"] is not None
            and not current_state().game["match_ended"]
        ),
        "rankings": get_final_rankings(current_state().game),
        "seat_winds": current_state().game["seat_winds"],
        "phase": current_state().game["phase"],
        "wall_remaining": len(current_state().game["wall"]),
        "can_tsumo": can_tsumo(current_state().game, human_index),
        "can_ron": can_ron(current_state().game, human_index) or human_can_chankan,
        "can_chankan": human_can_chankan,
        "last_discard": current_state().game["last_discard"],
        "winner_index": current_state().game["winner_index"],
        "winner_indices": current_state().game["winner_indices"],
        "end_reason": current_state().game["end_reason"],
        "abort_reason": current_state().game["abort_reason"],
        "can_kyuushu_kyuuhai": can_kyuushu_kyuuhai(current_state().game, human_index),
        "winning_hands": winning_hands,
        "scores": current_state().game["scores"],
        "settlement": current_state().game["settlement"],
        "riichi_declared": current_state().game["riichi_declared"],
        "riichi_sticks": current_state().game["riichi_sticks"],
        "can_riichi": bool(riichi_options),
        "riichi_options": riichi_options,
        "allowed_discard_indices": allowed_discard_indices,
        "pending_riichi": current_state().game["pending_riichi"],
        "riichi_furiten": current_state().game["riichi_furiten"],
        "melds": current_state().game["melds"],
        "is_closed": current_state().game["is_closed"],
        "can_pon": can_pon(current_state().game, human_index),
        "can_daiminkan": can_daiminkan(current_state().game, human_index),
        "after_call": current_state().game["after_call"],
        "can_chi": bool(chi_options),
        "chi_options": chi_options,
        "can_ankan": bool(ankan_options),
        "ankan_options": ankan_options,
        "can_kakan": bool(kakan_options),
        "kakan_options": kakan_options,
        "pending_kakan": current_state().game["pending_kakan"],
    }

@app.get("/")
def home():
    """Serve the game page from the static folder."""
    return FileResponse(base_dir / "static" / "index.html")


@app.get("/api/game")
def read_game():
    """Return the current view without advancing any turns."""
    return get_player_view()


@app.post("/api/discard")
@durable_action
def discard(request: DiscardRequest):
    """Apply the selected discard, then run computers until the next decision."""
    try:
        discarded_tile = finish_turn(
            current_state().game,
            current_state().game["human_player_index"],
            request.tile_index
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    advance_until_human(current_state().game)

    return {
        "discarded_tile": discarded_tile,
        "game": get_player_view()
    }


@app.post("/api/new-game")
@durable_action
def new_game():
    """Start a fresh match and advance to the first human decision."""
    # State comes from the visitor context, or the local game.

    current_state().game = create_game()
    advance_until_human(current_state().game)

    return get_player_view()


@app.post("/api/next-hand")
@durable_action
def next_hand():
    """Build the next hand, or return the final match standings."""
    # State comes from the visitor context, or the local game.

    try:
        candidate = create_next_hand(current_state().game)
        advance_until_human(candidate)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    current_state().game = candidate

    return get_player_view()


@app.post("/api/tsumo")
@durable_action
def tsumo():
    try:
        declare_tsumo(current_state().game, current_state().game["human_player_index"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return get_player_view()


@app.post("/api/ron")
@durable_action
def ron():
    """Use the correct win handler for a discard or an added Kan."""
    try:
        human_index = current_state().game["human_player_index"]

        if current_state().game["phase"] == "kakan_response":
            declare_chankan(current_state().game, human_index)
        else:
            declare_ron(current_state().game, human_index)

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return get_player_view()


@app.post("/api/pass")
@durable_action
def pass_response():
    """Pass the current discard or added-Kan response."""
    try:
        human_index = current_state().game["human_player_index"]

        if current_state().game["phase"] == "kakan_response":
            pass_chankan(current_state().game, human_index)
        else:
            pass_discard_response(current_state().game, human_index)

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    advance_until_human(current_state().game)

    return get_player_view()


# Developer scenario endpoints.
@app.post("/api/debug/ron")
@durable_action
def load_ron_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_ron_demo()

    return get_player_view()


@app.post("/api/riichi")
@durable_action
def riichi(request: DiscardRequest):
    """Declare Riichi with the selected discard and resolve responses."""
    try:
        discarded_tile = declare_riichi(
            current_state().game,
            current_state().game["human_player_index"],
            request.tile_index
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    advance_until_human(current_state().game)

    return {
        "discarded_tile": discarded_tile,
        "game": get_player_view()
    }


@app.post("/api/debug/riichi")
@durable_action
def load_riichi_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_riichi_demo()

    return get_player_view()


@app.post("/api/pon")
@durable_action
def pon():
    try:
        declare_pon(current_state().game, current_state().game["human_player_index"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # A higher-priority AI call may have won the response window.
    advance_until_human(current_state().game)

    return get_player_view()


@app.post("/api/debug/pon")
@durable_action
def load_pon_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_pon_demo()

    return get_player_view()


@app.post("/api/chi")
@durable_action
def chi(request: ChiRequest):
    """Use the option index from the current list of legal Chi choices."""
    try:
        declare_chi(
            current_state().game,
            current_state().game["human_player_index"],
            request.option_index
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # A higher-priority AI call may have won the response window.
    advance_until_human(current_state().game)

    return get_player_view()


@app.post("/api/debug/chi")
@durable_action
def load_chi_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_chi_demo()

    return get_player_view()


@app.post("/api/ankan")
@durable_action
def ankan(request: AnkanRequest):
    """Declare a concealed Kan and continue from its replacement draw."""
    try:
        declare_ankan(
            current_state().game,
            current_state().game["human_player_index"],
            request.tile
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return get_player_view()


@app.post("/api/debug/ankan")
@durable_action
def load_ankan_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_ankan_demo()

    return get_player_view()


@app.post("/api/daiminkan")
@durable_action
def daiminkan():
    try:
        declare_daiminkan(current_state().game, current_state().game["human_player_index"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # A higher-priority AI call may have won the response window.
    advance_until_human(current_state().game)

    return get_player_view()


@app.post("/api/debug/daiminkan")
@durable_action
def load_daiminkan_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_daiminkan_demo()

    return get_player_view()


@app.post("/api/kakan")
@durable_action
def kakan(request: KakanRequest):
    """Declare an added Kan and allow robbery responses before completing it."""
    try:
        declare_kakan(
            current_state().game,
            current_state().game["human_player_index"],
            request.meld_index
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    advance_until_human(current_state().game)

    return get_player_view()


@app.post("/api/debug/kakan")
@durable_action
def load_kakan_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_kakan_demo()

    return get_player_view()


@app.post("/api/debug/chankan")
@durable_action
def load_chankan_demo():
    # State comes from the visitor context, or the local game.

    current_state().game = create_chankan_demo()

    return get_player_view()

@app.post("/api/abort-nine-terminals")
@durable_action
def abort_nine_terminals():
    """Request a nine-types abort through the normal rule checks."""
    try:
        declare_kyuushu_kyuuhai(current_state().game, current_state().game["human_player_index"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return get_player_view()


@app.post("/api/advance")
@durable_action
def advance_one_step():
    """Resume a committed game; engine rules still control all human decisions."""
    advance_until_human(current_state().game)
    return get_player_view()
