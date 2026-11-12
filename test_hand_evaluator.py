import unittest

from hand_evaluator import (
    is_standard_hand,
    is_seven_pairs,
    is_thirteen_orphans,
    is_complete_hand
)


class HandEvaluatorTests(unittest.TestCase):
    def test_standard_hand(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z"
        ]

        self.assertTrue(is_standard_hand(hand))
        self.assertTrue(is_complete_hand(hand))

    def test_ambiguous_grouping(self):
        # Taking 111m first fails; using 11m as the pair succeeds.
        hand = [
            "1m", "1m", "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z"
        ]

        self.assertTrue(is_standard_hand(hand))

    def test_seven_pairs(self):
        hand = [
            "1m", "1m",
            "4m", "4m",
            "2p", "2p",
            "8p", "8p",
            "3s", "3s",
            "1z", "1z",
            "7z", "7z"
        ]

        self.assertTrue(is_seven_pairs(hand))
        self.assertTrue(is_complete_hand(hand))

    def test_four_identical_tiles_are_not_two_pairs(self):
        hand = [
            "1m", "1m", "1m", "1m",
            "2p", "2p",
            "4p", "4p",
            "6s", "6s",
            "1z", "1z",
            "7z", "7z"
        ]

        self.assertFalse(is_seven_pairs(hand))

    def test_thirteen_orphans(self):
        hand = [
            "1m", "9m", "1p", "9p", "1s", "9s",
            "1z", "2z", "3z", "4z", "5z", "6z", "7z",
            "1m"
        ]

        self.assertTrue(is_thirteen_orphans(hand))
        self.assertTrue(is_complete_hand(hand))

        # Missing 9m, despite having 14 tiles.
        hand[1] = "1p"
        self.assertFalse(is_thirteen_orphans(hand))

    def test_sequences_cannot_cross_suits(self):
        hand = [
            "8m", "9m", "1p",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z"
        ]

        self.assertFalse(is_complete_hand(hand))

    def test_invalid_hands(self):
        invalid_hands = [
            ["1m"] * 13,
            ["1m"] * 15,
            ["1m"] * 14,
            ["0m"] + ["1m"] * 13,
            [None] + ["1m"] * 13
        ]

        for hand in invalid_hands:
            with self.subTest(hand=hand):
                self.assertFalse(is_complete_hand(hand))

    def test_hand_is_not_modified(self):
        hand = [
            "5z", "1z", "9s", "8s", "7s",
            "6p", "5p", "4p",
            "3m", "2m", "1m",
            "1z", "5z", "1z"
        ]
        original = hand.copy()

        self.assertTrue(is_complete_hand(hand))
        self.assertEqual(hand, original)


if __name__ == "__main__":
    unittest.main()