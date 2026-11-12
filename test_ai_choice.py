import unittest
from collections import Counter
from copy import deepcopy
from unittest.mock import patch

from ai import choose_discard
from main import (
    create_game,
    get_ai_visible_tiles,
    get_ai_discard_index,
)


class AiChoiceTests(unittest.TestCase):
    def test_lower_shanten_has_priority(self):
        options = [
            {"tile_index": 0, "shanten": 2, "ukeire": 30},
            {"tile_index": 1, "shanten": 1, "ukeire": 5},
        ]

        with patch("ai.analyze_discards", return_value=options):
            self.assertEqual(choose_discard([]), 1)

    def test_higher_ukeire_breaks_shanten_tie(self):
        options = [
            {"tile_index": 0, "shanten": 1, "ukeire": 8},
            {"tile_index": 1, "shanten": 1, "ukeire": 12},
        ]

        with patch("ai.analyze_discards", return_value=options):
            self.assertEqual(choose_discard([]), 1)

    def test_lower_index_breaks_complete_tie(self):
        options = [
            {"tile_index": 5, "shanten": 1, "ukeire": 12},
            {"tile_index": 2, "shanten": 1, "ukeire": 12},
        ]

        with patch("ai.analyze_discards", return_value=options):
            self.assertEqual(choose_discard([]), 2)

    def test_public_tiles_do_not_double_count_own_melds(self):
        game = create_game()
        game["discards"] = [["5z"], ["6z"], [], []]
        game["discard_history"] = [["5z", "9m"], [], [], []]
        game["melds"] = [
            [],
            [{
                "type": "pon",
                "tiles": ["2m"] * 3,
                "from_player_index": 0,
            }],
            [{
                "type": "chi",
                "tiles": ["4p", "5p", "6p"],
                "from_player_index": 1,
            }],
            [],
        ]
        game["dead_wall"][4] = "3s"
        game["dora_indicator_count"] = 1

        visible = get_ai_visible_tiles(game, 1)

        self.assertEqual(
            Counter(visible),
            Counter(["5z", "6z", "4p", "5p", "6p", "3s"]),
        )

    def test_hidden_hands_and_wall_order_do_not_affect_visibility(self):
        game = create_game()
        before = get_ai_visible_tiles(game, 1)

        game["hands"][0] = ["hidden"]
        game["hands"][2] = ["hidden"]
        game["hands"][3] = ["hidden"]
        game["wall"].reverse()

        self.assertEqual(get_ai_visible_tiles(game, 1), before)

    def test_riichi_discards_drawn_tile_without_analysis(self):
        game = create_game()
        game["phase"] = "discard"
        game["current_player_index"] = 1
        game["riichi_declared"][1] = True
        game["hands"][1].append(game["wall"].pop())

        with patch("main.choose_discard") as choose:
            index = get_ai_discard_index(game, 1)

        self.assertEqual(index, len(game["hands"][1]) - 1)
        choose.assert_not_called()

    def test_forbidden_tiles_are_not_discarded(self):
        game = create_game()
        game["phase"] = "discard"
        game["current_player_index"] = 1
        game["hands"][1].append(game["wall"].pop())

        allowed_tile = game["hands"][1][0]

        game["forbidden_discard_tiles"] = [
            tile
            for tile in set(game["hands"][1])
            if tile != allowed_tile
        ]

        index = get_ai_discard_index(game, 1)

        self.assertEqual(game["hands"][1][index], allowed_tile)

    def test_selection_does_not_change_game(self):
        game = create_game()
        game["phase"] = "discard"
        game["current_player_index"] = 1
        game["hands"][1].append(game["wall"].pop())
        before = deepcopy(game)

        index = get_ai_discard_index(game, 1)

        self.assertIn(index, range(len(game["hands"][1])))
        self.assertEqual(game, before)


if __name__ == "__main__":
    unittest.main()