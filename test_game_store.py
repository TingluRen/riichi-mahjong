import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from game_store import GameStore, InvalidSaveError, validate_game
from main import (create_game, create_tiles, advance_until_human, start_turn,
                  declare_pon, declare_chi, declare_ankan, declare_daiminkan,
                  declare_kakan, declare_chankan, resolve_kakan_responses,
                  declare_riichi, resolve_ron_responses, declare_ron,
                  declare_tsumo, declare_kyuushu_kyuuhai, create_next_hand)
import debug_scenarios as demos


def first_draw(hand):
    game=create_game();pool=create_tiles()
    for tile in hand:pool.remove(tile)
    game['hands']=[hand[:-1].copy(),[],[],[]]
    for player in (1,2,3):game['hands'][player]=[pool.pop(0) for _ in range(13)]
    game['dead_wall']=[pool.pop(0) for _ in range(14)]
    game['wall']=pool+[hand[-1]]
    start_turn(game)
    return game


def ended_ron():
    game=demos.create_ron_demo();declare_ron(game,0)
    return game


class GameStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'data'/'saved_game.json'
        self.store=GameStore(self.path)

    def round_trip(self,game):
        before=deepcopy(game);self.store.save(game)
        self.assertEqual(self.store.load(),game)
        self.assertEqual(game,before)

    def test_constructor_and_missing_load_do_not_create_files(self):
        self.assertIsNone(self.store.load());self.assertFalse(self.path.parent.exists())

    def test_initial_game_round_trip(self):
        self.round_trip(create_game())
        envelope=json.loads(self.path.read_text())
        self.assertEqual(envelope['version'],1);self.assertIn('saved_at',envelope)

    def test_human_discard_phase_round_trip(self):
        game=create_game();advance_until_human(game);self.round_trip(game)

    def test_ron_response_round_trip(self):
        self.round_trip(demos.create_ron_demo())

    def test_pending_riichi_round_trip(self):
        game=demos.create_riichi_demo();declare_riichi(game,0,13);self.round_trip(game)
        self.assertEqual(self.store.load()['pending_riichi'],0)

    def test_accepted_riichi_state_round_trip(self):
        game=demos.create_riichi_demo();declare_riichi(game,0,13);resolve_ron_responses(game,[])
        self.round_trip(game)
        self.assertTrue(self.store.load()['riichi_declared'][0])
        self.assertEqual(self.store.load()['riichi_sticks'],1)

    def test_temporary_furiten_round_trip(self):
        from main import pass_ron
        game=demos.create_ron_demo();pass_ron(game,0)
        self.assertTrue(game['temporary_furiten'][0]);self.round_trip(game)

    def test_permanent_riichi_furiten_round_trip(self):
        from main import pass_ron
        game=demos.create_ron_demo();game['riichi_declared'][0]=True
        game['scores'][0]-=1000;game['riichi_sticks']=1
        pass_ron(game,0)
        self.assertTrue(game['riichi_furiten'][0]);self.round_trip(game)

    def test_post_riichi_ankan_state_round_trip(self):
        hand='1m 1m 1m 2p 3p 4p 6s 7s 8s 9p 9p 9p 5z 1m'.split()
        game=first_draw(hand)
        game['wall'].remove('9s');game['discards'][0]=['9s'];game['discard_history'][0]=['9s']
        game['riichi_declared'][0]=True;game['scores'][0]-=1000;game['riichi_sticks']=1
        declare_ankan(game,0,'1m');self.round_trip(game)

    def test_final_deposit_settlement_round_trip(self):
        from main import settle_exhaustive_draw
        game=create_game();game['discards'][2]=game['wall'].copy();game['discard_history'][2]=game['wall'].copy()
        game['wall']=[];game['phase']='ended';game['end_reason']='exhaustive_draw'
        game['round_wind']='2z';game['hand_number']=4
        game['scores'][0]-=1000;game['riichi_sticks']=1
        with patch('main.get_waiting_tiles',return_value=[]):settle_exhaustive_draw(game)
        finished=create_next_hand(game)
        self.assertTrue(finished['match_ended']);self.assertEqual(finished['final_riichi_award'],1000)
        self.round_trip(finished)

    def test_called_hand_round_trips(self):
        for factory,call in [(demos.create_pon_demo,lambda g:declare_pon(g,0)),
                             (demos.create_chi_demo,lambda g:declare_chi(g,0,0))]:
            with self.subTest(factory=factory.__name__):
                game=factory();call(game);self.round_trip(game)
                self.assertTrue(self.store.load()['after_call'])

    def test_rinshan_round_trips(self):
        for factory,call in [(demos.create_ankan_demo,lambda g:declare_ankan(g,0,'5z')),
                             (demos.create_daiminkan_demo,lambda g:declare_daiminkan(g,0))]:
            with self.subTest(factory=factory.__name__):
                game=factory();call(game);self.round_trip(game)
                self.assertEqual(self.store.load()['rinshan_player_index'],0)

    def test_pending_and_completed_kakan_round_trip(self):
        game=demos.create_kakan_demo();declare_kakan(game,0,0);self.round_trip(game)
        resolve_kakan_responses(game,[]);self.round_trip(game)

    def test_chankan_response_and_end_round_trip(self):
        game=demos.create_chankan_demo();self.round_trip(game)
        declare_chankan(game,0);self.round_trip(game)
        self.assertEqual(self.store.load()['end_reason'],'chankan')

    def test_ended_ron_does_not_pay_twice_on_load(self):
        game=ended_ron();self.round_trip(game)
        loaded=self.store.load();before=deepcopy(loaded)
        advance_until_human(loaded)
        self.assertEqual(loaded,before)

    def test_tsumo_round_trip(self):
        hand='1m 2m 3m 4p 5p 6p 7s 8s 9s 2z 2z 2z 5z 5z'.split()
        game=first_draw(hand);declare_tsumo(game,0);self.round_trip(game)

    def test_nagashi_round_trip(self):
        game=demos.create_ron_demo()
        game['discards'][2].extend(game['wall']);game['discard_history'][2].extend(game['wall'])
        game['wall']=[];resolve_ron_responses(game,[])
        self.assertEqual(game['end_reason'],'nagashi_mangan');self.round_trip(game)

    def test_abortive_draw_round_trip(self):
        hand='1m 9m 1p 9p 1s 9s 1z 2z 3z 4z 2m 3m 4m 6p'.split()
        game=first_draw(hand);declare_kyuushu_kyuuhai(game,0);self.round_trip(game)

    def test_bankrupt_match_round_trip(self):
        game=demos.create_ron_demo();game['scores'][1]=100;game['scores'][3]+=24900
        declare_ron(game,0);self.assertTrue(game['match_ended']);self.round_trip(game)

    def test_load_is_independent_copy(self):
        game=create_game();self.store.save(game);loaded=self.store.load()
        loaded['hands'][0].clear();self.assertEqual(self.store.load(),game)

    def test_bad_json_is_not_overwritten(self):
        self.path.parent.mkdir();raw=b'{not JSON';self.path.write_bytes(raw)
        with self.assertRaises(InvalidSaveError):self.store.load()
        self.assertEqual(self.path.read_bytes(),raw)

    def test_invalid_utf8_is_rejected(self):
        self.path.parent.mkdir();self.path.write_bytes(b'\xff\xfe')
        with self.assertRaises(InvalidSaveError):self.store.load()

    def test_unknown_version_is_rejected(self):
        self.store.save(create_game());envelope=json.loads(self.path.read_text());envelope['version']=2
        self.path.write_text(json.dumps(envelope))
        with self.assertRaises(InvalidSaveError):self.store.load()

    def test_oversized_save_is_rejected(self):
        self.path.parent.mkdir();self.path.write_bytes(b' '*2_000_001)
        with self.assertRaises(InvalidSaveError):self.store.load()

    def test_quarantine_retains_exact_bytes(self):
        self.path.parent.mkdir();raw=b'broken saved game';self.path.write_bytes(raw)
        backup=self.store.quarantine()
        self.assertEqual(backup.read_bytes(),raw);self.assertFalse(self.path.exists())
        self.assertTrue(backup.name.startswith('saved_game.corrupt-'))

    def test_invalid_game_cannot_replace_good_save(self):
        good=create_game();self.store.save(good);before=self.path.read_bytes()
        bad=deepcopy(good);bad['hands'][0].pop()
        with self.assertRaises(InvalidSaveError):self.store.save(bad)
        self.assertEqual(self.path.read_bytes(),before)

    def test_failed_replace_keeps_previous_save_and_removes_temp(self):
        good=create_game();self.store.save(good);before=self.path.read_bytes()
        with patch('game_store.os.replace',side_effect=OSError('Disk write failed')):
            with self.assertRaises(OSError):self.store.save(create_game())
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.path.parent.glob('.mahjong-*.tmp')),[])

    def test_fsync_failure_preserves_previous_save(self):
        self.store.save(create_game());before=self.path.read_bytes()
        with patch('game_store.os.fsync',side_effect=OSError('Flush failed')):
            with self.assertRaises(OSError):self.store.save(create_game())
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.path.parent.glob('.mahjong-*.tmp')),[])

    def test_invalid_structural_fields_rejected(self):
        for field,value in [('phase','wrong'),('current_player_index',True),('hands',[]),
                            ('scores',[25000]*3),('seat_winds',['1z']*4),
                            ('dead_wall',[]),('dora_indicator_count',5),('riichi_sticks',-1),
                            ('riichi_declared',[0]*4),('pending_kakan',{}),('honba',-1)]:
            with self.subTest(field=field):
                game=create_game();game[field]=value
                with self.assertRaises(InvalidSaveError):validate_game(game)

    def test_point_total_mismatch_rejected(self):
        game=create_game();game['scores'][0]+=1000
        with self.assertRaises(InvalidSaveError):validate_game(game)

    def test_fifth_copy_and_lost_tile_rejected(self):
        game=create_game();old=game['wall'][0]
        game['wall'][0]=next(tile for tile in game['dead_wall'] if tile!=old)
        with self.assertRaises(InvalidSaveError):validate_game(game)

    def test_missing_required_field_rejected(self):
        game=create_game();del game['riichi_furiten']
        with self.assertRaises(InvalidSaveError):validate_game(game)

    def test_river_history_mismatch_rejected(self):
        game=demos.create_ron_demo();game['discard_history'][1]=[]
        with self.assertRaises(InvalidSaveError):validate_game(game)

    def test_ended_result_without_settlement_rejected(self):
        game=ended_ron();game['settlement']=None
        with self.assertRaises(InvalidSaveError):validate_game(game)

    def test_settlement_balance_mismatch_rejected(self):
        game=ended_ron();game['settlement']['scores_after'][0]+=1
        with self.assertRaises(InvalidSaveError):validate_game(game)


if __name__=='__main__':unittest.main()
