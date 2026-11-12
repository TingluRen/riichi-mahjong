import unittest
from copy import deepcopy

from yaku import (
    get_supported_yaku,
    get_yaku_candidates,
    count_supported_yaku_han,
)


class ToitoiTests(unittest.TestCase):
    def test_closed_triplets(self):
        hand = (
            ["2m"] * 3
            + ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["5z"] * 2
        )

        yaku = get_supported_yaku(hand)

        self.assertIn("Toitoi", yaku)
        self.assertEqual(count_supported_yaku_han(yaku), 2)

    def test_open_pon(self):
        hand = (
            ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["5z"] * 2
        )
        melds = [{
            "type": "pon",
            "tiles": ["2m"] * 3,
            "from_player_index": 1,
        }]

        yaku = get_supported_yaku(hand, melds=melds)

        self.assertIn("Toitoi", yaku)
        self.assertEqual(
            count_supported_yaku_han(yaku, is_closed=False),
            2
        )

    def test_all_kan_types_count_as_triplet_groups(self):
        hand = (
            ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["5z"] * 2
        )

        for kan_type in ("ankan", "daiminkan", "kakan"):
            with self.subTest(kan_type=kan_type):
                meld = {
                    "type": kan_type,
                    "tiles": ["2m"] * 4,
                }

                if kan_type != "ankan":
                    meld["from_player_index"] = 1

                yaku = get_supported_yaku(hand, melds=[meld])

                self.assertIn("Toitoi", yaku)

    def test_concealed_sequence_blocks_toitoi(self):
        hand = (
            ["1m", "2m", "3m"]
            + ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["5z"] * 2
        )

        self.assertNotIn("Toitoi", get_supported_yaku(hand))

    def test_declared_chi_blocks_toitoi(self):
        hand = (
            ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["5z"] * 2
        )
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

        self.assertNotIn(
            "Toitoi",
            get_supported_yaku(hand, melds=melds)
        )

    def test_four_declared_groups_and_a_pair(self):
        hand = ["5z", "5z"]
        melds = [
            {
                "type": "pon",
                "tiles": [tile] * 3,
                "from_player_index": 1,
            }
            for tile in ("2m", "4p", "6s", "7s")
        ]

        self.assertIn(
            "Toitoi",
            get_supported_yaku(hand, melds=melds)
        )

    def test_combines_with_tanyao(self):
        hand = (
            ["2m"] * 3
            + ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["8p"] * 2
        )

        yaku = get_supported_yaku(hand)

        self.assertIn("Toitoi", yaku)
        self.assertIn("Tanyao", yaku)
        self.assertEqual(count_supported_yaku_han(yaku), 3)

    def test_different_decompositions_stay_separate(self):
        hand = (
            ["1m"] * 3
            + ["2m"] * 3
            + ["3m"] * 3
            + ["4p"] * 3
            + ["5z"] * 2
        )

        candidates = get_yaku_candidates(hand)

        # One interpretation has four triplets.
        self.assertTrue(any(
            "Toitoi" in candidate["yaku"]
            for candidate in candidates
        ))

        # Another interpretation has three identical sequences.
        self.assertTrue(any(
            "Iipeikou" in candidate["yaku"]
            for candidate in candidates
        ))

        for candidate in candidates:
            self.assertFalse(
                "Toitoi" in candidate["yaku"]
                and "Iipeikou" in candidate["yaku"]
            )

        selected = get_supported_yaku(hand)

        self.assertIn("Toitoi", selected)
        self.assertNotIn("Iipeikou", selected)

    def test_inputs_are_not_modified(self):
        hand = (
            ["4p"] * 3
            + ["6s"] * 3
            + ["7s"] * 3
            + ["5z"] * 2
        )
        melds = [{
            "type": "pon",
            "tiles": ["2m"] * 3,
            "from_player_index": 1,
        }]
        before = deepcopy((hand, melds))

        get_supported_yaku(hand, melds=melds)

        self.assertEqual((hand, melds), before)


if __name__ == "__main__":
    unittest.main()