"""Store one independent game per browser in a local SQLite database."""
import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from game_store import InvalidSaveError, validate_game
from main import advance_until_human, create_game

SESSION_SECONDS = 30 * 24 * 60 * 60
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class VisitorStore:
    """Keep loading, applying and saving an action in one database transaction."""

    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def session(self, token):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS visitor_games (
                token_hash TEXT PRIMARY KEY, snapshot TEXT NOT NULL,
                touched_at REAL NOT NULL
            )""")
            # Lock before reading so simultaneous actions cannot overwrite each other.
            connection.execute("BEGIN IMMEDIATE")
            now = time.time()
            connection.execute("DELETE FROM visitor_games WHERE touched_at < ?",
                               (now - SESSION_SECONDS,))
            valid_token = isinstance(token, str) and TOKEN_PATTERN.fullmatch(token)
            digest = hashlib.sha256(token.encode()).hexdigest() if valid_token else None
            row = connection.execute(
                "SELECT snapshot FROM visitor_games WHERE token_hash = ?", (digest,)
            ).fetchone() if digest else None

            # Unknown tokens never choose a new session ID, preventing session fixation.
            if row is None:
                token = secrets.token_urlsafe(32)
                digest = hashlib.sha256(token.encode()).hexdigest()
                game = create_game()
                advance_until_human(game)
            else:
                try:
                    game = validate_game(json.loads(row[0]))
                except (ValueError, TypeError) as error:
                    # Keep the damaged row untouched instead of silently resetting it.
                    raise InvalidSaveError("Visitor snapshot is invalid.") from error

            store = _TransactionStore(connection, digest)
            state = SimpleNamespace(game=game, game_store=store,
                                    save_notice="Progress is saved for this browser for up to 30 days of inactivity.",
                                    save_blocked=False)
            yield token, state
            # Reads also persist new sessions and refresh the inactivity expiry.
            store.save(state.game)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


class _TransactionStore:
    """Use the existing action-save interface inside the visitor transaction."""

    def __init__(self, connection, digest):
        self.connection = connection
        self.digest = digest

    def save(self, game):
        validate_game(game)
        snapshot = json.dumps(game, ensure_ascii=False, allow_nan=False)
        self.connection.execute("""INSERT INTO visitor_games VALUES (?, ?, ?)
            ON CONFLICT(token_hash) DO UPDATE SET
            snapshot = excluded.snapshot, touched_at = excluded.touched_at""",
            (self.digest, snapshot, time.time()))
