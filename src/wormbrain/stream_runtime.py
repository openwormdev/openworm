"""Isolated persistent NEURON process. Only stimuli change between advances."""
from __future__ import annotations
import contextlib
import importlib.util
import json
import math
import sys
from pathlib import Path

from .core import MODEL_CONFIG, READOUT, SENSORY


def emit(value):
    print("WORM_JSON " + json.dumps(value, allow_nan=False), flush=True)


def main():
    with contextlib.redirect_stdout(sys.stderr):
        spec = importlib.util.spec_from_file_location("generated_worm", Path.cwd() / "LEMS_WormBrain_nrn.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ns = module.NeuronSimulation(tstop=1, dt=MODEL_CONFIG["dt_ms"], seed=123456789, abs_tol=None, rel_tol=None)
        from neuron import h
        import numpy as np
        vectors = {n: getattr(h, f"v_{n}_v_neurons_v") for n in READOUT}
        pulses = {n: getattr(h, f"Input_{n}_stim_{n}_1_0") for n in SENSORY}
        def advance(ms):
            for _ in range(round(ms / MODEL_CONFIG["dt_ms"])):
                ns.advance()
        def sample(end):
            times = np.array(h.v_time)
            mask = (times >= end - MODEL_CONFIG["readout_ms"]) & (times < end)
            if not mask.any():
                raise RuntimeError("Missing live readout")
            frames = {n: float(np.mean(np.array(v)[mask])) for n, v in vectors.items()}
            if not all(math.isfinite(x) for x in frames.values()):
                raise RuntimeError("Non-finite neural state")
            stride = max(1, len(times) // 100)
            traces = dict(time_ms=[round(float(x), 4) for x in times[::stride]],
                          voltage_mv={n: [round(float(x), 6) for x in np.array(v)[::stride]] for n, v in vectors.items()})
            return frames, traces
        def clear_recordings():
            h.v_time.resize(0)
            for vector in vectors.values():
                vector.resize(0)
        advance(MODEL_CONFIG["warmup_ms"])
        null, _ = sample(float(h.t))
        clear_recordings()
    emit(dict(status="ready", null_mv=null, time_ms=round(float(h.t), 4)))
    for line in sys.stdin:
        command = json.loads(line)
        if command == {"stop": True}:
            return
        currents = command.get("stimulus_pa")
        if not isinstance(currents, dict) or set(currents) != set(SENSORY):
            raise ValueError("Invalid live stimulus")
        if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 5 for x in currents.values()):
            raise ValueError("Invalid current")
        with contextlib.redirect_stdout(sys.stderr):
            for name, pulse in pulses.items():
                pulse.delay = float(h.t) + MODEL_CONFIG["pulse_delay_ms"]
                pulse.duration = MODEL_CONFIG["pulse_duration_ms"]
                pulse.amplitude = currents[name] / 1000  # NEURON nA; public mapping pA.
            advance(MODEL_CONFIG["episode_ms"])
            frame, traces = sample(float(h.t))
            clear_recordings()  # Clears stored samples, never neuron/synapse state.
        emit(dict(status="advanced", time_ms=round(float(h.t), 4), voltage_mv=frame, traces=traces))


if __name__ == "__main__":
    main()
