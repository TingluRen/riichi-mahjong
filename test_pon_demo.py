import unittest
from copy import deepcopy

from debug_scenarios import create_pon_demo
from main import (
    advance_until_human,
    check_tile_counts,
    declare_pon,
    finish_turn,
    pass_response,
)


class PonDemoTests(unittest.TestCase):
    def test_waiting_does_not_advance(self):
        game = create_pon_demo()
        before = deepcopy(game)

        advance_until_human(game)

        self.assertEqual(game, before)
        check_tile_counts(game)

    def test_pon_and_next_turn_preserve_tiles(self):
        game = create_pon_demo()
        check_tile_counts(game)

        self.assertTrue(declare_pon(game, 0))
        check_tile_counts(game)

        self.assertEqual(len(game["wall"]), 69)
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertEqual(game["discard_history"][1], ["5z"])

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
        game = create_pon_demo()

        pass_response(game, 0)
        advance_until_human(game)

        check_tile_counts(game)
        self.assertEqual(game["melds"][0], [])
        self.assertTrue(game["is_closed"][0])


if __name__ == "__main__":
    unittest.main()