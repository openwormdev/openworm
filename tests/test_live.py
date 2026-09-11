import json
import time
import unittest

from wormbrain.core import PLASTICITY, READOUT
from wormbrain.live import LiveMonitor, sanitize_public_recording


def event():
    tx = "0x" + "b" * 64
    return dict(id=f"4663:10:{tx}:0", transactionHash=tx, blockNumber=10,
                timestamp=int(time.time()), side="buy", venue="pool",
                tokenAmount=str(10 * 10**18), quoteAmount=str(2 * 10**18))


class FakeBrain:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.model = {"kind": "c302-reference", "neurons": 300, "reader": "cect.readers.Cook2019HermReader"}
        self.null_mv = {name: -50.0 for name in READOUT}
        self.recorded_cells = list(READOUT)
        self.plasticity_targets = list(PLASTICITY["paths"])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def step(self, currents, *, feedback_pa, plasticity_gain):
        self.stop_event.set()
        voltage = {name: (-45.0 if name in {"AVBL", "AVBR", "PVCL", "PVCR"} else -50.0) for name in READOUT}
        return dict(time_ms=500.0, voltage_mv=voltage,
                    traces={"time_ms": [400.0, 500.0], "voltage_mv": {name: [-50.0, value] for name, value in voltage.items()}},
                    plasticity_applied_gain=plasticity_gain)


class LiveTests(unittest.TestCase):
    def test_live_frame_closes_paper_loop_without_absolute_session_time(self):
        monitor = LiveMonitor(fetcher=lambda: [event()], brain_factory=lambda: FakeBrain(monitor.stop_event))
        monitor._run(60)
        snapshot = monitor.snapshot()
        self.assertEqual(snapshot["trading_mode"], "paper")
        self.assertEqual(snapshot["status"], "stopped")
        self.assertEqual(len(snapshot["frames"]), 1)
        frame = snapshot["frames"][0]
        self.assertEqual(frame["decoder"]["state"], "FORWARD")
        self.assertEqual(frame["risk"], "BLOCK")
        self.assertIn("UNVERIFIED_LIQUIDITY", frame["reasons"])
        self.assertGreater(frame["next_feedback_pa"]["DVA"], 0)
        self.assertGreaterEqual(frame["plasticity"]["next_gain"], .25)
        raw = json.dumps(snapshot)
        for forbidden in ("session_started_at", "ready_at", "updated_at", "stopped_at", "observed_at"):
            self.assertNotIn(forbidden, raw)

    def test_public_recording_removes_event_clock_and_rebuilds_chain(self):
        monitor = LiveMonitor(fetcher=lambda: [event()], brain_factory=lambda: FakeBrain(monitor.stop_event))
        monitor._run(60)
        raw = monitor.snapshot()
        raw["frames"].append(copy := json.loads(json.dumps(raw["frames"][0])))
        copy["paper_tick"]["tick"] = 1
        copy["paper_tick"]["seconds"] = 15
        public = sanitize_public_recording(raw)
        self.assertEqual(public["frames"][0]["previous_hash"], "genesis")
        self.assertEqual(public["frames"][1]["previous_hash"], public["frames"][0]["event_hash"])
        self.assertEqual(public["audit_root"], public["frames"][1]["event_hash"])
        self.assertNotIn("latest_trade_at", json.dumps(public))


if __name__ == "__main__":
    unittest.main()
