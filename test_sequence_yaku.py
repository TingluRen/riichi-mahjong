import unittest
from copy import deepcopy

from yaku import (
    get_supported_yaku,
    get_yaku_candidates,
    count_supported_yaku_han,
)


class SequenceYakuTests(unittest.TestCase):
    def test_closed_sanshoku(self):
        hand = [
            "1m", "2m", "3m",
            "1p", "2p", "3p",
            "1s", "2s", "3s",
            "7m", "8m", "9m",
            "5z", "5z",
        ]

        yaku = get_supported_yaku(hand)

        self.assertIn("Sanshoku Doujun", yaku)
        self.assertNotIn("Ittsu", yaku)
        self.assertCountEqual(yaku, ["Sanshoku Doujun", "Chanta"])
        self.assertEqual(count_supported_yaku_han(yaku), 4)

    def test_open_sanshoku_includes_declared_chi(self):
        hand = [
            "1p", "2p", "3p",
            "1s", "2s", "3s",
            "7m", "8m", "9m",
            "5z", "5z",
        ]
        melds = [{
            "type": "chi",
            # An unsorted declared sequence is also valid.
            "tiles": ["3m", "1m", "2m"],
            "from_player_index": 3,
        }]

        yaku = get_supported_yaku(hand, melds=melds)

        self.assertCountEqual(yaku, ["Sanshoku Doujun", "Chanta"])
        self.assertEqual(
            count_supported_yaku_han(yaku, is_closed=False),
            2
        )

    def test_closed_ittsu(self):
        hand = [
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "7m", "8m", "9m",
            "2p", "3p", "4p",
            "5z", "5z",
        ]

        yaku = get_supported_yaku(hand)

        self.assertIn("Ittsu", yaku)
        self.assertNotIn("Sanshoku Doujun", yaku)
        self.assertEqual(count_supported_yaku_han(yaku), 2)

    def test_open_ittsu_includes_declared_chi(self):
        hand = [
            "4m", "5m", "6m",
            "7m", "8m", "9m",
            "2p", "3p", "4p",
            "5z", "5z",
        ]
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

        yaku = get_supported_yaku(hand, melds=melds)

        self.assertIn("Ittsu", yaku)
        self.assertEqual(
            count_supported_yaku_han(yaku, is_closed=False),
            1
        )

    def test_mismatched_sequences_are_not_sanshoku(self):
        hand = [
            "1m", "2m", "3m",
            "1p", "2p", "3p",
            "2s", "3s", "4s",
            "7m", "8m", "9m",
            "5z", "5z",
        ]

        self.assertNotIn(
            "Sanshoku Doujun",
            get_supported_yaku(hand)
        )

    def test_nine_ranks_alone_do_not_make_ittsu(self):
        # Contains every rank, but the actual groups are:
        # 123m, 345m, 678m, 999m and a White Dragon pair.
        hand = [
            "1m", "2m", "3m",
            "3m", "4m", "5m",
            "6m", "7m", "8m",
            "9m", "9m", "9m",
            "5z", "5z",
        ]

        self.assertNotIn("Ittsu", get_supported_yaku(hand))

    def test_selection_uses_total_supported_han(self):
        # Has both standard and seven-pairs interpretations.
        hand = [
            "1m", "2m", "3m",
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "4p", "5p", "6p",
            "5z", "5z",
        ]

        candidates = get_yaku_candidates(hand)
        selected = get_supported_yaku(hand)

        expected_han = max(
            count_supported_yaku_han(candidate["yaku"])
            for candidate in candidates
        )

        self.assertEqual(
            count_supported_yaku_han(selected),
            expected_han
        )
        self.assertIn("Ryanpeikou", selected)
        self.assertNotIn("Chiitoitsu", selected)

    def test_han_values_and_unknown_names(self):
        self.assertEqual(
            count_supported_yaku_han(
                ["Honitsu", "Ittsu"],
                is_closed=True,
            ),
            5
        )
        self.assertEqual(
            count_supported_yaku_han(
                ["Honitsu", "Ittsu"],
                is_closed=False,
            ),
            3
        )

        with self.assertRaises(ValueError):
            count_supported_yaku_han(["Unknown Yaku"])

    def test_inputs_are_not_modified(self):
        hand = [
            "1m", "2m", "3m",
            "1p", "2p", "3p",
            "1s", "2s", "3s",
            "7m", "8m", "9m",
            "5z", "5z",
        ]
        before = deepcopy(hand)

        get_yaku_candidates(hand)
        get_supported_yaku(hand)

        self.assertEqual(hand, before)


if __name__ == "__main__":
    unittest.main()