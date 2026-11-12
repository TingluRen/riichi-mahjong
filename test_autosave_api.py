import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import server
import debug_scenarios as demos
from game_store import GameStore
from main import create_game
from test_game_store import first_draw, ended_ron


class AutosaveApiTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.store=GameStore(Path(self.directory.name)/'data'/'saved_game.json')
        self.patcher=patch.multiple(server,game_store=self.store,game=create_game(),save_notice=None,save_blocked=False)
        self.patcher.start();self.addCleanup(self.patcher.stop)
        # Fault-injection tests intentionally exercise disk/backup failures.
        warning_patch=patch.object(server.logger,'warning')
        warning_patch.start();self.addCleanup(warning_patch.stop)

    def test_first_start_creates_save(self):
        with TestClient(server.app) as client:
            data=client.get('/api/game').json()
            self.assertEqual(data['phase'],'discard')
            self.assertEqual(self.store.load(),server.game)

    def test_restart_restores_exact_waiting_state(self):
        with TestClient(server.app) as client:
            client.post('/api/new-game')
            saved=deepcopy(server.game)
        server.game=create_game()
        with TestClient(server.app) as client:
            self.assertEqual(server.game,saved)
            self.assertIn('restored',client.get('/api/game').json()['save_notice'])

    def test_restart_does_not_draw_again_after_pon(self):
        game=demos.create_pon_demo();server.declare_pon(game,0);self.store.save(game)
        with TestClient(server.app) as client:
            self.assertEqual(server.game,game)
            self.assertTrue(client.get('/api/game').json()['after_call'])

    def test_restart_keeps_ron_and_chankan_response(self):
        for factory,phase in [(demos.create_ron_demo,'response'),(demos.create_chankan_demo,'kakan_response')]:
            with self.subTest(factory=factory.__name__):
                game=factory();self.store.save(game)
                with TestClient(server.app) as client:
                    data=client.get('/api/game').json()
                    self.assertEqual(server.game,game)
                    self.assertEqual(data['phase'],phase);self.assertTrue(data['can_ron'])

    def test_restart_keeps_finished_settlement(self):
        game=ended_ron();self.store.save(game)
        with TestClient(server.app) as client:
            client.get('/api/game');client.get('/api/game')
            self.assertEqual(server.game,game)

    def test_get_does_not_change_save_or_game(self):
        with TestClient(server.app) as client:
            before=self.store.path.read_bytes();game=deepcopy(server.game)
            client.get('/api/game');client.get('/api/game')
            self.assertEqual(server.game,game)
            self.assertEqual(self.store.path.read_bytes(),before)

    def test_invalid_request_changes_neither_memory_nor_file(self):
        with TestClient(server.app) as client:
            before=deepcopy(server.game);raw=self.store.path.read_bytes()
            for body,status in [({'tile_index':999},400),({'tile_index':-1},422),({'tile_index':True},422)]:
                with self.subTest(body=body):
                    self.assertEqual(client.post('/api/discard',json=body).status_code,status)
                    self.assertEqual(server.game,before);self.assertEqual(self.store.path.read_bytes(),raw)

    def test_save_failure_cancels_action_and_keeps_old_file(self):
        with TestClient(server.app) as client:
            original=server.game;before=deepcopy(original);raw=self.store.path.read_bytes()
            with patch.object(self.store,'save',side_effect=OSError('disk full')):
                response=client.post('/api/new-game')
            self.assertEqual(response.status_code,503)
            self.assertIn('cancelled',response.json()['detail'])
            self.assertIs(server.game,original);self.assertEqual(server.game,before)
            self.assertEqual(self.store.path.read_bytes(),raw)

    def test_failed_advance_rolls_back_http_action(self):
        with TestClient(server.app,raise_server_exceptions=False) as client:
            before=deepcopy(server.game);raw=self.store.path.read_bytes()
            with patch.object(server,'advance_until_human',side_effect=RuntimeError('test failure')):
                response=client.post('/api/new-game')
            self.assertEqual(response.status_code,500)
            self.assertEqual(server.game,before);self.assertEqual(self.store.path.read_bytes(),raw)

    def test_new_game_updates_save_and_clears_notice(self):
        game=ended_ron();self.store.save(game)
        with TestClient(server.app) as client:
            response=client.post('/api/new-game')
            self.assertEqual(response.status_code,200)
            self.assertIsNone(response.json()['save_notice'])
            self.assertIsNone(server.game['end_reason']);self.assertEqual(self.store.load(),server.game)

    def test_all_developer_scenarios_are_saved(self):
        with TestClient(server.app) as client:
            for scenario in ['ron','riichi','pon','chi','ankan','daiminkan','kakan','chankan']:
                with self.subTest(scenario=scenario):
                    response=client.post('/api/debug/'+scenario)
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(self.store.load(),server.game)

    def test_game_action_endpoints_save_the_result(self):
        cases=[
            (demos.create_ron_demo,'/api/ron',None),
            (demos.create_ron_demo,'/api/pass',None),
            (demos.create_pon_demo,'/api/pon',None),
            (demos.create_chi_demo,'/api/chi',{'option_index':0}),
            (demos.create_ankan_demo,'/api/ankan',{'tile':'5z'}),
            (demos.create_daiminkan_demo,'/api/daiminkan',None),
            (demos.create_kakan_demo,'/api/kakan',{'meld_index':0}),
            (demos.create_chankan_demo,'/api/ron',None),
            (demos.create_riichi_demo,'/api/riichi',{'tile_index':13}),
            (demos.create_riichi_demo,'/api/discard',{'tile_index':13}),
        ]
        with TestClient(server.app) as client:
            for factory,path,body in cases:
                with self.subTest(path=path,factory=factory.__name__):
                    server.game=factory()
                    # Exercise state mutation + durable write without running slow AI strategy.
                    with patch.object(server,'advance_until_human'):
                        response=client.post(path,json=body) if body else client.post(path)
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(self.store.load(),server.game)

    def test_tsumo_abort_and_next_hand_are_saved(self):
        win='1m 2m 3m 4p 5p 6p 7s 8s 9s 2z 2z 2z 5z 5z'.split()
        nine='1m 9m 1p 9p 1s 9s 1z 2z 3z 4z 2m 3m 4m 6p'.split()
        with TestClient(server.app) as client:
            for hand,path in [(win,'/api/tsumo'),(nine,'/api/abort-nine-terminals')]:
                server.game=first_draw(hand)
                response=client.post(path);self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(self.store.load(),server.game)
                response=client.post('/api/next-hand');self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(self.store.load(),server.game)

    def test_bad_json_backed_up_before_new_game(self):
        self.store.path.parent.mkdir();raw=b'{broken';self.store.path.write_bytes(raw)
        with TestClient(server.app) as client:
            self.assertIn('Original kept',client.get('/api/game').json()['save_notice'])
            backups=list(self.store.path.parent.glob('saved_game.corrupt-*.json'))
            self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),raw)
            self.assertEqual(self.store.load(),server.game)

    def test_structurally_invalid_save_backed_up(self):
        self.store.save(create_game())
        data=json.loads(self.store.path.read_text());data['game']['hands'][0].pop()
        raw=json.dumps(data).encode();self.store.path.write_bytes(raw)
        with TestClient(server.app):
            backups=list(self.store.path.parent.glob('saved_game.corrupt-*.json'))
            self.assertEqual(backups[0].read_bytes(),raw)
            self.assertEqual(self.store.load(),server.game)

    def test_backup_failure_preserves_original_and_blocks_overwrite(self):
        self.store.path.parent.mkdir();raw=b'{broken';self.store.path.write_bytes(raw)
        with patch.object(self.store,'quarantine',side_effect=OSError('permission denied')):
            with TestClient(server.app) as client:
                response=client.post('/api/new-game');self.assertEqual(response.status_code,503)
                self.assertIn('kept unchanged',client.get('/api/game').json()['save_notice'])
                self.assertEqual(self.store.path.read_bytes(),raw)

    def test_unreadable_file_not_overwritten(self):
        self.store.save(create_game());raw=self.store.path.read_bytes()
        with patch.object(self.store,'load',side_effect=OSError('permission denied')):
            with TestClient(server.app) as client:
                self.assertEqual(client.post('/api/new-game').status_code,503)
                self.assertEqual(self.store.path.read_bytes(),raw)

    def test_initial_write_failure_is_reported_and_can_retry(self):
        with patch.object(self.store,'save',side_effect=OSError('disk full')):
            server.initialize_saved_game()
        self.assertIn('unavailable',server.save_notice)
        self.assertFalse(server.save_blocked)
        # Retry uses the same transaction path as real HTTP actions.
        with TestClient(server.app) as client:
            self.assertEqual(client.post('/api/new-game').status_code,200)
            self.assertEqual(self.store.load(),server.game)

    def test_concurrent_requests_are_serialized(self):
        def increment_honba():
            value=server.game['honba'];time.sleep(.02)
            server.game['honba']=value+1
            return server.get_player_view()
        server.app.add_api_route('/api/test-increment-honba',server.durable_action(increment_honba),methods=['POST'])
        route=server.app.routes[-1]
        self.addCleanup(lambda:server.app.routes.remove(route))
        with TestClient(server.app) as client:
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses=list(executor.map(lambda _:client.post('/api/test-increment-honba'),range(2)))
            self.assertEqual(sorted(response.json()['honba'] for response in responses),[1,2])
            self.assertEqual(self.store.load()['honba'],2)

    def test_direct_function_calls_keep_existing_unit_test_behavior(self):
        before=deepcopy(server.game)
        with patch.object(self.store,'save',side_effect=AssertionError('Direct unit call must not write')):
            server.new_game()
        self.assertNotEqual(server.game,before)
        self.assertFalse(self.store.path.exists())


if __name__=='__main__':unittest.main()
