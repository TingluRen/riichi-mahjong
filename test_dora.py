import unittest

from main import indicator_to_dora, get_dora_tiles


class DoraTests(unittest.TestCase):
    def test_numbered_suits(self):
        for suit in ("m", "p", "s"):
            for number in range(1, 9):
                with self.subTest(suit=suit, number=number):
                    self.assertEqual(
                        indicator_to_dora(f"{number}{suit}"),
                        f"{number + 1}{suit}"
                    )

            self.assertEqual(
                indicator_to_dora(f"9{suit}"),
                f"1{suit}"
            )

    def test_honors(self):
        expected = {
            "1z": "2z",
            "2z": "3z",
            "3z": "4z",
            "4z": "1z",
            "5z": "6z",
            "6z": "7z",
            "7z": "5z",
        }

        for indicator, dora in expected.items():
            with self.subTest(indicator=indicator):
                self.assertEqual(indicator_to_dora(indicator), dora)

    def test_invalid_indicators(self):
        for indicator in ("10m", "8z", "1x", "", None):
            with self.subTest(indicator=indicator):
                with self.assertRaises(ValueError):
                    indicator_to_dora(indicator)

    def test_only_visible_indicators_are_used(self):
        game = {
            "dead_wall": ["1m"] * 14,
            "dora_indicator_count": 1,
        }

        game["dead_wall"][4] = "9m"
        game["dead_wall"][6] = "7z"

        self.assertEqual(get_dora_tiles(game), ["1m"])

        game["dora_indicator_count"] = 2

        self.assertEqual(get_dora_tiles(game), ["1m", "5z"])


if __name__ == "__main__":
    unittest.main()