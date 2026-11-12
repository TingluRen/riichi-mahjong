import unittest
from copy import deepcopy

from debug_scenarios import create_kakan_demo, create_chankan_demo
from main import (
    advance_until_human,
    can_chankan,
    can_tsumo,
    check_tile_counts,
    declare_kakan,
    declare_chankan,
    pass_chankan,
)


class KakanDemoTests(unittest.TestCase):
    def test_kakan_completes_and_preserves_tiles(self):
        game = create_kakan_demo()
        check_tile_counts(game)

        declare_kakan(game, 0, 0)

        self.assertEqual(game["phase"], "kakan_response")
        check_tile_counts(game)

        advance_until_human(game)

        self.assertEqual(game["phase"], "discard")
        self.assertEqual(game["melds"][0][0]["type"], "kakan")
        self.assertEqual(game["hands"][0][-1], "1z")
        self.assertEqual(len(game["wall"]), 68)
        self.assertEqual(game["dora_indicator_count"], 2)
        self.assertTrue(can_tsumo(game, 0))

        check_tile_counts(game)

    def test_chankan_waits_for_human(self):
        game = create_chankan_demo()
        before = deepcopy(game)

        self.assertTrue(can_chankan(game, 0))

        advance_until_human(game)

        self.assertEqual(game, before)
        check_tile_counts(game)

    def test_robbery_preserves_tiles_without_replacement(self):
        game = create_chankan_demo()

        declare_chankan(game, 0)

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["end_reason"], "chankan")
        self.assertEqual(game["winner_indices"], [0])
        self.assertEqual(game["robbed_kan_tile"], "6m")
        self.assertEqual(game["melds"][1][0]["type"], "pon")
        self.assertEqual(len(game["wall"]), 69)
        self.assertEqual(game["rinshan_draw_count"], 0)
        self.assertEqual(game["dora_indicator_count"], 1)

        check_tile_counts(game)

    def test_pass_completes_kakan_and_causes_furiten(self):
        game = create_chankan_demo()

        # Check immediately after Pass, before automatic turn advancement.
        pass_chankan(game, 0)

        self.assertEqual(game["phase"], "discard")
        self.assertEqual(game["current_player_index"], 1)
        self.assertEqual(game["melds"][1][0]["type"], "kakan")
        self.assertTrue(game["temporary_furiten"][0])
        self.assertEqual(len(game["wall"]), 68)
        self.assertEqual(game["rinshan_draw_count"], 1)
        self.assertEqual(game["dora_indicator_count"], 2)

        check_tile_counts(game)


if __name__ == "__main__":
    unittest.main()