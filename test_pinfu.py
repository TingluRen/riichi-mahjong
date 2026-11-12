import unittest
from copy import deepcopy

from main import create_game, can_ron, get_winner_yaku
from yaku import (
    get_win_yaku,
    get_yaku_candidates,
    count_supported_yaku_han,
)


class PinfuTests(unittest.TestCase):
    def make_hand(self, pair="2z"):
        return [
            "1m", "2m", "3m",
            "4m", "5m", "6m",
            "2p", "3p", "4p",
            "6s", "7s", "8s",
            pair, pair,
        ]

    def test_closed_ron_with_guest_wind_pair(self):
        yaku = get_win_yaku(
            self.make_hand(),
            winning_tile="1m",
        )

        self.assertCountEqual(yaku, ["Pinfu"])
        self.assertEqual(count_supported_yaku_han(yaku), 1)

    def test_tsumo_combines_with_pinfu(self):
        yaku = get_win_yaku(
            self.make_hand(),
            winning_tile="1m",
            is_tsumo=True,
        )

        self.assertCountEqual(yaku, ["Pinfu", "Menzen Tsumo"])

    def test_value_pairs_block_pinfu(self):
        cases = [
            ("5z", "1z", "1z"),
            ("6z", "1z", "1z"),
            ("7z", "1z", "1z"),
            ("2z", "2z", "1z"),
            ("2z", "1z", "2z"),
        ]

        for pair, seat_wind, round_wind in cases:
            with self.subTest(
                pair=pair,
                seat_wind=seat_wind,
                round_wind=round_wind,
            ):
                yaku = get_win_yaku(
                    self.make_hand(pair),
                    seat_wind=seat_wind,
                    round_wind=round_wind,
                    winning_tile="1m",
                )

                self.assertNotIn("Pinfu", yaku)

    def test_non_ryanmen_waits_block_pinfu(self):
        for tile in ("3m", "2m", "2z"):
            with self.subTest(winning_tile=tile):
                yaku = get_win_yaku(
                    self.make_hand(),
                    winning_tile=tile,
                )

                self.assertNotIn("Pinfu", yaku)

    def test_declared_chi_blocks_pinfu(self):
        hand = self.make_hand()[3:]
        melds = [{
            "type": "chi",
            "tiles": ["1m", "2m", "3m"],
            "from_player_index": 3,
        }]

        yaku = get_win_yaku(
            hand,
            melds=melds,
            winning_tile="4m",
        )

        self.assertNotIn("Pinfu", yaku)

    def test_triplet_blocks_pinfu(self):
        hand = (
            ["1m"] * 3
            + ["4m", "5m", "6m"]
            + ["2p", "3p", "4p"]
            + ["6s", "7s", "8s"]
            + ["2z"] * 2
        )

        yaku = get_win_yaku(hand, winning_tile="4m")

        self.assertNotIn("Pinfu", yaku)

    def test_same_hand_keeps_placement_results_separate(self):
        hand = [
            "1m", "2m", "3m",
            "1p", "2p", "3p",
            "6s", "7s", "8s",
            "4m", "5m", "6m",
            "4m", "4m",
        ]

        candidates = get_yaku_candidates(
            hand,
            winning_tile="4m",
        )

        pair_candidates = [
            candidate
            for candidate in candidates
            if candidate["winning_group"]["type"] == "pair"
        ]
        sequence_candidates = [
            candidate
            for candidate in candidates
            if candidate["winning_group"]["type"] == "sequence"
        ]

        self.assertTrue(pair_candidates)
        self.assertTrue(sequence_candidates)

        self.assertTrue(all(
            "Pinfu" not in candidate["yaku"]
            for candidate in pair_candidates
        ))
        self.assertTrue(any(
            "Pinfu" in candidate["yaku"]
            for candidate in sequence_candidates
        ))

        self.assertIn(
            "Pinfu",
            get_win_yaku(hand, winning_tile="4m")
        )

    def test_missing_context_does_not_guess_pinfu(self):
        self.assertNotIn(
            "Pinfu",
            get_win_yaku(self.make_hand())
        )

    def test_game_ron_and_result_display(self):
        game = create_game()
        hand = self.make_hand()
        hand.remove("1m")

        game["hands"][0] = hand
        game["melds"][0] = []
        game["is_closed"][0] = True
        game["seat_winds"][0] = "1z"
        game["round_wind"] = "1z"
        game["discard_history"][0] = []
        game["temporary_furiten"][0] = False
        game["riichi_furiten"][0] = False
        game["riichi_declared"][0] = False
        game["phase"] = "response"
        game["current_player_index"] = 1
        game["last_discard"] = {
            "player_index": 1,
            "tile": "1m",
        }

        self.assertTrue(can_ron(game, 0))

        game["phase"] = "ended"
        game["end_reason"] = "ron"
        game["winner_index"] = 0
        game["winner_indices"] = [0]

        self.assertIn("Pinfu", get_winner_yaku(game, 0))

    def test_inputs_are_not_modified(self):
        hand = self.make_hand()
        before = deepcopy(hand)

        get_win_yaku(hand, winning_tile="1m")

        self.assertEqual(hand, before)


if __name__ == "__main__":
    unittest.main()