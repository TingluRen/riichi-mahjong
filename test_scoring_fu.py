import unittest
from copy import deepcopy

from scoring import get_group_fu, get_fu_candidates


class FuTests(unittest.TestCase):
    def make_pinfu_hand(self, pair="2z"):
        return [
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "2p", "3p", "4p",
            "6s", "7s", "8s",
            pair, pair,
        ]

    def test_pinfu_tsumo_is_20(self):
        results = get_fu_candidates(
            self.make_pinfu_hand(),
            "1m",
            is_tsumo=True,
        )

        self.assertEqual(len(results), 1)
        self.assertIn("Pinfu", results[0]["yaku"])
        self.assertEqual(results[0]["fu"], 20)

    def test_pinfu_ron_is_30(self):
        result = get_fu_candidates(
            self.make_pinfu_hand(),
            "1m",
        )[0]

        self.assertEqual(result["raw_fu"], 30)
        self.assertEqual(result["fu"], 30)

    def test_seven_pairs_is_fixed_25(self):
        hand = [
            "1m", "1m", "4m", "4m", "7m", "7m",
            "2p", "2p", "5p", "5p",
            "3s", "3s", "6z", "6z",
        ]

        for is_tsumo in (False, True):
            with self.subTest(is_tsumo=is_tsumo):
                results = get_fu_candidates(
                    hand,
                    "6z",
                    is_tsumo=is_tsumo,
                )

                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["fu"], 25)

    def test_wait_fu(self):
        for tile in ("2m", "3m", "2z"):
            with self.subTest(winning_tile=tile):
                result = get_fu_candidates(
                    self.make_pinfu_hand(),
                    tile,
                )[0]

                self.assertEqual(result["raw_fu"], 32)
                self.assertEqual(result["fu"], 40)

    def test_dragon_pair(self):
        result = get_fu_candidates(
            self.make_pinfu_hand(pair="5z"),
            "1m",
        )[0]

        self.assertEqual(result["raw_fu"], 32)
        self.assertEqual(result["fu"], 40)

    def test_double_wind_pair_is_configurable(self):
        hand = self.make_pinfu_hand(pair="1z")

        for pair_fu, expected_raw in ((4, 34), (2, 32)):
            with self.subTest(pair_fu=pair_fu):
                result = get_fu_candidates(
                    hand,
                    "1m",
                    double_wind_pair_fu=pair_fu,
                )[0]

                self.assertEqual(result["raw_fu"], expected_raw)
                self.assertEqual(result["fu"], 40)

    def test_triplet_and_kan_fu_table(self):
        cases = [
            ("triplet", "2m", False, 2),
            ("triplet", "2m", True, 4),
            ("triplet", "1m", False, 4),
            ("triplet", "1z", True, 8),
            ("daiminkan", "2m", False, 8),
            ("ankan", "2m", True, 16),
            ("kakan", "9m", False, 16),
            ("ankan", "1z", True, 32),
        ]

        for group_type, tile, concealed, expected in cases:
            with self.subTest(
                group_type=group_type,
                tile=tile,
                concealed=concealed,
            ):
                tile_count = (
                    3 if group_type == "triplet" else 4
                )

                group = {
                    "type": group_type,
                    "tiles": [tile] * tile_count,
                }

                self.assertEqual(
                    get_group_fu(group, concealed=concealed),
                    expected
                )

    def test_ron_completed_triplet_uses_open_triplet_fu(self):
        hand = (
            ["2m"] * 3
            + ["4p", "5p", "6p"]
            + ["6s", "7s", "8s"]
            + ["7p", "8p", "9p"]
            + ["2z"] * 2
        )

        ron = get_fu_candidates(hand, "2m")[0]
        tsumo = get_fu_candidates(
            hand, "2m", is_tsumo=True
        )[0]

        # Ron: base 20 + closed Ron 10 + open simple triplet 2.
        self.assertEqual(ron["raw_fu"], 32)
        self.assertEqual(ron["fu"], 40)

        # Tsumo: base 20 + concealed simple triplet 4 + Tsumo 2.
        self.assertEqual(tsumo["raw_fu"], 26)
        self.assertEqual(tsumo["fu"], 30)

    def test_open_ron_minimum(self):
        hand = [
            "1p", "2p", "3p",
            "1s", "2s", "3s",
            "7m", "8m", "9m",
            "2z", "2z",
        ]
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

        result = get_fu_candidates(
            hand,
            "1p",
            melds,
        )[0]

        self.assertIn("Sanshoku Doujun", result["yaku"])
        self.assertNotIn("Pinfu", result["yaku"])
        self.assertEqual(result["fu"], 30)

    def test_ankan_counts_without_breaking_closed_ron(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "6s", "7s", "8s",
            "2z", "2z",
        ]
        melds = [{
            "type": "ankan",
            "tiles": ["9p"] * 4,
        }]

        result = get_fu_candidates(
            hand,
            "1m",
            melds,
        )[0]

        # Base 20 + closed Ron 10 + concealed terminal Kan 32.
        self.assertEqual(result["raw_fu"], 62)
        self.assertEqual(result["fu"], 70)

    def test_kokushi_does_not_use_fu(self):
        hand = [
            "1m", "9m", "1p", "9p", "1s", "9s",
            "1z", "2z", "3z", "4z", "5z", "6z", "7z",
            "1m",
        ]

        result = get_fu_candidates(hand, "1m")[0]

        self.assertIsNone(result["fu"])

    def test_inputs_are_not_modified(self):
        hand = self.make_pinfu_hand()
        before = deepcopy(hand)

        get_fu_candidates(hand, "1m")

        self.assertEqual(hand, before)


if __name__ == "__main__":
    unittest.main()