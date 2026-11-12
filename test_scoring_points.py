import unittest

from scoring import calculate_points


class PointCalculationTests(unittest.TestCase):
    def test_non_dealer_ron(self):
        cases = [
            (1, 30, 1000),
            (1, 40, 1300),
            (2, 25, 1600),
            (3, 40, 5200),
            (4, 30, 7700),
        ]

        for han, fu, expected in cases:
            with self.subTest(han=han, fu=fu):
                result = calculate_points(han, fu)

                self.assertEqual(result["ron_payment"], expected)
                self.assertEqual(result["total"], expected)

    def test_dealer_ron(self):
        cases = [
            (1, 30, 1500),
            (2, 40, 3900),
            (3, 40, 7700),
            (4, 30, 11600),
        ]

        for han, fu, expected in cases:
            with self.subTest(han=han, fu=fu):
                result = calculate_points(
                    han,
                    fu,
                    is_dealer=True,
                )

                self.assertEqual(result["ron_payment"], expected)

    def test_non_dealer_tsumo_rounds_each_payment(self):
        result = calculate_points(
            1,
            30,
            is_tsumo=True,
        )

        self.assertEqual(result["dealer_payment"], 500)
        self.assertEqual(result["non_dealer_payment"], 300)
        self.assertEqual(result["total"], 1100)
        self.assertIsNone(result["ron_payment"])

    def test_dealer_tsumo(self):
        result = calculate_points(
            3,
            40,
            is_dealer=True,
            is_tsumo=True,
        )

        self.assertEqual(result["non_dealer_payment"], 2600)
        self.assertEqual(result["total"], 7800)
        self.assertIsNone(result["dealer_payment"])

    def test_pinfu_tsumo(self):
        result = calculate_points(
            2,
            20,
            is_tsumo=True,
        )

        self.assertEqual(result["dealer_payment"], 700)
        self.assertEqual(result["non_dealer_payment"], 400)
        self.assertEqual(result["total"], 1500)

    def test_limit_hands(self):
        cases = [
            (3, 70, "Mangan", 8000),
            (4, 40, "Mangan", 8000),
            (5, 30, "Mangan", 8000),
            (6, 30, "Haneman", 12000),
            (7, 30, "Haneman", 12000),
            (8, 30, "Baiman", 16000),
            (10, 30, "Baiman", 16000),
            (11, 30, "Sanbaiman", 24000),
            (12, 30, "Sanbaiman", 24000),
            (13, 30, "Kazoe Yakuman", 32000),
            (26, 30, "Kazoe Yakuman", 32000),
        ]

        for han, fu, limit, payment in cases:
            with self.subTest(han=han, fu=fu):
                result = calculate_points(han, fu)

                self.assertEqual(result["limit"], limit)
                self.assertEqual(result["ron_payment"], payment)

    def test_kiriage_mangan_option(self):
        for han, fu in ((4, 30), (3, 60)):
            with self.subTest(han=han, fu=fu):
                normal = calculate_points(han, fu)
                kiriage = calculate_points(
                    han,
                    fu,
                    kiriage_mangan=True,
                )

                self.assertEqual(normal["ron_payment"], 7700)
                self.assertIsNone(normal["limit"])
                self.assertEqual(kiriage["ron_payment"], 8000)
                self.assertEqual(kiriage["limit"], "Mangan")

    def test_kazoe_sanbaiman_option(self):
        result = calculate_points(
            13,
            30,
            kazoe_limit="sanbaiman",
        )

        self.assertEqual(result["limit"], "Sanbaiman")
        self.assertEqual(result["ron_payment"], 24000)

    def test_actual_yakuman(self):
        result = calculate_points(
            0,
            None,
            yakuman_count=1,
        )

        self.assertEqual(result["basic_points"], 8000)
        self.assertEqual(result["ron_payment"], 32000)
        self.assertEqual(result["limit"], "Yakuman")

    def test_dealer_yakuman_tsumo(self):
        result = calculate_points(
            0,
            None,
            yakuman_count=1,
            is_dealer=True,
            is_tsumo=True,
        )

        self.assertEqual(result["non_dealer_payment"], 16000)
        self.assertEqual(result["total"], 48000)

    def test_multiple_actual_yakuman(self):
        result = calculate_points(
            0,
            None,
            yakuman_count=2,
        )

        self.assertEqual(result["ron_payment"], 64000)

    def test_invalid_inputs(self):
        cases = [
            {"han": 0, "fu": 30},
            {"han": True, "fu": 30},
            {"han": 1, "fu": 32},
            {"han": 1, "fu": 25},
            {"han": 2, "fu": 20},
            {"han": 2, "fu": None},
            {"han": 2, "fu": 30, "is_dealer": 1},
            {"han": 2, "fu": 30, "yakuman_count": -1},
            {"han": 2, "fu": 30, "kazoe_limit": "unknown"},
        ]

        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    calculate_points(**arguments)


if __name__ == "__main__":
    unittest.main()