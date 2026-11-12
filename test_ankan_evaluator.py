import unittest
from copy import deepcopy

from hand_evaluator import is_complete_hand, get_waiting_tiles


class AnkanEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z"
        ]

        self.melds = [{
            "type": "ankan",
            "tiles": ["5z", "5z", "5z", "5z"]
        }]

    def test_complete_hand_with_ankan(self):
        self.assertTrue(
            is_complete_hand(self.hand, self.melds)
        )

    def test_waiting_tiles_with_ankan(self):
        self.assertEqual(
            get_waiting_tiles(self.hand[:-1], self.melds),
            ["1z"]
        )

    def test_ankan_requires_four_identical_tiles(self):
        invalid_groups = [
            ["5z", "5z", "5z"],
            ["5z", "5z", "5z", "6z"],
            ["1m", "2m", "3m", "4m"],
        ]

        for tiles in invalid_groups:
            with self.subTest(tiles=tiles):
                melds = [{"type": "ankan", "tiles": tiles}]

                self.assertFalse(
                    is_complete_hand(self.hand, melds)
                )

    def test_fifth_copy_is_invalid(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z"
        ]

        self.assertFalse(
            is_complete_hand(hand, self.melds)
        )

    def test_waits_do_not_include_fifth_copy(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z"
        ]

        self.assertEqual(
            get_waiting_tiles(hand, self.melds),
            []
        )

    def test_mixed_chi_pon_and_ankan(self):
        hand = ["7s", "8s", "9s", "1z", "1z"]

        melds = [
            {"type": "chi", "tiles": ["1m", "2m", "3m"]},
            {"type": "pon", "tiles": ["6z", "6z", "6z"]},
            {"type": "ankan", "tiles": ["5z"] * 4},
        ]

        self.assertTrue(is_complete_hand(hand, melds))

    def test_inputs_are_not_modified(self):
        original = deepcopy((self.hand, self.melds))

        is_complete_hand(self.hand, self.melds)
        get_waiting_tiles(self.hand[:-1], self.melds)

        self.assertEqual((self.hand, self.melds), original)


if __name__ == "__main__":
    unittest.main()