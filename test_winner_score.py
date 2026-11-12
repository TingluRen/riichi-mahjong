import unittest
from copy import deepcopy

from main import (
    create_game,
    get_winner_score,
    get_winner_yaku,
)


class WinnerScoreTests(unittest.TestCase):
    def make_game(self, reason):
        game = create_game()

        hand = [
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "2p", "3p", "4p",
            "6s", "7s", "8s",
            "2z", "2z",
        ]

        # Keep the winning tile last for Tsumo.
        hand.remove("1m")

        if reason == "tsumo":
            hand.append("1m")
        elif reason == "ron":
            game["last_discard"] = {
                "player_index": 1,
                "tile": "1m",
            }
        elif reason == "chankan":
            game["robbed_kan_tile"] = "1m"

        game["hands"][0] = hand
        game["melds"][0] = []
        game["is_closed"][0] = True
        game["dealer_index"] = 0
        game["seat_winds"][0] = "1z"
        game["round_wind"] = "1z"
        game["riichi_declared"][0] = False
        game["rinshan_player_index"] = None

        # 9p indicates 1p, which this hand does not contain.
        game["dead_wall"][4] = "9p"
        game["dead_wall"][5] = "9p"
        game["dora_indicator_count"] = 1

        game["phase"] = "ended"
        game["end_reason"] = reason
        game["winner_index"] = 0
        game["winner_indices"] = [0]

        return game

    def test_dealer_ron_result(self):
        game = self.make_game("ron")
        score = get_winner_score(game, 0)

        self.assertEqual(score["yaku"], ["Pinfu"])
        self.assertEqual(score["han"], 1)
        self.assertEqual(score["fu"], 30)
        self.assertEqual(score["payments"]["ron_payment"], 1500)
        self.assertEqual(
            get_winner_yaku(game, 0),
            score["yaku"],
        )

    def test_dealer_tsumo_result(self):
        game = self.make_game("tsumo")
        score = get_winner_score(game, 0)

        self.assertCountEqual(
            score["yaku"],
            ["Pinfu", "Menzen Tsumo"],
        )
        self.assertEqual(score["han"], 2)
        self.assertEqual(score["fu"], 20)
        self.assertEqual(
            score["payments"]["non_dealer_payment"],
            700,
        )
        self.assertEqual(score["payments"]["total"], 2100)

    def test_chankan_uses_robbed_tile(self):
        game = self.make_game("chankan")
        score = get_winner_score(game, 0)

        self.assertIn("Pinfu", score["yaku"])
        self.assertIn("Chankan", score["yaku"])
        self.assertEqual(score["han"], 2)
        self.assertEqual(score["fu"], 30)
        self.assertEqual(score["payments"]["ron_payment"], 2900)

    def test_dora_and_ura_use_winning_tile(self):
        game = self.make_game("ron")
        game["riichi_declared"][0] = True

        # 9m indicates 1m, the tile claimed for Ron.
        game["dead_wall"][4] = "9m"
        game["dead_wall"][5] = "9m"

        score = get_winner_score(game, 0)

        self.assertEqual(score["dora_count"], 1)
        self.assertEqual(score["ura_dora_count"], 1)
        self.assertEqual(score["han"], 4)

    def test_unfinished_game_and_non_winner(self):
        game = self.make_game("ron")

        self.assertIsNone(get_winner_score(game, 1))

        game["phase"] = "response"

        self.assertIsNone(get_winner_score(game, 0))

    def test_repeated_reads_do_not_change_game_or_scores(self):
        game = self.make_game("ron")
        before = deepcopy(game)

        first = get_winner_score(game, 0)
        second = get_winner_score(game, 0)

        self.assertEqual(first, second)
        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()