"""Pure feature, stimulus, decoder, and paper-risk functions; no networking."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, field

FORWARD = ("AVBL", "AVBR", "PVCL", "PVCR")
REVERSE = ("AVAL", "AVAR", "AVDL", "AVDR", "AVEL", "AVER")
RIM = ("RIML", "RIMR")
RIB = ("RIBL", "RIBR")
SENSORY = ("ASEL", "ASER", "AWAL", "AWAR", "AWCL", "AWCR", "ASHL", "ASHR")
OPTIONAL_READOUT = RIM + RIB
READOUT = FORWARD + REVERSE + SENSORY + OPTIONAL_READOUT
PROPRIOCEPTIVE = ("PVCL", "PVCR", "DVA")
INPUT_CELLS = SENSORY + PROPRIOCEPTIVE
SCENARIOS = ("trend", "reversal", "liquidity-shock")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


SENSORY_CALIBRATION = {
    "version": "synthetic-salt-gradient-v1",
    "status": "engineered-synthetic-calibration",
    "equation": "I_pA = span_pA * tanh(max(signed_feature, 0) / half_saturation)",
    "channels": {
        "ASEL": {"feature": "positive_return_z", "span_pa": 2.4, "half_saturation": 0.75},
        "ASER": {"feature": "negative_return_z", "span_pa": 2.4, "half_saturation": 0.75},
        "AWAL": {"feature": "positive_imbalance", "span_pa": 1.8, "half_saturation": 0.45},
        "AWAR": {"feature": "positive_imbalance", "span_pa": 1.8, "half_saturation": 0.45},
        "AWCL": {"feature": "positive_imbalance", "span_pa": 1.8, "half_saturation": 0.45},
        "AWCR": {"feature": "positive_imbalance", "span_pa": 1.8, "half_saturation": 0.45},
        "ASHL": {"feature": "danger", "span_pa": 3.2, "half_saturation": 0.35},
        "ASHR": {"feature": "danger", "span_pa": 3.2, "half_saturation": 0.35},
    },
    "anchors": {"return_z": [-3.0, 0.0, 3.0], "imbalance": [-1.0, 0.0, 1.0]},
}
CURRENT_LIMITS_PA = {name: spec["span_pa"] for name, spec in SENSORY_CALIBRATION["channels"].items()}
CURRENT_LIMITS_PA.update(PVCL=1.0, PVCR=1.0, DVA=1.0)

PLASTICITY = {
    "version": "ase-association-v1",
    "family": "ASE to AIA/AIY chemical synapses",
    "paths": ["ASEL->AIAL", "ASEL->AIYL", "ASEL->AIYR",
              "ASER->AIAL", "ASER->AIAR", "ASER->AIYL", "ASER->AIYR"],
    "gain_bounds": [0.25, 1.0],
    "depression_rate": 0.08,
    "recovery_rate": 0.025,
    "eligibility": "max calibrated ASEL/ASER current",
    "valence": "engineered dopamine proxy from AWA/AWC attraction minus ASH avoidance",
}

PROPRIOCEPTION = {
    "version": "paper-outcome-v1",
    "targets": list(PROPRIOCEPTIVE),
    "delay": "one neural episode",
    "mapping": "paper fill drives PVC; vetoed or unfilled intent drives DVA",
}

MODEL_CONFIG = {
    "parameter_set": "C1", "reader": "cect.readers.Cook2019HermReader",
    "reader_adapter": "wormbrain.cect_reader",
    "reader_cache_sha256": "98bdafffce1341d3443a83066a6225a977c8218c28c27d69e4bd465782bd4cc8",
    "dt_ms": 0.05, "episode_ms": 200, "warmup_ms": 300,
    "pulse_delay_ms": 20, "pulse_duration_ms": 140, "readout_ms": 40,
    "voltage_span_mv": 10.0, "seed": 1234,
    "global_offset_pa": 0.0, "muscles": False,
    "sensory_calibration_hash": digest(SENSORY_CALIBRATION),
    "plasticity_hash": digest(PLASTICITY),
    "proprioception_hash": digest(PROPRIOCEPTION),
}
POLICY = {
    "decoder_activation_floor": 0.08, "decoder_switch_margin": 0.06,
    "entry_notional": 25.0, "initial_cash": 1000.0, "fee_bps": 30,
    "slippage_bps": 50, "cooldown_ticks": 2, "min_liquidity": 25000.0,
    "max_impact_bps": 200, "max_daily_loss": 20.0,
}


def clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    if not math.isfinite(value):
        raise ValueError("Non-finite numeric input")
    return max(lower, min(upper, value))


def scenario(name: str) -> list[dict]:
    """Fictional price paths: no real token, wallet, holder, or timestamp."""
    if name not in SCENARIOS:
        raise ValueError("Unknown scenario")
    paths = {
        "trend": [1, 1.01, 1.03, 1.04, 1.07, 1.09, 1.08, 1.11, 1.12, 1.15],
        "reversal": [1, 1.02, 1.05, 1.08, 1.10, 1.08, 1.03, .99, .95, .92],
        "liquidity-shock": [1, 1.02, 1.04, 1.07, 1.08, 1.06, .90, .76, .65, .61],
    }
    return [dict(tick=i, seconds=i * 15, price=p,
                 flow=.65 if i < 5 or name == "trend" else -.70,
                 liquidity=8000.0 if name == "liquidity-shock" and i >= 6 else 100000.0,
                 price_impact_bps=900 if name == "liquidity-shock" and i >= 6 else 40,
                 fresh=True, eligible=True)
            for i, p in enumerate(paths[name])]


def validate_ticks(ticks: list[dict]) -> None:
    if not isinstance(ticks, list):
        raise ValueError("Observations must be a JSON array")
    if not 2 <= len(ticks) <= 24:
        raise ValueError("A replay must have 2–24 observations")
    for i, tick in enumerate(ticks):
        if not isinstance(tick, dict) or set(tick) != {"tick", "seconds", "price", "flow", "liquidity", "price_impact_bps", "fresh", "eligible"}:
            raise ValueError("Unexpected observation fields; identity metadata is not accepted")
        if tick.get("tick") != i or tick.get("seconds") != i * 15:
            raise ValueError("Ticks must be consecutive at 15-second intervals")
        for name in ("price", "flow", "liquidity", "price_impact_bps"):
            value = tick.get(name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError("Invalid market observation")
        if tick["price"] <= 0 or tick["liquidity"] < 0 or tick["price_impact_bps"] < 0 or abs(tick["flow"]) > 1:
            raise ValueError("Market observation outside allowed range")
        if type(tick.get("fresh")) is not bool or type(tick.get("eligible")) is not bool:
            raise ValueError("Missing boolean risk facts")


def features(ticks: list[dict], index: int) -> dict:
    """Use the prefix only. Prior returns set scale; no future observations."""
    past = ticks[:index + 1]
    now = past[-1]
    r = math.log(now["price"] / past[-2]["price"]) if index else 0.0
    previous = [math.log(b["price"] / a["price"]) for a, b in zip(past[:-2], past[1:-1])]
    median = statistics.median(previous) if previous else 0.0
    mad = statistics.median([abs(x - median) for x in previous]) if previous else 0.0
    z = clip((r - median) / max(1.4826 * mad, .01), -3, 3)
    liquidity_change = (now["liquidity"] / past[-2]["liquidity"] - 1) if index and past[-2]["liquidity"] else 0.0
    drawdown = 1 - now["price"] / max(t["price"] for t in past)
    return dict(return_15s=r, return_z=z, flow=now["flow"],
                liquidity_change=liquidity_change, drawdown=drawdown,
                price_impact_bps=now["price_impact_bps"], quality=1.0 if now["fresh"] else 0.0)


def calibrated_current(neuron: str, signed_feature: float, quality: float) -> float:
    """Map a dimensionless synthetic analogue onto a named cell's published pA curve."""
    spec = SENSORY_CALIBRATION["channels"][neuron]
    if not 0 <= quality <= 1:
        raise ValueError("Invalid input quality")
    return spec["span_pa"] * math.tanh(max(signed_feature, 0.0) / spec["half_saturation"]) * quality


def encode(frame: dict) -> dict[str, float]:
    """Calibrated synthetic salt-gradient analogue; still not a biological claim."""
    positive = .8 * max(frame["return_z"], 0) / 3 + .2 * max(frame["liquidity_change"], 0)
    negative = .8 * max(-frame["return_z"], 0) / 3 + .2 * max(-frame["liquidity_change"], 0)
    attraction = max(frame["flow"], 0)
    danger = clip(.5 * frame["drawdown"] / .2 + .3 * frame["price_impact_bps"] / 300 + .2 * max(-frame["liquidity_change"], 0))
    values = {"ASEL": positive, "ASER": negative,
              **{n: attraction for n in ("AWAL", "AWAR", "AWCL", "AWCR")},
              "ASHL": danger, "ASHR": danger}
    return {name: calibrated_current(name, value, frame["quality"]) for name, value in values.items()}


def neural_scores(voltages_mv: dict, null_mv: dict) -> dict:
    required = FORWARD + REVERSE
    activity = {n: clip((voltages_mv[n] - null_mv[n]) / MODEL_CONFIG["voltage_span_mv"], -1, 1) for n in required}
    for name in OPTIONAL_READOUT:
        if name in voltages_mv and name in null_mv:
            activity[name] = clip((voltages_mv[name] - null_mv[name]) / MODEL_CONFIG["voltage_span_mv"], -1, 1)
    f = max(0.0, statistics.mean(activity[n] for n in FORWARD))
    r = max(0.0, statistics.mean(activity[n] for n in REVERSE))
    rim = statistics.mean(activity[n] for n in RIM) if set(RIM).issubset(activity) else None
    rib = statistics.mean(activity[n] for n in RIB) if set(RIB).issubset(activity) else None
    forward_drive = clip(f + .20 * max(rib or 0.0, 0.0))
    reverse_drive = clip(r + .20 * max(rim or 0.0, 0.0))
    peak = max(forward_drive, reverse_drive)
    pause = clip((POLICY["decoder_activation_floor"] - peak) / POLICY["decoder_activation_floor"])
    vector = dict(forward=forward_drive, reverse=reverse_drive, pause=pause, rim=rim, rib=rib)
    return dict(forward=f, reverse=r, margin=f - r, vector=vector, activity=activity)


@dataclass
class CommandStateMachine:
    state: str = "PAUSE"

    def step(self, vector: dict) -> dict:
        forward, reverse, pause = (vector[name] for name in ("forward", "reverse", "pause"))
        for value in (forward, reverse, pause):
            clip(value)
        if max(forward, reverse) < POLICY["decoder_activation_floor"] or abs(forward - reverse) < POLICY["decoder_switch_margin"]:
            candidate = "PAUSE"
        else:
            candidate = "FORWARD" if forward > reverse else "REVERSE"
        previous = self.state
        self.state = candidate
        return dict(state=self.state, previous=previous, transitioned=self.state != previous,
                    vector={"forward": forward, "reverse": reverse, "pause": pause,
                            "rim": vector.get("rim"), "rib": vector.get("rib")})


@dataclass
class DopaminePlasticity:
    gain: float = 1.0

    def update(self, stimulus_pa: dict) -> dict:
        eligibility = max(stimulus_pa[n] / CURRENT_LIMITS_PA[n] for n in ("ASEL", "ASER"))
        attraction = statistics.mean(stimulus_pa[n] / CURRENT_LIMITS_PA[n] for n in ("AWAL", "AWAR", "AWCL", "AWCR"))
        avoidance = statistics.mean(stimulus_pa[n] / CURRENT_LIMITS_PA[n] for n in ("ASHL", "ASHR"))
        valence = clip(attraction - avoidance, -1, 1)
        dopamine_gate = clip((valence + 1.0) / 2.0)
        applied = self.gain
        depression = PLASTICITY["depression_rate"] * eligibility * (1.0 - dopamine_gate)
        recovery = PLASTICITY["recovery_rate"] * dopamine_gate * (1.0 - self.gain)
        self.gain = clip(self.gain + recovery - depression, *PLASTICITY["gain_bounds"])
        return dict(applied_gain=applied, next_gain=self.gain, eligibility=eligibility,
                    valence=valence, dopamine_gate=dopamine_gate)


def proprioceptive_feedback(outcome: dict) -> dict[str, float]:
    """Return bounded currents for the next episode; never an execution command."""
    values = {name: 0.0 for name in PROPRIOCEPTIVE}
    fill = outcome.get("fill")
    if fill and fill["side"] == "BUY":
        values.update(PVCL=.9, PVCR=.9, DVA=.15)
    elif fill and fill["side"] == "SELL":
        values["DVA"] = .9
    elif outcome.get("intent") != "HOLD":
        values["DVA"] = .6
    return values


@dataclass
class PaperEngine:
    """No wallet, RPC, transaction builder, or real-order capability."""
    cash: float = POLICY["initial_cash"]
    units: float = 0.0
    cooldown_until: int = -1
    halted: bool = False
    halt_reason: str = ""
    cost_basis: float = 0.0
    realized: float = 0.0
    rows: list[dict] = field(default_factory=list)
    decoder: CommandStateMachine = field(default_factory=CommandStateMachine)

    def step(self, tick: dict, scores: dict, *, kill: bool = False) -> dict:
        decoder = self.decoder.step(scores["vector"])
        intent = "ENTER" if not self.units and decoder["state"] == "FORWARD" else "EXIT" if self.units and decoder["state"] == "REVERSE" else "HOLD"
        equity = self.cash + self.units * tick["price"]
        if kill:
            self.halted, self.halt_reason = True, "KILL_SWITCH"
        if POLICY["initial_cash"] - equity >= POLICY["max_daily_loss"]:
            self.halted, self.halt_reason = True, "LOSS_LIMIT"
        reasons = []
        if not tick["fresh"]: reasons.append("STALE_DATA")
        if not tick["eligible"]: reasons.append("INELIGIBLE")
        if tick.get("liquidity_verified") is False: reasons.append("UNVERIFIED_LIQUIDITY")
        if tick.get("price_impact_verified") is False: reasons.append("UNVERIFIED_IMPACT")
        if tick["liquidity"] < POLICY["min_liquidity"]: reasons.append("LOW_LIQUIDITY")
        if tick["price_impact_bps"] > POLICY["max_impact_bps"]: reasons.append("PRICE_IMPACT")
        if self.halted: reasons.append(self.halt_reason)
        can_fill = (tick["fresh"] and tick["eligible"] and tick.get("liquidity_verified", True)
                    and tick.get("price_impact_verified", True)
                    and tick["liquidity"] >= POLICY["min_liquidity"]
                    and tick["price_impact_bps"] <= POLICY["max_impact_bps"])
        effective = intent
        risk = "ALLOW"
        if reasons:
            effective = "EXIT" if self.units else "HOLD"
            risk = "FORCE_EXIT" if self.units else "BLOCK"
        if not self.units and tick["tick"] < self.cooldown_until and intent == "ENTER":
            effective, risk = "HOLD", "BLOCK"
            reasons.append("COOLDOWN")
        fill = None
        if effective == "ENTER" and not self.units:
            amount = POLICY["entry_notional"]
            fee = amount * POLICY["fee_bps"] / 10000
            if self.cash >= amount + fee and can_fill:
                price = tick["price"] * (1 + (POLICY["slippage_bps"] + tick["price_impact_bps"]) / 10000)
                self.units = amount / price
                self.cost_basis = amount + fee
                self.cash -= self.cost_basis
                fill = dict(side="BUY", price=price, units=self.units, fee=fee, source="PAPER_EXECUTOR")
        elif effective == "EXIT" and self.units and can_fill:
            price = tick["price"] * (1 - (POLICY["slippage_bps"] + tick["price_impact_bps"]) / 10000)
            proceeds = self.units * price
            fee = proceeds * POLICY["fee_bps"] / 10000
            fill = dict(side="SELL", price=price, units=self.units, fee=fee, source="RISK_CAGE" if reasons else "PAPER_EXECUTOR")
            self.cash += proceeds - fee
            self.realized += proceeds - fee - self.cost_basis
            self.units, self.cost_basis = 0.0, 0.0
            self.cooldown_until = tick["tick"] + POLICY["cooldown_ticks"] + 1
        execution = "FILLED" if fill else "EXIT_UNFILLED" if effective == "EXIT" and self.units else "NO_ORDER"
        row = dict(decoder=decoder, intent=intent, risk=risk, reasons=reasons, execution=execution, fill=fill,
                   cash=self.cash, units=self.units, equity=self.cash + self.units * tick["price"],
                   realized_pnl=self.realized, position="HELD" if self.units else "FLAT")
        self.rows.append(row)
        return row
