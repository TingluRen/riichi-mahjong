import unittest
from copy import deepcopy

from main import (
    create_game,
    create_tiles,
    can_daiminkan,
    declare_daiminkan,
    can_tsumo,
    check_tile_counts,
    get_dora_indicators,
)


class DaiminkanTests(unittest.TestCase):
    def make_game(self):
        game = create_game()
        pool = create_tiles()

        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z",
            "5z", "5z", "5z"
        ]

        for tile in hand:
            pool.remove(tile)

        # Reserve the discard and winning replacement.
        pool.remove("5z")
        pool.remove("1z")

        hands = [hand, [], [], []]

        for index in (1, 2, 3):
            for _ in range(13):
                hands[index].append(pool.pop(0))

        game["hands"] = hands
        game["dead_wall"] = ["1z"] + pool[:13]
        game["wall"] = pool[13:]
        game["discards"][1] = ["5z"]
        game["discard_history"][1] = ["5z"]
        game["current_player_index"] = 1
        game["phase"] = "response"
        game["last_discard"] = {
            "player_index": 1,
            "tile": "5z"
        }

        # Isolate successful calls from computer Ron decisions.
        for index in (1, 2, 3):
            game["temporary_furiten"][index] = True

        check_tile_counts(game)
        return game

    def test_can_daiminkan(self):
        game = self.make_game()

        self.assertTrue(can_daiminkan(game, 0))
        self.assertFalse(can_daiminkan(game, 1))

    def test_call_preserves_tiles_and_draws_replacement(self):
        game = self.make_game()
        wall_count = len(game["wall"])

        self.assertTrue(declare_daiminkan(game, 0))

        self.assertEqual(game["melds"][0], [{
            "type": "daiminkan",
            "tiles": ["5z"] * 4,
            "from_player_index": 1
        }])
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertEqual(game["hands"][0][-1], "1z")
        self.assertEqual(game["discards"][1], [])
        self.assertEqual(game["discard_history"][1], ["5z"])
        self.assertEqual(len(game["wall"]), wall_count - 1)
        self.assertEqual(len(game["dead_wall"]), 14)
        self.assertEqual(game["rinshan_draw_count"], 1)
        self.assertEqual(len(get_dora_indicators(game)), 2)
        self.assertFalse(game["is_closed"][0])
        self.assertFalse(game["after_call"])
        self.assertEqual(game["phase"], "discard")
        self.assertEqual(game["current_player_index"], 0)

        # The White Dragon Kan supplies Yakuhai.
        self.assertTrue(can_tsumo(game, 0))
        check_tile_counts(game)

    def test_invalid_call_changes_nothing(self):
        for case in ("riichi", "empty_wall", "rinshan_limit"):
            with self.subTest(case=case):
                game = self.make_game()

                if case == "riichi":
                    game["riichi_declared"][0] = True
                elif case == "empty_wall":
                    game["wall"] = []
                else:
                    game["rinshan_draw_count"] = 4

                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    declare_daiminkan(game, 0)

                self.assertEqual(game, before)

    def test_missing_discard_changes_nothing(self):
        game = self.make_game()
        game["discards"][1] = []
        before = deepcopy(game)

        with self.assertRaises(ValueError):
            declare_daiminkan(game, 0)

        self.assertEqual(game, before)

    def test_computer_ron_takes_priority(self):
        game = self.make_game()

        # Isolated fixture for response priority.
        game["hands"][2] = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "6z", "6z", "6z",
            "5z"
        ]
        game["temporary_furiten"][2] = False

        hand_before = game["hands"][0].copy()
        wall_before = game["wall"].copy()

        self.assertFalse(declare_daiminkan(game, 0))

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["winner_indices"], [2])
        self.assertEqual(game["hands"][0], hand_before)
        self.assertEqual(game["wall"], wall_before)
        self.assertEqual(game["melds"][0], [])
        self.assertEqual(game["discards"][1], ["5z"])
        self.assertEqual(game["rinshan_draw_count"], 0)


if __name__ == "__main__":
    unittest.main()