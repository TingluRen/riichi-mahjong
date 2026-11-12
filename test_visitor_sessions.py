"""Public-demo checks for visitor isolation, recovery and transaction rollback."""
import hashlib
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import debug_scenarios as demos
import server
import web_server
from visitor_store import SESSION_SECONDS, VisitorStore, _TransactionStore


class VisitorSessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = VisitorStore(Path(directory.name) / "visitors.sqlite3")
        patcher = patch.object(web_server, "visitor_store", self.store)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.a = TestClient(web_server.app)
        self.b = TestClient(web_server.app)
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def view(self, client):
        response = client.get("/api/game")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def seed(self, client, factory):
        self.view(client)
        token = client.cookies.get(web_server.COOKIE_NAME)
        with self.store.session(token) as (_, state):
            state.game = factory()

    def test_two_browsers_receive_different_sessions(self):
        self.view(self.a)
        self.view(self.b)
        self.assertNotEqual(self.a.cookies.get(web_server.COOKIE_NAME),
                            self.b.cookies.get(web_server.COOKIE_NAME))

    def test_discard_does_not_change_another_visitor(self):
        first = self.view(self.a)
        other = self.view(self.b)
        response = self.a.post("/api/discard", json={"tile_index": first["allowed_discard_indices"][0]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.view(self.b), other)
        self.assertNotEqual(self.view(self.a), first)

    def test_new_game_resets_only_its_visitor(self):
        self.seed(self.a, demos.create_ron_demo)
        other = self.view(self.b)
        self.assertEqual(self.a.post("/api/new-game").status_code, 200)
        self.assertEqual(self.view(self.a)["phase"], "discard")
        self.assertEqual(self.view(self.b), other)

    def test_refresh_keeps_session_and_state(self):
        first = self.view(self.a)
        token = self.a.cookies.get(web_server.COOKIE_NAME)
        self.assertEqual(self.view(self.a), first)
        self.assertEqual(self.a.cookies.get(web_server.COOKIE_NAME), token)

    def test_reopening_browser_with_cookie_restores_state(self):
        expected = self.view(self.a)
        with TestClient(web_server.app) as reopened:
            reopened.cookies.update(self.a.cookies)
            with patch.object(web_server, "visitor_store", VisitorStore(self.store.path)):
                self.assertEqual(self.view(reopened), expected)

    def test_saved_waiting_win_does_not_advance_on_read(self):
        for factory in (demos.create_ron_demo, demos.create_chankan_demo):
            with self.subTest(factory=factory.__name__):
                self.seed(self.a, factory)
                first = self.view(self.a)
                self.assertTrue(first["can_ron"])
                with patch.object(server, "advance_until_human", side_effect=AssertionError("Unexpected draw")):
                    self.assertEqual(self.view(self.a), first)

    def test_invalid_discard_keeps_both_games(self):
        first, other = self.view(self.a), self.view(self.b)
        for body, status in [({"tile_index": 999}, 400), ({"tile_index": True}, 422)]:
            response = self.a.post("/api/discard", json=body)
            self.assertEqual(response.status_code, status)
            self.assertEqual(self.view(self.a), first)
            self.assertEqual(self.view(self.b), other)

    def test_save_failure_rolls_back_entire_action(self):
        self.seed(self.a, demos.create_ron_demo)
        before = self.view(self.a)
        original = _TransactionStore.save
        def fail_after_write(store, game):
            original(store, game)
            raise sqlite3.OperationalError("disk full")
        with patch.object(_TransactionStore, "save", fail_after_write):
            self.assertEqual(self.a.post("/api/new-game").status_code, 503)
        self.assertEqual(self.view(self.a), before)

    def test_damaged_snapshot_is_preserved_and_other_visitor_can_play(self):
        self.view(self.a)
        other = self.view(self.b)
        token = self.a.cookies.get(web_server.COOKIE_NAME)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with closing(sqlite3.connect(self.store.path)) as connection, connection:
            connection.execute("UPDATE visitor_games SET snapshot = ? WHERE token_hash = ?",
                               ("{broken", digest))
        self.assertEqual(self.a.get("/api/game").status_code, 503)
        self.assertEqual(self.view(self.b), other)
        with closing(sqlite3.connect(self.store.path)) as connection, connection:
            raw = connection.execute("SELECT snapshot FROM visitor_games WHERE token_hash = ?",
                                     (digest,)).fetchone()[0]
        self.assertEqual(raw, "{broken")

    def test_invalid_cookie_does_not_select_a_session(self):
        for token in ("../saved_game", "x" * 43):
            self.b.cookies.clear()
            self.b.cookies.set(web_server.COOKIE_NAME, token, domain="testserver.local", path="/")
            self.view(self.b)
            self.assertNotEqual(self.b.cookies.get(web_server.COOKIE_NAME), token)

    def test_debug_endpoints_are_absent_and_buttons_hidden(self):
        for scenario in ("ron", "riichi", "pon", "chi", "ankan", "daiminkan", "kakan", "chankan"):
            self.assertEqual(self.a.post("/api/debug/" + scenario).status_code, 404)
        self.assertIn('<details class="developer-tools" hidden>', self.a.get("/").text)

    def test_cookies_and_responses_are_private(self):
        with TestClient(web_server.app, base_url="https://example.test") as client:
            response = client.get("/api/game")
            header = response.headers["set-cookie"].lower()
            for flag in ("httponly", "secure", "samesite=lax"):
                self.assertIn(flag, header)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn("hands", response.json())

    def test_cross_site_actions_are_rejected(self):
        before = self.view(self.a)
        response = self.a.post("/api/new-game", headers={"origin": "https://other.test"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.view(self.a), before)

    def test_health_check_creates_no_session(self):
        self.assertEqual(self.a.get("/health").json(), {"status": "ok"})
        self.assertFalse(self.store.path.exists())
        self.assertIsNone(self.a.cookies.get(web_server.COOKIE_NAME))

    def test_online_actions_leave_local_game_and_save_alone(self):
        before = deepcopy(server.game)
        with patch.object(server.game_store, "save", side_effect=AssertionError("Local save changed")):
            self.view(self.a)
            self.a.post("/api/new-game")
        self.assertEqual(server.game, before)
        self.assertIsNone(server.request_state.get())

    def test_expired_session_is_replaced(self):
        self.view(self.a)
        old = self.a.cookies.get(web_server.COOKIE_NAME)
        with closing(sqlite3.connect(self.store.path)) as connection, connection:
            connection.execute("UPDATE visitor_games SET touched_at = ?", (time.time() - SESSION_SECONDS - 1,))
        self.view(self.a)
        self.assertNotEqual(self.a.cookies.get(web_server.COOKIE_NAME), old)

    def test_database_keeps_hashes_not_cookie_tokens(self):
        self.view(self.a)
        token = self.a.cookies.get(web_server.COOKIE_NAME)
        with closing(sqlite3.connect(self.store.path)) as connection, connection:
            digest = connection.execute("SELECT token_hash FROM visitor_games").fetchone()[0]
        self.assertEqual(digest, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotEqual(digest, token)

    def test_concurrent_same_session_updates_are_not_lost(self):
        self.view(self.a)
        token = self.a.cookies.get(web_server.COOKIE_NAME)
        def increment(_):
            with self.store.session(token) as (_, state):
                state.game["honba"] += 1
        with ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(increment, range(6)))
        self.assertEqual(self.view(self.a)["honba"], 6)

    def test_online_action_routes_use_existing_rules(self):
        cases = [
            (demos.create_ron_demo, "/api/ron", None),
            (demos.create_ron_demo, "/api/pass", None),
            (demos.create_pon_demo, "/api/pon", None),
            (demos.create_chi_demo, "/api/chi", {"option_index": 0}),
            (demos.create_ankan_demo, "/api/ankan", {"tile": "5z"}),
            (demos.create_daiminkan_demo, "/api/daiminkan", None),
            (demos.create_kakan_demo, "/api/kakan", {"meld_index": 0}),
            (demos.create_chankan_demo, "/api/ron", None),
            (demos.create_riichi_demo, "/api/riichi", {"tile_index": 13}),
        ]
        for factory, path, body in cases:
            with self.subTest(path=path):
                self.seed(self.a, factory)
                other = self.view(self.b)
                response = self.a.post(path, json=body) if body else self.a.post(path)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(self.view(self.b), other)


if __name__ == "__main__":
    unittest.main()
