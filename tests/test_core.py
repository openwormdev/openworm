import copy
import math
import unittest

from wormbrain.core import PaperEngine, POLICY, SENSORY, digest, encode, features, neural_scores, scenario, validate_ticks, FORWARD, REVERSE


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.ticks=scenario('reversal')

    def test_features_never_read_future(self):
        changed=copy.deepcopy(self.ticks)
        for row in changed[4:]: row['price']=100000.0
        self.assertEqual(features(self.ticks,3),features(changed,3))

    def test_mapping_is_bounded_and_named(self):
        for i in range(len(self.ticks)):
            a=encode(features(self.ticks,i))
            self.assertEqual(set(a),set(SENSORY))
            self.assertTrue(all(0 <= v <= 5 for v in a.values()))
            self.assertEqual(a['ASHL'],a['ASHR'])

    def test_constant_data_and_stale_data(self):
        for row in self.ticks: row['price']=1.0
        self.assertTrue(all(math.isfinite(v) for v in features(self.ticks,5).values()))
        self.ticks[5]['fresh']=False
        self.assertEqual(set(encode(features(self.ticks,5)).values()),{0.0})

    def test_nan_invalid_time_and_unknown_scenario_rejected(self):
        self.ticks[3]['price']=float('nan')
        with self.assertRaises(ValueError): validate_ticks(self.ticks)
        with self.assertRaises(ValueError): scenario('not-a-scenario')
        self.ticks=scenario('trend');self.ticks[3]['seconds']=1
        with self.assertRaises(ValueError): validate_ticks(self.ticks)

    def test_real_neuron_decoder_formula(self):
        null={n:-50.0 for n in FORWARD+REVERSE}
        values={n:-45.0 if n in FORWARD else -50.0 for n in null}
        scores=neural_scores(values,null)
        self.assertAlmostEqual(scores['margin'],.5)
        with self.assertRaises(KeyError): neural_scores({},null)

    def test_entry_confirmation_no_double_entry_and_fee(self):
        engine=PaperEngine()
        first=engine.step(self.ticks[0],{'margin':.5})
        second=engine.step(self.ticks[1],{'margin':.5})
        third=engine.step(self.ticks[2],{'margin':.5})
        self.assertIsNone(first['fill']);self.assertEqual(second['fill']['side'],'BUY')
        self.assertIsNone(third['fill'])
        self.assertAlmostEqual(engine.cash,1000-25-.075)
        self.assertGreater(second['fill']['price'],self.ticks[1]['price'])

    def test_external_veto_keeps_worm_intent(self):
        engine=PaperEngine()
        engine.step(self.ticks[0],{'margin':.8})
        self.ticks[1]['eligible']=False
        row=engine.step(self.ticks[1],{'margin':.8})
        self.assertEqual(row['intent'],'ENTER');self.assertEqual(row['risk'],'BLOCK')
        self.assertEqual(engine.units,0)

    def test_illiquid_exit_is_not_fabricated(self):
        engine=PaperEngine()
        engine.step(self.ticks[0],{'margin':.8});engine.step(self.ticks[1],{'margin':.8})
        self.ticks[2]['liquidity']=0
        row=engine.step(self.ticks[2],{'margin':.5})
        self.assertEqual(row['intent'],'HOLD');self.assertEqual(row['risk'],'FORCE_EXIT')
        self.assertEqual(row['execution'],'EXIT_UNFILLED');self.assertGreater(engine.units,0)

    def test_kill_and_cooldown(self):
        engine=PaperEngine();engine.step(self.ticks[0],{'margin':.8})
        engine.step(self.ticks[1],{'margin':.8})
        exit_row=engine.step(self.ticks[2],{'margin':.8},kill=True)
        self.assertEqual(exit_row['risk'],'FORCE_EXIT');self.assertEqual(exit_row['fill']['side'],'SELL')
        engine.step(self.ticks[3],{'margin':.8})
        row=engine.step(self.ticks[4],{'margin':.8})
        self.assertIn('COOLDOWN',row['reasons']);self.assertIsNone(row['fill'])

    def test_stable_hash_and_nan_rejection(self):
        self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}))
        with self.assertRaises(ValueError):digest({'a':float('nan')})

    def test_unknown_identity_fields_rejected(self):
        self.ticks[0]['owner']='fictional'
        with self.assertRaises(ValueError):validate_ticks(self.ticks)

    def test_kill_latches_across_later_ticks(self):
        engine=PaperEngine()
        engine.step(self.ticks[0],{'margin':.8},kill=True)
        for tick in self.ticks[1:]:
            row=engine.step(tick,{'margin':.8})
            self.assertEqual(row['risk'],'BLOCK');self.assertIsNone(row['fill'])


if __name__=='__main__': unittest.main()
