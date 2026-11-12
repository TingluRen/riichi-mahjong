import unittest
from copy import deepcopy

from main import (
    create_game,
    declare_riichi,
    finish_turn,
    resolve_ron_responses,
    start_turn,
    can_ron,
    can_tsumo,
    pass_ron,
    get_winner_score,
)


class TestRiichiDeclaration(unittest.TestCase):
    def setUp(self):
        # Isolated fixtures for testing state transitions.
        self.game = create_game()
        self.game["current_player_index"] = 0
        self.game["phase"] = "discard"

        self.game["hands"][0] = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "9p"
        ]

    def accept_riichi(self):
        declare_riichi(self.game, 0, 13)
        resolve_ron_responses(self.game, [])

    def prepare_ron(self, tile="5z"):
        self.game["phase"] = "response"
        self.game["current_player_index"] = 1
        self.game["last_discard"] = {
            "player_index": 1,
            "tile": tile
        }

    def test_declaration_waits_before_payment(self):
        tile = declare_riichi(self.game, 0, 13)

        self.assertEqual(tile, "9p")
        self.assertEqual(self.game["phase"], "response")
        self.assertEqual(self.game["pending_riichi"], 0)
        self.assertFalse(self.game["riichi_declared"][0])
        self.assertEqual(self.game["scores"][0], 25000)
        self.assertEqual(self.game["riichi_sticks"], 0)
        self.assertEqual(len(self.game["hands"][0]), 13)
        self.assertEqual(self.game["discards"][0], ["9p"])

    def test_accepted_riichi_deducts_once(self):
        self.accept_riichi()

        self.assertTrue(self.game["riichi_declared"][0])
        self.assertIsNone(self.game["pending_riichi"])
        self.assertEqual(self.game["scores"][0], 24000)
        self.assertEqual(self.game["riichi_sticks"], 1)

        # A repeated resolution must not deduct points again.
        with self.assertRaises(ValueError):
            resolve_ron_responses(self.game, [])

        self.assertEqual(self.game["scores"][0], 24000)
        self.assertEqual(self.game["riichi_sticks"], 1)

    def test_invalid_declaration_changes_nothing(self):
        original = deepcopy(self.game)

        with self.assertRaises(ValueError):
            declare_riichi(self.game, 0, 0)

        self.assertEqual(self.game, original)

    def test_ron_on_declaration_cancels_riichi(self):
        # Player 2 can win on the declaration tile, 9p.
        self.game["hands"][1] = [
            "1m", "2m", "3m",
            "4s", "5s", "6s",
            "7s", "8s", "9s",
            "5z", "5z", "5z",
            "9p"
        ]

        declare_riichi(self.game, 0, 13)

        self.assertTrue(can_ron(self.game, 1))
        resolve_ron_responses(self.game, [1])

        self.assertEqual(self.game["end_reason"], "ron")
        self.assertFalse(self.game["riichi_declared"][0])
        self.assertIsNone(self.game["pending_riichi"])
        # Pay each winner, without deducting a Riichi deposit.
        ron_payment = sum(
            get_winner_score(self.game, winner)["payments"]["ron_payment"]
            for winner in self.game["winner_indices"]
        )

        self.assertEqual(
            self.game["scores"][0],
            25000 - ron_payment,
        )
        self.assertEqual(self.game["riichi_sticks"], 0)

    def test_only_drawn_tile_can_be_discarded(self):
        self.accept_riichi()

        self.game["current_player_index"] = 0
        self.game["phase"] = "draw"
        self.game["wall"].append("2p")
        start_turn(self.game)

        original = deepcopy(self.game)

        with self.assertRaises(ValueError):
            finish_turn(self.game, 0, 0)

        self.assertEqual(self.game, original)

        tile = finish_turn(self.game, 0, 13)
        self.assertEqual(tile, "2p")
        self.assertEqual(len(self.game["hands"][0]), 13)

    def test_riichi_supplies_yaku_for_ron(self):
        # This completed hand has no currently supported static yaku.
        self.game["hands"][0] = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "2z", "2z", "2z",
            "5z", "9p"
        ]

        self.accept_riichi()
        self.prepare_ron()

        self.game["riichi_declared"][0] = False
        self.assertFalse(can_ron(self.game, 0))

        self.game["riichi_declared"][0] = True
        self.assertTrue(can_ron(self.game, 0))

    def test_pass_after_riichi_persists_after_draw(self):
        self.accept_riichi()

        # Prevent other players from winning in this isolated test.
        for index in (1, 2, 3):
            self.game["temporary_furiten"][index] = True

        self.prepare_ron()
        self.assertTrue(can_ron(self.game, 0))

        pass_ron(self.game, 0)
        self.assertTrue(self.game["riichi_furiten"][0])

        self.game["current_player_index"] = 0
        self.game["phase"] = "draw"
        self.game["wall"].append("2p")
        start_turn(self.game)

        self.assertTrue(self.game["riichi_furiten"][0])

        finish_turn(self.game, 0, 13)
        self.prepare_ron()

        self.assertFalse(can_ron(self.game, 0))

    def test_existing_temporary_furiten_becomes_persistent(self):
        self.game["temporary_furiten"][0] = True

        self.accept_riichi()

        self.assertTrue(self.game["riichi_furiten"][0])

    def test_riichi_furiten_still_allows_tsumo(self):
        self.accept_riichi()
        self.game["riichi_furiten"][0] = True

        self.game["current_player_index"] = 0
        self.game["phase"] = "draw"
        self.game["wall"].append("5z")
        start_turn(self.game)

        self.assertTrue(can_tsumo(self.game, 0))


if __name__ == "__main__":
    unittest.main()