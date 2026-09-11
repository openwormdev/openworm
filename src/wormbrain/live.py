"""Bounded live observation session, isolated from the paper replay executor."""
from __future__ import annotations
import copy
import threading
import time

from .core import (MODEL_CONFIG, PLASTICITY, POLICY, PROPRIOCEPTION, PROPRIOCEPTIVE,
                   READOUT, SENSORY, SENSORY_CALIBRATION, DopaminePlasticity, PaperEngine,
                   digest, neural_scores, proprioceptive_feedback)
from .pons import FeedError, LIVE_ENCODING, POLL_SECONDS, SOURCE, TradeFeed, fetch_trades
from .stream import LiveBrain


def sanitize_public_recording(recording: dict) -> dict:
    """Remove wall clocks and rebuild the audit chain for publication."""
    if (recording.get("schema_version") != 2
            or recording.get("kind") != "wormbrain-live-observer"
            or recording.get("trading_mode") != "paper"
            or recording.get("live_execution") is not False):
        raise ValueError("Not a supported live observer recording")
    frames = recording.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("A public continuous recording needs at least two frames")
    public = copy.deepcopy(recording)
    previous = "genesis"
    for frame in public["frames"]:
        frame.pop("event_hash", None)
        frame.pop("previous_hash", None)
        frame.get("market", {}).pop("latest_trade_at", None)
        if set(frame.get("stimulus_pa", {})) != set(SENSORY):
            raise ValueError("Recording has incomplete sensory currents")
        required = set(READOUT)
        if not required.issubset(public.get("recorded_cells", ())) or not required.issubset(frame.get("voltage_mv", {})):
            raise ValueError("Recording has incomplete public voltages")
        frame["previous_hash"] = previous
        previous = digest(frame)
        frame["event_hash"] = previous
    public.update(status="stopped", error=None, audit_root=previous,
                  recording={"kind": "continuous-token-observer",
                             "clock": "relative tick and biological model time",
                             "privacy": "absolute polling and market-event times removed"})
    return public


class LiveMonitor:
    def __init__(self, *, fetcher=fetch_trades, brain_factory=LiveBrain):
        self.fetcher = fetcher
        self.brain_factory = brain_factory
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.state = dict(schema_version=2, kind="wormbrain-live-observer", status="idle",
                          source=SOURCE, encoding=LIVE_ENCODING, trading_mode="paper", live_execution=False,
                          policy=POLICY, calibration=SENSORY_CALIBRATION,
                          plasticity=PLASTICITY, proprioception=PROPRIOCEPTION,
                          frames=[], total_observed_events=0, total_stimulated_events=0,
                          audit_root="genesis", error=None)

    @property
    def active(self):
        return bool(self.thread and self.thread.is_alive())

    def snapshot(self, *, history=True):
        with self.lock:
            return copy.deepcopy({**self.state, "frames": self.state["frames"] if history else self.state["frames"][-1:]})

    def start(self, *, seconds=3600):
        if type(seconds) is not int or not 1 <= seconds <= 86400:
            raise ValueError("Session must be 1–86400 seconds")
        if self.active:
            raise ValueError("Live observation is already running")
        self.stop_event.clear()
        with self.lock:
            self.state.update(status="preparing-brain", frames=[], total_observed_events=0,
                              total_stimulated_events=0, audit_root="genesis", error=None,
                              session_elapsed_seconds=0, requested_seconds=seconds)
        self.thread = threading.Thread(target=self._run, args=(seconds,), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            if self.active:
                self.state["status"] = "stopping"

    def _run(self, seconds):
        feed = TradeFeed()
        engine = PaperEngine()
        plasticity = DopaminePlasticity()
        feedback = {name: 0.0 for name in PROPRIOCEPTIVE}
        fallback_price = 1.0
        tick_index = 0
        previous = "genesis"
        try:
            with self.brain_factory() as brain:
                deadline = time.monotonic() + seconds
                with self.lock:
                    self.state.update(status="connecting", model=brain.model, config=MODEL_CONFIG,
                                      null_mv=brain.null_mv, recorded_cells=brain.recorded_cells,
                                      plasticity_targets=brain.plasticity_targets)
                while not self.stop_event.is_set() and time.monotonic() < deadline:
                    begin = time.monotonic()
                    error = None
                    try:
                        observations = self.fetcher()
                        summary, currents = feed.ingest(observations)
                    except FeedError as exc:
                        summary = dict(observed_at=int(time.time()), new_events=0, stimulated_events=0,
                                       total_events=feed.total_events, feed_status="unavailable", coverage="unknown",
                                       latest_trade_at=feed.latest_timestamp, gap_count=feed.gap_count)
                        currents = {n: 0.0 for n in SENSORY}
                        error = str(exc)
                    if self.stop_event.is_set():
                        break
                    # Even during an outage the same network advances with zero external current.
                    applied_feedback = feedback
                    neural = brain.step(currents, feedback_pa=applied_feedback, plasticity_gain=plasticity.gain)
                    scores = neural_scores(neural["voltage_mv"], brain.null_mv)
                    if summary.get("price_quote"):
                        fallback_price = summary["price_quote"]
                    paper_tick = dict(tick=tick_index, seconds=tick_index * POLL_SECONDS,
                                      price=fallback_price, flow=summary.get("flow", 0.0),
                                      liquidity=0.0, price_impact_bps=0.0,
                                      fresh=bool(summary.get("stimulated_events")), eligible=True,
                                      liquidity_verified=False, price_impact_verified=False)
                    outcome = engine.step(paper_tick, scores)
                    plasticity_frame = plasticity.update(currents)
                    feedback = proprioceptive_feedback(outcome)
                    summary.pop("observed_at", None)
                    body = dict(market=summary, stimulus_pa=currents, time_ms=neural["time_ms"],
                                voltage_mv=neural["voltage_mv"], scores=scores, traces=neural["traces"],
                                paper_tick=paper_tick, plasticity=plasticity_frame,
                                feedback_pa=applied_feedback, next_feedback_pa=feedback,
                                previous_hash=previous, **outcome)
                    previous = digest(body)
                    row = dict(body, event_hash=previous)
                    with self.lock:
                        self.state["frames"] = (self.state["frames"] + [row])[-240:]
                        self.state.update(status="source-unavailable" if error else "observing", error=error,
                                          audit_root=previous, total_observed_events=feed.total_events,
                                          session_elapsed_seconds=tick_index * POLL_SECONDS)
                        self.state["total_stimulated_events"] += summary["stimulated_events"]
                    tick_index += 1
                    remaining = min(POLL_SECONDS - (time.monotonic() - begin), deadline - time.monotonic())
                    if remaining > 0:
                        self.stop_event.wait(remaining)
        except Exception:
            with self.lock:
                self.state.update(status="failed", error="Live model failed. Check Java and the native compiler locally.")
            return
        with self.lock:
            self.state["status"] = "stopped"


monitor = LiveMonitor()
