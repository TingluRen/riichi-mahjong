"""HTTP playback preserves turn order and hides computer hands."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
import server
import web_server
from visitor_store import VisitorStore


class TurnPlaybackTests(unittest.TestCase):
    def test_new_game_replays_dealer_before_human_and_keeps_frames_out_of_save(self):
        with tempfile.TemporaryDirectory() as directory:
            store = VisitorStore(Path(directory) / 'visitors.sqlite3')
            game = main.create_game()
            # Player 4 deals, so the opening AI turn precedes Player 1.
            game['seat_winds'] = ['2z', '3z', '4z', '1z']
            game['dealer_index'] = 3
            game['current_player_index'] = 3
            with patch.object(web_server, 'visitor_store', store), patch.object(server, 'create_game', return_value=game):
                with TestClient(web_server.app) as client:
                    response = client.post('/api/new-game')
                    self.assertEqual(response.status_code, 200, response.text)
                    data = response.json()
                    frames = data['playback_frames']
                    decisions = [f for f in frames if f['phase'] == 'discard' and f['current_player_index'] == 3]
                    self.assertTrue(decisions)
                    self.assertEqual(decisions[0]['discards'][3], [])
                    self.assertTrue(any(f['discards'][3] for f in frames))
                    for frame in frames:
                        self.assertNotIn('hands', frame)
                        self.assertNotIn('wall', frame)
                        self.assertNotIn('playback_frames', frame)
                    restored = client.get('/api/game').json()
                    self.assertNotIn('playback_frames', restored)
                    self.assertEqual(restored['discards'], data['discards'])
