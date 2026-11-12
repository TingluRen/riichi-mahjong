import unittest
from copy import deepcopy
from riichi_kan import is_riichi_ankan_legal
from hand_evaluator import get_waiting_tiles
from main import (create_game, create_tiles, start_turn, get_ankan_options,
                  declare_ankan, finish_turn, can_tsumo, declare_tsumo,
                  get_winner_score, check_tile_counts, can_kakan)

LOCKED = '1m 1m 1m 2p 3p 4p 6s 7s 8s 9p 9p 9p 5z'.split()
CURRENT = LOCKED + ['1m']


def riichi_game(*, replacements=('6p','7p'), locked=None, drawn='1m'):
    game=create_game();pool=create_tiles();locked=LOCKED.copy() if locked is None else list(locked)
    for tile in locked+[drawn]+list(replacements)+['9s']:pool.remove(tile)
    game['hands']=[locked,[],[],[]]
    for index in (1,2,3):game['hands'][index]=[pool.pop(0) for _ in range(13)]
    game['dead_wall']=list(replacements)+[pool.pop(0) for _ in range(14-len(replacements))]
    game['wall']=pool+[drawn]
    game['discards'][0]=['9s'];game['discard_history'][0]=['9s']
    game['riichi_declared'][0]=True;game['scores'][0]=24000;game['riichi_sticks']=1
    game['ippatsu_eligible'][0]=True
    start_turn(game)
    check_tile_counts(game)
    return game


class RiichiKanStructureTests(unittest.TestCase):
    def test_independent_triplet_is_legal(self):
        self.assertTrue(is_riichi_ankan_legal(CURRENT,[],'1m'))

    def test_honor_triplet_is_legal(self):
        hand=['1z' if tile=='1m' else tile for tile in CURRENT]
        self.assertTrue(is_riichi_ankan_legal(hand,[],'1z'))

    def test_drawn_tile_must_be_fourth_copy(self):
        hand=CURRENT.copy();hand[-1],hand[-2]=hand[-2],hand[-1]
        self.assertFalse(is_riichi_ankan_legal(hand,[],'1m'))

    def test_nine_gates_wait_change_blocks_kan(self):
        locked='1m 1m 1m 2m 3m 4m 5m 6m 7m 8m 9m 9m 9m'.split()
        current=locked+['1m']
        remaining=[t for t in current if t!='1m']
        self.assertNotEqual(set(get_waiting_tiles(locked)),set(get_waiting_tiles(remaining,[{'type':'ankan','tiles':['1m']*4}])))
        self.assertFalse(is_riichi_ankan_legal(current,[],'1m'))

    def test_unchanged_wait_but_lost_sequence_interpretation_is_illegal(self):
        locked='2m 2m 2m 3m 3m 3m 4m 4m 4m 2p 3p 4p 5z'.split()
        current=locked+['2m'];remaining=[t for t in current if t!='2m']
        self.assertEqual(set(get_waiting_tiles(locked)),set(get_waiting_tiles(remaining,[{'type':'ankan','tiles':['2m']*4}])))
        self.assertFalse(is_riichi_ankan_legal(current,[],'2m'))

    def test_ambiguity_in_other_groups_is_preserved_and_allowed(self):
        locked='1m 1m 1m 2p 2p 2p 3p 3p 3p 4p 4p 4p 5z'.split()
        self.assertTrue(is_riichi_ankan_legal(locked+['1m'],[],'1m'))

    def test_closed_kan_already_declared_is_allowed(self):
        melds=[{'type':'ankan','tiles':['9p']*4}]
        current=[t for t in CURRENT if t!='9p']
        self.assertTrue(is_riichi_ankan_legal(current,melds,'1m'))

    def test_open_meld_blocks_post_riichi_kan(self):
        melds=[{'type':'pon','tiles':['9p']*3}]
        current=[t for t in CURRENT if t!='9p']
        self.assertFalse(is_riichi_ankan_legal(current,melds,'1m'))

    def test_no_tenpai_before_draw_is_illegal(self):
        hand='1m 1m 1m 2p 4p 6p 6s 7s 8s 9p 9p 9p 5z 1m'.split()
        self.assertFalse(is_riichi_ankan_legal(hand,[],'1m'))

    def test_empty_short_and_non_quad_inputs(self):
        for hand in [[],CURRENT[:-1],LOCKED+['2m']]:
            with self.subTest(hand=hand):self.assertFalse(is_riichi_ankan_legal(hand,[],'1m'))

    def test_reader_is_pure(self):
        hand=CURRENT.copy();melds=[];before=deepcopy((hand,melds))
        is_riichi_ankan_legal(hand,melds,'1m')
        self.assertEqual((hand,melds),before)


class RiichiKanGameTests(unittest.TestCase):
    def test_option_available_on_normal_draw(self):
        game=riichi_game()
        self.assertEqual(get_ankan_options(game,0),['1m'])

    def test_wrong_phase_player_and_invalid_player(self):
        game=riichi_game()
        for index in (1,4,-1,None,True):
            with self.subTest(index=index):self.assertEqual(get_ankan_options(game,index),[])
        game['phase']='response'
        self.assertEqual(get_ankan_options(game,0),[])

    def test_no_current_draw_context_blocks_option(self):
        game=riichi_game();game['ordinary_draw_player']=None
        self.assertEqual(get_ankan_options(game,0),[])

    def test_after_call_blocks_option(self):
        game=riichi_game();game['after_call']=True
        self.assertEqual(get_ankan_options(game,0),[])

    def test_open_state_blocks_option(self):
        game=riichi_game();game['is_closed'][0]=False
        self.assertEqual(get_ankan_options(game,0),[])

    def test_invalid_resources_block_without_mutating(self):
        for key,value in [('wall',[]),('dead_wall',[]),('rinshan_draw_count',4),('dora_indicator_count',5)]:
            with self.subTest(key=key):
                game=riichi_game();game[key]=value;before=deepcopy(game)
                self.assertEqual(get_ankan_options(game,0),[])
                with self.assertRaises(ValueError):declare_ankan(game,0,'1m')
                self.assertEqual(game,before)

    def test_options_reader_is_pure(self):
        game=riichi_game();before=deepcopy(game)
        get_ankan_options(game,0)
        self.assertEqual(game,before)

    def test_wait_change_rejected_without_mutation(self):
        locked='1m 1m 1m 2m 3m 4m 5m 6m 7m 8m 9m 9m 9m'.split()
        game=riichi_game(locked=locked);before=deepcopy(game)
        with self.assertRaises(ValueError):declare_ankan(game,0,'1m')
        self.assertEqual(game,before)

    def test_ambiguous_triplet_rejected_without_mutation(self):
        locked='2m 2m 2m 3m 3m 3m 4m 4m 4m 2p 3p 4p 5z'.split()
        game=riichi_game(locked=locked,drawn='2m');before=deepcopy(game)
        with self.assertRaises(ValueError):declare_ankan(game,0,'2m')
        self.assertEqual(game,before)

    def test_non_riichi_keeps_existing_quad_options(self):
        game=riichi_game();game['riichi_declared'][0]=False
        game['hands'][0][-1],game['hands'][0][-2]=game['hands'][0][-2],game['hands'][0][-1]
        self.assertEqual(get_ankan_options(game,0),['1m'])

    def test_success_preserves_physical_tiles_and_closed_riichi(self):
        game=riichi_game();scores=game['scores'].copy();wall_count=len(game['wall'])
        before_waits=set(get_waiting_tiles(game['hands'][0][:-1]))
        drawn=declare_ankan(game,0,'1m')
        self.assertEqual(drawn,'6p')
        self.assertEqual(game['hands'][0][-1],'6p')
        self.assertEqual(len(game['hands'][0]),11)
        self.assertTrue(game['riichi_declared'][0]);self.assertTrue(game['is_closed'][0])
        self.assertEqual(game['scores'],scores);self.assertEqual(game['riichi_sticks'],1)
        self.assertEqual(game['melds'][0],[{'type':'ankan','tiles':['1m']*4}])
        self.assertEqual(game['dora_indicator_count'],2)
        self.assertEqual(game['rinshan_draw_count'],1)
        self.assertEqual(len(game['wall']),wall_count-1)
        self.assertEqual(game['rinshan_player_index'],0)
        self.assertEqual(set(get_waiting_tiles(game['hands'][0][:-1],game['melds'][0])),before_waits)
        check_tile_counts(game)

    def test_kan_cancels_everyones_ippatsu(self):
        game=riichi_game();game['ippatsu_eligible']=[True]*4
        declare_ankan(game,0,'1m')
        self.assertEqual(game['ippatsu_eligible'],[False]*4)
        self.assertTrue(game['calls_made'])

    def test_replacement_discard_still_locks_riichi(self):
        game=riichi_game();declare_ankan(game,0,'1m');before=deepcopy(game)
        with self.assertRaises(ValueError):finish_turn(game,0,0)
        self.assertEqual(game,before)
        self.assertEqual(finish_turn(game,0,len(game['hands'][0])-1),'6p')
        check_tile_counts(game)

    def test_rinshan_win_keeps_riichi_and_ura_but_not_ippatsu(self):
        game=riichi_game(replacements=('5z','7p'))
        declare_ankan(game,0,'1m');self.assertTrue(can_tsumo(game,0))
        declare_tsumo(game,0);score=get_winner_score(game,0)
        self.assertIn('Riichi',score['yaku'])
        self.assertIn('Rinshan Kaihou',score['yaku'])
        self.assertIn('Menzen Tsumo',score['yaku'])
        self.assertNotIn('Ippatsu',score['yaku'])
        self.assertIsNotNone(game['settlement']);check_tile_counts(game)

    def test_two_consecutive_legal_ankan_from_replacement(self):
        game=riichi_game(replacements=('9p','5z'))
        declare_ankan(game,0,'1m')
        self.assertEqual(get_ankan_options(game,0),['9p'])
        declare_ankan(game,0,'9p')
        self.assertEqual(len(game['melds'][0]),2)
        self.assertEqual(game['dora_indicator_count'],3)
        self.assertEqual(game['rinshan_draw_count'],2)
        self.assertTrue(can_tsumo(game,0));check_tile_counts(game)

    def test_riichi_furiten_does_not_block_legal_ankan_or_tsumo(self):
        game=riichi_game(replacements=('5z','7p'));game['riichi_furiten'][0]=True
        self.assertEqual(get_ankan_options(game,0),['1m'])
        declare_ankan(game,0,'1m');self.assertTrue(can_tsumo(game,0))
        self.assertTrue(game['riichi_furiten'][0])

    def test_cannot_kan_stale_quad_after_other_draw(self):
        game=riichi_game()
        game['hands'][0][-1],game['hands'][0][-2]=game['hands'][0][-2],game['hands'][0][-1]
        self.assertEqual(get_ankan_options(game,0),[])

    def test_kakan_remains_forbidden_after_riichi(self):
        game=riichi_game()
        self.assertFalse(can_kakan(game,0))


if __name__=='__main__':unittest.main()
