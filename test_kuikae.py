"""The same immediate exchange restrictions apply to humans and computers."""
import unittest
from copy import deepcopy

import main
from test_ai_calls import response


class KuikaeTests(unittest.TestCase):
    def test_confirmed_examples_and_reverse_exchanges(self):
        cases = [
            ('5m', ['3m','4m','5m'], ['2m','5m']),
            ('7m', ['5m','6m','7m'], ['4m','7m']),
            ('2p', ['2p','3p','4p'], ['2p','5p']),
            ('0s', ['3s','4s','0s'], ['2s','5s']),
        ]
        for called, group, expected in cases:
            with self.subTest(called=called):
                self.assertEqual(main.get_chi_forbidden_tiles(called, group), expected)

    def test_middle_call_forbids_same_tile_only(self):
        self.assertEqual(main.get_chi_forbidden_tiles('4m',['3m','4m','5m']), ['4m'])

    def test_exchange_discard_rejected_for_all_four_players(self):
        hand = '2m 3m 4m 2p 3p 4p 6s 7s 8s 5p 5p 2s 3s'
        for player in range(4):
            with self.subTest(player=player):
                game = response(hand, player=player, tile='5m', discarder=(player-1)%4)
                options = main.get_chi_options(game, player)
                option_index = next(i for i,o in enumerate(options) if o['hand_tiles']==['3m','4m'])
                # Direct declarations exercise the shared rule engine for any seat.
                self.assertTrue(main.declare_chi(game, player, option_index))
                self.assertIn('2m', game['forbidden_discard_tiles'])
                before = deepcopy(game)
                with self.assertRaises(ValueError):
                    main.finish_turn(game, player, game['hands'][player].index('2m'))
                self.assertEqual(game, before)
                legal = next(i for i,t in enumerate(game['hands'][player])
                             if t not in game['forbidden_discard_tiles'])
                main.finish_turn(game, player, legal)
                self.assertEqual(game['forbidden_discard_tiles'], [])
                main.check_tile_counts(game)

    def test_456_eat7_cannot_discard4(self):
        game = response('4m 5m 6m 2p 3p 4p 6s 7s 8s 5p 5p 2s 3s', tile='7m')
        index = next(i for i,o in enumerate(main.get_chi_options(game, 1)) if o['hand_tiles']==['5m','6m'])
        main.declare_chi(game, 1, index)
        with self.assertRaises(ValueError):
            main.finish_turn(game, 1, game['hands'][1].index('4m'))
        self.assertNotEqual(game['hands'][1][main.get_ai_discard_index(game, 1)], '4m')

    def test_human_view_excludes_exchange_discard(self):
        import server
        from unittest.mock import patch
        game = response('2m 3m 4m 2p 3p 4p 6s 7s 8s 5p 5p 2s 3s', player=0, tile='5m', discarder=3)
        index = next(i for i,o in enumerate(main.get_chi_options(game, 0)) if o['hand_tiles']==['3m','4m'])
        main.declare_chi(game, 0, index)
        with patch.object(server, 'game', game):
            view = server.get_player_view()
        self.assertNotIn(game['hands'][0].index('2m'), view['allowed_discard_indices'])


if __name__ == '__main__':
    unittest.main()
