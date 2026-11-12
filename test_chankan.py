import unittest
from copy import deepcopy

from main import create_game, declare_kakan, can_chankan
from yaku import get_supported_yaku


class ChankanTests(unittest.TestCase):
    def make_game(self):
        game = create_game()

        # Player 2 can upgrade an existing White Dragon Pon.
        game["current_player_index"] = 1
        game["phase"] = "discard"
        game["is_closed"][1] = False
        game["melds"][1] = [{
            "type": "pon",
            "tiles": ["5z"] * 3,
            "from_player_index": 2
        }]
        game["hands"][1] = [
            "1m", "4m", "7m",
            "1p", "4p", "7p",
            "1s", "4s", "7s",
            "5z", "2z"
        ]

        # Player 1 waits on 3m or 6m.
        # Start with 6m as the pending added tile instead.
        game["melds"][1][0]["tiles"] = ["6m"] * 3
        game["hands"][1][9] = "6m"

        game["hands"][0] = [
            "1p", "2p", "3p",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "4m", "5m",
            "2z", "2z"
        ]

        declare_kakan(game, 1, 0)

        return game

    def test_complete_hand_can_rob_kakan(self):
        game = self.make_game()

        self.assertTrue(can_chankan(game, 0))
        self.assertFalse(can_chankan(game, 1))

    def test_chankan_supplies_yaku(self):
        game = self.make_game()
        completed_hand = game["hands"][0] + ["6m"]

        # This hand has no currently supported static yaku.
        self.assertEqual(
            get_supported_yaku(
                completed_hand,
                seat_wind="1z",
                round_wind="1z"
            ),
            []
        )
        self.assertTrue(can_chankan(game, 0))

    def test_another_wait_in_discard_history_blocks_robbery(self):
        game = self.make_game()

        # The hand waits on both 3m and 6m.
        game["discard_history"][0] = ["3m"]

        self.assertFalse(can_chankan(game, 0))

    def test_temporary_furiten_blocks_robbery(self):
        game = self.make_game()
        game["temporary_furiten"][0] = True

        self.assertFalse(can_chankan(game, 0))

    def test_riichi_furiten_blocks_robbery(self):
        game = self.make_game()
        game["riichi_furiten"][0] = True

        self.assertFalse(can_chankan(game, 0))

    def test_incomplete_hand_cannot_rob(self):
        game = self.make_game()
        game["hands"][0][0] = "9m"

        self.assertFalse(can_chankan(game, 0))

    def test_wrong_phase_or_missing_declaration(self):
        game = self.make_game()
        game["phase"] = "discard"

        self.assertFalse(can_chankan(game, 0))

        game["phase"] = "kakan_response"
        game["pending_kakan"] = None

        self.assertFalse(can_chankan(game, 0))

    def test_open_hand_can_rob_kakan(self):
        game = self.make_game()

        game["hands"][0] = [
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "4m", "5m",
            "2z", "2z"
        ]
        game["melds"][0] = [{
            "type": "chi",
            "tiles": ["1p", "2p", "3p"],
            "from_player_index": 3
        }]
        game["is_closed"][0] = False

        self.assertTrue(can_chankan(game, 0))

    def test_no_mutation(self):
        game = self.make_game()
        before = deepcopy(game)

        can_chankan(game, 0)

        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()