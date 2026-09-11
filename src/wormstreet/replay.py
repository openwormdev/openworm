"""A replay is one continuous worm, one token, and an append-only audit chain."""
from __future__ import annotations
import tempfile
from pathlib import Path

from .brain import simulate
from .core import MODEL_CONFIG, POLICY, PaperEngine, digest, encode, features, neural_scores, scenario, validate_ticks


def run_replay(name: str, *, ticks: list[dict] | None = None) -> dict:
    observations = ticks if ticks is not None else scenario(name)
    validate_ticks(observations)
    feature_frames = [features(observations, i) for i in range(len(observations))]
    inputs = [encode(frame) for frame in feature_frames]
    with tempfile.TemporaryDirectory(prefix="wormstreet-") as folder:
        result = simulate(inputs, Path(folder))
    engine = PaperEngine()
    rows, previous = [], "genesis"
    for i, tick in enumerate(observations):
        scores = neural_scores(result["frames_mv"][i], result["null_mv"])
        outcome = engine.step(tick, scores)
        body = dict(tick=tick, features=feature_frames[i], stimulus_pa=inputs[i],
                    voltage_mv=result["frames_mv"][i], scores=scores, **outcome,
                    previous_hash=previous)
        previous = digest(body)
        rows.append(dict(body, event_hash=previous))
    report = dict(schema_version=1, scenario=name if ticks is None else "imported-replay",
                  market_source="synthetic" if ticks is None else "user-provided-unverified",
                  trading_mode="paper", token="SYNTH" if ticks is None else "REPLAY",
                  simulation_mode="real-c302", model=result["model"],
                  config=MODEL_CONFIG, policy=POLICY, null_mv=result["null_mv"],
                  traces=result["traces"], rows=rows, audit_root=previous,
                  claims=["No real orders", "Not a validated animal mind", "No evidence of profitability",
                          "Market-to-neuron map and financial decoder are engineered",
                          "No body physics or proprioceptive feedback"])
    report["report_hash"] = digest(report)
    return report
