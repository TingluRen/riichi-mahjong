import unittest
from copy import deepcopy

from hand_evaluator import (
    get_wait_type,
    get_winning_waits,
)


class WaitTypeTests(unittest.TestCase):
    def make_placement(self, group_type, tiles):
        return {
            "winning_group": {
                "type": group_type,
                "index": None if group_type == "pair" else 0,
                "tiles": tiles,
            }
        }

    def test_ryanmen(self):
        cases = [
            (["3m", "4m", "5m"], "3m"),
            (["3m", "4m", "5m"], "5m"),
            (["1p", "2p", "3p"], "1p"),
            (["7s", "8s", "9s"], "9s"),
        ]

        for tiles, winning_tile in cases:
            with self.subTest(tiles=tiles, winning_tile=winning_tile):
                placement = self.make_placement("sequence", tiles)

                self.assertEqual(
                    get_wait_type(placement, winning_tile),
                    "ryanmen"
                )

    def test_kanchan(self):
        for tiles, winning_tile in [
            (["1m", "2m", "3m"], "2m"),
            (["4p", "5p", "6p"], "5p"),
            (["7s", "8s", "9s"], "8s"),
        ]:
            with self.subTest(tiles=tiles):
                placement = self.make_placement("sequence", tiles)

                self.assertEqual(
                    get_wait_type(placement, winning_tile),
                    "kanchan"
                )

    def test_penchan(self):
        for tiles, winning_tile in [
            (["1m", "2m", "3m"], "3m"),
            (["7p", "8p", "9p"], "7p"),
        ]:
            with self.subTest(tiles=tiles):
                placement = self.make_placement("sequence", tiles)

                self.assertEqual(
                    get_wait_type(placement, winning_tile),
                    "penchan"
                )

    def test_shanpon(self):
        placement = self.make_placement(
            "triplet",
            ["6s", "6s", "6s"],
        )

        self.assertEqual(
            get_wait_type(placement, "6s"),
            "shanpon"
        )

    def test_tanki(self):
        placement = self.make_placement(
            "pair",
            ["5z", "5z"],
        )

        self.assertEqual(
            get_wait_type(placement, "5z"),
            "tanki"
        )

    def test_invalid_winning_tile(self):
        placement = self.make_placement(
            "sequence",
            ["1m", "2m", "3m"],
        )

        with self.assertRaises(ValueError):
            get_wait_type(placement, "4m")

    def test_multiple_placements_keep_different_wait_types(self):
        hand = [
            "1m", "2m", "3m",
            "1p", "2p", "3p",
            "1s", "2s", "3s",
            "4m", "5m", "6m",
            "5m", "5m",
        ]

        results = get_winning_waits(hand, "5m")

        self.assertEqual(len(results), 2)
        self.assertEqual(
            {result["wait_type"] for result in results},
            {"kanchan", "tanki"}
        )

    def test_uses_fixed_declared_groups(self):
        hand = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z",
        ]
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

        results = get_winning_waits(hand, "6p", melds)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["wait_type"], "ryanmen")
        self.assertEqual(
            results[0]["decomposition"]["declared_groups"],
            melds
        )

    def test_inputs_are_not_modified(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z",
        ]
        before = deepcopy(hand)

        results = get_winning_waits(hand, "6p")
        placement_before = deepcopy(results[0])

        get_wait_type(results[0], "6p")

        self.assertEqual(hand, before)
        self.assertEqual(results[0], placement_before)


if __name__ == "__main__":
    unittest.main()