import unittest
from copy import deepcopy

from main import (
    create_game,
    get_chi_forbidden_tiles,
    get_chi_options,
    can_chi,
)


class ChiOptionTests(unittest.TestCase):
    def make_game(self):
        game = create_game()
        game["hands"][0] = [
            "1m", "2m", "4m", "5m",
            "1p", "4p", "7p",
            "1s", "4s", "7s",
            "1z", "2z", "3z"
        ]
        game["phase"] = "response"
        game["current_player_index"] = 3
        game["last_discard"] = {
            "player_index": 3,
            "tile": "3m"
        }
        return game

    def test_calling_low_end(self):
        self.assertEqual(
            get_chi_forbidden_tiles("1m", ["1m", "2m", "3m"]),
            ["1m", "4m"]
        )

    def test_calling_high_end(self):
        self.assertEqual(
            get_chi_forbidden_tiles("4m", ["2m", "3m", "4m"]),
            ["1m", "4m"]
        )

    def test_calling_middle(self):
        self.assertEqual(
            get_chi_forbidden_tiles("3m", ["2m", "3m", "4m"]),
            ["3m"]
        )

    def test_boundaries_do_not_create_invalid_tiles(self):
        self.assertEqual(
            get_chi_forbidden_tiles("3m", ["1m", "2m", "3m"]),
            ["3m"]
        )
        self.assertEqual(
            get_chi_forbidden_tiles("7s", ["7s", "8s", "9s"]),
            ["7s"]
        )

    def test_options_include_restrictions(self):
        game = self.make_game()
        options = get_chi_options(game, 0)

        self.assertTrue(can_chi(game, 0))
        self.assertEqual(len(options), 3)

        self.assertEqual(
            options[0]["forbidden_discard_tiles"],
            ["3m"]
        )
        self.assertEqual(
            options[1]["forbidden_discard_tiles"],
            ["3m"]
        )
        self.assertEqual(
            options[2]["forbidden_discard_tiles"],
            ["3m", "6m"]
        )

    def test_option_without_legal_discard_is_removed(self):
        game = self.make_game()

        # Three existing melds leave four concealed tiles.
        game["melds"][0] = [
            {"type": "pon", "tiles": ["5z"] * 3},
            {"type": "pon", "tiles": ["6z"] * 3},
            {"type": "pon", "tiles": ["7z"] * 3},
        ]
        game["is_closed"][0] = False
        game["hands"][0] = ["2m", "3m", "1m", "4m"]
        game["last_discard"]["tile"] = "1m"

        # Calling 123m leaves only 1m and 4m, both forbidden.
        self.assertEqual(get_chi_options(game, 0), [])
        self.assertFalse(can_chi(game, 0))

    def test_no_mutation(self):
        game = self.make_game()
        before = deepcopy(game)

        get_chi_options(game, 0)
        can_chi(game, 0)

        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()