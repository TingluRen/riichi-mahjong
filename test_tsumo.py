import unittest
from copy import deepcopy

from main import (
    create_game,
    create_tiles,
    check_tile_counts,
    start_turn,
    can_tsumo,
    declare_tsumo,
    advance_until_human
)


WINNING_HAND = [
    "1m", "2m", "3m",
    "4p", "5p", "6p",
    "7s", "8s", "9s",
    "1z", "1z", "1z",
    "5z", "5z"
]


class TsumoTests(unittest.TestCase):
    def make_ready_game(self, player_index):
        game = create_game()
        pool = create_tiles()
        hands = [[] for _ in range(4)]

        # Reserve the player's starting hand.
        for tile in WINNING_HAND[:-1]:
            pool.remove(tile)
            hands[player_index].append(tile)

        # Reserve the winning draw before dealing other hands.
        winning_tile = WINNING_HAND[-1]
        pool.remove(winning_tile)

        # Deal 13 tiles to each other player.
        for index in range(4):
            if index != player_index:
                for _ in range(13):
                    hands[index].append(pool.pop(0))

        # Reserve a fresh dead wall from the remaining pool.
        game["dead_wall"] = pool[:14]
        game["wall"] = pool[14:]

        # pop() will draw the winning tile next.
        game["wall"].append(winning_tile)

        game["hands"] = hands
        game["current_player_index"] = player_index
        game["phase"] = "draw"

        check_tile_counts(game)

        return game

    def test_human_can_choose_tsumo(self):
        game = self.make_ready_game(0)
        advance_until_human(game)

        self.assertEqual(game["phase"], "discard")
        self.assertTrue(can_tsumo(game, 0))

        declare_tsumo(game, 0)

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["winner_index"], 0)
        self.assertEqual(game["end_reason"], "tsumo")
        self.assertEqual(len(game["hands"][0]), 14)
        self.assertEqual(game["discards"][0], [])

    def test_computer_automatically_wins(self):
        game = self.make_ready_game(1)
        advance_until_human(game)

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["winner_index"], 1)

    def test_wrong_player_cannot_win(self):
        game = self.make_ready_game(0)
        start_turn(game)
        before = deepcopy(game)

        with self.assertRaises(ValueError):
            declare_tsumo(game, 1)

        self.assertEqual(game, before)

    def test_cannot_win_before_drawing(self):
        game = self.make_ready_game(0)

        self.assertFalse(can_tsumo(game, 0))

        with self.assertRaises(ValueError):
            declare_tsumo(game, 0)


if __name__ == "__main__":
    unittest.main()