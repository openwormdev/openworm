import copy
import math
import unittest

from wormbrain.core import (CURRENT_LIMITS_PA, FORWARD, MODEL_CONFIG, PLASTICITY,
                            REVERSE, SENSORY, CommandStateMachine,
                            DopaminePlasticity, PaperEngine, digest, encode,
                            features, neural_scores, proprioceptive_feedback,
                            scenario, validate_ticks)


def scores(state):
    vector = {"forward": .7 if state == "FORWARD" else .05,
              "reverse": .7 if state == "REVERSE" else .05,
              "pause": .9 if state == "PAUSE" else 0.0, "rim": 0.0, "rib": 0.0}
    return {"forward": vector["forward"], "reverse": vector["reverse"],
            "margin": vector["forward"] - vector["reverse"], "vector": vector}


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
            self.assertTrue(all(0 <= v <= CURRENT_LIMITS_PA[n] for n,v in a.items()))
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
        self.assertEqual(scores['vector']['forward'],.5)
        with self.assertRaises(KeyError): neural_scores({},null)

    def test_command_vector_enters_without_margin_streak_and_no_double_entry(self):
        engine=PaperEngine()
        first=engine.step(self.ticks[0],scores('FORWARD'))
        second=engine.step(self.ticks[1],scores('FORWARD'))
        self.assertEqual(first['fill']['side'],'BUY');self.assertIsNone(second['fill'])
        self.assertEqual(first['decoder']['state'],'FORWARD')
        self.assertAlmostEqual(engine.cash,1000-25-.075)
        self.assertGreater(first['fill']['price'],self.ticks[0]['price'])

    def test_external_veto_keeps_worm_intent(self):
        engine=PaperEngine()
        self.ticks[0]['eligible']=False
        row=engine.step(self.ticks[0],scores('FORWARD'))
        self.assertEqual(row['intent'],'ENTER');self.assertEqual(row['risk'],'BLOCK')
        self.assertEqual(engine.units,0)

    def test_illiquid_exit_is_not_fabricated(self):
        engine=PaperEngine()
        engine.step(self.ticks[0],scores('FORWARD'))
        self.ticks[1]['liquidity']=0
        row=engine.step(self.ticks[1],scores('REVERSE'))
        self.assertEqual(row['intent'],'EXIT');self.assertEqual(row['risk'],'FORCE_EXIT')
        self.assertEqual(row['execution'],'EXIT_UNFILLED');self.assertGreater(engine.units,0)

    def test_kill_and_cooldown(self):
        engine=PaperEngine();engine.step(self.ticks[0],scores('FORWARD'))
        exit_row=engine.step(self.ticks[1],scores('REVERSE'),kill=True)
        self.assertEqual(exit_row['risk'],'FORCE_EXIT');self.assertEqual(exit_row['fill']['side'],'SELL')
        row=engine.step(self.ticks[2],scores('FORWARD'))
        self.assertIn('COOLDOWN',row['reasons']);self.assertIsNone(row['fill'])

    def test_stable_hash_and_nan_rejection(self):
        self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}))
        with self.assertRaises(ValueError):digest({'a':float('nan')})

    def test_unknown_identity_fields_rejected(self):
        self.ticks[0]['owner']='fictional'
        with self.assertRaises(ValueError):validate_ticks(self.ticks)

    def test_kill_latches_across_later_ticks(self):
        engine=PaperEngine()
        engine.step(self.ticks[0],scores('FORWARD'),kill=True)
        for tick in self.ticks[1:]:
            row=engine.step(tick,scores('FORWARD'))
            self.assertEqual(row['risk'],'BLOCK');self.assertIsNone(row['fill'])

    def test_decoder_pause_and_rim_rib_vector_are_public(self):
        decoder=CommandStateMachine()
        paused=decoder.step(scores('PAUSE')['vector'])
        moving=decoder.step(scores('REVERSE')['vector'])
        self.assertEqual(paused['state'],'PAUSE')
        self.assertEqual(moving['state'],'REVERSE')
        self.assertIn('rim',moving['vector']);self.assertIn('rib',moving['vector'])

    def test_plasticity_is_bounded_and_persistent(self):
        rule=DopaminePlasticity()
        adverse={name:0.0 for name in SENSORY}
        adverse.update(ASEL=CURRENT_LIMITS_PA['ASEL'],ASHL=CURRENT_LIMITS_PA['ASHL'],ASHR=CURRENT_LIMITS_PA['ASHR'])
        for _ in range(100): frame=rule.update(adverse)
        self.assertEqual(rule.gain,PLASTICITY['gain_bounds'][0])
        self.assertGreater(frame['eligibility'],0)
        safe={name:0.0 for name in SENSORY};safe.update(AWAL=1,AWAR=1,AWCL=1,AWCR=1)
        self.assertGreater(rule.update(safe)['next_gain'],PLASTICITY['gain_bounds'][0])

    def test_paper_outcome_feedback_is_bounded(self):
        veto=proprioceptive_feedback({'intent':'ENTER','fill':None})
        fill=proprioceptive_feedback({'intent':'ENTER','fill':{'side':'BUY'}})
        self.assertGreater(veto['DVA'],0);self.assertGreater(fill['PVCL'],0)
        self.assertTrue(all(0 <= v <= CURRENT_LIMITS_PA[n] for n,v in fill.items()))

    def test_reader_and_calibration_are_pinned_without_hardcoded_population(self):
        self.assertEqual(MODEL_CONFIG['parameter_set'],'C1')
        self.assertEqual(MODEL_CONFIG['reader'],'cect.readers.Cook2019HermReader')
        self.assertEqual(len(MODEL_CONFIG['reader_cache_sha256']),64)
        self.assertNotIn('neurons',MODEL_CONFIG)


if __name__=='__main__': unittest.main()
