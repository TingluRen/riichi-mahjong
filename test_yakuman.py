import unittest
from copy import deepcopy
from main import (create_game, create_tiles, start_turn, finish_turn, can_tsumo,
                  declare_tsumo, get_winner_score, get_event_yaku_flags,
                  interrupt_ippatsu, check_tile_counts, create_next_hand)
from yaku import get_supported_yaku, get_yakuman_count
from scoring import evaluate_hand_score


def tiles(text): return text.split()

SUUANKOU = tiles('2m 2m 2m 4p 4p 4p 6s 6s 6s 8m 8m 8m 5z 5z')
DAISANGEN = tiles('5z 5z 5z 6z 6z 6z 7z 7z 7z 1m 2m 3m 9p 9p')
TSUUIISOU = tiles('1z 1z 1z 2z 2z 2z 3z 3z 3z 5z 5z 5z 7z 7z')
RYUUIISOU = tiles('2s 3s 4s 2s 3s 4s 6s 6s 6s 8s 8s 8s 6z 6z')
CHINROUTOU = tiles('1m 1m 1m 9m 9m 9m 1p 1p 1p 9s 9s 9s 1s 1s')
SHOUSUUSHII = tiles('1z 1z 1z 2z 2z 2z 3z 3z 3z 4z 4z 1m 2m 3m')
DAISUUSHII = tiles('1z 1z 1z 2z 2z 2z 3z 3z 3z 4z 4z 4z 5z 5z')
CHUUREN = tiles('1m 1m 1m 2m 3m 4m 5m 6m 7m 8m 9m 9m 9m 5m')
NORMAL = tiles('1m 2m 3m 4p 5p 6p 7s 8s 9s 2z 2z 2z 5z 5z')


def first_draw_game(hand, player=0):
    game = create_game()
    pool = create_tiles()
    for tile in hand: pool.remove(tile)
    game['hands'] = [[],[],[],[]]
    game['hands'][player] = hand[:-1].copy()
    for index in range(4):
        if index != player: game['hands'][index] = [pool.pop(0) for _ in range(13)]
    game['dead_wall'] = [pool.pop(0) for _ in range(14)]
    game['wall'] = pool + [hand[-1]]
    game['current_player_index'] = player
    if player != 0:
        # Dealer's first discard has survived; turn is now the non-dealer's.
        tile = game['wall'].pop(0)
        game['discards'][0].append(tile)
        game['discard_history'][0].append(tile)
    check_tile_counts(game)
    return game


class YakumanTests(unittest.TestCase):
    def test_suuankou_tsumo(self):
        score = evaluate_hand_score(SUUANKOU, '8m', is_tsumo=True)
        self.assertEqual(score['yaku'], ['Suuankou'])
        self.assertEqual(score['yakuman_count'], 1)

    def test_suuankou_ron_on_pair(self):
        self.assertEqual(evaluate_hand_score(SUUANKOU,'5z')['yaku'], ['Suuankou'])

    def test_ron_on_triplet_is_not_suuankou(self):
        score = evaluate_hand_score(SUUANKOU,'8m')
        self.assertNotIn('Suuankou', score['yaku'])
        self.assertIn('Sanankou', score['yaku'])
        self.assertEqual(score['yakuman_count'], 0)

    def test_no_placement_does_not_guess_suuankou(self):
        self.assertNotIn('Suuankou', get_supported_yaku(SUUANKOU))

    def test_open_pon_blocks_suuankou(self):
        melds = [{'type':'pon','tiles':['2m']*3}]
        score = evaluate_hand_score(SUUANKOU[3:],'5z',melds,is_tsumo=True)
        self.assertNotIn('Suuankou',score['yaku'])

    def test_ankan_preserves_suuankou(self):
        melds = [{'type':'ankan','tiles':['2m']*4}]
        self.assertIn('Suuankou',evaluate_hand_score(SUUANKOU[3:],'5z',melds)['yaku'])

    def test_daisangen(self):
        self.assertEqual(get_supported_yaku(DAISANGEN), ['Daisangen'])

    def test_open_daisangen(self):
        melds = [{'type':'pon','tiles':['5z']*3}]
        self.assertEqual(evaluate_hand_score(DAISANGEN[3:],'9p',melds)['yaku'], ['Daisangen'])

    def test_tsuuiisou_standard(self):
        self.assertEqual(get_supported_yaku(TSUUIISOU), ['Tsuuiisou'])

    def test_tsuuiisou_seven_pairs(self):
        hand = [f'{n}z' for n in range(1,8) for _ in range(2)]
        score = evaluate_hand_score(hand,'7z')
        self.assertEqual(score['yaku'], ['Tsuuiisou'])
        self.assertIsNone(score['fu'])

    def test_ryuuiisou_with_green_dragon(self):
        self.assertEqual(get_supported_yaku(RYUUIISOU), ['Ryuuiisou'])

    def test_ryuuiisou_without_green_dragon(self):
        hand = RYUUIISOU[:-2]+['2s']*2
        self.assertEqual(get_supported_yaku(hand), ['Ryuuiisou'])

    def test_non_green_bamboo_blocks_ryuuiisou(self):
        self.assertNotIn('Ryuuiisou',get_supported_yaku(RYUUIISOU[:-2]+['5s']*2))

    def test_open_green_chi_is_valid(self):
        self.assertEqual(get_supported_yaku(RYUUIISOU[3:],melds=[{'type':'chi','tiles':RYUUIISOU[:3]}]), ['Ryuuiisou'])

    def test_chinroutou(self):
        self.assertEqual(get_supported_yaku(CHINROUTOU), ['Chinroutou'])

    def test_honor_blocks_chinroutou(self):
        self.assertNotIn('Chinroutou',get_supported_yaku(CHINROUTOU[:-2]+['2z']*2))

    def test_shousuushii(self):
        self.assertEqual(get_supported_yaku(SHOUSUUSHII), ['Shousuushii'])

    def test_daisuushii_excludes_shousuushii(self):
        yaku=get_supported_yaku(DAISUUSHII)
        self.assertIn('Daisuushii',yaku)
        self.assertNotIn('Shousuushii',yaku)
        self.assertIn('Tsuuiisou',yaku)

    def test_suukantsu(self):
        melds=[{'type':'daiminkan','tiles':[t]*4} for t in ['2m','3p','4s','5m']]
        score=evaluate_hand_score(['2z','2z'],'2z',melds)
        self.assertEqual(score['yaku'],['Suukantsu'])
        self.assertEqual(score['payments']['total'],32000)

    def test_four_ankan_stack_with_suuankou(self):
        melds=[{'type':'ankan','tiles':[t]*4} for t in ['2m','3p','4s','5m']]
        score=evaluate_hand_score(['2z','2z'],'2z',melds)
        self.assertCountEqual(score['yaku'],['Suuankou','Suukantsu'])
        self.assertEqual(score['yakuman_count'],2)

    def test_nine_gates_each_suit_and_extra_tile(self):
        for suit in 'mps':
            base=[f'{n}{suit}' for n in [1,1,1,2,3,4,5,6,7,8,9,9,9]]
            for n in range(1,10):
                with self.subTest(suit=suit,n=n):
                    self.assertIn('Chuuren Poutou',get_supported_yaku(base+[f'{n}{suit}']))

    def test_nine_gates_closed_only(self):
        self.assertNotIn('Chuuren Poutou',get_supported_yaku(CHUUREN,is_closed=False))

    def test_nine_gates_no_declared_kan(self):
        hand = tiles('2m 3m 4m 5m 6m 7m 8m 9m 9m 9m 5m')
        self.assertNotIn('Chuuren Poutou',get_supported_yaku(hand,melds=[{'type':'ankan','tiles':['1m']*4}]))

    def test_near_nine_gates_is_not_nine_gates(self):
        hand = tiles('1m 1m 1m 2m 3m 4m 5m 6m 7m 8m 8m 8m 9m 9m')
        self.assertNotIn('Chuuren Poutou',get_supported_yaku(hand))

    def test_multiple_yakuman_and_dealer_payment(self):
        score=evaluate_hand_score(DAISUUSHII,'5z',is_dealer=True,is_tsumo=True)
        self.assertCountEqual(score['yaku'],['Tsuuiisou','Daisuushii','Suuankou'])
        self.assertEqual(score['yakuman_count'],3)
        self.assertEqual(score['payments']['total'],144000)
        self.assertEqual(score['payments']['non_dealer_payment'],48000)

    def test_ordinary_yaku_and_dora_are_excluded(self):
        score=evaluate_hand_score(DAISANGEN,'9p',riichi=True,ippatsu=True,dora_count=10,ura_dora_count=5)
        self.assertEqual(score['yaku'],['Daisangen'])
        for key in ['han','yaku_han','bonus_han','dora_count','ura_dora_count']:self.assertEqual(score[key],0)
        self.assertIsNone(score['fu'])
        self.assertIsNone(score['raw_fu'])

    def test_duplicate_yakuman_not_counted_twice(self):
        self.assertEqual(get_yakuman_count(['Daisangen','Daisangen']),1)

    def test_invalid_and_incomplete_have_no_yakuman(self):
        self.assertEqual(get_supported_yaku(['1z']*14),[])
        self.assertEqual(get_supported_yaku(DAISANGEN[:-1]),[])

    def test_readers_do_not_mutate_input(self):
        hand=DAISANGEN.copy(); before=deepcopy(hand)
        get_supported_yaku(hand)
        evaluate_hand_score(hand,'9p')
        self.assertEqual(hand,before)


class OpeningYakumanTests(unittest.TestCase):
    def test_tenhou_legal_and_scored(self):
        game=first_draw_game(NORMAL)
        start_turn(game)
        self.assertTrue(can_tsumo(game,0))
        declare_tsumo(game,0)
        score=get_winner_score(game,0)
        self.assertEqual(score['yaku'],['Tenhou'])
        self.assertEqual(score['payments']['total'],48000)
        check_tile_counts(game)

    def test_chiihou_legal_and_scored(self):
        game=first_draw_game(NORMAL,1)
        start_turn(game)
        # Public scoring is independent of the human-only declaration wrapper.
        game.update(phase='ended',end_reason='tsumo',winner_index=1,winner_indices=[1])
        self.assertEqual(get_winner_score(game,1)['yaku'],['Chiihou'])
        self.assertEqual(get_winner_score(game,1)['payments']['total'],32000)
        check_tile_counts(game)

    def test_tenhou_stacks_with_tile_yakuman(self):
        game=first_draw_game(DAISANGEN)
        start_turn(game);declare_tsumo(game,0)
        self.assertCountEqual(get_winner_score(game,0)['yaku'],['Daisangen','Tenhou'])
        self.assertEqual(get_winner_score(game,0)['payments']['total'],96000)

    def test_kokushi_stacks_with_tenhou(self):
        hand=tiles('1m 9m 1p 9p 1s 9s 1z 2z 3z 4z 5z 6z 7z 1m')
        score=evaluate_hand_score(hand,'1m',is_tsumo=True,is_dealer=True,tenhou=True)
        self.assertCountEqual(score['yaku'],['Kokushi Musou','Tenhou'])
        self.assertEqual(score['yakuman_count'],2)

    def test_calls_cancel_opening_yakuman(self):
        game=first_draw_game(NORMAL,1)
        interrupt_ippatsu(game);start_turn(game)
        self.assertFalse(get_event_yaku_flags(game,1,is_tsumo=True)['chiihou'])

    def test_second_draw_is_not_chiihou(self):
        game=first_draw_game(NORMAL,1)
        game['ordinary_draw_counts'][1]=1
        start_turn(game)
        self.assertFalse(get_event_yaku_flags(game,1,is_tsumo=True)['chiihou'])

    def test_discard_ends_opening_draw_context(self):
        game=first_draw_game(NORMAL)
        start_turn(game);finish_turn(game,0,13)
        self.assertIsNone(game['ordinary_draw_player'])
        self.assertFalse(get_event_yaku_flags(game,0,is_tsumo=True)['tenhou'])

    def test_rinshan_never_opening_yakuman(self):
        game=first_draw_game(NORMAL)
        start_turn(game)
        game['rinshan_player_index']=0
        self.assertFalse(get_event_yaku_flags(game,0,is_tsumo=True)['tenhou'])

    def test_invalid_opening_flags(self):
        for flags in [{'tenhou':True},{'is_tsumo':True,'tenhou':True},
                      {'is_tsumo':True,'is_dealer':True,'chiihou':True},
                      {'is_tsumo':True,'tenhou':True,'chiihou':True}]:
            with self.subTest(flags=flags),self.assertRaises(ValueError):
                evaluate_hand_score(NORMAL,'5z',**flags)

    def test_synthetic_hand_does_not_automatically_get_tenhou(self):
        game=create_game();game['hands'][0]=NORMAL.copy();game['phase']='discard'
        self.assertFalse(get_event_yaku_flags(game,0,is_tsumo=True)['tenhou'])

    def test_next_hand_resets_draw_counts(self):
        game=first_draw_game(NORMAL);start_turn(game);declare_tsumo(game,0)
        nxt=create_next_hand(game)
        self.assertEqual(nxt['ordinary_draw_counts'],[0]*4)
        self.assertIsNone(nxt['ordinary_draw_player'])


if __name__=='__main__':unittest.main()
