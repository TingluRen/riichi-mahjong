import unittest
from copy import deepcopy

from main import (
    create_game,
    create_tiles,
    finish_turn,
    start_turn,
    can_ron,
    declare_ron,
    pass_ron,
    advance_until_human
)


class RonTests(unittest.TestCase):
    def make_ron_game(self):
        game = create_game()
        pool = create_tiles()

        # Human waits on 5z, with an East triplet as Yakuhai.
        human_hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z"
        ]

        for tile in human_hand:
            pool.remove(tile)

        # Reserve the tile Player 2 will discard.
        pool.remove("5z")

        hands = [human_hand, [], [], []]

        for index in (1, 2, 3):
            for _ in range(13):
                hands[index].append(pool.pop(0))

        hands[1].append("5z")

        game["hands"] = hands
        game["discards"] = [[] for _ in range(4)]
        game["dead_wall"] = pool[:14]
        game["wall"] = pool[14:]
        game["current_player_index"] = 1
        game["phase"] = "discard"

        finish_turn(game, 1, 13)

        return game

    def test_human_can_ron(self):
        game = self.make_ron_game()

        self.assertEqual(game["phase"], "response")
        self.assertTrue(can_ron(game, 0))
        self.assertFalse(can_ron(game, 1))

    def test_waiting_for_human_does_not_advance(self):
        game = self.make_ron_game()
        before = deepcopy(game)

        advance_until_human(game)

        self.assertEqual(game, before)

    def test_declare_ron(self):
        game = self.make_ron_game()
        hand_before = game["hands"][0].copy()

        declare_ron(game, 0)

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["end_reason"], "ron")
        self.assertEqual(game["winner_indices"], [0])

        # The physical winning tile stays in the discard pile.
        self.assertEqual(game["hands"][0], hand_before)
        self.assertEqual(game["discards"][1], ["5z"])

    def test_pass_causes_temporary_furiten(self):
        game = self.make_ron_game()

        pass_ron(game, 0)

        self.assertTrue(game["temporary_furiten"][0])
        self.assertEqual(game["phase"], "draw")
        self.assertEqual(game["current_player_index"], 2)

    def test_temporary_furiten_blocks_ron(self):
        game = self.make_ron_game()
        game["temporary_furiten"][0] = True

        self.assertFalse(can_ron(game, 0))

    def test_own_discard_blocks_ron(self):
        game = self.make_ron_game()

        # Move a real copy from the wall into the human's discards.
        game["wall"].remove("5z")
        game["discards"][0].append("5z")
        game["discard_history"][0].append("5z")

        self.assertFalse(can_ron(game, 0))

    def test_drawing_clears_temporary_furiten(self):
        game = self.make_ron_game()
        game["temporary_furiten"][0] = True
        game["current_player_index"] = 0
        game["phase"] = "draw"

        start_turn(game)

        self.assertFalse(game["temporary_furiten"][0])

    def test_last_discard_can_still_be_claimed(self):
        game = self.make_ron_game()
        game["wall"] = []

        advance_until_human(game)

        self.assertEqual(game["phase"], "response")
        self.assertTrue(can_ron(game, 0))

        declare_ron(game, 0)

        self.assertEqual(game["end_reason"], "ron")

    def test_passing_last_discard_ends_round(self):
        game = self.make_ron_game()

        # An earlier simple discard prevents Nagashi Mangan.
        tile = next(
            tile for tile in game["wall"]
            if tile[1] in ("m", "p", "s")
            and tile[0] in "2345678"
        )
        game["wall"].remove(tile)
        game["discards"][1].insert(0, tile)
        game["discard_history"][1].insert(0, tile)

        # Simulate the final discard with no live tiles remaining.
        game["wall"] = []

        pass_ron(game, 0)

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["end_reason"], "exhaustive_draw")


if __name__ == "__main__":
    unittest.main()