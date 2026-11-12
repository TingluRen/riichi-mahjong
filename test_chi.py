import unittest
from copy import deepcopy

from main import (
    create_game,
    declare_chi,
    finish_turn,
    can_tsumo,
    can_riichi,
)


class ChiTests(unittest.TestCase):
    def make_game(self):
        game = create_game()

        game["hands"][0] = [
            "1m", "2m", "3m", "4m",
            "1p", "4p", "7p",
            "1s", "4s", "7s",
            "1z", "2z", "3z"
        ]

        # Isolate Chi behavior from computer Ron decisions.
        for index in (1, 2, 3):
            game["temporary_furiten"][index] = True

        game["current_player_index"] = 3
        game["phase"] = "response"
        game["last_discard"] = {
            "player_index": 3,
            "tile": "1m"
        }
        game["discards"][3] = ["1m"]
        game["discard_history"][3] = ["1m"]

        return game

    def test_chi_moves_tiles_without_drawing(self):
        game = self.make_game()
        wall_before = game["wall"].copy()

        self.assertTrue(declare_chi(game, 0, 0))

        self.assertEqual(game["wall"], wall_before)
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertNotIn("2m", game["hands"][0])
        self.assertNotIn("3m", game["hands"][0])

        self.assertEqual(game["melds"][0], [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3
        }])

        self.assertEqual(game["discards"][3], [])
        self.assertEqual(game["discard_history"][3], ["1m"])
        self.assertEqual(game["current_player_index"], 0)
        self.assertEqual(game["phase"], "discard")
        self.assertTrue(game["after_call"])
        self.assertFalse(game["is_closed"][0])
        self.assertFalse(can_tsumo(game, 0))
        self.assertFalse(can_riichi(game, 0))

    def test_forbidden_discards_do_not_change_game(self):
        for tile in ("1m", "4m"):
            with self.subTest(tile=tile):
                game = self.make_game()
                declare_chi(game, 0, 0)

                tile_index = game["hands"][0].index(tile)
                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    finish_turn(game, 0, tile_index)

                self.assertEqual(game, before)

    def test_legal_discard_clears_call_restrictions(self):
        game = self.make_game()
        declare_chi(game, 0, 0)

        tile_index = game["hands"][0].index("1p")
        discarded = finish_turn(game, 0, tile_index)

        self.assertEqual(discarded, "1p")
        self.assertEqual(len(game["hands"][0]), 10)
        self.assertFalse(game["after_call"])
        self.assertEqual(game["forbidden_discard_tiles"], [])
        self.assertEqual(game["phase"], "response")

    def test_invalid_option_changes_nothing(self):
        for option_index in (-1, 99, True, "0"):
            with self.subTest(option_index=option_index):
                game = self.make_game()
                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    declare_chi(game, 0, option_index)

                self.assertEqual(game, before)

    def test_wrong_discarder_changes_nothing(self):
        game = self.make_game()
        game["last_discard"]["player_index"] = 1
        before = deepcopy(game)

        with self.assertRaises(ValueError):
            declare_chi(game, 0, 0)

        self.assertEqual(game, before)

    def test_computer_ron_takes_priority(self):
        game = self.make_game()

        game["temporary_furiten"][1] = False
        game["hands"][1] = [
            "2p", "3p", "4p",
            "6s", "7s", "8s",
            "5z", "5z", "5z",
            "6z", "6z", "6z",
            "1m"
        ]

        hand_before = game["hands"][0].copy()

        self.assertFalse(declare_chi(game, 0, 0))

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["end_reason"], "ron")
        self.assertEqual(game["winner_indices"], [1])
        self.assertEqual(game["hands"][0], hand_before)
        self.assertEqual(game["melds"][0], [])
        self.assertEqual(game["discards"][3], ["1m"])


if __name__ == "__main__":
    unittest.main()