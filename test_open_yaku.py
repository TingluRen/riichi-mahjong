import unittest
from copy import deepcopy

from yaku import get_supported_yaku
from win_rules import is_discard_furiten


class OpenYakuTests(unittest.TestCase):
    def setUp(self):
        self.hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "2z", "2z"
        ]

        self.melds = [{
            "type": "pon",
            "tiles": ["5z", "5z", "5z"],
            "from_player_index": 1
        }]

    def test_exposed_dragon_supplies_yaku(self):
        yaku = get_supported_yaku(
            self.hand,
            melds=self.melds
        )

        self.assertIn("Yakuhai: White Dragon", yaku)

    def test_open_complete_hand_can_have_no_supported_yaku(self):
        melds = [{
            "type": "pon",
            "tiles": ["9m", "9m", "9m"],
            "from_player_index": 1
        }]

        yaku = get_supported_yaku(
            self.hand,
            seat_wind="1z",
            round_wind="1z",
            melds=melds
        )

        self.assertEqual(yaku, [])

    def test_exposed_terminal_prevents_tanyao(self):
        hand = [
            "2m", "3m", "4m",
            "3p", "4p", "5p",
            "6s", "7s", "8s",
            "2p", "2p"
        ]

        melds = [{
            "type": "pon",
            "tiles": ["1s", "1s", "1s"]
        }]

        self.assertNotIn(
            "Tanyao",
            get_supported_yaku(hand, melds=melds)
        )

    def test_exposed_suit_prevents_false_chinitsu(self):
        hand = [
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "7m", "8m", "9m",
            "2m", "2m"
        ]

        melds = [{
            "type": "pon",
            "tiles": ["5p", "5p", "5p"]
        }]

        self.assertNotIn(
            "Chinitsu",
            get_supported_yaku(hand, melds=melds)
        )

    def test_open_wait_can_be_discard_furiten(self):
        waiting_hand = self.hand[:-1]

        self.assertTrue(
            is_discard_furiten(
                waiting_hand,
                ["2z"],
                self.melds
            )
        )

        self.assertFalse(
            is_discard_furiten(
                waiting_hand,
                ["3z"],
                self.melds
            )
        )

    def test_evaluation_does_not_modify_inputs(self):
        original = deepcopy((self.hand, self.melds))

        get_supported_yaku(self.hand, melds=self.melds)
        is_discard_furiten(
            self.hand[:-1],
            ["2z"],
            self.melds
        )

        self.assertEqual((self.hand, self.melds), original)


if __name__ == "__main__":
    unittest.main()