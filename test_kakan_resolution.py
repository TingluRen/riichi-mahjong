import unittest
from copy import deepcopy

from main import (
    create_game,
    declare_kakan,
    resolve_kakan_responses,
)


class KakanResolutionTests(unittest.TestCase):
    def make_game(self):
        game = create_game()
        game["current_player_index"] = 1
        game["phase"] = "discard"
        game["is_closed"][1] = False

        game["melds"][1] = [{
            "type": "pon",
            "tiles": ["6m"] * 3,
            "from_player_index": 2
        }]

        game["hands"][1] = [
            "1m", "4m", "7m",
            "1p", "4p", "7p",
            "1s", "4s", "7s",
            "6m", "2z"
        ]

        game["hands"][0] = [
            "1p", "2p", "3p",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "4m", "5m",
            "2z", "2z"
        ]

        declare_kakan(game, 1, 0)
        return game

    def test_robbery_keeps_pon_and_does_not_draw(self):
        game = self.make_game()
        wall_before = game["wall"].copy()
        dead_wall_before = game["dead_wall"].copy()

        resolve_kakan_responses(game, [0])

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["end_reason"], "chankan")
        self.assertEqual(game["winner_indices"], [0])
        self.assertEqual(game["robbed_kan_tile"], "6m")
        self.assertNotIn("6m", game["hands"][1])
        self.assertEqual(game["melds"][1][0]["type"], "pon")
        self.assertEqual(game["melds"][1][0]["tiles"], ["6m"] * 3)

        self.assertEqual(game["wall"], wall_before)
        self.assertEqual(game["dead_wall"], dead_wall_before)
        self.assertEqual(game["rinshan_draw_count"], 0)
        self.assertEqual(game["dora_indicator_count"], 1)
        self.assertIsNone(game["pending_kakan"])

    def test_no_winner_completes_upgrade(self):
        game = self.make_game()
        replacement = game["dead_wall"][0]
        wall_count = len(game["wall"])

        resolve_kakan_responses(game, [])

        self.assertEqual(game["phase"], "discard")
        self.assertEqual(game["current_player_index"], 1)
        self.assertEqual(game["melds"][1][0], {
            "type": "kakan",
            "tiles": ["6m"] * 4,
            "from_player_index": 2
        })
        self.assertEqual(len(game["hands"][1]), 11)
        self.assertEqual(game["hands"][1][-1], replacement)
        self.assertEqual(len(game["wall"]), wall_count - 1)
        self.assertEqual(len(game["dead_wall"]), 14)
        self.assertEqual(game["rinshan_draw_count"], 1)
        self.assertEqual(game["dora_indicator_count"], 2)
        self.assertTrue(game["temporary_furiten"][0])
        self.assertFalse(game["is_closed"][1])
        self.assertIsNone(game["pending_kakan"])

    def test_pass_after_riichi_causes_persistent_furiten(self):
        game = self.make_game()
        game["riichi_declared"][0] = True

        resolve_kakan_responses(game, [])

        self.assertTrue(game["riichi_furiten"][0])

    def test_invalid_winners_change_nothing(self):
        for winners in ([1], [0, 0]):
            with self.subTest(winners=winners):
                game = self.make_game()
                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    resolve_kakan_responses(game, winners)

                self.assertEqual(game, before)

    def test_cannot_resolve_twice(self):
        game = self.make_game()
        resolve_kakan_responses(game, [])
        before = deepcopy(game)

        with self.assertRaises(ValueError):
            resolve_kakan_responses(game, [])

        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()