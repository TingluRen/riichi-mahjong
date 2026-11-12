import unittest
from copy import deepcopy

from main import (
    create_game,
    create_tiles,
    declare_ankan,
    finish_turn,
    get_dora_indicators,
    check_tile_counts,
    can_tsumo,
)


class AnkanTests(unittest.TestCase):
    def make_game(self):
        game = create_game()
        pool = create_tiles()

        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z",
            "5z", "5z", "5z", "5z"
        ]

        for tile in hand:
            pool.remove(tile)

        # Reserve a winning replacement tile.
        pool.remove("1z")

        hands = [hand, [], [], []]

        for player_index in (1, 2, 3):
            for _ in range(13):
                hands[player_index].append(pool.pop(0))

        game["hands"] = hands

        # Slot 0 is the first replacement tile.
        game["dead_wall"] = ["1z"] + pool[:13]
        game["wall"] = pool[13:]

        game["current_player_index"] = 0
        game["phase"] = "discard"

        check_tile_counts(game)

        return game

    def test_ankan_and_replacement_preserve_tiles(self):
        game = self.make_game()
        wall_count = len(game["wall"])
        indicator_slots = [
            game["dead_wall"][index]
            for index in (4, 6, 8, 10, 12)
        ]

        drawn_tile = declare_ankan(game, 0, "5z")

        self.assertEqual(drawn_tile, "1z")
        self.assertEqual(game["hands"][0][-1], "1z")
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertNotIn("5z", game["hands"][0])

        self.assertEqual(game["melds"][0], [{
            "type": "ankan",
            "tiles": ["5z"] * 4
        }])

        self.assertEqual(len(game["wall"]), wall_count - 1)
        self.assertEqual(len(game["dead_wall"]), 14)
        self.assertEqual(game["rinshan_draw_count"], 1)
        self.assertEqual(game["dora_indicator_count"], 2)
        self.assertEqual(
            get_dora_indicators(game),
            indicator_slots[:2]
        )

        check_tile_counts(game)

    def test_ankan_keeps_closed_status_and_current_turn(self):
        game = self.make_game()

        declare_ankan(game, 0, "5z")

        self.assertTrue(game["is_closed"][0])
        self.assertEqual(game["current_player_index"], 0)
        self.assertEqual(game["phase"], "discard")
        self.assertFalse(game["after_call"])
        self.assertEqual(game["forbidden_discard_tiles"], [])

    def test_replacement_can_complete_tsumo(self):
        game = self.make_game()

        declare_ankan(game, 0, "5z")

        self.assertTrue(can_tsumo(game, 0))

    def test_player_can_discard_after_ankan(self):
        game = self.make_game()

        declare_ankan(game, 0, "5z")

        # Declining Tsumo and discarding is still possible.
        tile = finish_turn(game, 0, len(game["hands"][0]) - 1)

        self.assertEqual(tile, "1z")
        self.assertEqual(len(game["hands"][0]), 10)
        self.assertEqual(game["phase"], "response")

        check_tile_counts(game)

    def test_invalid_ankan_changes_nothing(self):
        for case in ("missing_quad", "riichi", "bad_dead_wall"):
            with self.subTest(case=case):
                game = self.make_game()
                tile = "5z"

                if case == "missing_quad":
                    tile = "1m"
                elif case == "riichi":
                    game["riichi_declared"][0] = True
                else:
                    game["dead_wall"].pop()

                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    declare_ankan(game, 0, tile)

                self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()