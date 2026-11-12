import unittest
from copy import deepcopy
from unittest.mock import patch

from main import create_game, settle_win
from scoring import calculate_points


class HonbaSettlementTests(unittest.TestCase):
    def make_game(self, reason, winners, discarder=None):
        game = create_game()
        game["phase"] = "ended"
        game["end_reason"] = reason
        game["winner_indices"] = list(winners)
        game["winner_index"] = winners[0]
        game["winning_discarder_index"] = discarder
        game["honba"] = 2
        return game

    def test_ron_adds_300_per_honba(self):
        game = self.make_game("ron", [1], discarder=2)
        score = {"payments": calculate_points(1, 30)}

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [0, 1600, -1600, 0],
        )
        self.assertEqual(
            result["honba_awards"],
            [0, 600, 0, 0],
        )
        self.assertEqual(result["honba"], 2)

    def test_non_dealer_tsumo_adds_100_per_payer(self):
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
            [-900, 2100, -600, -600],
        )
        self.assertEqual(result["honba_awards"][1], 600)

    def test_dealer_tsumo(self):
        game = self.make_game("tsumo", [0])
        score = {
            "payments": calculate_points(
                2, 20, is_tsumo=True, is_dealer=True
            )
        }

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [2700, -900, -900, -900],
        )
        self.assertEqual(result["honba_awards"][0], 600)

    def test_chankan_uses_ron_honba(self):
        game = self.make_game("chankan", [1], discarder=3)
        score = {"payments": calculate_points(2, 30)}

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [0, 2600, 0, -2600],
        )

    def test_multiple_ron_each_receives_honba(self):
        game = self.make_game("ron", [1, 2], discarder=0)
        scores = {
            1: {"payments": calculate_points(1, 30)},
            2: {"payments": calculate_points(2, 30)},
        }

        with patch(
            "main.get_winner_score",
            side_effect=lambda game, index: scores[index],
        ):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [-4200, 1600, 2600, 0],
        )
        self.assertEqual(
            result["honba_awards"],
            [0, 600, 600, 0],
        )
        self.assertEqual(sum(game["scores"]), 100000)

    def test_riichi_award_is_separate_and_not_paid_twice(self):
        game = self.make_game("ron", [1], discarder=2)
        game["scores"][0] -= 1000
        game["riichi_sticks"] = 1
        score = {"payments": calculate_points(1, 30)}

        with patch("main.get_winner_score", return_value=score):
            first = settle_win(game)
            before = deepcopy(game)
            second = settle_win(game)

        self.assertEqual(
            first["score_deltas"],
            [0, 2600, -1600, 0],
        )
        self.assertEqual(first["honba_awards"][1], 600)
        self.assertEqual(first["riichi_award"], 1000)
        self.assertEqual(first, second)
        self.assertEqual(game, before)
        self.assertEqual(sum(game["scores"]), 100000)

    def test_zero_honba_preserves_base_payments(self):
        game = self.make_game("ron", [1], discarder=2)
        game["honba"] = 0
        score = {"payments": calculate_points(1, 30)}

        with patch("main.get_winner_score", return_value=score):
            result = settle_win(game)

        self.assertEqual(
            result["score_deltas"],
            [0, 1000, -1000, 0],
        )
        self.assertEqual(result["honba_awards"], [0, 0, 0, 0])

    def test_invalid_honba_changes_nothing(self):
        for honba in (-1, True, 1.5):
            with self.subTest(honba=honba):
                game = self.make_game("ron", [1], discarder=2)
                game["honba"] = honba
                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    settle_win(game)

                self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()