"""Pure feature, stimulus, decoder, and paper-risk functions; no networking."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, field

FORWARD = ("AVBL", "AVBR", "PVCL", "PVCR")
REVERSE = ("AVAL", "AVAR", "AVDL", "AVDR", "AVEL", "AVER")
SENSORY = ("ASEL", "ASER", "AWAL", "AWAR", "AWCL", "AWCR", "ASHL", "ASHR")
READOUT = FORWARD + REVERSE + SENSORY
SCENARIOS = ("trend", "reversal", "liquidity-shock")
MODEL_CONFIG = {
    "parameter_set": "C1", "reader": "cect.readers.SpreadsheetDataReader",
    "dt_ms": 0.05, "episode_ms": 200, "warmup_ms": 300,
    "pulse_delay_ms": 20, "pulse_duration_ms": 140, "readout_ms": 40,
    "max_current_pa": 5.0, "voltage_span_mv": 10.0, "seed": 1234,
    "global_offset_pa": 0.0, "muscles": False,
}
POLICY = {
    "enter_margin": 0.20, "exit_margin": -0.10, "entry_confirmations": 2,
    "entry_notional": 25.0, "initial_cash": 1000.0, "fee_bps": 30,
    "slippage_bps": 50, "cooldown_ticks": 2, "min_liquidity": 25000.0,
    "max_impact_bps": 200, "max_daily_loss": 20.0,
}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


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


def encode(frame: dict) -> dict[str, float]:
    """Experimental, frozen market-to-sensory map; NOT a biological claim."""
    positive = clip(.8 * max(frame["return_z"], 0) / 3 + .2 * max(frame["liquidity_change"], 0))
    negative = clip(.8 * max(-frame["return_z"], 0) / 3 + .2 * max(-frame["liquidity_change"], 0))
    attraction = clip(frame["flow"])
    danger = clip(.5 * frame["drawdown"] / .2 + .3 * frame["price_impact_bps"] / 300 + .2 * max(-frame["liquidity_change"], 0))
    scale = MODEL_CONFIG["max_current_pa"] * frame["quality"]
    return {"ASEL": positive * scale, "ASER": negative * scale,
            **{n: attraction * scale for n in ("AWAL", "AWAR", "AWCL", "AWCR")},
            "ASHL": danger * scale, "ASHR": danger * scale}


def neural_scores(voltages_mv: dict, null_mv: dict) -> dict:
    activity = {n: clip((voltages_mv[n] - null_mv[n]) / MODEL_CONFIG["voltage_span_mv"]) for n in FORWARD + REVERSE}
    f = statistics.mean(activity[n] for n in FORWARD)
    r = statistics.mean(activity[n] for n in REVERSE)
    return dict(forward=f, reverse=r, margin=f - r, activity=activity)


@dataclass
class PaperEngine:
    """No wallet, RPC, transaction builder, or real-order capability."""
    cash: float = POLICY["initial_cash"]
    units: float = 0.0
    streak: int = 0
    cooldown_until: int = -1
    halted: bool = False
    halt_reason: str = ""
    cost_basis: float = 0.0
    realized: float = 0.0
    rows: list[dict] = field(default_factory=list)

    def step(self, tick: dict, scores: dict, *, kill: bool = False) -> dict:
        margin = scores["margin"]
        clip(margin, -1, 1)
        self.streak = self.streak + 1 if margin >= POLICY["enter_margin"] else 0
        intent = "EXIT" if self.units and margin <= POLICY["exit_margin"] else "HOLD"
        if not self.units and self.streak >= POLICY["entry_confirmations"]:
            intent = "ENTER"
        equity = self.cash + self.units * tick["price"]
        if kill:
            self.halted, self.halt_reason = True, "KILL_SWITCH"
        if POLICY["initial_cash"] - equity >= POLICY["max_daily_loss"]:
            self.halted, self.halt_reason = True, "LOSS_LIMIT"
        reasons = []
        if not tick["fresh"]: reasons.append("STALE_DATA")
        if not tick["eligible"]: reasons.append("INELIGIBLE")
        if tick["liquidity"] < POLICY["min_liquidity"]: reasons.append("LOW_LIQUIDITY")
        if tick["price_impact_bps"] > POLICY["max_impact_bps"]: reasons.append("PRICE_IMPACT")
        if self.halted: reasons.append(self.halt_reason)
        can_fill = tick["fresh"] and tick["liquidity"] >= POLICY["min_liquidity"] and tick["price_impact_bps"] <= POLICY["max_impact_bps"]
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
                self.streak = 0
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
            self.streak = 0
        execution = "FILLED" if fill else "EXIT_UNFILLED" if effective == "EXIT" and self.units else "NO_ORDER"
        row = dict(intent=intent, risk=risk, reasons=reasons, execution=execution, fill=fill,
                   cash=self.cash, units=self.units, equity=self.cash + self.units * tick["price"],
                   realized_pnl=self.realized, position="HELD" if self.units else "FLAT")
        self.rows.append(row)
        return row
