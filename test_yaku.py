import unittest

from yaku import get_supported_yaku


class YakuTests(unittest.TestCase):
    def test_tanyao(self):
        hand = [
            "2m", "3m", "4m",
            "3p", "4p", "5p",
            "4s", "5s", "6s",
            "6s", "7s", "8s",
            "2p", "2p"
        ]

        self.assertEqual(get_supported_yaku(hand), ["Tanyao"])

    def test_dragon_triplet(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "7z", "7z", "7z",
            "5z", "5z"
        ]

        self.assertEqual(
            get_supported_yaku(hand),
            ["Yakuhai: Red Dragon"]
        )

    def test_double_wind(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "5z"
        ]

        self.assertEqual(
            get_supported_yaku(hand, "1z", "1z"),
            ["Yakuhai: Seat Wind", "Yakuhai: Round Wind"]
        )

        # East is neither the player's wind nor the round wind.
        self.assertEqual(
            get_supported_yaku(hand, "2z", "3z"),
            []
        )

    def test_seven_pairs_and_honitsu(self):
        hand = [
            "1m", "1m",
            "2m", "2m",
            "4m", "4m",
            "6m", "6m",
            "8m", "8m",
            "1z", "1z",
            "7z", "7z"
        ]

        self.assertCountEqual(
            get_supported_yaku(hand),
            ["Chiitoitsu", "Honitsu"]
        )

    def test_chinitsu(self):
        hand = [
            "1m", "2m", "3m",
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "7m", "8m", "9m",
            "5m", "5m"
        ]

        yaku = get_supported_yaku(hand)

        self.assertIn("Chinitsu", yaku)
        self.assertNotIn("Honitsu", yaku)

    def test_kokushi(self):
        hand = [
            "1m", "9m", "1p", "9p", "1s", "9s",
            "1z", "2z", "3z", "4z", "5z", "6z", "7z",
            "1m"
        ]

        self.assertEqual(
            get_supported_yaku(hand),
            ["Kokushi Musou"]
        )

    def test_complete_hand_without_yaku(self):
        # The dragon pair is not Yakuhai.
        # Winning on 2m would also be a closed wait, not Pinfu.
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "2s", "3s", "4s",
            "5z", "5z"
        ]

        self.assertEqual(get_supported_yaku(hand), [])

    def test_incomplete_all_simples_hand(self):
        # All tiles are simples, but the structure is incomplete.
        hand = [
            "2m", "2m", "2m", "2m",
            "4p", "4p", "4p", "4p",
            "6s", "6s", "6s", "6s",
            "8m", "8p"
        ]

        self.assertEqual(get_supported_yaku(hand), [])

    def test_invalid_wind(self):
        with self.assertRaises(ValueError):
            get_supported_yaku([], seat_wind="5z")


if __name__ == "__main__":
    unittest.main()