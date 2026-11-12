import unittest
from copy import deepcopy

from main import (
    create_game,
    can_pon,
    declare_pon,
    can_tsumo,
    can_riichi,
    finish_turn,
)


class PonTests(unittest.TestCase):
    def make_game(self):
        game = create_game()

        # A deliberately scattered hand with two White Dragons.
        game["hands"][0] = [
            "1m", "2m", "4m", "5m", "7m", "8m",
            "1p", "4p", "7p", "1s", "4s",
            "5z", "5z"
        ]

        # Keep computers out of Ron contention in this fixture.
        for index in (1, 2, 3):
            game["temporary_furiten"][index] = True

        game["discards"][1] = ["5z"]
        game["discard_history"][1] = ["5z"]
        game["last_discard"] = {
            "player_index": 1,
            "tile": "5z"
        }
        game["current_player_index"] = 1
        game["phase"] = "response"

        return game

    def test_can_pon(self):
        game = self.make_game()

        self.assertTrue(can_pon(game, 0))
        self.assertFalse(can_pon(game, 1))

    def test_riichi_blocks_pon(self):
        game = self.make_game()
        game["riichi_declared"][0] = True

        self.assertFalse(can_pon(game, 0))

    def test_final_discard_cannot_be_called(self):
        game = self.make_game()
        game["wall"] = []

        self.assertFalse(can_pon(game, 0))

    def test_pon_moves_tiles_without_drawing(self):
        game = self.make_game()
        wall_before = game["wall"].copy()

        self.assertTrue(declare_pon(game, 0))

        self.assertEqual(game["wall"], wall_before)
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertEqual(game["hands"][0].count("5z"), 0)
        self.assertEqual(game["discards"][1], [])
        self.assertEqual(game["discard_history"][1], ["5z"])
        self.assertEqual(game["melds"][0], [{
            "type": "pon",
            "tiles": ["5z", "5z", "5z"],
            "from_player_index": 1
        }])
        self.assertEqual(game["current_player_index"], 0)
        self.assertEqual(game["phase"], "discard")
        self.assertFalse(game["is_closed"][0])
        self.assertFalse(can_riichi(game, 0))
        self.assertFalse(can_tsumo(game, 0))

        finish_turn(game, 0, 0)

        self.assertEqual(len(game["hands"][0]), 10)
        self.assertEqual(game["phase"], "response")
        self.assertFalse(game["after_call"])

    def test_invalid_pon_changes_nothing(self):
        game = self.make_game()
        game["phase"] = "draw"
        original = deepcopy(game)

        with self.assertRaises(ValueError):
            declare_pon(game, 0)

        self.assertEqual(game, original)

    def test_same_tile_discard_is_rejected(self):
        game = self.make_game()
        game["hands"][0][0] = "5z"

        declare_pon(game, 0)

        tile_index = game["hands"][0].index("5z")
        original = deepcopy(game)

        with self.assertRaises(ValueError):
            finish_turn(game, 0, tile_index)

        self.assertEqual(game, original)


if __name__ == "__main__":
    unittest.main()