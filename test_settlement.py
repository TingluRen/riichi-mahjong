import unittest
from copy import deepcopy
from unittest.mock import patch

from main import create_game, settle_win, declare_ron
from debug_scenarios import create_ron_demo
from scoring import calculate_points


class SettlementTests(unittest.TestCase):
    def make_game(self, reason, winners, discarder=None):
        game = create_game()
        game["phase"] = "ended"
        game["end_reason"] = reason
        game["winner_indices"] = list(winners)
        game["winner_index"] = winners[0]
        game["winning_discarder_index"] = discarder
        return game

    def test_ron(self):
        game = self.make_game("ron", [1], discarder=2)
        score = {
            "payments": calculate_points(3, 40)
        }

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [0, 5200, -5200, 0],
        )
        self.assertEqual(
            game["scores"],
            [25000, 30200, 19800, 25000],
        )

    def test_dealer_tsumo(self):
        game = self.make_game("tsumo", [0])
        score = {
            "payments": calculate_points(
                2, 20, is_dealer=True, is_tsumo=True
            )
        }

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [2100, -700, -700, -700],
        )

    def test_non_dealer_tsumo(self):
        game = self.make_game("tsumo", [1])
        score = {
            "payments": calculate_points(
                2, 20, is_tsumo=True
            )
        }

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [-700, 1500, -400, -400],
        )

    def test_chankan(self):
        game = self.make_game("chankan", [1], discarder=3)
        score = {
            "payments": calculate_points(2, 30)
        }

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [0, 2000, 0, -2000],
        )

    def test_multiple_ron_and_riichi_pool(self):
        game = self.make_game("ron", [2, 1], discarder=0)

        # Two deposits were already deducted when Riichi was accepted.
        game["scores"] = [25000, 24000, 24000, 25000]
        game["riichi_sticks"] = 2

        scores = {
            1: {"payments": calculate_points(1, 30)},
            2: {"payments": calculate_points(2, 30)},
        }

        with patch(
            "main.get_winner_score",
            side_effect=lambda game, index: scores[index],
        ):
            result = settle_win(game)

        self.assertEqual(result["riichi_recipient"], 1)
        self.assertEqual(result["riichi_award"], 2000)
        self.assertEqual(
            result["score_deltas"],
            [-3000, 3000, 2000, 0],
        )
        self.assertEqual(game["riichi_sticks"], 0)
        self.assertEqual(sum(game["scores"]), 100000)

    def test_repeated_settlement_does_not_pay_again(self):
        game = self.make_game("ron", [1], discarder=2)
        score = {
            "payments": calculate_points(1, 30)
        }

        with patch("main.get_winner_score", return_value=score):
            first = settle_win(game)
            before = deepcopy(game)
            second = settle_win(game)

        self.assertEqual(first, second)
        self.assertEqual(game, before)

        # Returned information must not mutate the stored settlement.
        second["score_deltas"][0] = 999
        self.assertEqual(game, before)

    def test_failed_calculation_does_not_change_balances(self):
        game = self.make_game("ron", [1, 2], discarder=0)
        game["riichi_sticks"] = 1
        before = deepcopy(game)

        score = {
            "payments": calculate_points(1, 30)
        }

        with patch(
            "main.get_winner_score",
            side_effect=[score, None],
        ):
            with self.assertRaises(ValueError):
                settle_win(game)

        self.assertEqual(game, before)

    def test_real_ron_flow_settles_automatically(self):
        game = create_ron_demo()
        before = list(game["scores"])

        declare_ron(game, game["human_player_index"])

        self.assertIsNotNone(game["settlement"])
        self.assertNotEqual(game["scores"], before)

        after = deepcopy(game)
        settle_win(game)

        self.assertEqual(game, after)


if __name__ == "__main__":
    unittest.main()