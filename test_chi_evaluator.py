import unittest
from copy import deepcopy

from hand_evaluator import is_complete_hand, get_waiting_tiles


class ChiEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.hand = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z", "5z",
            "1z", "1z"
        ]

        self.melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3
        }]

    def test_complete_hand_with_chi(self):
        self.assertTrue(
            is_complete_hand(self.hand, self.melds)
        )

    def test_waiting_tiles_with_chi(self):
        self.assertEqual(
            get_waiting_tiles(self.hand[:-1], self.melds),
            ["1z"]
        )

    def test_unsorted_sequence_is_valid(self):
        self.melds[0]["tiles"] = ["3m", "1m", "2m"]

        self.assertTrue(
            is_complete_hand(self.hand, self.melds)
        )

    def test_invalid_sequences(self):
        invalid_sequences = [
            ["1m", "2m", "4m"],
            ["1m", "2m", "3p"],
            ["1z", "2z", "3z"],
            ["2m", "2m", "3m"],
            ["8m", "9m", "1m"],
        ]

        for tiles in invalid_sequences:
            with self.subTest(tiles=tiles):
                melds = [{"type": "chi", "tiles": tiles}]

                self.assertFalse(
                    is_complete_hand(self.hand, melds)
                )
                self.assertEqual(
                    get_waiting_tiles(self.hand[:-1], melds),
                    []
                )

    def test_mixed_chi_and_pon(self):
        hand = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z"
        ]

        melds = self.melds + [{
            "type": "pon",
            "tiles": ["5z", "5z", "5z"],
            "from_player_index": 1
        }]

        self.assertTrue(is_complete_hand(hand, melds))

    def test_fixed_chi_cannot_be_regrouped(self):
        hand = [
            "1m", "1m", "2m", "2m", "3m",
            "4p", "5p", "6p",
            "7z", "7z", "7z"
        ]

        # Flattened tiles can form a closed winning hand.
        self.assertTrue(
            is_complete_hand(hand + ["1m", "2m", "3m"])
        )

        # But the fixed Chi cannot be broken apart to regroup.
        self.assertFalse(
            is_complete_hand(hand, self.melds)
        )

    def test_inputs_are_not_modified(self):
        original = deepcopy((self.hand, self.melds))

        is_complete_hand(self.hand, self.melds)
        get_waiting_tiles(self.hand[:-1], self.melds)

        self.assertEqual((self.hand, self.melds), original)


if __name__ == "__main__":
    unittest.main()