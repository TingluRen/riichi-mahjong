import unittest
from copy import deepcopy

from main import count_dora


class DoraCountTests(unittest.TestCase):
    def test_counts_concealed_tiles(self):
        hand = ["4m", "4m", "5p"]

        self.assertEqual(count_dora(hand, [], ["3m"]), 2)

    def test_counts_declared_kan_as_four_tiles(self):
        melds = [{
            "type": "ankan",
            "tiles": ["4m"] * 4
        }]

        self.assertEqual(count_dora([], melds, ["3m"]), 4)

    def test_repeated_indicators_stack(self):
        hand = ["4m", "4m"]

        self.assertEqual(
            count_dora(hand, [], ["3m", "3m"]),
            4
        )

    def test_counts_winning_tile(self):
        # The final tile is the tile claimed for Ron.
        winning_hand = ["1m", "2m", "4m"]

        self.assertEqual(
            count_dora(winning_hand, [], ["3m"]),
            1
        )

    def test_no_matching_tiles(self):
        self.assertEqual(
            count_dora(["1m", "2p"], [], ["3m"]),
            0
        )

    def test_inputs_are_not_modified(self):
        hand = ["4m", "2p"]
        melds = [{
            "type": "pon",
            "tiles": ["5z"] * 3,
            "from_player_index": 1
        }]
        indicators = ["3m", "7z"]

        before = deepcopy((hand, melds, indicators))

        self.assertEqual(count_dora(hand, melds, indicators), 4)
        self.assertEqual((hand, melds, indicators), before)


if __name__ == "__main__":
    unittest.main()