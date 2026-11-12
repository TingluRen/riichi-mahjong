import unittest
from copy import deepcopy

from hand_evaluator import get_winning_tile_placements


class WinningTilePlacementTests(unittest.TestCase):
    def test_winning_tile_completes_pair(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z",
        ]

        results = get_winning_tile_placements(hand, "5z")

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["winning_group"],
            {
                "type": "pair",
                "index": None,
                "tiles": ["5z", "5z"],
            }
        )

    def test_winning_tile_completes_sequence(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z",
        ]

        results = get_winning_tile_placements(hand, "3m")

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["winning_group"]["type"],
            "sequence"
        )
        self.assertEqual(
            results[0]["winning_group"]["tiles"],
            ["1m", "2m", "3m"]
        )

    def test_winning_tile_completes_triplet(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z",
        ]

        results = get_winning_tile_placements(hand, "1z")

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["winning_group"]["type"],
            "triplet"
        )

    def test_same_decomposition_can_have_two_placements(self):
        hand = [
            "1m", "2m", "3m",
            "1p", "2p", "3p",
            "1s", "2s", "3s",
            "4m", "5m", "6m",
            "5m", "5m",
        ]

        results = get_winning_tile_placements(hand, "5m")

        self.assertEqual(len(results), 2)
        self.assertEqual(
            {result["winning_group"]["type"] for result in results},
            {"pair", "sequence"}
        )
        self.assertEqual(
            results[0]["decomposition"],
            results[1]["decomposition"]
        )

    def test_multiple_decompositions_are_preserved(self):
        hand = (
            ["1m"] * 3
            + ["2m"] * 3
            + ["3m"] * 3
            + ["4p"] * 3
            + ["5z"] * 2
        )

        results = get_winning_tile_placements(hand, "1m")

        types = {
            result["winning_group"]["type"]
            for result in results
        }

        self.assertEqual(types, {"triplet", "sequence"})

        for result in results:
            group = result["winning_group"]
            index = group["index"]

            self.assertEqual(
                result["decomposition"]["concealed_groups"][index]["tiles"],
                group["tiles"]
            )

    def test_declared_group_is_not_a_placement(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z",
        ]
        melds = [{
            "type": "pon",
            "tiles": ["1m"] * 3,
            "from_player_index": 1,
        }]

        results = get_winning_tile_placements(hand, "1m", melds)

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["winning_group"]["type"],
            "sequence"
        )

    def test_missing_tile_or_incomplete_hand(self):
        self.assertEqual(
            get_winning_tile_placements(["1m", "2m"], "3m"),
            []
        )
        self.assertEqual(
            get_winning_tile_placements(["1m", "2m"], "1m"),
            []
        )

    def test_inputs_and_results_are_independent(self):
        hand = [
            "1m", "2m", "3m",
            "1p", "2p", "3p",
            "1s", "2s", "3s",
            "4m", "5m", "6m",
            "5m", "5m",
        ]
        before = deepcopy(hand)

        results = get_winning_tile_placements(hand, "5m")
        second_before = deepcopy(results[1])

        results[0]["decomposition"]["pair"][0] = "7z"

        self.assertEqual(hand, before)
        self.assertEqual(results[1], second_before)


if __name__ == "__main__":
    unittest.main()