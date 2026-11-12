import unittest
from copy import deepcopy

from main import create_game, create_next_hand


class NextHandTests(unittest.TestCase):
    def make_ended_game(self, reason="ron", winners=None):
        game = create_game()
        game["phase"] = "ended"
        game["end_reason"] = reason
        game["winner_indices"] = (
            [1] if winners is None else list(winners)
        )
        game["winner_index"] = (
            game["winner_indices"][0]
            if game["winner_indices"]
            else None
        )

        # These tests isolate progression after settlement.
        game["settlement"] = {
            "score_deltas": [0, 0, 0, 0],
            "tenpai_flags": [False, False, False, False],
        }

        return game

    def test_dealer_win_repeats_hand(self):
        game = self.make_ended_game(winners=[0])
        game["honba"] = 2

        next_game = create_next_hand(game)

        self.assertEqual(next_game["dealer_index"], 0)
        self.assertEqual(next_game["hand_number"], 1)
        self.assertEqual(next_game["honba"], 3)

    def test_non_dealer_win_rotates_dealer(self):
        game = self.make_ended_game(winners=[1])
        game["honba"] = 2

        next_game = create_next_hand(game)

        self.assertEqual(next_game["dealer_index"], 1)
        self.assertEqual(next_game["current_player_index"], 1)
        self.assertEqual(next_game["hand_number"], 2)
        self.assertEqual(next_game["honba"], 0)
        self.assertEqual(
            next_game["seat_winds"],
            ["4z", "1z", "2z", "3z"],
        )

    def test_dealer_in_multiple_ron_keeps_deal(self):
        game = self.make_ended_game(winners=[2, 0])

        next_game = create_next_hand(game)

        self.assertEqual(next_game["dealer_index"], 0)
        self.assertEqual(next_game["hand_number"], 1)

    def test_draw_dealer_tenpai_repeats(self):
        game = self.make_ended_game(
            reason="exhaustive_draw",
            winners=[],
        )
        game["settlement"]["tenpai_flags"][0] = True

        next_game = create_next_hand(game)

        self.assertEqual(next_game["dealer_index"], 0)
        self.assertEqual(next_game["hand_number"], 1)
        self.assertEqual(next_game["honba"], 1)

    def test_draw_dealer_noten_rotates_but_keeps_honba(self):
        game = self.make_ended_game(
            reason="exhaustive_draw",
            winners=[],
        )
        game["honba"] = 2

        next_game = create_next_hand(game)

        self.assertEqual(next_game["dealer_index"], 1)
        self.assertEqual(next_game["hand_number"], 2)
        self.assertEqual(next_game["honba"], 3)

    def test_east_four_advances_to_south_one(self):
        game = self.make_ended_game(winners=[0])
        game["dealer_index"] = 3
        game["hand_number"] = 4

        next_game = create_next_hand(game)

        self.assertEqual(next_game["round_wind"], "2z")
        self.assertEqual(next_game["hand_number"], 1)
        self.assertEqual(next_game["dealer_index"], 0)

    def test_preserves_balances_and_resets_hand_state(self):
        game = self.make_ended_game()
        game["scores"] = [28000, 23000, 24000, 24000]
        game["riichi_sticks"] = 1
        game["human_player_index"] = 2
        game["discards"][0] = ["1m"]
        game["riichi_declared"][0] = True
        game["temporary_furiten"][0] = True

        next_game = create_next_hand(game)

        self.assertEqual(next_game["scores"], game["scores"])
        self.assertIsNot(next_game["scores"], game["scores"])
        self.assertEqual(next_game["riichi_sticks"], 1)
        self.assertEqual(next_game["human_player_index"], 2)
        self.assertEqual(next_game["phase"], "draw")
        self.assertIsNone(next_game["settlement"])
        self.assertEqual(next_game["winner_indices"], [])
        self.assertEqual(next_game["discards"], [[], [], [], []])
        self.assertEqual(next_game["melds"], [[], [], [], []])
        self.assertFalse(any(next_game["riichi_declared"]))
        self.assertFalse(any(next_game["temporary_furiten"]))
        self.assertEqual(
            [len(hand) for hand in next_game["hands"]],
            [13, 13, 13, 13],
        )
        self.assertEqual(len(next_game["wall"]), 70)
        self.assertEqual(len(next_game["dead_wall"]), 14)

    def test_south_four_ends_when_dealer_rotates(self):
        game = self.make_ended_game(winners=[0])
        game["round_wind"] = "2z"
        game["hand_number"] = 4
        game["dealer_index"] = 3

        next_game = create_next_hand(game)

        self.assertTrue(next_game["match_ended"])
        self.assertEqual(next_game["phase"], "ended")
        self.assertEqual(next_game["hands"], game["hands"])
        self.assertEqual(next_game["scores"], game["scores"])

    def test_south_four_can_continue_with_dealer(self):
        game = self.make_ended_game(winners=[3])
        game["round_wind"] = "2z"
        game["hand_number"] = 4
        game["dealer_index"] = 3

        next_game = create_next_hand(game)

        self.assertFalse(next_game["match_ended"])
        self.assertEqual(next_game["round_wind"], "2z")
        self.assertEqual(next_game["hand_number"], 4)
        self.assertEqual(next_game["dealer_index"], 3)
        self.assertEqual(next_game["honba"], 1)

    def test_old_game_is_not_modified(self):
        game = self.make_ended_game()
        before = deepcopy(game)

        create_next_hand(game)

        self.assertEqual(game, before)

    def test_rejects_unfinished_unsettled_or_finished_match(self):
        for case in ("playing", "unsettled", "match_ended"):
            with self.subTest(case=case):
                game = self.make_ended_game()

                if case == "playing":
                    game["phase"] = "discard"
                elif case == "unsettled":
                    game["settlement"] = None
                else:
                    game["match_ended"] = True

                before = deepcopy(game)

                with self.assertRaises(ValueError):
                    create_next_hand(game)

                self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()