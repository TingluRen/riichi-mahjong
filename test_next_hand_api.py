import unittest
from copy import deepcopy
from unittest.mock import patch

from fastapi import HTTPException

import server
from main import create_game


class NextHandApiTests(unittest.TestCase):
    def make_ended_game(self):
        game = create_game()
        game["phase"] = "ended"
        game["end_reason"] = "exhaustive_draw"
        game["wall"] = []
        game["winner_indices"] = []
        game["winner_index"] = None
        game["scores"] = [28000, 23000, 24000, 24000]
        game["riichi_sticks"] = 1

        game["settlement"] = {
            "score_deltas": [0, 0, 0, 0],
            "scores_before": list(game["scores"]),
            "scores_after": list(game["scores"]),
            "tenpai_flags": [False, False, False, False],
            "riichi_award": 0,
            "riichi_recipient": None,
        }

        return game

    def test_next_hand_preserves_scores_and_advances(self):
        old_game = self.make_ended_game()
        before = deepcopy(old_game)

        with patch.object(server, "game", old_game):
            with patch.object(server, "advance_until_human") as advance:
                view = server.next_hand()

                advance.assert_called_once_with(server.game)

            self.assertEqual(view["hand_number"], 2)
            self.assertEqual(view["dealer_index"], 1)
            self.assertEqual(view["honba"], 1)
            self.assertEqual(view["scores"], before["scores"])
            self.assertEqual(view["riichi_sticks"], 1)
            self.assertFalse(view["can_next_hand"])
            self.assertFalse(view["match_ended"])
            self.assertEqual(view["rankings"], [])

        self.assertEqual(old_game, before)

    def test_unfinished_hand_is_rejected(self):
        game = create_game()
        before = deepcopy(game)

        with patch.object(server, "game", game):
            with self.assertRaises(HTTPException) as caught:
                server.next_hand()

            self.assertEqual(caught.exception.status_code, 400)
            self.assertEqual(server.game, before)

    def test_match_end_returns_rankings(self):
        game = self.make_ended_game()
        game["round_wind"] = "2z"
        game["hand_number"] = 4
        game["dealer_index"] = 3
        original = deepcopy(game)

        with patch.object(server, "game", game):
            view = server.next_hand()

            self.assertTrue(view["match_ended"])
            self.assertFalse(view["can_next_hand"])

            # The remaining Riichi deposit goes to Player 1.
            self.assertEqual(
                view["scores"],
                [29000, 23000, 24000, 24000],
            )
            self.assertEqual(view["riichi_sticks"], 0)
            self.assertEqual(view["final_riichi_award"], 1000)
            self.assertEqual(view["final_riichi_recipient"], 0)

            self.assertEqual(
                [item["player_index"] for item in view["rankings"]],
                [0, 2, 3, 1],
            )
            self.assertEqual(
                [item["score"] for item in view["rankings"]],
                [29000, 24000, 24000, 23000],
            )
            self.assertEqual(
                [item["rank"] for item in view["rankings"]],
                [1, 2, 2, 4],
            )

            # Finishing the match must not modify the original game.
            self.assertEqual(game, original)

            # A finished match cannot advance or pay deposits again.
            before = deepcopy(server.game)

            with self.assertRaises(HTTPException) as caught:
                server.next_hand()

            self.assertEqual(caught.exception.status_code, 400)
            self.assertEqual(server.game, before)

    def test_failed_advance_keeps_old_game(self):
        game = self.make_ended_game()
        before = deepcopy(game)

        with patch.object(server, "game", game):
            with patch.object(
                server,
                "advance_until_human",
                side_effect=ValueError("Test failure"),
            ):
                with self.assertRaises(HTTPException):
                    server.next_hand()

            self.assertIs(server.game, game)
            self.assertEqual(server.game, before)

    def test_reading_view_does_not_advance_or_change_scores(self):
        game = self.make_ended_game()
        before = deepcopy(game)

        with patch.object(server, "game", game):
            first = server.get_player_view()
            second = server.get_player_view()

            self.assertTrue(first["can_next_hand"])
            self.assertEqual(first, second)
            self.assertEqual(server.game, before)


if __name__ == "__main__":
    unittest.main()