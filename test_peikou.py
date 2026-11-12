import unittest
from copy import deepcopy

from yaku import (
    get_supported_yaku,
    get_win_yaku,
    get_yaku_candidates,
)


class PeikouTests(unittest.TestCase):
    def make_iipeikou_hand(self):
        return [
            "1m", "2m", "3m",
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z",
        ]

    def make_ryanpeikou_hand(self):
        return [
            "1m", "2m", "3m",
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "4p", "5p", "6p",
            "5z", "5z",
        ]

    def test_closed_iipeikou(self):
        yaku = get_supported_yaku(self.make_iipeikou_hand())

        self.assertIn("Iipeikou", yaku)
        self.assertNotIn("Ryanpeikou", yaku)

    def test_ryanpeikou_excludes_other_interpretations(self):
        yaku = get_supported_yaku(self.make_ryanpeikou_hand())

        self.assertIn("Ryanpeikou", yaku)
        self.assertNotIn("Iipeikou", yaku)
        self.assertNotIn("Chiitoitsu", yaku)

    def test_candidates_keep_seven_pairs_separate(self):
        candidates = get_yaku_candidates(
            self.make_ryanpeikou_hand()
        )

        self.assertTrue(any(
            "Chiitoitsu" in candidate["yaku"]
            for candidate in candidates
        ))
        self.assertTrue(any(
            "Ryanpeikou" in candidate["yaku"]
            for candidate in candidates
        ))

        for candidate in candidates:
            self.assertFalse(
                "Chiitoitsu" in candidate["yaku"]
                and "Ryanpeikou" in candidate["yaku"]
            )

    def test_open_chi_blocks_iipeikou(self):
        hand = [
            "1m", "2m", "3m",
            "1m", "2m", "3m",
            "7s", "8s", "9s",
            "5z", "5z",
        ]
        melds = [{
            "type": "chi",
            "tiles": ["4p", "5p", "6p"],
            "from_player_index": 3,
        }]

        yaku = get_supported_yaku(hand, melds=melds)

        self.assertNotIn("Iipeikou", yaku)
        self.assertNotIn("Ryanpeikou", yaku)

    def test_ankan_preserves_closed_iipeikou(self):
        hand = [
            "1m", "2m", "3m",
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "5z", "5z",
        ]
        melds = [{
            "type": "ankan",
            "tiles": ["1z"] * 4,
        }]

        yaku = get_supported_yaku(hand, melds=melds)

        self.assertIn("Iipeikou", yaku)

    def test_explicit_open_state_is_respected(self):
        yaku = get_win_yaku(
            self.make_iipeikou_hand(),
            is_closed=False,
        )

        self.assertNotIn("Iipeikou", yaku)

    def test_four_identical_sequences_form_ryanpeikou(self):
        hand = (
            ["1m"] * 4
            + ["2m"] * 4
            + ["3m"] * 4
            + ["5z"] * 2
        )

        yaku = get_supported_yaku(hand)

        self.assertIn("Ryanpeikou", yaku)
        self.assertNotIn("Iipeikou", yaku)

    def test_no_matching_sequences(self):
        hand = [
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z",
        ]

        yaku = get_supported_yaku(hand)

        self.assertNotIn("Iipeikou", yaku)
        self.assertNotIn("Ryanpeikou", yaku)

    def test_inputs_are_not_modified(self):
        hand = self.make_ryanpeikou_hand()
        before = deepcopy(hand)

        get_yaku_candidates(hand)
        get_supported_yaku(hand)

        self.assertEqual(hand, before)


if __name__ == "__main__":
    unittest.main()