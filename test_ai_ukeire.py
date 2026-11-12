import unittest
from copy import deepcopy

from ai import analyze_discards


class UkeireTests(unittest.TestCase):
    def make_hand(self):
        return [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "9p",
        ]

    def test_discard_to_tenpai(self):
        result = analyze_discards(
            self.make_hand(),
            allowed_indices=[13],
        )[0]

        self.assertEqual(result["tile"], "9p")
        self.assertEqual(result["shanten"], 0)
        self.assertEqual(result["ukeire"], 3)
        self.assertEqual(
            result["improving_tiles"],
            [{
                "tile": "5z",
                "remaining": 3,
                "shanten": -1,
            }],
        )

    def test_visible_tiles_reduce_ukeire(self):
        result = analyze_discards(
            self.make_hand(),
            visible_tiles=["5z", "5z"],
            allowed_indices=[13],
        )[0]

        self.assertEqual(result["shanten"], 0)
        self.assertEqual(result["ukeire"], 1)
        self.assertEqual(
            result["improving_tiles"][0]["remaining"],
            1,
        )

    def test_exhausted_wait_is_not_counted(self):
        result = analyze_discards(
            self.make_hand(),
            visible_tiles=["5z"] * 3,
            allowed_indices=[13],
        )[0]

        # Structurally Tenpai, but no unseen winning tiles remain.
        self.assertEqual(result["shanten"], 0)
        self.assertEqual(result["ukeire"], 0)
        self.assertEqual(result["improving_tiles"], [])

    def test_discarded_copy_remains_known(self):
        hand = self.make_hand()
        hand[-1] = "5z"

        result = analyze_discards(
            hand,
            allowed_indices=[13],
        )[0]

        # One copy remains in hand, one is discarded.
        self.assertEqual(result["ukeire"], 2)
        self.assertEqual(
            result["improving_tiles"],
            [{
                "tile": "5z",
                "remaining": 2,
                "shanten": -1,
            }],
        )

    def test_allowed_indices_are_respected(self):
        results = analyze_discards(
            self.make_hand(),
            allowed_indices=[12, 13],
        )

        self.assertEqual(
            [result["tile_index"] for result in results],
            [12, 13],
        )

        self.assertEqual(
            analyze_discards(
                self.make_hand(),
                allowed_indices=[],
            ),
            [],
        )

    def test_open_hand(self):
        hand = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "9p",
        ]
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

        result = analyze_discards(
            hand,
            melds,
            allowed_indices=[10],
        )[0]

        self.assertEqual(result["shanten"], 0)
        self.assertEqual(result["ukeire"], 3)

    def test_invalid_inputs(self):
        hand = self.make_hand()

        cases = [
            {"visible_tiles": ["5z"] * 4},
            {"visible_tiles": ["invalid"]},
            {"allowed_indices": [-1]},
            {"allowed_indices": [True]},
            {"allowed_indices": [0, 0]},
        ]

        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    analyze_discards(hand, **arguments)

        with self.assertRaises(ValueError):
            analyze_discards(hand[:-1])

    def test_inputs_and_duplicate_results_are_independent(self):
        hand = self.make_hand()
        visible = ["5z"]
        before = deepcopy((hand, visible))

        results = analyze_discards(
            hand,
            visible_tiles=visible,
            allowed_indices=[9, 10],
        )

        self.assertEqual((hand, visible), before)

        self.assertEqual(
            results[0]["improving_tiles"],
            results[1]["improving_tiles"],
        )

        second_before = deepcopy(results[1])
        results[0]["improving_tiles"].append({
            "tile": "9z",
            "remaining": 0,
            "shanten": 0,
        })

        self.assertEqual(results[1], second_before)


if __name__ == "__main__":
    unittest.main()