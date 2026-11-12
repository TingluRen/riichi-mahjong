import unittest
from copy import deepcopy

from debug_scenarios import create_chi_demo
from main import (
    advance_until_human,
    check_tile_counts,
    declare_chi,
    finish_turn,
    get_chi_options,
    pass_response,
)


class ChiDemoTests(unittest.TestCase):
    def test_waiting_does_not_advance(self):
        game = create_chi_demo()
        before = deepcopy(game)

        advance_until_human(game)

        self.assertEqual(game, before)
        check_tile_counts(game)

    def test_each_option_preserves_tiles(self):
        for option_index in range(3):
            with self.subTest(option_index=option_index):
                game = create_chi_demo()
                option = get_chi_options(game, 0)[option_index]

                self.assertTrue(declare_chi(game, 0, option_index))
                check_tile_counts(game)

                self.assertEqual(len(game["wall"]), 69)
                self.assertEqual(len(game["hands"][0]), 11)
                self.assertEqual(
                    game["melds"][0][0]["tiles"],
                    option["tiles"]
                )
                self.assertEqual(game["discards"][3], [])
                self.assertEqual(game["discard_history"][3], ["3m"])

    def test_call_and_next_turn_preserve_tiles(self):
        game = create_chi_demo()
        declare_chi(game, 0, 2)

        self.assertIn("6m", game["forbidden_discard_tiles"])

        tile_index = game["hands"][0].index("1m")
        finish_turn(game, 0, tile_index)
        check_tile_counts(game)

        advance_until_human(game)
        check_tile_counts(game)

        self.assertEqual(game["phase"], "discard")
        self.assertEqual(game["current_player_index"], 0)
        self.assertEqual(len(game["wall"]), 65)
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertEqual(game["hands"][0][-1], "2s")

    def test_pass_keeps_hand_closed(self):
        game = create_chi_demo()

        pass_response(game, 0)
        advance_until_human(game)

        check_tile_counts(game)
        self.assertTrue(game["is_closed"][0])
        self.assertEqual(game["melds"][0], [])
        self.assertEqual(game["phase"], "discard")
        self.assertEqual(game["current_player_index"], 0)
        self.assertEqual(len(game["wall"]), 68)
        self.assertEqual(len(game["hands"][0]), 14)


if __name__ == "__main__":
    unittest.main()