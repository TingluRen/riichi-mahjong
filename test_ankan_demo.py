import unittest

from debug_scenarios import create_ankan_demo
from main import (
    check_tile_counts,
    get_ankan_options,
    declare_ankan,
    get_dora_indicators,
    can_tsumo,
    declare_tsumo,
)


class AnkanDemoTests(unittest.TestCase):
    def test_demo_offers_ankan(self):
        game = create_ankan_demo()

        check_tile_counts(game)

        self.assertEqual(get_ankan_options(game, 0), ["5z"])
        self.assertEqual(len(game["wall"]), 69)
        self.assertEqual(len(game["hands"][0]), 14)
        self.assertEqual(len(get_dora_indicators(game)), 1)
        self.assertFalse(can_tsumo(game, 0))

    def test_ankan_then_tsumo_preserves_tiles(self):
        game = create_ankan_demo()

        self.assertEqual(declare_ankan(game, 0, "5z"), "1z")

        check_tile_counts(game)

        self.assertEqual(len(game["wall"]), 68)
        self.assertEqual(len(game["dead_wall"]), 14)
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertEqual(len(get_dora_indicators(game)), 2)
        self.assertTrue(game["is_closed"][0])
        self.assertTrue(can_tsumo(game, 0))

        declare_tsumo(game, 0)

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["winner_indices"], [0])
        self.assertEqual(game["end_reason"], "tsumo")

        check_tile_counts(game)


if __name__ == "__main__":
    unittest.main()