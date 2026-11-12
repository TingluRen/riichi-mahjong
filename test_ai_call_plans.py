"""Checks for earlier yaku plans and useful equal-Shanten calls."""
import unittest
from copy import deepcopy

import main
from ai import calculate_shanten
from ai_calls import yaku_plan_costs, safe_discard_indices, score_call, waiting_ukeire
from test_ai_calls import response


class AiCallPlanTests(unittest.TestCase):
    def test_early_tanyao_call_is_accepted(self):
        game = response('3m 4m 1p 2p 3p 6s 7s 8s 5p 5p 1z 9m 3s', tile='2m')
        claim = main.get_ai_discard_claim(game)
        self.assertEqual((claim['player_index'],claim['type']), (1,'chi'))
        main.resolve_ron_responses(game, [])
        index = main.get_ai_discard_index(game,1)
        self.assertIn(game['hands'][1][index], ['1p','1z','9m'])
        main.finish_turn(game,1,index)
        self.assertIn('tanyao',yaku_plan_costs(game['hands'][1],game['melds'][1],'2z','1z',main.get_ai_visible_tiles(game,1)))
        main.check_tile_counts(game)

    def test_live_value_pair_supports_a_call_plan(self):
        groups=[{'type':'chi','tiles':['2m','3m','4m']}]
        hand='1p 2p 3p 6s 7s 8s 5z 5z 9m 1z'.split()
        self.assertEqual(yaku_plan_costs(hand,groups,'2z','1z')['yakuhai:5z'],1)

    def test_dead_value_pair_is_not_a_plan(self):
        groups=[{'type':'chi','tiles':['2m','3m','4m']}]
        hand='1p 2p 3p 6s 7s 8s 5z 5z 9m 1z'.split()
        self.assertNotIn('yakuhai:5z',yaku_plan_costs(hand,groups,'2z','1z',['5z','5z']))

    def test_pending_value_pair_is_protected(self):
        groups=[{'type':'pon','tiles':['4z']*3}]
        hand='1m 2m 3m 4p 5p 6p 7s 8s 5z 5z 9m'.split()
        indices=safe_discard_indices(hand,groups,list(range(11)),'2z','1z')
        self.assertTrue(indices)
        self.assertTrue(all(hand[index]!='5z' for index in indices))

    def test_tanyao_plan_accepts_two_unwanted_tiles_not_three(self):
        groups=[{'type':'chi','tiles':['2m','3m','4m']}]
        self.assertEqual(yaku_plan_costs(['1p','9p','2s'],groups,'2z','1z')['tanyao'],2)
        self.assertNotIn('tanyao',yaku_plan_costs(['1p','9p','1s'],groups,'2z','1z'))

    def test_fixed_terminal_group_cannot_plan_tanyao(self):
        groups=[{'type':'chi','tiles':['1m','2m','3m']}]
        self.assertNotIn('tanyao',yaku_plan_costs(['2p','3p'],groups,'2z','1z'))

    def test_flush_plan_accepts_limited_off_suit_tiles(self):
        groups=[{'type':'chi','tiles':['1m','2m','3m']}]
        hand='1m 2m 3m 4m 5m 6m 1z 1z 5p 6s'.split()
        self.assertEqual(yaku_plan_costs(hand,groups,'2z','1z')['flush:m'],2)
        self.assertNotIn('flush:m',yaku_plan_costs(hand+['7p'],groups,'2z','1z'))

    def test_fixed_groups_in_two_suits_block_flush_plan(self):
        groups=[{'type':'chi','tiles':['1m','2m','3m']},
                {'type':'pon','tiles':['1p']*3}]
        costs=yaku_plan_costs(['1m','2m','9s'],groups,'2z','1z')
        self.assertFalse(any(name.startswith('flush:') for name in costs))

    def test_secured_yaku_is_preferred_to_an_unfinished_plan(self):
        groups=[{'type':'chi','tiles':['2m','3m','4m']}]
        hand='2p 3p 4p 6s 7s 8s 5p 5p 2s 3s 1z'.split()
        self.assertEqual(safe_discard_indices(hand,groups,list(range(11)),'2z','1z'),[10])

    def test_equal_shanten_call_with_more_ukeire_is_accepted(self):
        game=response('5s 7p 3p 7m 7p 4p 6p 2p 5s 6p 4m 3m 5s',tile='8p')
        option=next(o for o in main.get_chi_options(game,1) if o['hand_tiles']==['6p','7p'])
        claim=main._make_call(game,1,'chi',option)
        visible=main.get_ai_visible_tiles(game,1)
        before=deepcopy(game)
        quality=score_call(game['hands'][1],[],claim,visible,'2z','1z')
        self.assertEqual(quality[0],calculate_shanten(game['hands'][1],[]))
        self.assertEqual(waiting_ukeire(game['hands'][1],[],visible),12)
        self.assertEqual(-quality[1],25)
        self.assertEqual(game,before)

    def test_equal_shanten_call_with_fewer_ukeire_is_rejected(self):
        game=response('8s 8s 3s 4s 3p 6s 5m 5m 7s 6p 8m 3p 6p',tile='6s')
        option=next(o for o in main.get_chi_options(game,1) if o['hand_tiles']==['7s','8s'])
        claim=main._make_call(game,1,'chi',option)
        self.assertIsNone(score_call(game['hands'][1],[],claim,main.get_ai_visible_tiles(game,1),'2z','1z'))

    def test_red_fives_count_as_simples_for_the_plan(self):
        groups=[{'type':'pon','tiles':['0m','5m','5m']}]
        self.assertEqual(yaku_plan_costs(['0p','0s','1z'],groups,'2z','1z')['tanyao'],1)

    def test_unfinished_plan_never_supplies_a_win_yaku(self):
        # A non-value honor Pon has no role in this otherwise mixed winning hand.
        game=response('1m 2m 3m 4p 5p 6p 7s 8s 2z 2z',
                      tile='9s',melds=[{'type':'pon','tiles':['4z']*3,'from_player_index':0}])
        self.assertFalse(main.can_ron(game,1))
        game['discards'][0].pop();game['discard_history'][0].pop()
        game['hands'][1].append('9s');game['last_discard']=None
        game['phase']='discard';game['current_player_index']=1
        self.assertFalse(main.can_tsumo(game,1))


if __name__=='__main__':
    unittest.main()
