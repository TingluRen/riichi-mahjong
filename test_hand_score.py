import unittest
from copy import deepcopy

from scoring import evaluate_hand_score


class HandScoreTests(unittest.TestCase):
    def make_pinfu_hand(self):
        return [
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "2p", "3p", "4p",
            "6s", "7s", "8s",
            "2z", "2z",
        ]

    def test_pinfu_tsumo_with_dora(self):
        result = evaluate_hand_score(
            self.make_pinfu_hand(),
            "1m",
            is_tsumo=True,
            dora_count=1,
        )

        self.assertCountEqual(
            result["yaku"],
            ["Pinfu", "Menzen Tsumo"],
        )
        self.assertEqual(result["yaku_han"], 2)
        self.assertEqual(result["bonus_han"], 1)
        self.assertEqual(result["han"], 3)
        self.assertEqual(result["fu"], 20)
        self.assertEqual(result["payments"]["total"], 2700)

    def test_dora_cannot_supply_the_only_yaku(self):
        # Winning on 3m is an edge wait, so no Pinfu.
        result = evaluate_hand_score(
            self.make_pinfu_hand(),
            "3m",
            dora_count=13,
        )

        self.assertIsNone(result)

    def test_riichi_and_ura_dora(self):
        result = evaluate_hand_score(
            self.make_pinfu_hand(),
            "1m",
            riichi=True,
            dora_count=1,
            ura_dora_count=2,
        )

        self.assertCountEqual(result["yaku"], ["Pinfu", "Riichi"])
        self.assertEqual(result["yaku_han"], 2)
        self.assertEqual(result["bonus_han"], 3)
        self.assertEqual(result["han"], 5)
        self.assertEqual(result["payments"]["limit"], "Mangan")
        self.assertEqual(result["payments"]["ron_payment"], 8000)

    def test_ura_is_ignored_without_riichi(self):
        result = evaluate_hand_score(
            self.make_pinfu_hand(),
            "1m",
            ura_dora_count=3,
        )

        self.assertEqual(result["ura_dora_count"], 0)
        self.assertEqual(result["han"], 1)
        self.assertEqual(result["payments"]["ron_payment"], 1000)

    def test_selects_standard_over_seven_pairs(self):
        hand = [
            "1m", "2m", "3m",
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "4p", "5p", "6p",
            "5z", "5z",
        ]

        result = evaluate_hand_score(hand, "1m")

        self.assertIn("Ryanpeikou", result["yaku"])
        self.assertNotIn("Chiitoitsu", result["yaku"])
        self.assertEqual(result["han"], 3)
        self.assertEqual(result["fu"], 40)
        self.assertEqual(result["payments"]["ron_payment"], 5200)

    def test_actual_yakuman_ignores_bonus_han(self):
        hand = [
            "1m", "9m", "1p", "9p", "1s", "9s",
            "1z", "2z", "3z", "4z", "5z", "6z", "7z",
            "1m",
        ]

        result = evaluate_hand_score(
            hand,
            "1m",
            riichi=True,
            dora_count=5,
            ura_dora_count=5,
        )

        self.assertEqual(result["yaku"], ["Kokushi Musou"])
        self.assertEqual(result["yakuman_count"], 1)
        self.assertEqual(result["bonus_han"], 0)
        self.assertEqual(result["han"], 0)
        self.assertIsNone(result["fu"])
        self.assertEqual(result["payments"]["ron_payment"], 32000)

    def test_open_rinshan_supplies_the_only_yaku(self):
        hand = [
            "1p", "2p", "3p",
            "4s", "5s", "6s",
            "7m", "8m", "9m",
            "2z", "2z",
        ]
        melds = [{
            "type": "daiminkan",
            "tiles": ["1m"] * 4,
            "from_player_index": 1,
        }]

        without_rinshan = evaluate_hand_score(
            hand,
            "2z",
            melds,
            is_tsumo=True,
        )
        with_rinshan = evaluate_hand_score(
            hand,
            "2z",
            melds,
            is_tsumo=True,
            rinshan=True,
        )

        self.assertIsNone(without_rinshan)
        self.assertEqual(
            with_rinshan["yaku"],
            ["Rinshan Kaihou"],
        )
        self.assertEqual(with_rinshan["han"], 1)
        self.assertEqual(with_rinshan["fu"], 40)

    def test_invalid_context(self):
        for arguments in (
            {"is_tsumo": True, "chankan": True},
            {"rinshan": True},
            {"dora_count": -1},
            {"ura_dora_count": True},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    evaluate_hand_score(
                        self.make_pinfu_hand(),
                        "1m",
                        **arguments,
                    )

    def test_incomplete_hand_returns_none(self):
        self.assertIsNone(
            evaluate_hand_score(["1m", "2m"], "2m")
        )

    def test_inputs_are_not_modified(self):
        hand = self.make_pinfu_hand()
        before = deepcopy(hand)

        evaluate_hand_score(
            hand,
            "1m",
            is_tsumo=True,
            dora_count=1,
        )

        self.assertEqual(hand, before)


if __name__ == "__main__":
    unittest.main()