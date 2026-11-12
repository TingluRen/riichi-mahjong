import unittest
from copy import deepcopy

from ai import calculate_shanten


class ShantenTests(unittest.TestCase):
    def test_complete_standard_hand(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z",
        ]

        self.assertEqual(calculate_shanten(hand), -1)

    def test_standard_tenpai(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z",
        ]

        self.assertEqual(calculate_shanten(hand), 0)

    def test_one_shanten(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z",
            "2m", "8p",
        ]

        self.assertEqual(calculate_shanten(hand), 1)

    def test_seven_pairs_complete_and_tenpai(self):
        hand = [
            "1m", "1m",
            "4m", "4m",
            "7m", "7m",
            "2p", "2p",
            "5p", "5p",
            "3s", "3s",
            "6z", "6z",
        ]

        self.assertEqual(calculate_shanten(hand), -1)
        self.assertEqual(calculate_shanten(hand[:-1]), 0)

    def test_thirteen_orphans_complete_and_tenpai(self):
        hand = [
            "1m", "9m",
            "1p", "9p",
            "1s", "9s",
            "1z", "2z", "3z", "4z", "5z", "6z", "7z",
        ]

        self.assertEqual(calculate_shanten(hand), 0)
        self.assertEqual(
            calculate_shanten(hand + ["1m"]),
            -1,
        )

    def test_open_hand(self):
        hand = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z",
        ]
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

        self.assertEqual(calculate_shanten(hand, melds), 0)
        self.assertEqual(
            calculate_shanten(hand + ["5z"], melds),
            -1,
        )

    def test_kan_is_one_fixed_group(self):
        hand = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z",
        ]
        melds = [{
            "type": "ankan",
            "tiles": ["2m"] * 4,
        }]

        self.assertEqual(calculate_shanten(hand, melds), 0)

    def test_four_identical_tiles_are_not_two_distinct_pairs(self):
        hand = (
            ["1m"] * 4
            + ["2p"] * 2
            + ["3p"] * 2
            + ["4s"] * 2
            + ["5s"] * 2
            + ["6z"]
        )

        self.assertEqual(calculate_shanten(hand), 2)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            calculate_shanten(["1m", "2m"])

        with self.assertRaises(ValueError):
            calculate_shanten(["invalid"] * 13)

        with self.assertRaises(ValueError):
            calculate_shanten(
                ["1m"] * 5 + ["2p"] * 4 + ["3s"] * 4
            )

    def test_inputs_are_not_modified(self):
        hand = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z",
        ]
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]
        before = deepcopy((hand, melds))

        calculate_shanten(hand, melds)

        self.assertEqual((hand, melds), before)


if __name__ == "__main__":
    unittest.main()