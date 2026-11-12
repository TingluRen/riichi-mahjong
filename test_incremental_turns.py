"""Incremental public requests preserve rules, saves and hidden information."""
import random
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
import server
import web_server
from visitor_store import VisitorStore

class IncrementalTurnsTests(unittest.TestCase):
    def setUp(self):
        state = random.getstate()
        self.addCleanup(random.setstate, state)

    def test_bounded_steps_match_complete_engine(self):
        for seed in range(12):
            random.seed(seed)
            game = main.create_game()
            main.advance_until_human(game)
            if game['phase'] != 'discard':
                continue
            main.finish_turn(game, game['human_player_index'], 0)
            expected = deepcopy(game)
            main.advance_until_human(expected)
            for _ in range(100):
                if not main.advance_until_human(game, max_steps=1):
                    break
            else:
                self.fail('AI steps did not stop')
            self.assertEqual(game, expected)

    def test_http_step_resume_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            store = VisitorStore(Path(directory) / 'visitors.sqlite3')
            with patch.object(web_server, 'visitor_store', store):
                with TestClient(web_server.app) as client:
                    client.headers['X-Mahjong-Step'] = '1'
                    view = client.post('/api/new-game').json()
                    for _ in range(100):
                        if not view.get('turns_pending'):
                            break
                        view = client.post('/api/advance').json()
                    self.assertFalse(view.get('turns_pending'))
                    if view['phase'] != 'discard':
                        return
                    response = client.post('/api/discard', json={'tile_index': 0})
                    self.assertEqual(response.status_code, 200, response.text)
                    view = response.json()['game']
                    self.assertTrue(view['turns_pending'])
                    # Reload sees an intermediate persisted state and can resume it.
                    reloaded = client.get('/api/game').json()
                    self.assertTrue(reloaded['turns_pending'])
                    for _ in range(100):
                        self.assertNotIn('hands', view)
                        self.assertNotIn('wall', view)
                        if not view.get('turns_pending'):
                            break
                        response = client.post('/api/advance')
                        self.assertEqual(response.status_code, 200, response.text)
                        view = response.json()
                    self.assertFalse(view.get('turns_pending'))
                    with store.session(client.cookies[web_server.COOKIE_NAME]) as (_, state):
                        self.assertNotIn('turns_pending', state.game)
                        self.assertEqual(view['discards'], state.game['discards'])
