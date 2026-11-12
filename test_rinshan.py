import unittest
from copy import deepcopy

from main import (
    create_game,
    create_tiles,
    draw_rinshan_tile,
    get_dora_indicators,
    check_tile_counts,
)


class RinshanTests(unittest.TestCase):
    def make_game(self):
        game = create_game()
        pool = create_tiles()

        # Simulate a declared Ankan before its replacement draw.
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z"
        ]
        kan_tiles = ["5z"] * 4

        for tile in hand + kan_tiles:
            pool.remove(tile)

        hands = [hand, [], [], []]

        for player_index in (1, 2, 3):
            for _ in range(13):
                hands[player_index].append(pool.pop(0))

        game["hands"] = hands
        game["melds"][0] = [{
            "type": "ankan",
            "tiles": kan_tiles
        }]
        game["dead_wall"] = pool[:14]
        game["wall"] = pool[14:]
        game["current_player_index"] = 0
        game["phase"] = "discard"

        check_tile_counts(game)

        return game

    def test_draw_preserves_physical_tiles(self):
        game = self.make_game()
        expected_tile = game["dead_wall"][0]
        incoming_tile = game["wall"][0]
        wall_count = len(game["wall"])
        indicators_before = get_dora_indicators(game)

        tile = draw_rinshan_tile(game, 0)

        self.assertEqual(tile, expected_tile)
        self.assertEqual(game["hands"][0][-1], expected_tile)
        self.assertEqual(len(game["hands"][0]), 11)
        self.assertEqual(game["dead_wall"][0], incoming_tile)
        self.assertEqual(len(game["dead_wall"]), 14)
        self.assertEqual(len(game["wall"]), wall_count - 1)
        self.assertEqual(game["rinshan_draw_count"], 1)
        self.assertEqual(get_dora_indicators(game), indicators_before)

        check_tile_counts(game)

    def test_next_slot_is_used(self):
        game = self.make_game()
        game["rinshan_draw_count"] = 1
        expected_tile = game["dead_wall"][1]

        tile = draw_rinshan_tile(game, 0)

        self.assertEqual(tile, expected_tile)
        self.assertEqual(game["rinshan_draw_count"], 2)
        check_tile_counts(game)

    def test_invalid_draw_changes_nothing(self):
        cases = ("wrong_player", "wrong_phase", "empty_wall", "limit")

        for case in cases:
            with self.subTest(case=case):
                game = self.make_game()
                player_index = 0

                if case == "wrong_player":
                    player_index = 1
                elif case == "wrong_phase":
                    game["phase"] = "response"
                elif case == "empty_wall":
                    game["wall"] = []
                else:
                    game["rinshan_draw_count"] = 4

                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    draw_rinshan_tile(game, player_index)

                self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()