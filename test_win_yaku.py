import unittest

from yaku import get_win_yaku
from debug_scenarios import (
    create_ankan_demo,
    create_daiminkan_demo,
    create_chankan_demo,
)
from main import (
    declare_ankan,
    declare_daiminkan,
    declare_tsumo,
    declare_chankan,
    finish_turn,
    start_turn,
    get_winner_yaku,
)


class WinYakuTests(unittest.TestCase):
    def test_closed_tsumo_with_riichi(self):
        hand = [
            "1m", "2m", "3m",
            "4p", "5p", "6p",
            "7s", "8s", "9s",
            "2z", "2z", "2z",
            "5z", "5z"
        ]

        yaku = get_win_yaku(
            hand,
            is_closed=True,
            is_tsumo=True,
            riichi=True
        )

        self.assertIn("Riichi", yaku)
        self.assertIn("Menzen Tsumo", yaku)
        self.assertNotIn("Rinshan Kaihou", yaku)
        self.assertNotIn("Chankan", yaku)

    def test_ankan_tsumo_includes_rinshan(self):
        game = create_ankan_demo()
        declare_ankan(game, 0, "5z")
        declare_tsumo(game, 0)

        yaku = get_winner_yaku(game, 0)

        self.assertIn("Rinshan Kaihou", yaku)
        self.assertIn("Menzen Tsumo", yaku)
        self.assertIn("Yakuhai: White Dragon", yaku)

    def test_open_kan_tsumo_excludes_menzen(self):
        game = create_daiminkan_demo()
        declare_daiminkan(game, 0)
        declare_tsumo(game, 0)

        yaku = get_winner_yaku(game, 0)

        self.assertIn("Rinshan Kaihou", yaku)
        self.assertNotIn("Menzen Tsumo", yaku)

    def test_chankan_result_has_correct_yaku(self):
        game = create_chankan_demo()
        declare_chankan(game, 0)

        yaku = get_winner_yaku(game, 0)

        self.assertIn("Chankan", yaku)
        self.assertNotIn("Rinshan Kaihou", yaku)
        self.assertNotIn("Menzen Tsumo", yaku)

    def test_successful_discard_clears_rinshan(self):
        game = create_ankan_demo()
        declare_ankan(game, 0, "5z")

        finish_turn(game, 0, len(game["hands"][0]) - 1)

        self.assertIsNone(game["rinshan_player_index"])

    def test_normal_draw_clears_rinshan(self):
        game = create_ankan_demo()
        game["rinshan_player_index"] = 1
        game["phase"] = "draw"

        start_turn(game)

        self.assertIsNone(game["rinshan_player_index"])

    def test_open_rinshan_can_supply_the_only_yaku(self):
        hand = [
            "1p", "2p", "3p",
            "4s", "5s", "6s",
            "7m", "8m", "9m",
            "2z", "2z"
        ]
        melds = [{
            "type": "daiminkan",
            "tiles": ["1m"] * 4,
            "from_player_index": 1
        }]

        self.assertEqual(
            get_win_yaku(
                hand,
                melds=melds,
                is_closed=False,
                is_tsumo=True
            ),
            []
        )

        self.assertEqual(
            get_win_yaku(
                hand,
                melds=melds,
                is_closed=False,
                is_tsumo=True,
                rinshan=True
            ),
            ["Rinshan Kaihou"]
        )


if __name__ == "__main__":
    unittest.main()