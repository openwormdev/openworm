"""Isolated persistent NEURON process. Only stimuli change between advances."""
from __future__ import annotations
import contextlib
import importlib.util
import json
import math
import sys
from pathlib import Path

from .core import CURRENT_LIMITS_PA, INPUT_CELLS, MODEL_CONFIG, PLASTICITY, PROPRIOCEPTIVE, READOUT, SENSORY


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
        vectors = {n: getattr(h, f"v_{n}_v_neurons_v") for n in READOUT if hasattr(h, f"v_{n}_v_neurons_v")}
        pulses = {n: getattr(h, f"Input_{n}_stim_{n}_1_0") for n in INPUT_CELLS}
        plastic_synapses = []
        for path in PLASTICITY["paths"]:
            component = f"{path.replace('->', '_to_')}_exc_syn"
            instances = h.List(component)
            if int(instances.count()) < 1:
                raise RuntimeError("Plastic synapse instance missing from generated model")
            for index in range(int(instances.count())):
                synapse = instances.o(index)
                if not hasattr(synapse, "conductance"):
                    raise RuntimeError("Plastic synapse conductance is not mutable")
                plastic_synapses.append((path, synapse, float(synapse.conductance)))
        def apply_plasticity(gain):
            if type(gain) not in (int, float) or not math.isfinite(gain) or not PLASTICITY["gain_bounds"][0] <= gain <= PLASTICITY["gain_bounds"][1]:
                raise ValueError("Invalid plasticity gain")
            for _, synapse, baseline in plastic_synapses:
                synapse.conductance = baseline * gain
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
    emit(dict(status="ready", null_mv=null, time_ms=round(float(h.t), 4),
              recorded_cells=list(vectors), plasticity_targets=sorted({path for path, _, _ in plastic_synapses})))
    for line in sys.stdin:
        command = json.loads(line)
        if command == {"stop": True}:
            return
        currents = command.get("stimulus_pa")
        if not isinstance(currents, dict) or set(currents) != set(SENSORY):
            raise ValueError("Invalid live stimulus")
        feedback = command.get("feedback_pa")
        if not isinstance(feedback, dict) or set(feedback) != set(PROPRIOCEPTIVE):
            raise ValueError("Invalid proprioceptive feedback")
        all_currents = {**currents, **feedback}
        if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= CURRENT_LIMITS_PA[name] for name, value in all_currents.items()):
            raise ValueError("Invalid current")
        with contextlib.redirect_stdout(sys.stderr):
            apply_plasticity(command.get("plasticity_gain"))
            for name, pulse in pulses.items():
                pulse.delay = float(h.t) + MODEL_CONFIG["pulse_delay_ms"]
                pulse.duration = MODEL_CONFIG["pulse_duration_ms"]
                pulse.amplitude = all_currents[name] / 1000  # NEURON nA; public mapping pA.
            advance(MODEL_CONFIG["episode_ms"])
            frame, traces = sample(float(h.t))
            clear_recordings()  # Clears stored samples, never neuron/synapse state.
        emit(dict(status="advanced", time_ms=round(float(h.t), 4), voltage_mv=frame, traces=traces,
                  plasticity_applied_gain=command["plasticity_gain"]))


if __name__ == "__main__":
    main()
