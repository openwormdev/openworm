"""A bounded numerical smoke comparison, NOT whole-behavior equivalence."""
import json
import tempfile
from pathlib import Path
import numpy as np
from wormbrain.brain import simulate
from wormbrain.core import MODEL_CONFIG, READOUT, SENSORY


def main():
    original = dict(MODEL_CONFIG)
    MODEL_CONFIG.update(warmup_ms=20, episode_ms=20, readout_ms=5, pulse_delay_ms=2, pulse_duration_ms=14)
    inputs = [{n: (2.5 if n in {'ASEL', 'AWAL', 'AWAR'} else 0.0) for n in SENSORY},
              {n: (2.5 if n in {'ASER', 'ASHL', 'ASHR'} else 0.0) for n in SENSORY}]
    try:
        with tempfile.TemporaryDirectory(prefix='wormbrain-comparison-') as folder:
            reference = simulate(inputs, Path(folder) / 'java', backend='jneuroml')
            exported = simulate(inputs, Path(folder) / 'neuron', backend='neuron')
        a,b=reference['traces'],exported['traces']
        end=min(a['time_ms'][-1],b['time_ms'][-1])
        times=np.asarray([t for t in a['time_ms'] if t <= end])
        errors={}
        for neuron in READOUT:
            expected=np.interp(times,a['time_ms'],a['voltage_mv'][neuron])
            actual=np.interp(times,b['time_ms'],b['voltage_mv'][neuron])
            delta=actual-expected
            errors[neuron]={'max_abs_mv':float(np.max(np.abs(delta))),'rmse_mv':float(np.sqrt(np.mean(delta**2)))}
        summary={'scope':'60 ms transient and driven smoke comparison; 302 neurons, 18 observed',
                 'reference':'jNeuroML interpreter','export':'NEURON via official jNeuroML exporter',
                 'dt_ms':.05,'threshold_max_abs_mv':1.0,'errors':errors,
                 'passed':max(e['max_abs_mv'] for e in errors.values()) <= 1.0,
                 'limitation':'Does not establish long-run or behavioral equivalence.'}
        Path('docs/backend-validation.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps({'passed':summary['passed'],'worst_error_mv':max(e['max_abs_mv'] for e in errors.values())}))
        if not summary['passed']:
            raise SystemExit('Backend comparison exceeds the declared 1 mV smoke threshold')
    finally:
        MODEL_CONFIG.clear();MODEL_CONFIG.update(original)


if __name__=='__main__':main()
