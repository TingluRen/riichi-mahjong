import unittest
from copy import deepcopy
from unittest.mock import patch
from nagashi import get_nagashi_winners, get_nagashi_score
from main import (create_game, create_tiles, settle_exhaustive_draw, settle_win,
                  get_winner_score, get_winner_yaku, get_winner_ura_dora_indicators,
                  create_next_hand, check_tile_counts, start_turn,
                  resolve_ron_responses, declare_ron)
from debug_scenarios import create_ron_demo


def ended_game(winners=(0,), *, dealer=0):
    """Physical 136-tile fixture with complete history for every river."""
    game=create_game();pool=create_tiles()
    game['hands']=[[pool.pop(0) for _ in range(13)] for _ in range(4)]
    game['dead_wall']=[pool.pop(0) for _ in range(14)]
    game['discards']=[[],[],[],[]]
    for player in winners:
        tile=next(t for t in pool if t[1]=='z' or t[0] in ('1','9'))
        pool.remove(tile);game['discards'][player].append(tile)
    other=next((i for i in range(4) if i not in winners),None)
    if other is not None:game['discards'][other].extend(pool)
    game['discard_history']=deepcopy(game['discards'])
    game['wall']=[];game['dealer_index']=dealer
    game['phase']='ended';game['end_reason']='exhaustive_draw'
    if other is not None:check_tile_counts(game)
    return game


class NagashiEligibilityTests(unittest.TestCase):
    def test_terminal_or_honor_discards_qualify(self):
        game=ended_game((0,))
        self.assertEqual(get_nagashi_winners(game),[0])

    def test_all_terminal_and_honor_types_accepted(self):
        for tile in ['1m','9m','1p','9p','1s','9s']+[f'{n}z' for n in range(1,8)]:
            with self.subTest(tile=tile):
                game=ended_game(());game['discard_history'][0]=[tile];game['discards'][0]=[tile]
                self.assertIn(0,get_nagashi_winners(game))

    def test_simple_in_full_history_disqualifies(self):
        game=ended_game((0,));game['discards'][0].append('2p');game['discard_history'][0].append('2p')
        self.assertEqual(get_nagashi_winners(game),[])

    def test_called_away_terminal_disqualifies(self):
        game=ended_game((0,));game['discard_history'][0].append('1m')
        self.assertEqual(get_nagashi_winners(game),[])

    def test_called_away_simple_cannot_be_hidden(self):
        game=ended_game((0,));game['discard_history'][0].append('2p')
        self.assertEqual(get_nagashi_winners(game),[])

    def test_empty_river_is_not_qualification(self):
        game=ended_game(())
        self.assertEqual(get_nagashi_winners(game),[])

    def test_missing_full_history_is_not_qualification(self):
        game=ended_game((0,));game['discard_history'][0]=[]
        self.assertEqual(get_nagashi_winners(game),[])

    def test_mismatched_river_disqualifies(self):
        game=ended_game((0,));game['discards'][0]=['7z','7z']
        self.assertEqual(get_nagashi_winners(game),[])

    def test_noten_and_furiten_do_not_block(self):
        game=ended_game((0,));game['temporary_furiten'][0]=True;game['riichi_furiten'][0]=True
        self.assertEqual(get_nagashi_winners(game),[0])

    def test_own_melds_allowed_in_discard_based_variant(self):
        game=ended_game((0,));game['melds'][0]=[{'type':'chi','tiles':['2p','3p','4p']}]
        self.assertEqual(get_nagashi_winners(game),[0])

    def test_not_before_end_or_before_empty_wall(self):
        game=ended_game((0,));game['phase']='response'
        self.assertEqual(get_nagashi_winners(game),[])
        game['phase']='ended';game['wall']=['5p']
        self.assertEqual(get_nagashi_winners(game),[])

    def test_abortive_draw_and_existing_win_do_not_qualify(self):
        for reason in ['abortive_draw','ron','tsumo','chankan']:
            game=ended_game((0,));game['end_reason']=reason
            with self.subTest(reason=reason):self.assertEqual(get_nagashi_winners(game),[])
        game=ended_game((0,));game['winner_indices']=[1]
        self.assertEqual(get_nagashi_winners(game),[])

    def test_reader_does_not_mutate(self):
        game=ended_game((1,2));before=deepcopy(game)
        get_nagashi_winners(game)
        self.assertEqual(game,before)


class NagashiSettlementTests(unittest.TestCase):
    def test_dealer_mangan(self):
        game=ended_game((0,));settlement=settle_exhaustive_draw(game)
        self.assertEqual(game['end_reason'],'nagashi_mangan')
        self.assertEqual(game['winner_indices'],[0])
        self.assertEqual(settlement['score_deltas'],[12000,-4000,-4000,-4000])
        self.assertNotIn('tenpai_flags',settlement)
        check_tile_counts(game)

    def test_non_dealer_mangan(self):
        game=ended_game((1,));settlement=settle_exhaustive_draw(game)
        self.assertEqual(settlement['score_deltas'],[-4000,8000,-2000,-2000])

    def test_non_dealer_honba(self):
        game=ended_game((1,));game['honba']=2
        settlement=settle_exhaustive_draw(game)
        self.assertEqual(settlement['score_deltas'],[-4200,8600,-2200,-2200])
        self.assertEqual(settlement['honba_awards'],[0,600,0,0])

    def test_two_non_dealers_settle_independently(self):
        game=ended_game((1,2));settlement=settle_exhaustive_draw(game)
        self.assertEqual(settlement['score_deltas'],[-8000,6000,6000,-4000])
        self.assertEqual(game['winner_indices'],[1,2])

    def test_dealer_and_non_dealer_settle_independently(self):
        game=ended_game((0,1));settlement=settle_exhaustive_draw(game)
        self.assertEqual(settlement['score_deltas'],[8000,4000,-6000,-6000])

    def test_three_non_dealers(self):
        game=ended_game((1,2,3));settlement=settle_exhaustive_draw(game)
        self.assertEqual(settlement['score_deltas'],[-12000,4000,4000,4000])

    def test_four_synthetic_qualifiers_cancel_payments(self):
        # Policy-level settlement case, not a full physical discard distribution.
        game=ended_game((0,1,2,3));settlement=settle_exhaustive_draw(game)
        self.assertEqual(settlement['score_deltas'],[0]*4)

    def test_multiple_honba_net_payments(self):
        game=ended_game((1,2));game['honba']=1
        self.assertEqual(settle_exhaustive_draw(game)['score_deltas'],[-8200,6200,6200,-4200])

    def test_deposits_awarded_once_in_dealer_first_order(self):
        game=ended_game((1,3),dealer=2)
        game['riichi_sticks']=3;game['scores'][0]-=3000
        settlement=settle_exhaustive_draw(game)
        self.assertEqual(game['winner_indices'],[3,1])
        self.assertEqual(settlement['riichi_recipient'],3)
        self.assertEqual(settlement['riichi_award'],3000)
        self.assertEqual(game['riichi_sticks'],0)
        self.assertEqual(sum(game['scores']),100000)

    def test_riichi_does_not_add_yaku_or_ura(self):
        game=ended_game((0,));game['riichi_declared'][0]=True
        settle_exhaustive_draw(game)
        score=get_winner_score(game,0)
        self.assertEqual(score['yaku'],['Nagashi Mangan'])
        self.assertEqual(score['dora_count'],0)
        self.assertEqual(score['ura_dora_count'],0)
        self.assertEqual(get_winner_ura_dora_indicators(game,0),[])
        self.assertIsNone(score['fu'])
        self.assertIsNone(score['payments']['fu'])

    def test_settlement_idempotent_and_copy_safe(self):
        game=ended_game((0,));first=settle_exhaustive_draw(game);before=deepcopy(game)
        self.assertEqual(settle_exhaustive_draw(game),first)
        self.assertEqual(settle_win(game),first)
        self.assertEqual(game,before)
        first['score_deltas'][0]=999
        self.assertNotEqual(game['settlement']['score_deltas'][0],999)

    def test_no_tenpai_check_for_nagashi(self):
        game=ended_game((0,))
        with patch('main.get_waiting_tiles',side_effect=AssertionError('Should not check Tenpai')):
            settle_exhaustive_draw(game)

    def test_no_hand_evaluation_for_nagashi(self):
        game=ended_game((0,))
        with patch('main.evaluate_hand_score',side_effect=AssertionError('No completed hand required')):
            settle_exhaustive_draw(game)
            self.assertEqual(get_winner_yaku(game,0),['Nagashi Mangan'])

    def test_no_qualifiers_retains_normal_noten_payments(self):
        game=ended_game(())
        with patch('main.get_waiting_tiles',side_effect=[['5z'],[],[],[]]):
            settlement=settle_exhaustive_draw(game)
        self.assertEqual(game['end_reason'],'exhaustive_draw')
        self.assertEqual(settlement['score_deltas'],[3000,-1000,-1000,-1000])
        self.assertEqual(settlement['tenpai_flags'],[True,False,False,False])

    def test_invalid_state_does_not_mutate(self):
        game=ended_game((0,));game['wall']=['5p'];before=deepcopy(game)
        with self.assertRaises(ValueError):settle_exhaustive_draw(game)
        self.assertEqual(game,before)

    def test_invalid_honba_does_not_partially_commit_conversion(self):
        game=ended_game((0,));game['honba']=-1;before=deepcopy(game)
        with self.assertRaises(ValueError):settle_exhaustive_draw(game)
        self.assertEqual(game,before)

    def test_physical_tiles_unchanged(self):
        game=ended_game((1,2));before=deepcopy(game)
        settle_exhaustive_draw(game)
        for key in ['hands','discards','discard_history','wall','dead_wall','melds']:
            self.assertEqual(game[key],before[key])
        check_tile_counts(game)

    def test_nonwinner_has_no_winner_score(self):
        game=ended_game((1,));settle_exhaustive_draw(game)
        self.assertIsNone(get_winner_score(game,0))

    def test_score_reader_returns_fresh_results(self):
        a=get_nagashi_score(is_dealer=False);a['payments']['total']=1
        self.assertEqual(get_nagashi_score(is_dealer=False)['payments']['total'],8000)

    def test_start_turn_empty_wall_uses_nagashi(self):
        game=ended_game((1,));game['phase']='draw';game['end_reason']=None
        start_turn(game)
        self.assertEqual(game['end_reason'],'nagashi_mangan')

    def test_passing_last_discard_uses_nagashi(self):
        game=create_ron_demo();game['wall']=[]
        resolve_ron_responses(game,[])
        self.assertEqual(game['end_reason'],'nagashi_mangan')
        self.assertEqual(game['winner_indices'],[1])

    def test_last_discard_ron_takes_priority(self):
        game=create_ron_demo();game['wall']=[]
        declare_ron(game,0)
        self.assertEqual(game['end_reason'],'ron')
        self.assertEqual(game['winner_indices'],[0])


class NagashiContinuationTests(unittest.TestCase):
    def test_dealer_qualifier_repeats_and_adds_honba(self):
        game=ended_game((0,));game['honba']=2;settle_exhaustive_draw(game)
        nxt=create_next_hand(game)
        self.assertEqual(nxt['dealer_index'],0)
        self.assertEqual(nxt['hand_number'],1)
        self.assertEqual(nxt['honba'],3)

    def test_non_dealer_qualifier_rotates_and_resets_honba(self):
        game=ended_game((1,));game['honba']=2;settle_exhaustive_draw(game)
        nxt=create_next_hand(game)
        self.assertEqual(nxt['dealer_index'],1)
        self.assertEqual(nxt['hand_number'],2)
        self.assertEqual(nxt['honba'],0)

    def test_dealer_in_multiple_qualifiers_repeats(self):
        game=ended_game((0,2));settle_exhaustive_draw(game)
        self.assertEqual(create_next_hand(game)['dealer_index'],0)

    def test_south_four_non_dealer_qualifier_finishes_match(self):
        game=ended_game((1,));game['round_wind']='2z';game['hand_number']=4
        settle_exhaustive_draw(game)
        nxt=create_next_hand(game)
        self.assertTrue(nxt['match_ended'])
        self.assertEqual(nxt['scores'],game['scores'])

    def test_next_hand_resets_result_state(self):
        game=ended_game((1,));settle_exhaustive_draw(game);before=deepcopy(game)
        nxt=create_next_hand(game)
        self.assertEqual(game,before)
        self.assertIsNone(nxt['settlement'])
        self.assertIsNone(nxt['end_reason'])
        self.assertEqual(nxt['winner_indices'],[])
        self.assertEqual(nxt['scores'],game['scores'])
        check_tile_counts(nxt)


if __name__=='__main__':unittest.main()
