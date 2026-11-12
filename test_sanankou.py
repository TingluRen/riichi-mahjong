import unittest
from copy import deepcopy

from main import create_game, can_ron, can_tsumo, get_winner_yaku
from yaku import get_win_yaku


class SanankouTests(unittest.TestCase):
    def make_hand(self):
        return (
            ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["5z"] * 2
        )

    def make_melds(self):
        return [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

    def evaluate(self, winning_tile, is_tsumo):
        return get_win_yaku(
            self.make_hand(),
            melds=self.make_melds(),
            is_closed=False,
            winning_tile=winning_tile,
            is_tsumo=is_tsumo,
        )

    def test_tsumo_completed_triplet_counts_as_concealed(self):
        self.assertIn("Sanankou", self.evaluate("7s", True))

    def test_ron_completed_triplet_is_not_concealed(self):
        self.assertNotIn("Sanankou", self.evaluate("7s", False))

    def test_ron_completed_pair_preserves_three_triplets(self):
        self.assertIn("Sanankou", self.evaluate("5z", False))

    def test_ankan_counts_as_concealed(self):
        hand = ["6s"] * 3 + ["7s"] * 3 + ["5z"] * 2
        melds = self.make_melds() + [{
            "type": "ankan",
            "tiles": ["4p"] * 4,
        }]

        yaku = get_win_yaku(
            hand,
            melds=melds,
            is_closed=False,
            winning_tile="5z",
        )

        self.assertIn("Sanankou", yaku)

    def test_open_kans_do_not_count_as_concealed(self):
        hand = ["6s"] * 3 + ["7s"] * 3 + ["5z"] * 2

        for kan_type in ("daiminkan", "kakan"):
            with self.subTest(kan_type=kan_type):
                melds = self.make_melds() + [{
                    "type": kan_type,
                    "tiles": ["4p"] * 4,
                    "from_player_index": 1,
                }]

                yaku = get_win_yaku(
                    hand,
                    melds=melds,
                    is_closed=False,
                    winning_tile="5z",
                )

                self.assertNotIn("Sanankou", yaku)

    def make_game(self):
        game = create_game()
        game["melds"][0] = self.make_melds()
        game["is_closed"][0] = False
        game["discards"][0] = []
        game["discard_history"][0] = []
        game["temporary_furiten"][0] = False
        game["riichi_furiten"][0] = False
        game["riichi_declared"][0] = False
        return game

    def test_ron_eligibility_uses_winning_tile(self):
        for tile, expected in (("5z", True), ("7s", False)):
            with self.subTest(tile=tile):
                game = self.make_game()
                hand = self.make_hand()
                hand.remove(tile)

                game["hands"][0] = hand
                game["phase"] = "response"
                game["current_player_index"] = 1
                game["last_discard"] = {
                    "player_index": 1,
                    "tile": tile,
                }

                self.assertEqual(can_ron(game, 0), expected)

    def test_tsumo_and_winner_display_use_context(self):
        game = self.make_game()
        hand = self.make_hand()
        hand.remove("7s")
        hand.append("7s")

        game["hands"][0] = hand
        game["phase"] = "discard"
        game["current_player_index"] = 0
        game["after_call"] = False

        self.assertTrue(can_tsumo(game, 0))

        game["phase"] = "ended"
        game["end_reason"] = "tsumo"
        game["winner_index"] = 0
        game["winner_indices"] = [0]

        self.assertIn("Sanankou", get_winner_yaku(game, 0))

    def test_inputs_are_not_modified(self):
        hand = self.make_hand()
        melds = self.make_melds()
        before = deepcopy((hand, melds))

        get_win_yaku(
            hand,
            melds=melds,
            is_closed=False,
            winning_tile="5z",
        )

        self.assertEqual((hand, melds), before)


if __name__ == "__main__":
    unittest.main()