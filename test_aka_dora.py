import unittest
import tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from collections import Counter
import main
from tile_utils import normalize_tiles, count_aka_dora
from hand_evaluator import is_complete_hand, get_waiting_tiles, get_tenpai_discards
from win_rules import is_discard_furiten
from scoring import evaluate_hand_score
from ai import calculate_shanten, choose_discard
from game_store import GameStore, validate_game

HAND = '3m 4m 0m 4p 5p 6p 2s 3s 4s 6s 7s 8s 2p 2p'.split()

def response_game(hand, called='5m', melds=None):
    g=main.create_game();pool=main.create_tiles();melds=melds or []
    for t in hand+[called]+[t for m in melds for t in m['tiles']]: pool.remove(t)
    g['hands']=[list(hand),[],[],[]];g['melds'][0]=deepcopy(melds)
    for i in (1,2,3):g['hands'][i]=[pool.pop(0) for _ in range(13)]
    g['dead_wall']=[pool.pop(0) for _ in range(14)];g['wall']=pool
    g['discards'][3]=[called];g['discard_history'][3]=[called]
    g['last_discard']={'player_index':3,'tile':called};g['phase']='response'
    g['current_player_index']=3
    return g

class AkaDoraTests(unittest.TestCase):
    def test_deck(self):
        c=Counter(main.create_tiles());self.assertEqual(sum(c.values()),136)
        for suit in 'mps':self.assertEqual((c['0'+suit],c['5'+suit]),(1,3))
        self.assertEqual(set(Counter(normalize_tiles(main.create_tiles())).values()),{4})
    def test_legacy_deck(self):self.assertEqual(len(main.create_tiles(False)),136)
    def test_completion_and_no_mutation(self):
        before=HAND.copy();self.assertTrue(is_complete_hand(HAND));self.assertEqual(HAND,before)
    def test_seven_pairs(self):
        self.assertTrue(is_complete_hand('0m 5m 1m 1m 2p 2p 3p 3p 4s 4s 6s 6s 7z 7z'.split()))
    def test_five_copies_rejected(self):
        self.assertFalse(is_complete_hand('0m 5m 5m 5m 5m 1p 2p 3p 1s 2s 3s 7z 7z 7z'.split()))
    def test_waits(self):self.assertEqual(get_waiting_tiles(HAND[:-1]),['2p'])
    def test_discard_indices(self):
        result=get_tenpai_discards(HAND)
        self.assertTrue(all(0<=x['tile_index']<14 for x in result))
    def test_furiten_red_history(self):
        h='3m 4m 4p 5p 6p 2s 3s 4s 6s 7s 8s 2p 2p'.split()
        self.assertTrue(is_discard_furiten(h,['0m']))
    def test_furiten_normal_history(self):
        h='0m 4p 5p 6p 2s 3s 4s 6s 7s 8s 1z 1z 1z'.split()
        self.assertTrue(is_discard_furiten(h,['5m']))
    def test_red_indicator(self):self.assertEqual(main.indicator_to_dora('0p'),'6p')
    def test_normal_dora_counts_red(self):self.assertEqual(main.count_dora(['0m','5m'],[],['4m']),2)
    def test_aka_in_meld(self):self.assertEqual(count_aka_dora(['0m'],[{'tiles':['0p','5p','5p']}]),2)
    def test_bonus_stack(self):
        score=evaluate_hand_score(HAND,'2p',riichi=True,dora_count=1,ura_dora_count=1)
        self.assertEqual(score['aka_dora_count'],1)
        self.assertEqual(score['bonus_han'],3)
        self.assertEqual(score['han'],score['yaku_han']+3)
    def test_aka_is_not_yaku(self):
        hand='1m 2m 3m 4p 0p 6p 7s 8s 9s 2z 2z 2z 5z 5z'.split()
        self.assertIsNone(evaluate_hand_score(hand,'3m'))
    def test_yakuman_ignores_aka(self):
        hand='1m 1m 1m 2m 3m 4m 0m 6m 7m 8m 9m 9m 9m 5m'.split()
        score=evaluate_hand_score(hand,'5m',is_tsumo=True)
        self.assertGreater(score['yakuman_count'],0);self.assertEqual(score['aka_dora_count'],0)
    def test_ai_accepts_red(self):
        self.assertEqual(calculate_shanten(HAND),-1)
        self.assertIn(choose_discard(HAND),range(14))
    def test_sort(self):
        hand=['6m','0m','4m','5m'];main.sort_tiles(hand)
        self.assertEqual(normalize_tiles(hand),['4m','5m','5m','6m'])
    def test_chi_has_red_and_normal_choices(self):
        g=response_game('3m 0m 5m 1p 2p 4p 7p 8p 2s 4s 6s 1z 2z'.split(),'4m')
        opts=main.get_chi_options(g,0)
        self.assertTrue(any('0m' in o['hand_tiles'] for o in opts))
        self.assertTrue(any('5m' in o['hand_tiles'] for o in opts))
        with patch.object(main,'can_ron',return_value=False):
            idx=next(i for i,o in enumerate(opts) if '0m' in o['hand_tiles'])
            main.declare_chi(g,0,idx)
        self.assertIn('0m',g['melds'][0][0]['tiles']);main.check_tile_counts(g)
    def test_pon_preserves_red(self):
        g=response_game('0m 5m 1p 2p 4p 7p 8p 2s 4s 6s 1z 2z 3z'.split())
        with patch.object(main,'can_ron',return_value=False):main.declare_pon(g,0)
        self.assertEqual(Counter(g['melds'][0][0]['tiles']),Counter(['0m','5m','5m']))
        main.check_tile_counts(g)
        before=deepcopy(g)
        # The last ordinary five may not be swapped for a called five.
        g['hands'][0].append('0m')
        with self.assertRaises(ValueError):main.finish_turn(g,0,len(g['hands'][0])-1)
        g['hands'][0].pop();self.assertEqual(g,before)
    def test_red_discard_pon(self):
        g=response_game('5m 5m 1p 2p 4p 7p 8p 2s 4s 6s 1z 2z 3z'.split(),'0m')
        with patch.object(main,'can_ron',return_value=False):main.declare_pon(g,0)
        self.assertIn('0m',g['melds'][0][0]['tiles']);main.check_tile_counts(g)
    def test_daiminkan(self):
        g=response_game('0m 5m 5m 1p 2p 4p 7p 8p 2s 4s 6s 1z 2z'.split())
        with patch.object(main,'can_ron',return_value=False):main.declare_daiminkan(g,0)
        self.assertEqual(g['melds'][0][0]['tiles'].count('0m'),1);main.check_tile_counts(g)
    def test_ankan(self):
        g=response_game('0m 5m 5m 1p 2p 4p 7p 8p 2s 4s 6s 1z 2z'.split())
        g['hands'][0].append(g['discards'][3].pop());g['discard_history'][3]=[]
        g['last_discard']=None;g['current_player_index']=0;g['phase']='discard'
        self.assertIn('5m',main.get_ankan_options(g,0));main.declare_ankan(g,0,'5m')
        self.assertIn('0m',g['melds'][0][0]['tiles']);main.check_tile_counts(g)
    def test_kakan_and_chankan_tile(self):
        meld={'type':'pon','tiles':['5m']*3,'from_player_index':3}
        g=response_game('0m 1p 2p 4p 7p 8p 2s 4s 6s 1z 1z'.split(),'2z',[meld])
        g['phase']='discard';g['current_player_index']=0;g['last_discard']=None
        self.assertEqual(main.get_kakan_options(g,0)[0]['tile'],'0m')
        main.declare_kakan(g,0,0)
        self.assertEqual(g['pending_kakan']['tile'],'0m')
        main.resolve_kakan_responses(g,[])
        self.assertIn('0m',g['melds'][0][0]['tiles']);main.check_tile_counts(g)
    def test_ron_claims_red_and_scores_it(self):
        hand='3m 4m 1p 2p 3p 7s 8s 9s 1z 1z 1z 2z 2z'.split()
        g=response_game(hand,'0m')
        self.assertTrue(main.can_ron(g,0));main.declare_ron(g,0)
        self.assertEqual(main.get_winner_score(g,0)['aka_dora_count'],1)
        self.assertEqual(g['discards'][3][-1],'0m');main.check_tile_counts(g)
    def test_chankan_red_physical_tile(self):
        hand='3m 4m 1p 2p 3p 7s 8s 9s 1z 1z 1z 2z 2z'.split()
        g=response_game(hand,'0m')
        # Gather all three normal fives into Player 2's Pon.
        for pile in [g['wall'],g['dead_wall']]+g['hands'][1:]:
            while '5m' in pile:
                pile.remove('5m')
                # Refill hands/dead wall from a non-five in the wall.
                if pile is not g['wall']:
                    idx=next(i for i,t in enumerate(g['wall']) if t!='5m')
                    pile.append(g['wall'].pop(idx))
        g['melds'][1]=[{'type':'pon','tiles':['5m']*3,'from_player_index':2}]
        g['wall'].extend(g['hands'][1][-3:]);del g['hands'][1][-3:]
        g['hands'][1].append(g['discards'][3].pop());g['discard_history'][3]=[]
        g['last_discard']=None;g['phase']='discard';g['current_player_index']=1
        g['is_closed'][1]=False
        main.check_tile_counts(g);main.declare_kakan(g,1,0)
        self.assertTrue(main.can_chankan(g,0));main.declare_chankan(g,0)
        self.assertEqual(g['robbed_kan_tile'],'0m')
        self.assertEqual(main.get_winner_score(g,0)['aka_dora_count'],1)
        main.check_tile_counts(g)
    def test_riichi_ankan_with_drawn_red(self):
        from riichi_kan import is_riichi_ankan_legal
        hand='5m 5m 5m 2p 3p 4p 6s 7s 8s 9p 9p 9p 5z 0m'.split()
        self.assertTrue(is_riichi_ankan_legal(hand, [], '5m'))
    def test_kakan_red_in_existing_pon(self):
        meld={'type':'pon','tiles':['0m','5m','5m'],'from_player_index':3}
        g=response_game('5m 1p 2p 4p 7p 8p 2s 4s 6s 1z 1z'.split(),'2z',[meld])
        g['phase']='discard';g['current_player_index']=0;g['last_discard']=None
        main.declare_kakan(g,0,0);main.resolve_kakan_responses(g,[])
        self.assertEqual(g['melds'][0][0]['tiles'].count('0m'),1);main.check_tile_counts(g)
    def test_red_tsumo_api_score(self):
        import server
        g=main.create_game();g['hands'][0]=HAND.copy()
        g['current_player_index']=0;g['phase']='discard'
        g['ordinary_draw_player']=0;g['calls_made']=True
        g['ordinary_draw_counts']=[2,2,2,2]
        self.assertTrue(main.can_tsumo(g,0));main.declare_tsumo(g,0)
        self.assertEqual(main.get_winner_score(g,0)['aka_dora_count'],1)
        with patch.object(server,'game',g):
            view=server.get_player_view()
        self.assertEqual(view['winning_hands'][0]['aka_dora_count'],1)
    def test_red_deck_save_roundtrip(self):
        g=main.create_game();main.advance_until_human(g)
        validate_game(g)
        with tempfile.TemporaryDirectory() as tmp:
            store=GameStore(Path(tmp)/'save.json');store.save(g)
            self.assertEqual(store.load(),g)
    def test_legacy_save(self):
        g=normalize_tiles(main.create_game());validate_game(g)
    def test_invalid_red_distribution(self):
        g=main.create_game()
        # Replacing just one red with normal is an invalid partial red deck.
        for pile in [g['wall'],g['dead_wall']]+g['hands']:
            if '0m' in pile:pile[pile.index('0m')]='5m';break
        with self.assertRaises(ValueError):validate_game(g)

if __name__=='__main__':unittest.main()
