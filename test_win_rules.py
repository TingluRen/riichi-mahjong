import unittest

from hand_evaluator import get_waiting_tiles
from win_rules import is_discard_furiten


class WaitingAndFuritenTests(unittest.TestCase):
    def setUp(self):
        # 45m waits on 3m or 6m.
        self.hand = [
            "4m", "5m",
            "1p", "2p", "3p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z"
        ]

    def test_two_sided_wait(self):
        self.assertEqual(
            set(get_waiting_tiles(self.hand)),
            {"3m", "6m"}
        )

    def test_own_discard_causes_furiten(self):
        self.assertTrue(
            is_discard_furiten(self.hand, ["3m"])
        )

    def test_other_wait_is_also_blocked(self):
        # Even though 6m was not discarded, discarding 3m blocks Ron.
        self.assertIn("6m", get_waiting_tiles(self.hand))
        self.assertTrue(
            is_discard_furiten(self.hand, ["3m"])
        )

    def test_unrelated_discard_does_not_cause_furiten(self):
        self.assertFalse(
            is_discard_furiten(self.hand, ["9p", "7z"])
        )

    def test_no_discards(self):
        self.assertFalse(
            is_discard_furiten(self.hand, [])
        )

    def test_hand_is_not_modified(self):
        original = self.hand.copy()

        get_waiting_tiles(self.hand)

        self.assertEqual(self.hand, original)

    def test_invalid_hand_length(self):
        self.assertEqual(
            get_waiting_tiles(self.hand + ["2z"]),
            []
        )


if __name__ == "__main__":
    unittest.main()