import unittest
from copy import deepcopy

from main import create_game, get_kakan_options, can_kakan


class KakanOptionTests(unittest.TestCase):
    def make_game(self):
        game = create_game()

        game["phase"] = "discard"
        game["current_player_index"] = 0
        game["is_closed"][0] = False

        game["melds"][0] = [{
            "type": "pon",
            "tiles": ["5z"] * 3,
            "from_player_index": 1
        }]

        game["hands"][0] = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "5z", "1z"
        ]

        return game

    def test_existing_pon_can_be_upgraded(self):
        game = self.make_game()

        self.assertEqual(get_kakan_options(game, 0), [
            {"meld_index": 0, "tile": "5z"}
        ])
        self.assertTrue(can_kakan(game, 0))

    def test_fourth_tile_need_not_be_last(self):
        game = self.make_game()

        self.assertNotEqual(game["hands"][0][-1], "5z")
        self.assertTrue(can_kakan(game, 0))

    def test_missing_fourth_tile(self):
        game = self.make_game()
        game["hands"][0][9] = "2z"

        self.assertEqual(get_kakan_options(game, 0), [])

    def test_only_pon_can_be_upgraded(self):
        game = self.make_game()

        game["melds"][0] = [{
            "type": "chi",
            "tiles": ["4m", "5m", "6m"],
            "from_player_index": 3
        }]

        self.assertFalse(can_kakan(game, 0))

    def test_wrong_turn_and_phase(self):
        game = self.make_game()

        self.assertFalse(can_kakan(game, 1))

        game["phase"] = "response"
        self.assertFalse(can_kakan(game, 0))

    def test_call_turn_and_riichi_are_blocked(self):
        for case in ("call", "riichi"):
            with self.subTest(case=case):
                game = self.make_game()

                if case == "call":
                    game["after_call"] = True
                else:
                    game["riichi_declared"][0] = True

                self.assertFalse(can_kakan(game, 0))

    def test_replacement_limits(self):
        for case in ("wall", "rinshan", "indicators"):
            with self.subTest(case=case):
                game = self.make_game()

                if case == "wall":
                    game["wall"] = []
                elif case == "rinshan":
                    game["rinshan_draw_count"] = 4
                else:
                    game["dora_indicator_count"] = 5

                self.assertFalse(can_kakan(game, 0))

    def test_multiple_pons(self):
        game = self.make_game()

        game["melds"][0].append({
            "type": "pon",
            "tiles": ["6z"] * 3,
            "from_player_index": 2
        })

        game["hands"][0] = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "5z", "6z"
        ]

        self.assertEqual(get_kakan_options(game, 0), [
            {"meld_index": 0, "tile": "5z"},
            {"meld_index": 1, "tile": "6z"}
        ])

    def test_no_mutation(self):
        game = self.make_game()
        before = deepcopy(game)

        get_kakan_options(game, 0)
        can_kakan(game, 0)

        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()