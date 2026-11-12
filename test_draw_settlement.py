import unittest
from copy import deepcopy

from main import (
    create_game,
    start_turn,
    settle_exhaustive_draw,
)


TENPAI_HAND = [
    "1m", "2m", "3m",
    "4p", "5p", "6p",
    "7s", "8s", "9s",
    "1z", "1z", "1z",
    "5z",
]

NOTEN_HAND = [
    "1m", "4m", "7m",
    "1p", "4p", "7p",
    "1s", "4s", "7s",
    "1z", "2z", "3z", "4z",
]


class DrawSettlementTests(unittest.TestCase):
    def make_game(self, flags):
        game = create_game()
        game["wall"] = []
        game["phase"] = "ended"
        game["end_reason"] = "exhaustive_draw"
        game["winner_indices"] = []
        game["winner_index"] = None
        game["melds"] = [[] for _ in range(4)]
        game["hands"] = [
            list(TENPAI_HAND if flag else NOTEN_HAND)
            for flag in flags
        ]

        return game

    def test_all_tenpai_counts(self):
        cases = [
            ([False, False, False, False], [0, 0, 0, 0]),
            ([True, False, False, False], [3000, -1000, -1000, -1000]),
            ([True, True, False, False], [1500, 1500, -1500, -1500]),
            ([True, True, True, False], [1000, 1000, 1000, -3000]),
            ([True, True, True, True], [0, 0, 0, 0]),
        ]

        for flags, expected in cases:
            with self.subTest(flags=flags):
                game = self.make_game(flags)
                result = settle_exhaustive_draw(game)

                self.assertEqual(result["tenpai_flags"], flags)
                self.assertEqual(result["score_deltas"], expected)
                self.assertEqual(sum(result["score_deltas"]), 0)
                self.assertEqual(sum(game["scores"]), 100000)

    def test_riichi_pool_stays_on_table(self):
        game = self.make_game([True, False, False, False])
        game["scores"][0] -= 1000
        game["riichi_sticks"] = 1

        result = settle_exhaustive_draw(game)

        self.assertEqual(game["riichi_sticks"], 1)
        self.assertEqual(result["riichi_award"], 0)
        self.assertIsNone(result["riichi_recipient"])
        self.assertEqual(
            sum(game["scores"]) + game["riichi_sticks"] * 1000,
            100000,
        )

    def test_furiten_does_not_block_tenpai(self):
        game = self.make_game([True, False, False, False])
        game["discard_history"][0] = ["5z"]
        game["temporary_furiten"][0] = True
        game["riichi_furiten"][0] = True

        result = settle_exhaustive_draw(game)

        self.assertTrue(result["tenpai_flags"][0])
        self.assertEqual(result["score_deltas"][0], 3000)

    def test_open_hand_tenpai(self):
        game = self.make_game([False, False, False, False])

        game["hands"][0] = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z",
        ]
        game["melds"][0] = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]
        game["is_closed"][0] = False

        result = settle_exhaustive_draw(game)

        self.assertTrue(result["tenpai_flags"][0])
        self.assertEqual(result["score_deltas"][0], 3000)

    def test_no_yaku_is_still_tenpai(self):
        game = self.make_game([False, False, False, False])

        game["hands"][0] = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "2m", "3m", "4m",
            "5z",
        ]
        game["melds"][0] = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]
        game["is_closed"][0] = False

        result = settle_exhaustive_draw(game)

        self.assertTrue(result["tenpai_flags"][0])

    def test_repeated_settlement_is_safe(self):
        game = self.make_game([True, False, False, False])

        first = settle_exhaustive_draw(game)
        before = deepcopy(game)
        second = settle_exhaustive_draw(game)

        self.assertEqual(first, second)
        self.assertEqual(game, before)

        second["tenpai_flags"][0] = False
        self.assertEqual(game, before)

    def test_start_turn_settles_empty_wall(self):
        game = self.make_game([True, False, False, False])
        game["phase"] = "draw"
        game["end_reason"] = None

        start_turn(game)

        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["end_reason"], "exhaustive_draw")
        self.assertIsNotNone(game["settlement"])
        self.assertEqual(game["scores"][0], 28000)

    def test_invalid_phase_does_not_change_game(self):
        game = self.make_game([True, False, False, False])
        game["phase"] = "response"
        before = deepcopy(game)

        with self.assertRaises(ValueError):
            settle_exhaustive_draw(game)

        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()