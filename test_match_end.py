import unittest
from copy import deepcopy
from unittest.mock import patch
from match_rules import finish_match, finish_if_bankrupt
from main import (create_game, create_next_hand, settle_win, settle_exhaustive_draw,
                  get_winner_score, declare_ron, check_tile_counts)
from debug_scenarios import create_ron_demo


def settled_game(scores=None, sticks=0):
    game=create_game();game['phase']='ended';game['end_reason']='exhaustive_draw'
    game['scores']=list(scores or [25000]*4);game['riichi_sticks']=sticks
    game['settlement']={'scores_before':game['scores'].copy(),'scores_after':game['scores'].copy(),
                        'score_deltas':[0]*4,'tenpai_flags':[False]*4,
                        'riichi_award':0,'riichi_recipient':None}
    return game


def ron_game():
    game=create_ron_demo()
    game.update(phase='ended',end_reason='ron',winner_index=0,winner_indices=[0],winning_discarder_index=1)
    return game


class MatchCompletionTests(unittest.TestCase):
    def test_below_zero_ends(self):
        game=settled_game([-100,40100,30000,30000])
        finish_if_bankrupt(game)
        self.assertTrue(game['match_ended'])
        self.assertEqual(game['match_end_reason'],'bankruptcy')

    def test_exact_zero_continues(self):
        game=settled_game([0,40000,30000,30000]);before=deepcopy(game)
        finish_if_bankrupt(game)
        self.assertEqual(game,before)

    def test_positive_scores_continue(self):
        game=settled_game();finish_if_bankrupt(game)
        self.assertFalse(game['match_ended'])

    def test_leftover_deposits_go_to_top_once(self):
        game=settled_game([24000,30000,24000,20000],sticks=2)
        finish_match(game,'south_round_complete')
        self.assertEqual(game['scores'],[24000,32000,24000,20000])
        self.assertEqual(game['final_riichi_award'],2000)
        self.assertEqual(game['final_riichi_recipient'],1)
        self.assertEqual(game['riichi_sticks'],0)
        self.assertEqual(sum(game['scores']),100000)

    def test_tied_leaders_use_initial_player_index_for_deposits(self):
        game=settled_game([29000,29000,20000,20000],sticks=2)
        finish_match(game,'south_round_complete')
        self.assertEqual(game['final_riichi_recipient'],0)
        self.assertEqual(game['scores'][0],31000)

    def test_no_deposits_has_no_recipient(self):
        game=settled_game();finish_match(game,'south_round_complete')
        self.assertEqual(game['final_riichi_award'],0)
        self.assertIsNone(game['final_riichi_recipient'])

    def test_finishing_is_idempotent(self):
        game=settled_game(sticks=2);finish_match(game,'south_round_complete');before=deepcopy(game)
        finish_match(game,'south_round_complete');finish_if_bankrupt(game)
        self.assertEqual(game,before)

    def test_settlement_tracks_final_award_separately(self):
        game=settled_game([24000,30000,24000,20000],sticks=2)
        finish_match(game,'south_round_complete')
        self.assertEqual(game['settlement']['scores_after'],game['scores'])
        self.assertEqual(game['settlement']['score_deltas'],[0,2000,0,0])
        self.assertEqual(game['settlement']['riichi_award'],0)
        self.assertEqual(game['settlement']['final_riichi_award'],2000)
        self.assertEqual(game['settlement']['scores_before'],[24000,30000,24000,20000])

    def test_invalid_finish_does_not_mutate(self):
        for change in [('phase','discard'),('settlement',None),('riichi_sticks',-1),('scores',[25000]*3)]:
            game=settled_game();game[change[0]]=change[1];before=deepcopy(game)
            with self.subTest(change=change),self.assertRaises(ValueError):finish_match(game,'south_round_complete')
            self.assertEqual(game,before)

    def test_unknown_reason_does_not_mutate(self):
        game=settled_game();before=deepcopy(game)
        with self.assertRaises(ValueError):finish_match(game,'unknown')
        self.assertEqual(game,before)

    def test_finished_match_rejects_next_hand(self):
        game=settled_game();finish_match(game,'south_round_complete')
        with self.assertRaises(ValueError):create_next_hand(game)

    def test_new_game_resets_final_metadata(self):
        game=create_game()
        self.assertFalse(game['match_ended'])
        self.assertIsNone(game['match_end_reason'])
        self.assertEqual(game['final_riichi_award'],0)
        self.assertIsNone(game['final_riichi_recipient'])


class MatchSettlementIntegrationTests(unittest.TestCase):
    def test_ron_can_bankrupt_payer(self):
        game=create_ron_demo();game['scores'][1]=100;total=sum(game['scores'])
        declare_ron(game,0)
        self.assertTrue(game['match_ended'])
        self.assertLess(game['scores'][1],0)
        self.assertEqual(sum(game['scores']),total)
        check_tile_counts(game)

    def test_exact_zero_after_ron_continues(self):
        game=ron_game();payment=get_winner_score(game,0)['payments']['ron_payment']
        game['scores'][1]=payment
        settle_win(game)
        self.assertEqual(game['scores'][1],0)
        self.assertFalse(game['match_ended'])

    def test_multi_ron_all_payments_finish_before_bankruptcy(self):
        game=create_game();game.update(phase='ended',end_reason='ron',winner_indices=[1,2],winner_index=1,winning_discarder_index=0)
        game['scores']=[5000,35000,30000,30000]
        with patch('main.get_winner_score',return_value={'payments':{'ron_payment':4000}}):
            result=settle_win(game)
        self.assertTrue(game['match_ended'])
        self.assertEqual(result['score_deltas'],[-8000,4000,4000,0])
        self.assertEqual(game['scores'][0],-3000)

    def test_normal_draw_can_bankrupt_after_noten_payment(self):
        game=create_game();game.update(phase='ended',end_reason='exhaustive_draw',wall=[])
        game['scores']=[500,40000,30000,27500];game['riichi_sticks']=2
        with patch('main.get_waiting_tiles',side_effect=[[],['5z'],[],[]]):result=settle_exhaustive_draw(game)
        self.assertTrue(game['match_ended'])
        self.assertEqual(game['match_end_reason'],'bankruptcy')
        self.assertEqual(game['scores'][0],-500)
        self.assertEqual(game['final_riichi_award'],2000)
        self.assertEqual(game['final_riichi_recipient'],1)
        self.assertEqual(sum(game['scores']),100000)
        self.assertEqual(result['scores_after'],game['scores'])

    def test_zero_after_draw_keeps_deposits_on_table(self):
        game=create_game();game.update(phase='ended',end_reason='exhaustive_draw',wall=[])
        game['scores']=[1000,40000,30000,28000];game['riichi_sticks']=1
        with patch('main.get_waiting_tiles',side_effect=[[],['5z'],[],[]]):settle_exhaustive_draw(game)
        self.assertEqual(game['scores'][0],0)
        self.assertFalse(game['match_ended'])
        self.assertEqual(game['riichi_sticks'],1)

    def test_nagashi_conversion_preserves_bankruptcy_flag(self):
        game=create_game();game.update(phase='ended',end_reason='exhaustive_draw',wall=[])
        game['discards'][0]=['1z'];game['discard_history'][0]=['1z'];game['scores'][1]=100
        settle_exhaustive_draw(game)
        self.assertEqual(game['end_reason'],'nagashi_mangan')
        self.assertTrue(game['match_ended'])
        self.assertEqual(game['match_end_reason'],'bankruptcy')

    def test_no_double_payment_when_reading_settlement_after_finish(self):
        game=create_ron_demo();game['scores'][1]=100;declare_ron(game,0)
        before=deepcopy(game);result=settle_win(game)
        self.assertEqual(game,before)
        result['score_deltas'][0]=123
        self.assertNotEqual(game['settlement']['score_deltas'][0],123)


class MatchSouthRoundTests(unittest.TestCase):
    def south_draw(self,tenpai=False,sticks=0):
        game=settled_game([25000,25000,25000,25000-sticks*1000],sticks=sticks)
        game['round_wind']='2z';game['hand_number']=4;game['honba']=2
        game['settlement']['tenpai_flags'][0]=tenpai
        return game

    def test_south_four_noten_dealer_finishes(self):
        game=self.south_draw();finished=create_next_hand(game)
        self.assertTrue(finished['match_ended'])
        self.assertEqual(finished['match_end_reason'],'south_round_complete')

    def test_south_four_leftover_sticks_awarded(self):
        game=self.south_draw(sticks=2);finished=create_next_hand(game)
        self.assertEqual(finished['final_riichi_recipient'],0)
        self.assertEqual(finished['scores'],[27000,25000,25000,23000])
        self.assertEqual(finished['riichi_sticks'],0)
        self.assertEqual(sum(finished['scores']),100000)

    def test_south_four_tenpai_dealer_still_repeats(self):
        game=self.south_draw(tenpai=True,sticks=1);nxt=create_next_hand(game)
        self.assertFalse(nxt['match_ended'])
        self.assertEqual(nxt['dealer_index'],0)
        self.assertEqual(nxt['hand_number'],4)
        self.assertEqual(nxt['honba'],3)
        self.assertEqual(nxt['riichi_sticks'],1)

    def test_south_four_dealer_win_still_repeats(self):
        game=self.south_draw();game['end_reason']='tsumo';game['winner_indices']=[0]
        game['scores']=[60000,15000,15000,10000]
        nxt=create_next_hand(game)
        self.assertFalse(nxt['match_ended'])
        self.assertEqual(nxt['honba'],3)

    def test_south_four_non_dealer_win_finishes(self):
        game=self.south_draw();game['end_reason']='ron';game['winner_indices']=[1]
        finished=create_next_hand(game)
        self.assertTrue(finished['match_ended'])

    def test_fixed_south_match_does_not_extend_west_below_30000(self):
        game=self.south_draw();finished=create_next_hand(game)
        self.assertTrue(finished['match_ended'])
        self.assertEqual(finished['round_wind'],'2z')
        self.assertEqual(finished['hand_number'],4)

    def test_abortive_draw_south_four_repeats_and_preserves_sticks(self):
        game=self.south_draw(sticks=2);game['end_reason']='abortive_draw'
        nxt=create_next_hand(game)
        self.assertFalse(nxt['match_ended'])
        self.assertEqual(nxt['riichi_sticks'],2)
        self.assertEqual(nxt['honba'],3)

    def test_next_hand_does_not_mutate_original_final_hand(self):
        game=self.south_draw(sticks=2);before=deepcopy(game)
        create_next_hand(game)
        self.assertEqual(game,before)

    def test_east_four_still_advances_south(self):
        game=self.south_draw();game['round_wind']='1z'
        nxt=create_next_hand(game)
        self.assertFalse(nxt['match_ended'])
        self.assertEqual(nxt['round_wind'],'2z')
        self.assertEqual(nxt['hand_number'],1)

    def test_defensive_next_hand_cannot_continue_with_negative_score(self):
        game=settled_game([-100,40100,30000,30000])
        finished=create_next_hand(game)
        self.assertTrue(finished['match_ended'])
        self.assertEqual(finished['match_end_reason'],'bankruptcy')


if __name__=='__main__':unittest.main()
