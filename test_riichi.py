import unittest
from copy import deepcopy

from main import create_game, get_riichi_options, can_riichi


class TestRiichiEligibility(unittest.TestCase):
    def setUp(self):
        # Build an isolated fixture for eligibility checks.
        self.game = create_game()
        self.player_index = 0

        self.game["current_player_index"] = self.player_index
        self.game["phase"] = "discard"

        # Discarding 9p leaves a hand waiting for 5z.
        self.game["hands"][self.player_index] = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "9p"
        ]

    def test_eligible_hand(self):
        options = get_riichi_options(self.game, self.player_index)

        option = next(
            option
            for option in options
            if option["tile_index"] == 13
        )

        self.assertEqual(option["tile"], "9p")
        self.assertEqual(option["waiting_tiles"], ["5z"])
        self.assertTrue(can_riichi(self.game, self.player_index))

    def test_score_boundary(self):
        self.game["scores"][self.player_index] = 1000
        self.assertTrue(can_riichi(self.game, self.player_index))

        self.game["scores"][self.player_index] = 999
        self.assertFalse(can_riichi(self.game, self.player_index))

    def test_already_declared(self):
        self.game["riichi_declared"][self.player_index] = True

        self.assertFalse(can_riichi(self.game, self.player_index))

    def test_open_hand(self):
        self.game["is_closed"][self.player_index] = False

        self.assertFalse(can_riichi(self.game, self.player_index))

    def test_wrong_player(self):
        self.game["current_player_index"] = 1

        self.assertFalse(can_riichi(self.game, self.player_index))

    def test_wrong_phase(self):
        for phase in ["draw", "response", "ended"]:
            with self.subTest(phase=phase):
                self.game["phase"] = phase

                self.assertFalse(
                    can_riichi(self.game, self.player_index)
                )

    def test_wall_boundary(self):
        minimum = self.game["riichi_min_wall_tiles"]
        self.game["wall"] = self.game["wall"][:minimum]

        self.assertTrue(can_riichi(self.game, self.player_index))

        self.game["wall"].pop()

        self.assertFalse(can_riichi(self.game, self.player_index))

    def test_hand_without_tenpai_discards(self):
        self.game["hands"][self.player_index] = [
            "1m", "2m", "4m", "5m", "7m", "8m",
            "1p", "4p", "7p",
            "1s", "4s", "7s",
            "1z", "2z"
        ]

        self.assertEqual(
            get_riichi_options(self.game, self.player_index),
            []
        )
        self.assertFalse(can_riichi(self.game, self.player_index))

    def test_checks_do_not_change_game(self):
        original_game = deepcopy(self.game)

        get_riichi_options(self.game, self.player_index)
        can_riichi(self.game, self.player_index)

        self.assertEqual(self.game, original_game)


if __name__ == "__main__":
    unittest.main()