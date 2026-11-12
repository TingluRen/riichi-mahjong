import unittest
from copy import deepcopy

from main import (
    create_game,
    count_dora,
    get_ura_dora_indicators,
    get_winner_ura_dora_indicators,
)


class UraDoraTests(unittest.TestCase):
    def make_game(self):
        game = create_game()

        # Use fixed indicators to make these tests deterministic.
        game["dead_wall"][5] = "3m"
        game["dead_wall"][7] = "4p"
        game["dead_wall"][9] = "7z"
        game["dora_indicator_count"] = 1

        return game

    def make_winning_game(self):
        game = self.make_game()
        game["phase"] = "ended"
        game["end_reason"] = "tsumo"
        game["winner_index"] = 0
        game["winner_indices"] = [0]
        game["riichi_declared"][0] = True

        return game

    def test_one_indicator(self):
        game = self.make_game()

        self.assertEqual(
            get_ura_dora_indicators(game),
            ["3m"]
        )

    def test_indicator_count_matches_visible_dora(self):
        game = self.make_game()
        game["dora_indicator_count"] = 3

        self.assertEqual(
            get_ura_dora_indicators(game),
            ["3m", "4p", "7z"]
        )

    def test_hidden_during_play(self):
        game = self.make_winning_game()
        game["phase"] = "discard"

        self.assertEqual(
            get_winner_ura_dora_indicators(game, 0),
            []
        )

    def test_winner_without_riichi_gets_none(self):
        game = self.make_winning_game()
        game["riichi_declared"][0] = False

        indicators = get_winner_ura_dora_indicators(game, 0)

        self.assertEqual(indicators, [])
        self.assertEqual(count_dora(["4m"], [], indicators), 0)

    def test_non_winner_gets_none(self):
        game = self.make_winning_game()
        game["riichi_declared"][1] = True

        self.assertEqual(
            get_winner_ura_dora_indicators(game, 1),
            []
        )

    def test_riichi_winner_can_count_ura_dora(self):
        game = self.make_winning_game()

        indicators = get_winner_ura_dora_indicators(game, 0)

        self.assertEqual(indicators, ["3m"])
        self.assertEqual(
            count_dora(["4m", "4m", "2p"], [], indicators),
            2
        )

    def test_checks_do_not_change_game(self):
        game = self.make_winning_game()
        before = deepcopy(game)

        get_ura_dora_indicators(game)
        get_winner_ura_dora_indicators(game, 0)

        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()