import unittest
from copy import deepcopy

from main import (create_game, create_tiles, start_turn, finish_turn, declare_riichi,
                  resolve_ron_responses, can_tsumo, can_ron, declare_tsumo,
                  declare_ron, get_winner_score, get_event_yaku_flags,
                  declare_ankan, declare_kakan, declare_chi, declare_pon,
                  declare_daiminkan, check_tile_counts, create_next_hand)
from yaku import get_situational_yaku, get_win_yaku, count_supported_yaku_han
from scoring import evaluate_hand_score
from debug_scenarios import (create_riichi_demo, create_ankan_demo, create_pon_demo,
                            create_chi_demo, create_daiminkan_demo, create_kakan_demo,
                            create_chankan_demo, create_ron_demo)

# A valid open hand with no tile-based yaku: only Haitei / Houtei can supply one.
OPEN_HAND = ['2p', '3p', '4p', '6s', '7s', '8s', '1z', '1z', '1z', '5z', '5z']
OPEN_MELDS = [{'type': 'chi', 'tiles': ['1m', '2m', '3m'], 'from_player_index': 3}]


def last_draw_game(*, winner=0, drawn_by=0):
    """Distribute a full physical set deterministically; leave one live tile."""
    game = create_game()
    pool = create_tiles()
    hand = OPEN_HAND[:-1]
    for tile in hand + OPEN_MELDS[0]['tiles'] + ['5z']:
        pool.remove(tile)
    game['hands'] = [[], [], [], []]
    game['hands'][winner] = hand.copy()
    game['melds'][winner] = deepcopy(OPEN_MELDS)
    game['is_closed'][winner] = False
    for index in range(4):
        if index != winner:
            game['hands'][index] = [pool.pop(0) for _ in range(13)]
    game['dead_wall'] = [pool.pop(0) for _ in range(14)]
    # The remaining physical tiles were discarded earlier.
    game['discards'][2] = pool
    game['discard_history'][2] = pool.copy()
    game['wall'] = ['5z']
    game['calls_made'] = True
    game['current_player_index'] = drawn_by
    game['phase'] = 'draw'
    check_tile_counts(game)
    return game


class EventYakuTests(unittest.TestCase):
    def test_double_replaces_ordinary_riichi(self):
        self.assertEqual(get_situational_yaku(riichi=True, double_riichi=True), ['Double Riichi'])
        self.assertEqual(count_supported_yaku_han(['Double Riichi', 'Ippatsu']), 3)

    def test_each_new_yaku_han(self):
        for name in ('Ippatsu', 'Haitei Raoyue', 'Houtei Raoyui'):
            with self.subTest(name=name):
                self.assertEqual(count_supported_yaku_han([name]), 1)

    def test_invalid_event_combinations(self):
        for flags in ({'ippatsu': True}, {'double_riichi': True},
                      {'riichi': True, 'ippatsu': True, 'is_closed': False},
                      {'haitei': True}, {'is_tsumo': True, 'houtei': True},
                      {'is_tsumo': True, 'rinshan': True, 'haitei': True},
                      {'chankan': True, 'houtei': True}):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                get_situational_yaku(**flags)

    def test_open_no_yaku_without_last_tile(self):
        self.assertEqual(get_win_yaku(OPEN_HAND, melds=OPEN_MELDS,
                                     is_closed=False, seat_wind='2z', round_wind='3z'), [])
        self.assertIsNone(evaluate_hand_score(OPEN_HAND, '5z', OPEN_MELDS,
                                              is_closed=False, seat_wind='2z', round_wind='3z'))

    def test_open_haitei_can_supply_only_yaku(self):
        score = evaluate_hand_score(OPEN_HAND, '5z', OPEN_MELDS, is_closed=False,
                                    seat_wind='2z', round_wind='3z', is_tsumo=True, haitei=True)
        self.assertEqual(score['yaku'], ['Haitei Raoyue'])
        self.assertEqual(score['han'], 1)

    def test_open_houtei_can_supply_only_yaku(self):
        score = evaluate_hand_score(OPEN_HAND, '5z', OPEN_MELDS, is_closed=False,
                                    seat_wind='2z', round_wind='3z', houtei=True)
        self.assertEqual(score['yaku'], ['Houtei Raoyui'])
        self.assertEqual(score['han'], 1)

    def test_ippatsu_and_double_score_and_ura(self):
        hand = ['1m','2m','3m','4p','5p','6p','7s','8s','9s','2z','2z','2z','5z','5z']
        score = evaluate_hand_score(hand, '5z', riichi=True, double_riichi=True,
                                    ippatsu=True, ura_dora_count=1)
        self.assertIn('Double Riichi', score['yaku'])
        self.assertIn('Ippatsu', score['yaku'])
        self.assertNotIn('Riichi', score['yaku'])
        self.assertEqual(score['han'], 4)

    def test_kokushi_ignores_ordinary_event_yaku(self):
        hand = ['1m','9m','1p','9p','1s','9s','1z','2z','3z','4z','5z','6z','7z','1m']
        score = evaluate_hand_score(hand, '1m', riichi=True, double_riichi=True,
                                    ippatsu=True, is_tsumo=True, haitei=True)
        self.assertEqual(score['yaku'], ['Kokushi Musou'])
        self.assertEqual(score['yakuman_count'], 1)


class EventStateTests(unittest.TestCase):
    def accept_riichi(self, *, prior_discard=False, called=False):
        game = create_riichi_demo()
        game['calls_made'] = called
        if prior_discard:
            game['discard_history'][0] = ['6z']
        index = len(game['hands'][0]) - 1
        declare_riichi(game, 0, index)
        return game

    def test_declaration_is_pending_before_response(self):
        game = self.accept_riichi()
        self.assertTrue(game['pending_double_riichi'])
        self.assertFalse(game['double_riichi'][0])
        self.assertFalse(game['ippatsu_eligible'][0])
        self.assertEqual(game['scores'][0], 25000)

    def test_first_discard_accepts_double_riichi(self):
        game = self.accept_riichi()
        resolve_ron_responses(game, [])
        self.assertTrue(game['double_riichi'][0])
        self.assertTrue(game['ippatsu_eligible'][0])
        self.assertEqual(game['scores'][0], 24000)

    def test_previous_discard_blocks_double(self):
        game = self.accept_riichi(prior_discard=True)
        resolve_ron_responses(game, [])
        self.assertFalse(game['double_riichi'][0])
        self.assertTrue(game['ippatsu_eligible'][0])

    def test_prior_call_blocks_double(self):
        game = self.accept_riichi(called=True)
        resolve_ron_responses(game, [])
        self.assertFalse(game['double_riichi'][0])

    def test_invalid_declaration_does_not_mutate(self):
        game = create_riichi_demo()
        before = deepcopy(game)
        with self.assertRaises(ValueError):
            declare_riichi(game, 0, -1)
        self.assertEqual(game, before)

    def test_ippatsu_survives_next_draw_expires_on_discard(self):
        game = self.accept_riichi()
        resolve_ron_responses(game, [])
        game['current_player_index'] = 0
        game['phase'] = 'draw'
        start_turn(game)
        self.assertTrue(game['ippatsu_eligible'][0])
        before = deepcopy(game)
        with self.assertRaises(ValueError):
            finish_turn(game, 0, 0)
        self.assertEqual(game, before)
        finish_turn(game, 0, len(game['hands'][0])-1)
        self.assertFalse(game['ippatsu_eligible'][0])

    def test_other_player_discard_keeps_ippatsu(self):
        game = self.accept_riichi()
        resolve_ron_responses(game, [])
        start_turn(game)
        finish_turn(game, 1, 13)
        self.assertTrue(game['ippatsu_eligible'][0])

    def test_calls_cancel_ippatsu_and_break_first_turn(self):
        for factory, call in (
            (create_pon_demo, lambda g: declare_pon(g, 0)),
            (create_chi_demo, lambda g: declare_chi(g, 0, 0)),
            (create_daiminkan_demo, lambda g: declare_daiminkan(g, 0)),
            (create_ankan_demo, lambda g: declare_ankan(g, 0, '5z')),
            (create_kakan_demo, lambda g: declare_kakan(g, 0, 0)),
        ):
            with self.subTest(factory=factory.__name__):
                game = factory()
                game['ippatsu_eligible'][1] = True
                call(game)
                self.assertEqual(game['ippatsu_eligible'], [False]*4)
                self.assertTrue(game['calls_made'])
                check_tile_counts(game)

    def test_invalid_call_keeps_windows(self):
        game = create_ankan_demo()
        game['ippatsu_eligible'][1] = True
        before = deepcopy(game)
        with self.assertRaises(ValueError):
            declare_ankan(game, 0, '9m')
        self.assertEqual(game, before)

    def test_last_draw_allows_open_haitei_and_settles(self):
        game = last_draw_game()
        game['seat_winds'][0] = '2z'
        game['round_wind'] = '3z'
        start_turn(game)
        self.assertTrue(can_tsumo(game, 0))
        before = deepcopy(game)
        can_tsumo(game, 0)
        self.assertEqual(game, before)
        declare_tsumo(game, 0)
        self.assertEqual(get_winner_score(game, 0)['yaku'], ['Haitei Raoyue'])
        self.assertIsNotNone(game['settlement'])
        check_tile_counts(game)

    def test_last_discard_allows_open_houtei_and_settles(self):
        game = last_draw_game(winner=0, drawn_by=1)
        game['seat_winds'][0] = '2z'
        game['round_wind'] = '3z'
        start_turn(game)
        finish_turn(game, 1, len(game['hands'][1])-1)
        self.assertTrue(game['last_discard_is_houtei'])
        self.assertTrue(can_ron(game, 0))
        declare_ron(game, 0)
        self.assertEqual(get_winner_score(game, 0)['yaku'], ['Houtei Raoyui'])
        check_tile_counts(game)

    def test_empty_wall_alone_is_not_houtei(self):
        game = create_ron_demo()
        game['wall'] = []
        self.assertFalse(get_event_yaku_flags(game, 0, is_tsumo=False)['houtei'])

    def test_rinshan_is_not_haitei_or_houtei(self):
        game = create_ankan_demo()
        # Keep one live tile, moving the rest into an existing physical discard pile.
        moved = game['wall'][:-1]
        game['discards'][2].extend(moved)
        game['discard_history'][2].extend(moved)
        game['wall'] = game['wall'][-1:]
        declare_ankan(game, 0, '5z')
        self.assertEqual(game['wall'], [])
        self.assertFalse(get_event_yaku_flags(game, 0, is_tsumo=True)['haitei'])
        finish_turn(game, 0, len(game['hands'][0])-1)
        self.assertFalse(game['last_discard_is_houtei'])
        check_tile_counts(game)

    def test_chankan_cancels_ippatsu_before_win(self):
        game = create_chankan_demo()
        self.assertEqual(game['phase'], 'kakan_response')
        self.assertTrue(game['calls_made'])
        self.assertEqual(game['ippatsu_eligible'], [False]*4)
        self.assertFalse(get_event_yaku_flags(game, 0, is_tsumo=False, chankan=True)['houtei'])

    def test_ron_on_declaration_cancels_pending_double(self):
        game = create_riichi_demo()
        game['hands'][1] = ['1m','2m','3m','4p','5p','6p','7s','8s','9s','5z','5z','5z','9p']
        declare_riichi(game, 0, 13)
        self.assertTrue(can_ron(game, 1))
        resolve_ron_responses(game, [1])
        self.assertFalse(game['riichi_declared'][0])
        self.assertFalse(game['double_riichi'][0])
        self.assertFalse(game['ippatsu_eligible'][0])
        self.assertFalse(game['pending_double_riichi'])
        self.assertEqual(game['riichi_sticks'], 0)

    def test_accepted_double_ippatsu_tsumo_reaches_settlement(self):
        game = self.accept_riichi()
        resolve_ron_responses(game, [])
        game['current_player_index'] = 0
        game['phase'] = 'draw'
        game['wall'].remove('5z')
        game['wall'].append('5z')
        start_turn(game)
        declare_tsumo(game, 0)
        score = get_winner_score(game, 0)
        self.assertIn('Double Riichi', score['yaku'])
        self.assertIn('Ippatsu', score['yaku'])
        self.assertNotIn('Riichi', score['yaku'])
        self.assertIsNotNone(game['settlement'])
        check_tile_counts(game)

    def test_ippatsu_ron_reaches_settlement(self):
        game = create_ron_demo()
        game['riichi_declared'][0] = True
        game['ippatsu_eligible'][0] = True
        declare_ron(game, 0)
        self.assertIn('Ippatsu', get_winner_score(game, 0)['yaku'])
        check_tile_counts(game)

    def test_discard_furiten_still_blocks_houtei(self):
        game = last_draw_game(winner=0, drawn_by=1)
        game['discard_history'][0] = ['5z']
        start_turn(game)
        finish_turn(game, 1, len(game['hands'][1])-1)
        self.assertTrue(game['last_discard_is_houtei'])
        self.assertFalse(can_ron(game, 0))

    def test_another_riichi_does_not_interrupt_ippatsu(self):
        game = self.accept_riichi()
        resolve_ron_responses(game, [])
        # Give Player 2 a synthetic eligible hand to exercise the declaration path.
        game['hands'][1] = game['hands'][0] + ['9p']
        game['current_player_index'] = 1
        game['phase'] = 'discard'
        declare_riichi(game, 1, 13)
        resolve_ron_responses(game, [])
        self.assertTrue(game['ippatsu_eligible'][0])
        self.assertTrue(game['ippatsu_eligible'][1])

    def test_new_hand_resets_event_state(self):
        game = last_draw_game()
        start_turn(game)
        declare_tsumo(game, 0)
        game['double_riichi'][0] = True
        game['ippatsu_eligible'][0] = True
        next_game = create_next_hand(game)
        self.assertFalse(next_game['calls_made'])
        self.assertEqual(next_game['double_riichi'], [False]*4)
        self.assertEqual(next_game['ippatsu_eligible'], [False]*4)
        self.assertIsNone(next_game['last_live_draw_player'])


if __name__ == '__main__':
    unittest.main()
