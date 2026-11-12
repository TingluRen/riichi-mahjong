import unittest
from unittest.mock import patch

from main import (
    create_game,
    create_tiles,
    perform_ai_discard,
    resolve_ron_responses,
    advance_until_human,
    declare_ron,
    can_ron,
    check_tile_counts,
)


class AiRiichiTests(unittest.TestCase):
    def make_game(self):
        game = create_game()
        pool = create_tiles()

        human_hand = [
            "2m", "3m", "4m",
            "2p", "3p", "4p",
            "2s", "3s", "4s",
            "6z", "6z", "6z",
            "9p",
        ]

        computer_hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "1z", "1z", "1z",
            "5z", "9p",
        ]

        for tile in human_hand + computer_hand:
            pool.remove(tile)

        hands = [human_hand, computer_hand, [], []]

        for index in (2, 3):
            for _ in range(13):
                hands[index].append(pool.pop(0))

        game["hands"] = hands
        game["dead_wall"] = pool[:14]
        game["wall"] = pool[14:]
        game["phase"] = "discard"
        game["current_player_index"] = 1

        check_tile_counts(game)

        return game

    def discard_declaration_tile(self, game):
        # Select 9p, leaving the computer waiting on 5z.
        with patch("main.get_ai_discard_index", return_value=13):
            return perform_ai_discard(game, 1)

    def test_declaration_waits_before_payment(self):
        game = self.make_game()

        result = self.discard_declaration_tile(game)

        self.assertTrue(result["riichi_attempted"])
        self.assertEqual(result["tile"], "9p")
        self.assertEqual(game["phase"], "response")
        self.assertEqual(game["pending_riichi"], 1)
        self.assertFalse(game["riichi_declared"][1])
        self.assertEqual(game["scores"][1], 25000)
        self.assertEqual(game["riichi_sticks"], 0)

        check_tile_counts(game)

    def test_accepted_declaration_pays_once(self):
        game = self.make_game()
        self.discard_declaration_tile(game)

        # Resolve with no Ron claims.
        resolve_ron_responses(game, [])

        self.assertTrue(game["riichi_declared"][1])
        self.assertIsNone(game["pending_riichi"])
        self.assertEqual(game["scores"][1], 24000)
        self.assertEqual(game["riichi_sticks"], 1)

        check_tile_counts(game)

    def test_human_response_pauses_the_loop(self):
        game = self.make_game()
        self.discard_declaration_tile(game)

        self.assertTrue(can_ron(game, 0))

        advance_until_human(game)

        self.assertEqual(game["phase"], "response")
        self.assertEqual(game["pending_riichi"], 1)
        self.assertEqual(game["scores"][1], 25000)

    def test_ron_cancels_computer_riichi(self):
        game = self.make_game()
        self.discard_declaration_tile(game)

        declare_ron(game, 0)

        self.assertEqual(game["end_reason"], "ron")
        self.assertFalse(game["riichi_declared"][1])
        self.assertIsNone(game["pending_riichi"])
        self.assertEqual(game["riichi_sticks"], 0)

        # The computer pays Ron, but no Riichi deposit.
        delta = game["settlement"]["score_deltas"][1]

        self.assertEqual(game["scores"][1], 25000 + delta)
        self.assertEqual(game["settlement"]["riichi_award"], 0)

        check_tile_counts(game)

    def test_insufficient_score_uses_normal_discard(self):
        game = self.make_game()
        game["scores"][1] = 900

        result = self.discard_declaration_tile(game)

        self.assertFalse(result["riichi_attempted"])
        self.assertIsNone(game["pending_riichi"])
        self.assertEqual(game["scores"][1], 900)
        self.assertEqual(game["phase"], "response")

    def test_short_wall_uses_normal_discard(self):
        game = self.make_game()
        game["riichi_min_wall_tiles"] = len(game["wall"]) + 1

        result = self.discard_declaration_tile(game)

        self.assertFalse(result["riichi_attempted"])
        self.assertIsNone(game["pending_riichi"])

    def test_already_riichi_discards_only_drawn_tile(self):
        game = self.make_game()
        game["riichi_declared"][1] = True
        game["scores"][1] = 24000
        game["riichi_sticks"] = 1

        with patch("main.choose_discard") as choose:
            result = perform_ai_discard(game, 1)

        choose.assert_not_called()
        self.assertEqual(result["tile"], "9p")
        self.assertFalse(result["riichi_attempted"])
        self.assertEqual(game["scores"][1], 24000)
        self.assertEqual(game["riichi_sticks"], 1)

    def test_tsumo_has_priority_over_discard(self):
        game = self.make_game()

        # Replace the drawn 9p with the winning 5z.
        game["hands"][1].remove("9p")
        game["wall"].append("9p")
        game["wall"].remove("5z")
        game["hands"][1].append("5z")

        with patch("main.perform_ai_discard") as discard:
            advance_until_human(game)

        discard.assert_not_called()
        self.assertEqual(game["phase"], "ended")
        self.assertEqual(game["end_reason"], "tsumo")
        self.assertEqual(game["winner_index"], 1)

        check_tile_counts(game)


if __name__ == "__main__":
    unittest.main()