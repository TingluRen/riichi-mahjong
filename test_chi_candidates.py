import unittest
from copy import deepcopy

from main import create_game, get_chi_candidates


class ChiCandidateTests(unittest.TestCase):
    def make_game(self):
        game = create_game()

        game["hands"][0] = [
            "1m", "2m", "4m", "5m",
            "1p", "4p", "7p",
            "1s", "4s", "7s",
            "1z", "2z", "3z"
        ]

        game["current_player_index"] = 3
        game["phase"] = "response"
        game["last_discard"] = {
            "player_index": 3,
            "tile": "3m"
        }

        return game

    def test_three_combinations(self):
        game = self.make_game()

        self.assertEqual(get_chi_candidates(game, 0), [
            {
                "tiles": ["1m", "2m", "3m"],
                "hand_tiles": ["1m", "2m"]
            },
            {
                "tiles": ["2m", "3m", "4m"],
                "hand_tiles": ["2m", "4m"]
            },
            {
                "tiles": ["3m", "4m", "5m"],
                "hand_tiles": ["4m", "5m"]
            }
        ])

    def test_only_previous_player(self):
        game = self.make_game()

        for discarder in (0, 1, 2):
            with self.subTest(discarder=discarder):
                game["last_discard"]["player_index"] = discarder

                self.assertEqual(get_chi_candidates(game, 0), [])

    def test_honors_cannot_form_chi(self):
        game = self.make_game()
        game["last_discard"]["tile"] = "2z"

        self.assertEqual(get_chi_candidates(game, 0), [])

    def test_number_boundaries(self):
        game = self.make_game()
        game["hands"][0][:4] = ["2m", "3m", "7m", "8m"]

        game["last_discard"]["tile"] = "1m"
        self.assertEqual(
            [option["tiles"] for option in get_chi_candidates(game, 0)],
            [["1m", "2m", "3m"]]
        )

        game["last_discard"]["tile"] = "9m"
        self.assertEqual(
            [option["tiles"] for option in get_chi_candidates(game, 0)],
            [["7m", "8m", "9m"]]
        )

    def test_missing_tiles(self):
        game = self.make_game()
        game["last_discard"]["tile"] = "6p"

        self.assertEqual(get_chi_candidates(game, 0), [])

    def test_riichi_blocks_chi(self):
        game = self.make_game()
        game["riichi_declared"][0] = True

        self.assertEqual(get_chi_candidates(game, 0), [])

    def test_wrong_phase(self):
        game = self.make_game()
        game["phase"] = "draw"

        self.assertEqual(get_chi_candidates(game, 0), [])

    def test_final_discard_blocks_chi(self):
        game = self.make_game()
        game["wall"] = []

        self.assertEqual(get_chi_candidates(game, 0), [])

    def test_no_mutation(self):
        game = self.make_game()
        original = deepcopy(game)

        get_chi_candidates(game, 0)

        self.assertEqual(game, original)


if __name__ == "__main__":
    unittest.main()