import unittest
from copy import deepcopy

from main import create_game, get_ankan_options, can_ankan


class AnkanOptionTests(unittest.TestCase):
    def make_game(self):
        game = create_game()
        game["phase"] = "discard"
        game["current_player_index"] = 0
        game["hands"][0] = [
            "3m", "3m", "3m", "3m",
            "1p", "2p", "3p",
            "4s", "5s", "6s",
            "1z", "1z", "5z", "6z"
        ]
        return game

    def test_four_identical_tiles(self):
        game = self.make_game()

        self.assertEqual(get_ankan_options(game, 0), ["3m"])
        self.assertTrue(can_ankan(game, 0))

    def test_two_options(self):
        game = self.make_game()
        game["hands"][0][4:8] = ["5z"] * 4
        game["hands"][0][12] = "7z"

        self.assertEqual(
            get_ankan_options(game, 0),
            ["3m", "5z"]
        )

    def test_three_copies_are_not_enough(self):
        game = self.make_game()
        game["hands"][0][0] = "9m"

        self.assertFalse(can_ankan(game, 0))

    def test_wrong_turn_or_phase(self):
        game = self.make_game()

        self.assertFalse(can_ankan(game, 1))

        game["phase"] = "draw"
        self.assertFalse(can_ankan(game, 0))

    def test_riichi_and_call_turn_are_blocked(self):
        for field in ("riichi", "call"):
            with self.subTest(field=field):
                game = self.make_game()

                if field == "riichi":
                    game["riichi_declared"][0] = True
                else:
                    game["after_call"] = True

                self.assertFalse(can_ankan(game, 0))

    def test_replacement_limits(self):
        for limit in ("wall", "rinshan", "indicators"):
            with self.subTest(limit=limit):
                game = self.make_game()

                if limit == "wall":
                    game["wall"] = []
                elif limit == "rinshan":
                    game["rinshan_draw_count"] = 4
                else:
                    game["dora_indicator_count"] = 5

                self.assertFalse(can_ankan(game, 0))

    def test_open_hand_can_still_have_ankan(self):
        game = self.make_game()
        game["melds"][0] = [{
            "type": "pon",
            "tiles": ["7z"] * 3,
            "from_player_index": 1
        }]
        game["is_closed"][0] = False
        game["hands"][0] = game["hands"][0][:11]

        self.assertEqual(get_ankan_options(game, 0), ["3m"])

    def test_no_mutation(self):
        game = self.make_game()
        before = deepcopy(game)

        get_ankan_options(game, 0)
        can_ankan(game, 0)

        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()