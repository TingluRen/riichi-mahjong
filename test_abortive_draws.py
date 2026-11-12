import unittest
from copy import deepcopy
import main
from main import (create_game, create_tiles, start_turn, finish_turn,
                  can_kyuushu_kyuuhai, declare_kyuushu_kyuuhai,
                  get_automatic_abort_reason, resolve_ron_responses,
                  create_next_hand, check_tile_counts, advance_until_human,
                  declare_ankan, declare_riichi, can_ron, can_pon, can_chi,
                  can_daiminkan)
from debug_scenarios import create_riichi_demo

NINE = '1m 9m 1p 9p 1s 9s 1z 2z 3z 4z 2m 3m 4m 6p'.split()


def ready_first_draw(hand=NINE, player=0):
    game=create_game(); pool=create_tiles()
    for tile in hand:pool.remove(tile)
    game['hands']=[[],[],[],[]];game['hands'][player]=hand[:-1].copy()
    for index in range(4):
        if index!=player:game['hands'][index]=[pool.pop(0) for _ in range(13)]
    game['dead_wall']=[pool.pop(0) for _ in range(14)]
    game['wall']=pool+[hand[-1]];game['current_player_index']=player
    check_tile_counts(game)
    return game


def four_kan_game(replacement='6p'):
    game=create_game();pool=create_tiles()
    game['hands']=[['4s']*4+['2p','3p','4p','5p'],[],[],[]]
    game['melds']=[
        [{'type':'ankan','tiles':['1m']*4},{'type':'ankan','tiles':['9m']*4}],
        [{'type':'ankan','tiles':['1p']*4}],[],[]]
    for tile in game['hands'][0]:pool.remove(tile)
    for groups in game['melds']:
        for meld in groups:
            for tile in meld['tiles']:pool.remove(tile)
    pool.remove(replacement)
    for index in (1,2,3):
        game['hands'][index]=[pool.pop(0) for _ in range(13-3*len(game['melds'][index]))]
    # Three consumed rinshan slots contain replenished wall tiles; slot 3 is next.
    game['dead_wall']=[pool.pop(0) for _ in range(3)]+[replacement]+[pool.pop(0) for _ in range(10)]
    game['wall']=pool;game['phase']='discard'
    game['rinshan_draw_count']=3;game['dora_indicator_count']=4;game['calls_made']=True
    check_tile_counts(game)
    return game


class NineTerminalsTests(unittest.TestCase):
    def test_eligible_on_first_draw(self):
        game=ready_first_draw();start_turn(game)
        self.assertTrue(can_kyuushu_kyuuhai(game,0))
        check_tile_counts(game)

    def test_nine_distinct_is_enough(self):
        hand='1m 9m 1p 9p 1s 9s 1z 2z 3z 2m 3m 4m 6p 7p'.split()
        game=ready_first_draw(hand);start_turn(game)
        self.assertTrue(can_kyuushu_kyuuhai(game,0))

    def test_duplicates_do_not_count_as_types(self):
        hand='1m 1m 1m 9m 9m 1p 9p 1s 9s 1z 2z 2m 3m 4m'.split()
        game=ready_first_draw(hand);start_turn(game)
        self.assertFalse(can_kyuushu_kyuuhai(game,0))

    def test_no_automatic_abort_for_human(self):
        game=ready_first_draw();advance_until_human(game)
        before=deepcopy(game);advance_until_human(game)
        self.assertEqual(game,before)
        self.assertEqual(game['phase'],'discard')

    def test_optional_continue_by_discard(self):
        game=ready_first_draw();start_turn(game);finish_turn(game,0,13)
        self.assertFalse(can_kyuushu_kyuuhai(game,0))
        self.assertEqual(game['phase'],'response')

    def test_no_eligibility_before_draw(self):
        self.assertFalse(can_kyuushu_kyuuhai(ready_first_draw(),0))

    def test_calls_cancel_eligibility(self):
        game=ready_first_draw();start_turn(game);game['calls_made']=True
        self.assertFalse(can_kyuushu_kyuuhai(game,0))

    def test_second_draw_is_not_eligible(self):
        game=ready_first_draw();game['ordinary_draw_counts'][0]=1;start_turn(game)
        self.assertFalse(can_kyuushu_kyuuhai(game,0))

    def test_wrong_player_and_invalid_index(self):
        game=ready_first_draw();start_turn(game)
        for index in [1,-1,4,None,True]:
            with self.subTest(index=index):self.assertFalse(can_kyuushu_kyuuhai(game,index))

    def test_rinshan_not_eligible(self):
        game=ready_first_draw();start_turn(game);game['rinshan_player_index']=0
        self.assertFalse(can_kyuushu_kyuuhai(game,0))

    def test_declaring_preserves_all_physical_tiles_and_deposits(self):
        game=ready_first_draw();start_turn(game)
        game['scores'][1]=23000;game['riichi_sticks']=2
        before=deepcopy(game)
        declare_kyuushu_kyuuhai(game,0)
        self.assertEqual(game['abort_reason'],'kyuushu_kyuuhai')
        self.assertEqual(game['end_reason'],'abortive_draw')
        self.assertEqual(game['scores'],before['scores'])
        self.assertEqual(game['riichi_sticks'],2)
        for key in ['hands','wall','dead_wall','discards','melds']:
            self.assertEqual(game[key],before[key])
        self.assertEqual(game['settlement']['score_deltas'],[0]*4)
        self.assertNotIn('tenpai_flags',game['settlement'])
        check_tile_counts(game)

    def test_invalid_declaration_does_not_mutate(self):
        game=ready_first_draw();before=deepcopy(game)
        with self.assertRaises(ValueError):declare_kyuushu_kyuuhai(game,0)
        self.assertEqual(game,before)

    def test_repeat_declaration_does_not_mutate(self):
        game=ready_first_draw();start_turn(game);declare_kyuushu_kyuuhai(game,0)
        before=deepcopy(game)
        with self.assertRaises(ValueError):declare_kyuushu_kyuuhai(game,0)
        advance_until_human(game)
        self.assertEqual(game,before)

    def test_ai_aborts_eligible_hand(self):
        game=ready_first_draw(player=1)
        advance_until_human(game)
        self.assertEqual(game['abort_reason'],'kyuushu_kyuuhai')
        check_tile_counts(game)

    def test_ai_takes_win_before_nine_terminals_abort(self):
        hand='1m 9m 1p 9p 1s 9s 1z 2z 3z 4z 5z 6z 7z 1m'.split()
        game=ready_first_draw(hand,player=1)
        advance_until_human(game)
        self.assertEqual(game['end_reason'],'tsumo')
        self.assertIsNone(game['abort_reason'])

    def test_next_hand_repeats_dealer_and_adds_honba(self):
        game=ready_first_draw();start_turn(game);game['honba']=2
        game['riichi_sticks']=1;game['scores'][1]-=1000
        declare_kyuushu_kyuuhai(game,0);before=deepcopy(game)
        nxt=create_next_hand(game)
        self.assertEqual(game,before)
        for key in ['dealer_index','hand_number','round_wind','scores','riichi_sticks']:
            self.assertEqual(nxt[key],game[key])
        self.assertEqual(nxt['honba'],3)
        self.assertIsNone(nxt['abort_reason'])
        self.assertIsNone(nxt['settlement'])
        self.assertEqual(nxt['ordinary_draw_counts'],[0]*4)
        check_tile_counts(nxt)


class AutomaticDrawTests(unittest.TestCase):
    def wind_game(self,tile='1z'):
        game=create_game();pool=create_tiles()
        game['hands']=[[tile] for _ in range(4)]
        for _ in range(4):pool.remove(tile)
        for hand in game['hands']:hand.extend(pool.pop(0) for _ in range(12))
        game['dead_wall']=pool[:14];game['wall']=pool[14:]
        for player in range(4):
            start_turn(game)
            finish_turn(game,player,game['hands'][player].index(tile))
            if player<3:resolve_ron_responses(game,[])
        check_tile_counts(game)
        return game

    def test_same_first_winds_abort_after_responses(self):
        for tile in ['1z','2z','3z','4z']:
            with self.subTest(tile=tile):
                game=self.wind_game(tile)
                self.assertEqual(game['phase'],'response')
                self.assertEqual(get_automatic_abort_reason(game),'suufon_renda')
                resolve_ron_responses(game,[])
                self.assertEqual(game['abort_reason'],'suufon_renda')
                self.assertEqual(game['settlement']['score_deltas'],[0]*4)
                check_tile_counts(game)

    def test_dragons_do_not_trigger_four_winds(self):
        game=self.wind_game('5z');resolve_ron_responses(game,[])
        self.assertIsNone(game['abort_reason'])

    def test_prior_call_blocks_four_winds(self):
        game=self.wind_game();game['calls_made']=True
        resolve_ron_responses(game,[])
        self.assertIsNone(game['abort_reason'])

    def test_different_winds_do_not_abort(self):
        game=self.wind_game();game['discard_history'][0]=['2z']
        self.assertIsNone(get_automatic_abort_reason(game))

    def test_second_discard_does_not_trigger_four_winds(self):
        game=self.wind_game();game['discard_history'][0].append('1z')
        self.assertIsNone(get_automatic_abort_reason(game))

    def four_riichi_game(self):
        game=create_riichi_demo()
        game['riichi_declared']=[False,True,True,True]
        game['scores']=[25000,24000,24000,24000]
        game['riichi_sticks']=3
        declare_riichi(game,0,13)
        return game

    def test_fourth_riichi_waits_then_deposits_and_aborts(self):
        game=self.four_riichi_game()
        self.assertEqual(game['phase'],'response')
        self.assertEqual(game['riichi_sticks'],3)
        resolve_ron_responses(game,[])
        self.assertEqual(game['abort_reason'],'suucha_riichi')
        self.assertEqual(game['riichi_sticks'],4)
        self.assertEqual(game['scores'],[24000]*4)
        nxt=create_next_hand(game)
        self.assertEqual(nxt['riichi_sticks'],4)
        self.assertEqual(nxt['dealer_index'],game['dealer_index'])

    def test_ron_on_fourth_declaration_wins_and_cancels_deposit(self):
        game=self.four_riichi_game()
        game['hands'][1]='1m 2m 3m 4p 5p 6p 7s 8s 9s 5z 5z 5z 9p'.split()
        self.assertTrue(can_ron(game,1))
        resolve_ron_responses(game,[1])
        self.assertEqual(game['end_reason'],'ron')
        self.assertFalse(game['riichi_declared'][0])
        self.assertIsNone(game['abort_reason'])
        self.assertEqual(game['settlement']['riichi_award'],3000)

    def test_fourth_kan_waits_for_replacement_and_discard(self):
        game=four_kan_game();declare_ankan(game,0,'4s')
        self.assertEqual(game['phase'],'discard')
        self.assertIsNone(get_automatic_abort_reason(game))
        finish_turn(game,0,len(game['hands'][0])-1)
        self.assertEqual(game['phase'],'response')
        self.assertEqual(get_automatic_abort_reason(game),'suukaikan')
        for player in range(4):
            self.assertFalse(can_pon(game,player))
            self.assertFalse(can_chi(game,player))
            self.assertFalse(can_daiminkan(game,player))
        resolve_ron_responses(game,[])
        self.assertEqual(game['abort_reason'],'suukaikan')
        check_tile_counts(game)

    def test_fourth_kan_rinshan_win_takes_priority(self):
        game=four_kan_game('5p');declare_ankan(game,0,'4s')
        self.assertTrue(main.can_tsumo(game,0))
        main.declare_tsumo(game,0)
        self.assertEqual(game['end_reason'],'tsumo')
        self.assertIsNone(game['abort_reason'])
        check_tile_counts(game)

    def test_fourth_kan_discard_ron_takes_priority(self):
        game=four_kan_game();declare_ankan(game,0,'4s')
        # Player 2 already has one Ankan; complete the other two groups and pair.
        game['hands'][1]='1s 2s 3s 5p 5p 5p 6p 2z 2z 2z'.split()
        game['riichi_declared'][1]=True
        finish_turn(game,0,len(game['hands'][0])-1)
        self.assertTrue(can_ron(game,1))
        resolve_ron_responses(game,[1])
        self.assertEqual(game['end_reason'],'ron')
        self.assertIsNone(game['abort_reason'])

    def test_one_players_four_kans_continue(self):
        game=create_game();game['phase']='response'
        game['melds'][0]=[{'type':'ankan','tiles':[tile]*4} for tile in ['1m','9m','1p','9p']]
        self.assertIsNone(get_automatic_abort_reason(game))

    def test_three_kans_do_not_abort(self):
        game=four_kan_game();game['phase']='response'
        self.assertIsNone(get_automatic_abort_reason(game))

    def test_fourth_pending_kakan_is_not_committed_fourth_kan(self):
        game=four_kan_game();game['phase']='kakan_response'
        self.assertIsNone(get_automatic_abort_reason(game))

    def test_multi_ron_still_supported(self):
        game=create_riichi_demo();finish_turn(game,0,13)
        ready='1m 2m 3m 4p 5p 6p 7s 8s 9s 5z 5z 5z 9p'.split()
        game['hands'][1]=ready.copy();game['hands'][2]=ready.copy()
        resolve_ron_responses(game,[1,2])
        self.assertEqual(game['winner_indices'],[1,2])
        self.assertEqual(game['end_reason'],'ron')


if __name__=='__main__':unittest.main()
