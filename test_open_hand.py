import unittest
from copy import deepcopy

from hand_evaluator import is_complete_hand, get_waiting_tiles


class OpenHandTests(unittest.TestCase):
    def setUp(self):
        self.melds = [{
            "type": "pon",
            "tiles": ["5z", "5z", "5z"],
            "from_player_index": 1
        }]

        self.hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z"
        ]

    def test_complete_hand_with_one_pon(self):
        self.assertTrue(is_complete_hand(self.hand, self.melds))

    def test_wait_with_one_pon(self):
        waiting_hand = self.hand[:-1]

        self.assertEqual(
            get_waiting_tiles(waiting_hand, self.melds),
            ["1z"]
        )

    def test_five_copies_across_hand_and_meld_are_invalid(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "5z"
        ]

        self.assertFalse(is_complete_hand(hand, self.melds))

    def test_invalid_pon(self):
        melds = [{
            "type": "pon",
            "tiles": ["5z", "5z", "6z"]
        }]

        self.assertFalse(is_complete_hand(self.hand, melds))

    def test_exposed_tiles_cannot_be_regrouped(self):
        melds = [{
            "type": "pon",
            "tiles": ["1m", "1m", "1m"]
        }]

        # Flattening everything would allow 111m + 123m + 123m,
        # but those groups break apart the fixed exposed Pon.
        hand = [
            "1m", "2m", "2m", "3m", "3m",
            "4p", "5p", "6p",
            "7z", "7z", "7z"
        ]

        self.assertFalse(is_complete_hand(hand, melds))

    def test_checks_do_not_modify_input(self):
        original = deepcopy((self.hand, self.melds))

        is_complete_hand(self.hand, self.melds)
        get_waiting_tiles(self.hand[:-1], self.melds)

        self.assertEqual((self.hand, self.melds), original)


if __name__ == "__main__":
    unittest.main()