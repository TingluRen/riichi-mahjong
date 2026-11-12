import unittest
from copy import deepcopy

from debug_scenarios import create_daiminkan_demo
from main import (
    advance_until_human,
    can_daiminkan,
    can_pon,
    can_ron,
    can_tsumo,
    check_tile_counts,
    declare_daiminkan,
    declare_pon,
    declare_tsumo,
    pass_response,
)


class DaiminkanDemoTests(unittest.TestCase):
    def test_demo_waits_for_human(self):
        game = create_daiminkan_demo()
        before = deepcopy(game)

        self.assertTrue(can_daiminkan(game, 0))
        self.assertTrue(can_pon(game, 0))
        self.assertFalse(can_ron(game, 0))

        advance_until_human(game)

        self.assertEqual(game, before)
        check_tile_counts(game)

    def test_kan_then_tsumo(self):
        game = create_daiminkan_demo()

        self.assertTrue(declare_daiminkan(game, 0))
        check_tile_counts(game)

        self.assertEqual(len(game["wall"]), 68)
        self.assertEqual(len(game["dead_wall"]), 14)
        self.assertEqual(game["hands"][0][-1], "1z")
        self.assertEqual(game["dora_indicator_count"], 2)
        self.assertFalse(game["is_closed"][0])
        self.assertTrue(can_tsumo(game, 0))

        declare_tsumo(game, 0)

        self.assertEqual(game["winner_indices"], [0])
        self.assertEqual(game["phase"], "ended")
        check_tile_counts(game)

    def test_pon_does_not_draw_replacement(self):
        game = create_daiminkan_demo()
        wall_before = game["wall"].copy()

        self.assertTrue(declare_pon(game, 0))

        self.assertEqual(game["wall"], wall_before)
        self.assertEqual(game["rinshan_draw_count"], 0)
        self.assertEqual(game["dora_indicator_count"], 1)
        self.assertEqual(game["hands"][0].count("5z"), 1)
        self.assertIn("5z", game["forbidden_discard_tiles"])
        self.assertEqual(game["melds"][0][0]["type"], "pon")

        check_tile_counts(game)

    def test_pass_keeps_hand_closed(self):
        game = create_daiminkan_demo()

        pass_response(game, 0)

        self.assertEqual(game["phase"], "draw")
        self.assertEqual(game["current_player_index"], 2)
        self.assertEqual(game["melds"][0], [])
        self.assertTrue(game["is_closed"][0])
        self.assertEqual(game["discards"][1], ["5z"])
        self.assertEqual(game["rinshan_draw_count"], 0)

        check_tile_counts(game)


if __name__ == "__main__":
    unittest.main()