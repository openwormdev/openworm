"""Generate a full c302 C1 network and execute its official simulator export."""
from __future__ import annotations

import contextlib
import importlib.metadata
import io
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .core import MODEL_CONFIG, READOUT, SENSORY, digest


def simulate(stimuli: list[dict[str, float]], folder: Path, *, backend: str = "neuron") -> dict:
    if shutil.which("java") is None:
        raise RuntimeError("Java is required for the c302 reference simulator")
    if backend not in {"neuron", "jneuroml"}:
        raise ValueError("Unknown simulation backend")
    if not 2 <= len(stimuli) <= 24:
        raise ValueError("Simulation must contain 2–24 sensory frames")
    for frame in stimuli:
        if set(frame) != set(SENSORY) or any(not math.isfinite(x) or not 0 <= x <= 5 for x in frame.values()):
            raise ValueError("Invalid sensory input")
    # Third-party generators print local paths. Capture, never publish them.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import c302
        import numpy as np
        from c302.parameters_C1 import ParameterisedModel
        from neuroml.writers import NeuroMLWriter
        from pyneuroml import pynml

        folder.mkdir(parents=True, exist_ok=True)
        duration = MODEL_CONFIG["warmup_ms"] + len(stimuli) * MODEL_CONFIG["episode_ms"]
        params = ParameterisedModel()
        params.set_bioparameter("unphysiological_offset_current", "0pA", "No hidden market stimulus", "0")
        doc = c302.generate("WormStreet", params,
                            data_reader=MODEL_CONFIG["reader"], cells=None,
                            cells_to_plot=[], cells_to_stimulate=[], muscles_to_include=[],
                            duration=duration, dt=MODEL_CONFIG["dt_ms"], seed=MODEL_CONFIG["seed"],
                            target_directory=str(folder), verbose=False)
        network = doc.networks[0]
        # Upstream adds optional donor labels. They are metadata, not physiology.
        for population in network.populations:
            population.properties[:] = [p for p in population.properties if p.tag != "OpenWormBackerAssignedName"]
        names = sorted(p.id for p in network.populations)
        if not set(READOUT).issubset(names):
            raise RuntimeError("Required biological neurons are absent from this reader")
        for i, frame in enumerate(stimuli):
            delay = MODEL_CONFIG["warmup_ms"] + i * MODEL_CONFIG["episode_ms"] + MODEL_CONFIG["pulse_delay_ms"]
            for neuron, amplitude in sorted(frame.items()):
                c302.add_new_input(doc, neuron, f"{delay}ms", f"{MODEL_CONFIG['pulse_duration_ms']}ms", f"{amplitude:.8f}pA", params)
        nml = folder / "WormStreet.net.nml"
        NeuroMLWriter.write(doc, str(nml))
        import xml.etree.ElementTree as ET
        lems_path = folder / "LEMS_WormStreet.xml"
        lems_tree = ET.parse(lems_path)
        # Record selected cells only; all generated neurons still participate.
        for sim in lems_tree.getroot().iter("Simulation"):
            for output in list(sim.findall("OutputFile")):
                if output.attrib.get("fileName") != "WormStreet.dat":
                    sim.remove(output)
                else:
                    for column in list(output):
                        if column.attrib.get("quantity", "").split("/")[0] not in READOUT:
                            output.remove(column)
        lems_tree.write(lems_path, encoding="utf-8", xml_declaration=True)
        jar = pynml.get_path_to_jnml_jar()
        # Direct argv avoids shell interpolation and guarantees a hard timeout.
        def checked(argv, timeout, env=None):
            try:
                completed = subprocess.run(argv, cwd=folder, capture_output=True, timeout=timeout, check=False, env=env)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Reference simulator exceeded its time limit") from exc
            if completed.returncode:
                raise RuntimeError("Reference simulation or compilation failed; check local runtime dependencies")
        java = ["java", "-Xmx1G", "-jar", jar, "LEMS_WormStreet.xml"]
        if backend == "jneuroml":
            checked(java + ["-nogui"], 900)
        else:
            compiler = Path(sys.executable).parent / "nrnivmodl"
            if not compiler.is_file() or not all(shutil.which(x) for x in ("gcc", "g++", "make")):
                raise RuntimeError("NEURON, GCC/G++, and Make are required")
            checked(java + ["-neuron", "-nogui"], 45)
            compiler_env = os.environ.copy()
            compiler_env.update(CC=shutil.which("gcc"), CXX=shutil.which("g++"))
            checked([str(compiler)], 120, env=compiler_env)
            checked([sys.executable, "LEMS_WormStreet_nrn.py"], 120)
        data = np.loadtxt(folder / "WormStreet.dat")
        if data.ndim != 2 or data.shape[1] != len(READOUT) + 1 or not np.isfinite(data).all():
            raise RuntimeError("Invalid or incomplete simulator traces")
        if data[-1, 0] * 1000 < duration - 2 * MODEL_CONFIG["dt_ms"]:
            raise RuntimeError("Simulation stopped before the requested horizon")
        # Resolve the actual LEMS column names; never assume sorted output order.
        root = ET.parse(folder / "LEMS_WormStreet.xml").getroot()
        columns = []
        for output in root.iter("OutputFile"):
            if output.attrib.get("fileName") == "WormStreet.dat":
                columns = [c.attrib["quantity"].split("/")[0] for c in output.findall("OutputColumn")]
        if set(columns) != set(READOUT):
            raise RuntimeError("NeuroML output columns disagree with model populations")
        times = data[:, 0] * 1000
        lookup = {n: columns.index(n) + 1 for n in READOUT}
        warmup = MODEL_CONFIG["warmup_ms"]
        window = MODEL_CONFIG["readout_ms"]
        episode = MODEL_CONFIG["episode_ms"]
        null_mask = (times >= warmup - window) & (times < warmup)
        if not null_mask.any():
            raise RuntimeError("Missing pre-stimulus baseline")
        null = {n: float(np.mean(data[null_mask, col]) * 1000) for n, col in lookup.items()}
        frames = []
        for i in range(len(stimuli)):
            end = warmup + (i + 1) * episode
            mask = (times >= end - window) & (times < end)
            if not mask.any():
                raise RuntimeError("Missing neural readout window")
            frames.append({n: float(np.mean(data[mask, col]) * 1000) for n, col in lookup.items()})
        stride = max(1, len(times) // 500)
        traces = {n: [round(float(x) * 1000, 6) for x in data[::stride, col]] for n, col in lookup.items()}
        projections = len(network.projections) + len(network.electrical_projections) + len(network.continuous_projections)
        identity = {k: importlib.metadata.version(k) for k in ("c302", "cect", "pyNeuroML", "libNeuroML", "neuron")}
        identity.update(parameter_set="C1", reader=MODEL_CONFIG["reader"], neurons=len(names),
                        projections=projections, population_hash=digest(names),
                        config_hash=digest(MODEL_CONFIG), kind="c302-reference",
                        runtime="NEURON via jNeuroML exporter" if backend == "neuron" else "jNeuroML interpreter",
                        backend=backend, continuity="continuous-within-token-replay")
        # Identity for all generated equations and topology, with host paths excluded.
        import hashlib
        identity["network_sha256"] = hashlib.sha256(nml.read_bytes()).hexdigest()
        identity["jar_sha256"] = hashlib.sha256(Path(jar).read_bytes()).hexdigest()
        identity["cell_components_sha256"] = hashlib.sha256((folder / "cell_C.xml").read_bytes()).hexdigest()
    return dict(model=identity, null_mv=null, frames_mv=frames,
                traces=dict(time_ms=[round(float(x), 4) for x in times[::stride]], voltage_mv=traces))
