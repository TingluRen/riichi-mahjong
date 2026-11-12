import unittest

from hand_evaluator import get_tenpai_discards


class TestTenpaiDiscards(unittest.TestCase):
    def test_discard_to_tenpai(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "9p"
        ]

        results = get_tenpai_discards(hand)

        # Discarding 9p leaves a hand waiting for 5z.
        option = next(
            result
            for result in results
            if result["tile_index"] == 13
        )

        self.assertEqual(option["tile"], "9p")
        self.assertEqual(option["waiting_tiles"], ["5z"])

    def test_original_hand_is_unchanged(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "9p"
        ]
        original_hand = hand.copy()

        get_tenpai_discards(hand)

        self.assertEqual(hand, original_hand)

    def test_invalid_hand_length(self):
        with self.assertRaises(ValueError):
            get_tenpai_discards(["1m"] * 13)


if __name__ == "__main__":
    unittest.main()