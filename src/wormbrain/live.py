"""Bounded live observation session, isolated from the paper replay executor."""
from __future__ import annotations
import copy
import threading
import time

from .core import MODEL_CONFIG, SENSORY, digest, neural_scores
from .pons import FeedError, LIVE_ENCODING, POLL_SECONDS, SOURCE, TradeFeed, fetch_trades
from .stream import LiveBrain


class LiveMonitor:
    def __init__(self, *, fetcher=fetch_trades, brain_factory=LiveBrain):
        self.fetcher = fetcher
        self.brain_factory = brain_factory
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.state = dict(schema_version=1, kind="wormbrain-live-observer", status="idle",
                          source=SOURCE, encoding=LIVE_ENCODING, trading_mode="observation-only", live_execution=False,
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
                              session_started_at=int(time.time()), requested_seconds=seconds)
        self.thread = threading.Thread(target=self._run, args=(seconds,), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            if self.active:
                self.state["status"] = "stopping"

    def _run(self, seconds):
        feed = TradeFeed()
        previous = "genesis"
        try:
            with self.brain_factory() as brain:
                deadline = time.monotonic() + seconds
                with self.lock:
                    self.state.update(status="connecting", model=brain.model, config=MODEL_CONFIG,
                                      null_mv=brain.null_mv, ready_at=int(time.time()))
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
                    neural = brain.step(currents)
                    scores = neural_scores(neural["voltage_mv"], brain.null_mv)
                    body = dict(market=summary, stimulus_pa=currents, time_ms=neural["time_ms"],
                                voltage_mv=neural["voltage_mv"], scores=scores, traces=neural["traces"],
                                previous_hash=previous, execution="DISABLED_OBSERVER")
                    previous = digest(body)
                    row = dict(body, event_hash=previous)
                    with self.lock:
                        self.state["frames"] = (self.state["frames"] + [row])[-240:]
                        self.state.update(status="source-unavailable" if error else "observing", error=error,
                                          audit_root=previous, total_observed_events=feed.total_events,
                                          updated_at=int(time.time()))
                        self.state["total_stimulated_events"] += summary["stimulated_events"]
                    remaining = min(POLL_SECONDS - (time.monotonic() - begin), deadline - time.monotonic())
                    if remaining > 0:
                        self.stop_event.wait(remaining)
        except Exception:
            with self.lock:
                self.state.update(status="failed", error="Live model failed. Check Java and the native compiler locally.")
            return
        with self.lock:
            self.state["status"] = "stopped"
            self.state["stopped_at"] = int(time.time())


monitor = LiveMonitor()
