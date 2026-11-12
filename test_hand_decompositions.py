import unittest
from copy import deepcopy

from hand_evaluator import get_standard_hand_decompositions


class HandDecompositionTests(unittest.TestCase):
    def test_standard_hand(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z"
        ]

        results = get_standard_hand_decompositions(hand)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["pair"], ["5z", "5z"])
        self.assertEqual(
            results[0]["concealed_groups"],
            [
                {"type": "sequence", "tiles": ["1m", "2m", "3m"]},
                {"type": "sequence", "tiles": ["4p", "5p", "6p"]},
                {"type": "sequence", "tiles": ["7s", "8s", "9s"]},
                {"type": "triplet", "tiles": ["1z"] * 3},
            ]
        )

    def test_preserves_multiple_decompositions(self):
        hand = (
            ["1m"] * 3
            + ["2m"] * 3
            + ["3m"] * 3
            + ["4z"] * 3
            + ["5z"] * 2
        )

        results = get_standard_hand_decompositions(hand)

        # 111m + 222m + 333m, or three copies of 123m.
        self.assertEqual(len(results), 2)

        sequence_counts = sorted(
            sum(
                group["type"] == "sequence"
                for group in result["concealed_groups"]
            )
            for result in results
        )

        self.assertEqual(sequence_counts, [0, 3])

    def test_declared_pon_stays_fixed(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z"
        ]
        melds = [{
            "type": "pon",
            "tiles": ["1z"] * 3,
            "from_player_index": 1
        }]

        results = get_standard_hand_decompositions(hand, melds)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]["concealed_groups"]), 3)
        self.assertEqual(results[0]["declared_groups"], melds)

    def test_declared_kan_counts_as_one_group(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z"
        ]
        melds = [{
            "type": "ankan",
            "tiles": ["1z"] * 4
        }]

        results = get_standard_hand_decompositions(hand, melds)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]["concealed_groups"]), 3)
        self.assertEqual(results[0]["declared_groups"], melds)

    def test_special_hands_have_no_standard_decomposition(self):
        seven_pairs = [
            "1m", "1m", "4m", "4m", "7m", "7m",
            "2p", "2p", "5p", "5p",
            "3s", "3s", "6z", "6z"
        ]
        kokushi = [
            "1m", "9m", "1p", "9p", "1s", "9s",
            "1z", "2z", "3z", "4z", "5z", "6z", "7z",
            "1m"
        ]

        for hand in (seven_pairs, kokushi):
            with self.subTest(hand=hand):
                self.assertEqual(
                    get_standard_hand_decompositions(hand),
                    []
                )

    def test_incomplete_hand_returns_empty(self):
        self.assertEqual(
            get_standard_hand_decompositions(["1m", "2m"]),
            []
        )

    def test_inputs_and_results_are_independent(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z"
        ]
        melds = [{
            "type": "pon",
            "tiles": ["1z"] * 3,
            "from_player_index": 1
        }]
        before = deepcopy((hand, melds))

        results = get_standard_hand_decompositions(hand, melds)

        self.assertEqual((hand, melds), before)

        results[0]["declared_groups"][0]["tiles"][0] = "7z"

        self.assertEqual((hand, melds), before)


if __name__ == "__main__":
    unittest.main()