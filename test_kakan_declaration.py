import unittest
from copy import deepcopy

from main import (
    create_game,
    declare_kakan,
    finish_turn,
    start_turn,
    advance_until_human,
)


class KakanDeclarationTests(unittest.TestCase):
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

    def test_declaration_only_changes_response_state(self):
        game = self.make_game()
        before = deepcopy(game)

        declare_kakan(game, 0, 0)

        self.assertEqual(game["phase"], "kakan_response")
        self.assertEqual(game["pending_kakan"], {
            "player_index": 0,
            "meld_index": 0,
            "tile": "5z"
        })

        # All physical tile locations remain unchanged.
        for field in ("hands", "melds", "wall", "dead_wall", "discards"):
            self.assertEqual(game[field], before[field])

        self.assertEqual(game["rinshan_draw_count"], 0)
        self.assertEqual(game["dora_indicator_count"], 1)
        self.assertEqual(game["scores"], before["scores"])

    def test_invalid_index_changes_nothing(self):
        for meld_index in (-1, 99, True, "0"):
            with self.subTest(meld_index=meld_index):
                game = self.make_game()
                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    declare_kakan(game, 0, meld_index)

                self.assertEqual(game, before)

    def test_cannot_declare_twice(self):
        game = self.make_game()
        declare_kakan(game, 0, 0)
        before = deepcopy(game)

        with self.assertRaises(ValueError):
            declare_kakan(game, 0, 0)

        self.assertEqual(game, before)

    def test_draw_and_discard_are_blocked_while_pending(self):
        game = self.make_game()
        declare_kakan(game, 0, 0)
        before = deepcopy(game)

        with self.assertRaises(ValueError):
            start_turn(game)

        with self.assertRaises(ValueError):
            finish_turn(game, 0, 0)

        self.assertEqual(game, before)

    def test_automatic_advance_resolves_pending_kakan(self):
        game = self.make_game()

        # Ensure computers decline robbery in this isolated test.
        for index in (1, 2, 3):
            game["temporary_furiten"][index] = True

        declare_kakan(game, 0, 0)
        advance_until_human(game)

        self.assertEqual(game["phase"], "discard")
        self.assertEqual(game["current_player_index"], 0)
        self.assertIsNone(game["pending_kakan"])
        self.assertEqual(game["melds"][0][0]["type"], "kakan")
        self.assertEqual(game["rinshan_draw_count"], 1)


if __name__ == "__main__":
    unittest.main()