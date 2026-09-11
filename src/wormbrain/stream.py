"""Prepare once, advance a persistent official NEURON model for each input."""
from __future__ import annotations
import json
import os
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .brain import simulate
from .core import PLASTICITY, PROPRIOCEPTIVE, SENSORY


class LiveBrain:
    def __init__(self):
        self.folder = None
        self.process = None
        self.buffer = b""

    def __enter__(self):
        self.folder = tempfile.TemporaryDirectory(prefix="wormbrain-live-")
        try:
            identity = simulate([{n: 0.0 for n in SENSORY} for _ in range(2)], Path(self.folder.name), _prepare_stream=True)
            self.model = identity["model"]
            self.process = subprocess.Popen([sys.executable, "-u", "-m", "wormbrain.stream_runtime"],
                                            cwd=self.folder.name, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, bufsize=0)
            ready = self._read()
            if ready.get("status") != "ready":
                raise RuntimeError("Live brain did not initialize")
            self.null_mv = ready["null_mv"]
            self.recorded_cells = ready["recorded_cells"]
            self.plasticity_targets = ready["plasticity_targets"]
            if set(self.plasticity_targets) != set(PLASTICITY["paths"]):
                raise RuntimeError("Live brain did not expose every pinned plasticity target")
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def _read(self):
        deadline = time.monotonic() + 40
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                while b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    if line.startswith(b"WORM_JSON "):
                        return json.loads(line[len(b"WORM_JSON "):])
                if not selector.select(max(0, deadline - time.monotonic())):
                    break
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    break
                self.buffer += chunk
                if len(self.buffer) > 2_000_000:
                    break
        raise RuntimeError("Live simulator failed or timed out")

    def step(self, currents, *, feedback_pa=None, plasticity_gain=1.0):
        feedback_pa = feedback_pa or {name: 0.0 for name in PROPRIOCEPTIVE}
        command = dict(stimulus_pa=currents, feedback_pa=feedback_pa, plasticity_gain=plasticity_gain)
        self.process.stdin.write((json.dumps(command, allow_nan=False) + "\n").encode())
        self.process.stdin.flush()
        result = self._read()
        if result.get("status") != "advanced":
            raise RuntimeError("Live simulator did not advance")
        if result.get("plasticity_applied_gain") != plasticity_gain:
            raise RuntimeError("Live simulator did not apply the requested plasticity gain")
        return result

    def __exit__(self, *args):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
        if self.folder:
            self.folder.cleanup()
