"""AI call, yaku-route and table-priority regression checks."""
import random
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import main
from ai import analyze_discards, calculate_shanten
from ai_calls import open_yaku_routes, safe_discard_indices
from game_store import GameStore, validate_game
from hand_evaluator import get_waiting_tiles, get_tenpai_discards

def response(hand, *, player=1, tile='5z', discarder=0, human=0, melds=None, extras=None, others=None, red=False):
 g=main.create_game();pool=main.create_tiles(red)
 g['hands']=[[] for _ in range(4)];g['discards']=[[] for _ in range(4)];g['discard_history']=[[] for _ in range(4)];g['melds']=[[] for _ in range(4)]
 g['hands'][player]=hand.split() if isinstance(hand,str) else list(hand)
 for i,tiles in (others or {}).items():g['hands'][i]=tiles.split()
 g['melds'][player]=melds or []
 for i,groups in (extras or {}).items():g['melds'][i]=groups
 g['discards'][discarder]=[tile];g['discard_history'][discarder]=[tile]
 for t in [t for hand in g['hands'] for t in hand]+[tile]+[t for groups in g['melds'] for m in groups for t in m['tiles']]:pool.remove(t)
 random.Random(31).shuffle(pool)
 for i in range(4):
  if not g['hands'][i]:
   count=13-3*len(g['melds'][i]);g['hands'][i]=pool[:count];del pool[:count]
 g['dead_wall']=pool[:14];g['wall']=pool[14:];g['phase']='response';g['current_player_index']=discarder;g['human_player_index']=human;g['last_discard']={'player_index':discarder,'tile':tile};g['ordinary_draw_counts']=[2]*4
 g['is_closed']=[all(m['type']=='ankan' for m in groups) for groups in g['melds']]
 main.check_tile_counts(g)
 return g


def turn(hand, *, tile='5z', player=1, melds=None, extras=None):
    game = response(hand, tile=tile, player=player, melds=melds, extras=extras)
    game['discards'][0].pop()
    game['discard_history'][0].pop()
    game['hands'][player].append(tile)
    game['last_discard'] = None
    game['phase'] = 'discard'
    game['current_player_index'] = player
    game['ordinary_draw_player'] = player
    main.check_tile_counts(game)
    return game


PON_HAND = '5z 5z 2m 3m 4p 5p 6p 6s 7s 8p 8p 1z 9m'
CHI_HAND = '3m 4m 2p 3p 4p 6s 7s 8s 5p 5p 2s 8m 3s'
KAN_HAND = '5z 5z 5z 2m 3m 4m 4p 5p 6p 7s 8s 2z 2z'
VALUE_PON = {'type': 'pon', 'tiles': ['5z'] * 3, 'from_player_index': 0}


class AiCallTests(unittest.TestCase):
    def test_value_pon_is_chosen_and_preserves_tiles(self):
        game = response(PON_HAND)
        before = deepcopy(game)
        claim = main.get_ai_discard_claim(game)
        self.assertEqual((claim['player_index'], claim['type']), (1, 'pon'))
        self.assertEqual(game, before)
        wall = len(game['wall'])
        main.resolve_ron_responses(game, [])
        self.assertEqual(game['melds'][1][0]['type'], 'pon')
        self.assertEqual(game['current_player_index'], 1)
        self.assertEqual(game['phase'], 'discard')
        self.assertTrue(game['after_call'])
        self.assertEqual(len(game['wall']), wall)
        self.assertEqual(game['discard_history'][0], ['5z'])
        self.assertEqual(game['discards'][0], [])
        main.check_tile_counts(game)
        validate_game(game)

    def test_tanyao_chi_is_chosen(self):
        game = response(CHI_HAND, tile='2m')
        claim = main.get_ai_discard_claim(game)
        self.assertEqual(claim['type'], 'chi')
        main.resolve_ron_responses(game, [])
        index = main.get_ai_discard_index(game, 1)
        main.finish_turn(game, 1, index)
        self.assertIn('tanyao', open_yaku_routes(game['hands'][1], game['melds'][1], '2z', '1z'))
        main.check_tile_counts(game)

    def test_open_kan_draws_once_and_adds_indicator(self):
        game = response(KAN_HAND)
        wall = len(game['wall'])
        main.resolve_ron_responses(game, [])
        self.assertEqual(game['melds'][1][0]['type'], 'daiminkan')
        self.assertEqual(game['rinshan_draw_count'], 1)
        self.assertEqual(game['dora_indicator_count'], 2)
        self.assertEqual(len(game['wall']), wall - 1)
        self.assertFalse(game['after_call'])
        self.assertEqual(game['rinshan_player_index'], 1)
        main.check_tile_counts(game)
        validate_game(game)

    def test_no_yaku_chi_is_rejected(self):
        game = response('3m 4m 1p 2p 3p 6s 7s 8s 5p 5p 1z 9m 9s', tile='2m')
        self.assertTrue(main.get_chi_options(game, 1))
        claim = main.get_ai_discard_claim(game)
        self.assertTrue(claim is None or claim['player_index'] != 1)

    def test_no_yaku_pon_is_rejected(self):
        game = response(PON_HAND.replace('5z 5z', '4z 4z'), tile='4z')
        self.assertTrue(main.can_pon(game, 1))
        claim = main.get_ai_discard_claim(game)
        self.assertTrue(claim is None or claim['player_index'] != 1)

    def test_no_yaku_open_kan_is_rejected(self):
        game = response(KAN_HAND.replace('5z 5z 5z', '4z 4z 4z').replace('2z 2z', '2z 3z'), tile='4z')
        self.assertTrue(main.can_daiminkan(game, 1))
        claim = main.get_ai_discard_claim(game)
        self.assertTrue(claim is None or claim['player_index'] != 1)

    def test_all_three_ai_seats_can_pon(self):
        for player in (1, 2, 3):
            with self.subTest(player=player):
                game = response(PON_HAND, player=player)
                self.assertEqual(main.get_ai_discard_claim(game)['player_index'], player)
                main.resolve_ron_responses(game, [])
                self.assertEqual(game['melds'][player][0]['type'], 'pon')

    def test_chi_only_from_previous_player(self):
        game = response(CHI_HAND, tile='2m', player=2, discarder=0)
        self.assertEqual(main.get_chi_options(game, 2), [])

    def test_ai_does_not_call_after_riichi(self):
        game = response(PON_HAND)
        game['riichi_declared'][1] = True
        claim = main.get_ai_discard_claim(game)
        self.assertTrue(claim is None or claim['player_index'] != 1)

    def test_final_discard_cannot_be_called(self):
        game = response(PON_HAND)
        game['wall'] = []
        self.assertIsNone(main.get_ai_discard_claim(game))

    def test_open_tanyao_discards_off_route_draw(self):
        groups = [{'type': 'chi', 'tiles': ['2m','3m','4m'], 'from_player_index': 0}]
        game = turn('2p 3p 4p 6s 7s 8s 5p 5p 2s 3s', tile='1z', melds=groups)
        index = main.get_ai_discard_index(game, 1)
        self.assertEqual(game['hands'][1][index], '1z')

    def test_fixed_yakuhai_does_not_restrict_other_discards(self):
        hand = '1m 2m 3m 4p 5p 6p 7s 8s 2z 2z 4z'.split()
        self.assertEqual(safe_discard_indices(hand, [VALUE_PON], list(range(11)), '2z','1z'), list(range(11)))

    def test_dora_is_not_a_yaku_route(self):
        self.assertEqual(open_yaku_routes('1m 2m 3m 4p 5p 6p'.split(),
                         [{'type':'pon','tiles':['4z']*3}], '2z','1z'), set())

    def test_concealed_kan_is_chosen_without_peeking(self):
        game = turn(KAN_HAND)
        before = deepcopy(game)
        self.assertEqual(main.get_ai_turn_kan(game, 1), {'type':'ankan','tile':'5z'})
        self.assertEqual(game, before)
        game['dead_wall'].reverse()
        self.assertEqual(main.get_ai_turn_kan(game, 1), {'type':'ankan','tile':'5z'})

    def test_added_kan_is_chosen(self):
        game = turn('2m 3m 4m 4p 5p 6p 7s 8s 2z 2z', melds=[VALUE_PON])
        action = main.get_ai_turn_kan(game, 1)
        self.assertEqual((action['type'], action['meld_index']), ('kakan', 0))

    def test_kan_does_not_replace_post_call_discard(self):
        game = response(PON_HAND)
        main.resolve_ron_responses(game, [])
        self.assertIsNone(main.get_ai_turn_kan(game, 1))

    def test_loop_executes_concealed_kan(self):
        game = turn(KAN_HAND)
        def stop_after_discard(state, player):
            self.assertEqual(state['melds'][player][0]['type'], 'ankan')
            self.assertEqual(state['rinshan_draw_count'], 1)
            state['phase'] = 'ended'
        with patch.object(main, 'perform_ai_discard', side_effect=stop_after_discard):
            main.advance_until_human(game)
        main.check_tile_counts(game)

    def test_added_kan_pauses_for_human_robbery(self):
        game = turn('2m 3m 4m 4p 5p 6p 7s 8s 2z 2z', melds=[VALUE_PON])
        original = main.can_chankan
        with patch.object(main, 'can_chankan', side_effect=lambda g,p: p==0 if g['phase']=='kakan_response' else original(g,p)):
            main.advance_until_human(game)
        self.assertEqual(game['phase'], 'kakan_response')
        self.assertEqual(game['pending_kakan']['player_index'], 1)
        self.assertEqual(game['melds'][1][0]['type'], 'pon')
        self.assertEqual(game['rinshan_draw_count'], 0)

    def test_call_cancels_ippatsu_and_keeps_accepted_deposit(self):
        game = response(PON_HAND)
        game['pending_riichi'] = 0
        game['pending_double_riichi'] = True
        game['ippatsu_eligible'][2] = True
        main.resolve_ron_responses(game, [])
        self.assertEqual(game['scores'][0], 24000)
        self.assertEqual(game['riichi_sticks'], 1)
        self.assertTrue(game['riichi_declared'][0])
        self.assertFalse(any(game['ippatsu_eligible']))

    def test_ai_call_snapshot_round_trips(self):
        game = response(PON_HAND)
        main.resolve_ron_responses(game, [])
        with tempfile.TemporaryDirectory() as folder:
            store = GameStore(Path(folder)/'saved_game.json')
            store.save(game)
            self.assertEqual(store.load(), game)

    def test_own_discard_furiten_still_allows_tsumo(self):
        game = turn('2m 3m 4m 4p 5p 6p 7s 8s 2z 2z', tile='9s', melds=[VALUE_PON])
        # History alone records a previously discarded wait; no physical copy is added.
        game['discard_history'][1] = ['9s']
        game['temporary_furiten'][1] = True
        game['riichi_furiten'][1] = True
        self.assertTrue(main.can_tsumo(game, 1))

    def test_dead_wait_survives_another_players_kan(self):
        extra = {2:[{'type':'ankan','tiles':['9s']*4}]}
        game = response('2m 3m 4m 4p 5p 6p 7s 8s 2z 2z', tile='4z', melds=[VALUE_PON], extras=extra)
        waits = get_waiting_tiles(game['hands'][1], game['melds'][1])
        self.assertIn('9s', waits)
        self.assertEqual(calculate_shanten(game['hands'][1], game['melds'][1]), 0)
        # Make a post-draw hand; the fully exposed 9s has zero Ukeire, not an invalid wait.
        game['discards'][0].pop(); game['discard_history'][0].pop()
        game['hands'][1].append('4z'); game['last_discard']=None
        options = analyze_discards(game['hands'][1], game['melds'][1],
                                  visible_tiles=main.get_ai_visible_tiles(game, 1))
        option = next(option for option in options if option['tile']=='4z')
        self.assertEqual(option['shanten'], 0)
        self.assertNotIn('9s', [item['tile'] for item in option['improving_tiles']])


    def competing_chi(self, ron=False):
        hand = ('3m 4m 2p 3p 4p 6s 7s 8s 5z 5z 5z 2z 2z' if ron else
                '3m 4m 1p 2p 3p 6s 7s 8s 5p 5p 1z 9m 3s')
        other = '5m 5m 2p 3p 4p 6s 7s 8s 2s 3s 8p 8p 7p'
        return response(hand, tile='5m', human=1, others={2: other})

    def test_ai_pon_precedes_requested_human_chi(self):
        game = self.competing_chi()
        self.assertEqual(main.get_ai_discard_claim(game)['player_index'], 2)
        option = next(i for i,o in enumerate(main.get_chi_options(game, 1)) if o['hand_tiles']==['3m','4m'])
        self.assertFalse(main.declare_chi(game, 1, option))
        self.assertEqual(game['melds'][1], [])
        self.assertEqual(game['melds'][2][0]['type'], 'pon')
        self.assertEqual(game['current_player_index'], 2)
        main.check_tile_counts(game)

    def test_passing_human_response_still_allows_ai_call(self):
        game = self.competing_chi()
        main.pass_response(game, 1)
        self.assertEqual(game['current_player_index'], 2)
        self.assertEqual(game['melds'][2][0]['type'], 'pon')

    def test_human_ron_window_precedes_ai_pon(self):
        game = self.competing_chi(ron=True)
        self.assertTrue(main.can_ron(game, 1))
        main.advance_until_human(game)
        self.assertEqual(game['phase'], 'response')
        self.assertFalse(any(game['melds']))
        main.declare_ron(game, 1)
        self.assertEqual(game['end_reason'], 'ron')
        self.assertIn(1, game['winner_indices'])
        self.assertEqual(game['melds'][2], [])

    def test_passing_ron_keeps_furiten_when_ai_calls(self):
        game = self.competing_chi(ron=True)
        main.pass_ron(game, 1)
        self.assertTrue(game['temporary_furiten'][1])
        self.assertEqual(game['melds'][2][0]['type'], 'pon')

    def test_table_priority_orders_pon_before_chi(self):
        chi = {'type':'chi','player_index':1,'from_player_index':0}
        pon = {'type':'pon','player_index':3,'from_player_index':0}
        self.assertLess(main._call_priority(pon), main._call_priority(chi))
        far = {'type':'daiminkan','player_index':3,'from_player_index':0}
        near = {'type':'pon','player_index':1,'from_player_index':0}
        self.assertLess(main._call_priority(near), main._call_priority(far))

    def test_riichi_ankan_still_uses_strict_legality_check(self):
        game = turn(KAN_HAND)
        game['riichi_declared'][1] = True
        self.assertIn('5z', main.get_ankan_options(game, 1))
        self.assertEqual(main.get_ai_turn_kan(game, 1)['type'], 'ankan')
        with patch.object(main, 'is_riichi_ankan_legal', return_value=False):
            self.assertIsNone(main.get_ai_turn_kan(game, 1))

    def test_kan_resources_limit_ai_choices(self):
        game = turn(KAN_HAND)
        game['rinshan_draw_count'] = 4
        game['dora_indicator_count'] = 5
        self.assertIsNone(main.get_ai_turn_kan(game, 1))

    def test_ai_discard_still_respects_same_tile_pon_restriction(self):
        game = response('5z 5z 5z 2m 3m 4p 5p 6p 6s 7s 8p 8p 1z')
        self.assertTrue(main.declare_pon(game, 1))
        index = main.get_ai_discard_index(game, 1)
        self.assertNotEqual(game['hands'][1][index], '5z')

    def test_flush_route_rejects_an_off_suit_discard_choice(self):
        meld = [{'type':'chi','tiles':['2m','3m','4m']}]
        hand = '1m 2m 3m 4m 5m 6m 8m 8m 1z 1z 5p'.split()
        self.assertEqual(safe_discard_indices(hand, meld, list(range(11)), '2z','1z'), [10])


    def test_ai_red_chi_preserves_physical_red_tile(self):
        game = response('3s 4s 2p 3p 4p 6m 7m 8m 5p 5p 2m 3m 8p', tile='0s', red=True)
        claim = main.get_ai_discard_claim(game)
        self.assertIsNotNone(claim)
        self.assertEqual(claim['type'], 'chi')
        main.resolve_ron_responses(game, [])
        self.assertIn('0s', game['melds'][1][0]['tiles'])
        main.check_tile_counts(game)
        validate_game(game)

    def test_chi_api_advances_when_ai_pon_preempts_human(self):
        import server
        hand = '3m 4m 2p 3p 4p 6s 7s 8s 5z 5z 5z 2z 2z'
        other = '5m 5m 2p 3p 4p 6s 7s 8s 2s 3s 8p 8p 7p'
        game = response(hand, player=0, tile='5m', discarder=3, others={1:other})
        index = next(i for i,o in enumerate(main.get_chi_options(game,0)) if o['hand_tiles']==['3m','4m'])
        with patch.object(server,'game',game):
            view = server.chi(server.ChiRequest(option_index=index))
        self.assertEqual(game['melds'][1][0]['type'],'pon')
        self.assertFalse(view['phase']=='discard' and view['current_player_index']!=0)
        main.check_tile_counts(game)
        validate_game(game)


    def test_concealed_yakuhai_triplet_allows_chi_and_stays_protected(self):
        game = response('3m 4m 1p 2p 3p 6s 7s 8s 5z 5z 5z 2z 9m', tile='5m')
        claim = main.get_ai_discard_claim(game)
        self.assertEqual(claim['type'], 'chi')
        main.resolve_ron_responses(game, [])
        index = main.get_ai_discard_index(game, 1)
        self.assertNotEqual(game['hands'][1][index], '5z')
        indices = safe_discard_indices(game['hands'][1], game['melds'][1],
                    list(range(len(game['hands'][1]))), '2z','1z')
        self.assertTrue(indices)
        self.assertTrue(all(game['hands'][1][i]!='5z' for i in indices))

    def test_missing_physical_discard_cannot_trigger_ai_call(self):
        game = response(PON_HAND)
        game['discards'][0].clear()
        self.assertIsNone(main.get_ai_discard_claim(game))


    def test_own_kan_does_not_ban_a_zero_ukeire_structural_wait(self):
        groups = [{'type':'ankan','tiles':['3m']*4}]
        game = turn('1m 2m 4p 5p 6p 6s 7s 8s 2z 2z', tile='4z', melds=groups)
        index = main.get_ai_discard_index(game, 1)
        self.assertEqual(game['hands'][1][index], '4z')
        remaining = game['hands'][1][:index]+game['hands'][1][index+1:]
        self.assertEqual(calculate_shanten(remaining, groups), 0)
        option = next(o for o in analyze_discards(game['hands'][1], groups,
                     visible_tiles=main.get_ai_visible_tiles(game,1)) if o['tile']=='4z')
        self.assertEqual(option['ukeire'], 0)

    def test_own_history_does_not_block_ai_call(self):
        game = response(PON_HAND)
        game['discard_history'][1] = ['6s','8s']
        game['temporary_furiten'][1] = True
        self.assertEqual(main.get_ai_discard_claim(game)['type'],'pon')


if __name__ == '__main__':
    unittest.main()
