import unittest
from copy import deepcopy
from yaku import get_supported_yaku, get_yaku_candidates, count_supported_yaku_han
from scoring import evaluate_hand_score
from main import create_game, can_tsumo, can_ron, declare_tsumo, get_winner_score


def tiles(text):
    return text.split()


CHANTA = tiles('1m 2m 3m 7p 8p 9p 1s 1s 1s 2z 2z 2z 9s 9s')
JUNCHAN = tiles('1m 2m 3m 7p 8p 9p 1s 1s 1s 9m 9m 9m 9s 9s')
HONROUTOU = tiles('1m 1m 1m 9p 9p 9p 1s 1s 1s 2z 2z 2z 9s 9s')
SHOUSANGEN = tiles('5z 5z 5z 6z 6z 6z 7z 7z 1m 2m 3m 4p 5p 6p')
SANSHOKU = tiles('2m 2m 2m 2p 2p 2p 2s 2s 2s 4m 5m 6m 8p 8p')


class PatternYakuTests(unittest.TestCase):
    def yaku(self, hand, melds=None, **kwargs):
        return get_supported_yaku(hand, melds=melds, seat_wind='3z', round_wind='4z', **kwargs)

    def test_closed_chanta(self):
        self.assertIn('Chanta', self.yaku(CHANTA))
        self.assertNotIn('Junchan', self.yaku(CHANTA))

    def test_open_chanta(self):
        hand = CHANTA[3:]
        melds = [{'type':'chi', 'tiles':CHANTA[:3]}]
        yaku = self.yaku(hand, melds)
        self.assertEqual(yaku, ['Chanta'])
        self.assertEqual(count_supported_yaku_han(yaku, is_closed=False), 1)

    def test_closed_junchan_excludes_chanta(self):
        yaku = self.yaku(JUNCHAN)
        self.assertIn('Junchan', yaku)
        self.assertNotIn('Chanta', yaku)

    def test_open_junchan_han(self):
        melds = [{'type':'chi', 'tiles':JUNCHAN[:3]}]
        yaku = self.yaku(JUNCHAN[3:], melds)
        self.assertEqual(yaku, ['Junchan'])
        self.assertEqual(count_supported_yaku_han(yaku, is_closed=False), 2)

    def test_inside_pair_blocks_outside_yaku(self):
        hand = CHANTA[:-2] + ['5s']*2
        self.assertNotIn('Chanta', self.yaku(hand))
        hand = JUNCHAN[:-2] + ['5s']*2
        self.assertNotIn('Junchan', self.yaku(hand))

    def test_inside_sequence_blocks_chanta(self):
        hand = ['2m','3m','4m'] + CHANTA[3:]
        self.assertNotIn('Chanta', self.yaku(hand))

    def test_declared_inside_sequence_blocks_chanta(self):
        melds = [{'type':'chi', 'tiles':['2m','3m','4m']}]
        self.assertNotIn('Chanta', self.yaku(CHANTA[3:], melds))

    def test_chanta_needs_sequence(self):
        yaku = self.yaku(HONROUTOU)
        self.assertIn('Honroutou', yaku)
        self.assertIn('Toitoi', yaku)
        self.assertNotIn('Chanta', yaku)
        self.assertNotIn('Junchan', yaku)

    def test_honroutou_seven_pairs(self):
        hand = tiles('1m 1m 9m 9m 1p 1p 9p 9p 1s 1s 9s 9s 2z 2z')
        self.assertCountEqual(self.yaku(hand), ['Honroutou', 'Chiitoitsu'])
        score = evaluate_hand_score(hand, '2z', seat_wind='3z', round_wind='4z')
        self.assertEqual(score['han'], 4)
        self.assertEqual(score['fu'], 25)

    def test_simple_tile_blocks_honroutou(self):
        hand = HONROUTOU[:-2] + ['5s']*2
        self.assertNotIn('Honroutou', self.yaku(hand))

    def test_open_honroutou(self):
        melds = [{'type':'pon', 'tiles':['1m']*3}]
        yaku = self.yaku(HONROUTOU[3:], melds)
        self.assertCountEqual(yaku, ['Honroutou', 'Toitoi'])

    def test_shousangen_combines_two_dragon_yaku(self):
        self.assertCountEqual(self.yaku(SHOUSANGEN),
                              ['Shousangen','Yakuhai: White Dragon','Yakuhai: Green Dragon'])
        score = evaluate_hand_score(SHOUSANGEN, '7z')
        self.assertEqual(score['han'], 4)

    def test_shousangen_all_three_pair_choices(self):
        for pair in ['5z','6z','7z']:
            hand = ['1m','2m','3m','4p','5p','6p'] + [pair]*2
            for dragon in ['5z','6z','7z']:
                if dragon != pair: hand.extend([dragon]*3)
            with self.subTest(pair=pair):self.assertIn('Shousangen', self.yaku(hand))

    def test_open_dragon_kan_counts_for_shousangen(self):
        melds = [{'type':'daiminkan', 'tiles':['5z']*4}]
        self.assertIn('Shousangen', self.yaku(SHOUSANGEN[3:], melds))

    def test_non_dragon_pair_blocks_shousangen(self):
        hand = [t for t in SHOUSANGEN if t != '7z'] + ['2z']*2
        self.assertNotIn('Shousangen', self.yaku(hand))

    def test_sanshoku_doukou(self):
        self.assertIn('Sanshoku Doukou', self.yaku(SANSHOKU))
        self.assertNotIn('Sanshoku Doujun', self.yaku(SANSHOKU))

    def test_kan_counts_for_sanshoku_doukou(self):
        melds = [{'type':'kakan', 'tiles':['2m']*4}]
        self.assertIn('Sanshoku Doukou', self.yaku(SANSHOKU[3:], melds))

    def test_different_number_blocks_sanshoku_doukou(self):
        hand = ['3m']*3 + SANSHOKU[3:]
        self.assertNotIn('Sanshoku Doukou', self.yaku(hand))

    def test_same_sequence_is_not_same_triplet(self):
        hand = tiles('1m 2m 3m 1p 2p 3p 1s 2s 3s 7s 8s 9s 5z 5z')
        self.assertNotIn('Sanshoku Doukou', self.yaku(hand))
        self.assertIn('Sanshoku Doujun', self.yaku(hand))

    def test_three_kans(self):
        melds = [{'type':kind, 'tiles':[tile]*4}
                 for kind,tile in [('ankan','2m'),('daiminkan','3p'),('kakan','4s')]]
        yaku = self.yaku(tiles('6m 7m 8m 2z 2z'), melds)
        self.assertEqual(yaku, ['Sankantsu'])
        score = evaluate_hand_score(tiles('6m 7m 8m 2z 2z'), '2z', melds,
                                    seat_wind='3z', round_wind='4z')
        self.assertEqual(score['han'], 2)

    def test_two_kans_and_pon_do_not_count_as_three_kans(self):
        melds = [{'type':'ankan', 'tiles':['2m']*4},
                 {'type':'daiminkan','tiles':['3p']*4},
                 {'type':'pon','tiles':['4s']*3}]
        self.assertNotIn('Sankantsu', self.yaku(tiles('6m 7m 8m 2z 2z'), melds))

    def test_three_concealed_kans_keep_hand_closed(self):
        melds = [{'type':'ankan', 'tiles':[t]*4} for t in ['1m','9p','1s']]
        hand = tiles('7m 8m 9m 2z 2z')
        yaku = self.yaku(hand, melds, winning_tile='2z', is_tsumo=True)
        self.assertIn('Sankantsu', yaku)
        self.assertIn('Sanankou', yaku)
        self.assertIn('Chanta', yaku)
        self.assertEqual(count_supported_yaku_han(yaku), 6)

    def test_chanta_and_junchan_han_values(self):
        self.assertEqual(count_supported_yaku_han(['Chanta']), 2)
        self.assertEqual(count_supported_yaku_han(['Junchan']), 3)
        for name in ['Honroutou','Shousangen','Sanshoku Doukou','Sankantsu']:
            with self.subTest(name=name):
                self.assertEqual(count_supported_yaku_han([name], is_closed=True), 2)
                self.assertEqual(count_supported_yaku_han([name], is_closed=False), 2)

    def test_invalid_and_incomplete_hands_get_no_yaku(self):
        for hand in [CHANTA[:-1], JUNCHAN+['2z'], ['1m']*14]:
            with self.subTest(hand=hand):self.assertEqual(self.yaku(hand), [])

    def test_inputs_not_modified(self):
        melds = [{'type':'chi','tiles':['3m','1m','2m']}]
        hand = CHANTA[3:]
        before = deepcopy((hand,melds))
        self.yaku(hand,melds)
        evaluate_hand_score(hand, '9s', melds)
        self.assertEqual((hand,melds), before)

    def test_honroutou_candidates_do_not_gain_sequence_yaku(self):
        for candidate in get_yaku_candidates(HONROUTOU):
            self.assertNotIn('Chanta', candidate['yaku'])
            self.assertNotIn('Junchan', candidate['yaku'])

    def test_new_open_yaku_can_enable_tsumo_and_settlement(self):
        game = create_game()
        game['phase'] = 'discard'
        game['hands'][0] = CHANTA[3:]
        game['melds'][0] = [{'type':'chi','tiles':CHANTA[:3]}]
        game['is_closed'][0] = False
        game['seat_winds'][0] = '3z'
        game['round_wind'] = '4z'
        self.assertTrue(can_tsumo(game,0))
        declare_tsumo(game,0)
        self.assertEqual(get_winner_score(game,0)['yaku'], ['Chanta'])
        self.assertIsNotNone(game['settlement'])

    def test_new_open_yaku_can_enable_ron(self):
        game = create_game()
        game['phase'] = 'response'
        game['hands'][0] = CHANTA[3:-1]
        game['melds'][0] = [{'type':'chi','tiles':CHANTA[:3]}]
        game['is_closed'][0] = False
        game['seat_winds'][0] = '3z'
        game['round_wind'] = '4z'
        game['last_discard'] = {'player_index':1,'tile':'9s'}
        self.assertTrue(can_ron(game,0))
        game['discard_history'][0] = ['9s']
        self.assertFalse(can_ron(game,0))


if __name__ == '__main__':unittest.main()
