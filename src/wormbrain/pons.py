"""Read-only Pons v2 trade observations; wallet/account fields never retained."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass

from .core import clip, digest

TOKEN = "0x2703295342c5914e0292adfdb612618ce24105d1"
QUOTE = "0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3"
TRADE_URL = f"https://www.ponsfamily.com/api/pons-v2-market/{TOKEN}/trades"
SOURCE = dict(provider="pons-public-indexer", chain_id=4663, token=TOKEN,
              symbol="WORMBRAIN", quote_token=QUOTE, quote_symbol="GOOGL",
              token_decimals=18, quote_decimals=18, receipt_verification=False,
              coverage="Recent indexed events only; not a complete chain history")
POLL_SECONDS = 15
MAX_AGE_SECONDS = 60
LIVE_ENCODING = dict(version="pons-observation-v1", max_current_pa=5.0,
                     gradient_weight=.7, imbalance_weight=.3,
                     drawdown_weight=.6, sell_pressure_weight=.4,
                     description="Engineered observed-price and quote-volume map; no biological calibration")


def live_encode(frame: dict, buy_share: float) -> dict:
    scale = 5.0 * frame["quality"]
    buy_pressure, sell_pressure = max(frame["flow"], 0), max(-frame["flow"], 0)
    up = clip(.7 * max(frame["return_z"], 0) / 3 + .3 * buy_pressure)
    down = clip(.7 * max(-frame["return_z"], 0) / 3 + .3 * sell_pressure)
    danger = clip(.6 * frame["drawdown"] / .2 + .4 * sell_pressure)
    return {"ASEL": up * scale, "ASER": down * scale,
            **{n: clip(buy_share) * scale for n in ("AWAL", "AWAR", "AWCL", "AWCR")},
            "ASHL": danger * scale, "ASHR": danger * scale}


class FeedError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise FeedError("Trade source redirected; monitoring paused")


def fetch_trades() -> list[dict]:
    # The origin and token are fixed. No arbitrary URLs, account lookups or keys.
    request = urllib.request.Request(TRADE_URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise FeedError("Trade source response is too large")
        value = json.loads(raw)
        rows = value.get("trades") if isinstance(value, dict) else None
        if not isinstance(rows, list) or len(rows) > 500:
            raise FeedError("Unexpected trade source response")
        return rows
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise FeedError("Trade source unavailable; no invented activity supplied") from exc


@dataclass(frozen=True)
class Trade:
    event_id: str
    block: int
    log_index: int
    timestamp: int
    side: str
    venue: str
    token_amount: float
    quote_amount: float


def parse_trade(row: dict, now: float) -> Trade:
    if not isinstance(row, dict):
        raise FeedError("Invalid trade record")
    event = row.get("id", "")
    if not isinstance(event, str):
        raise FeedError("Missing event identity")
    match = re.fullmatch(r"4663:(\d+):(0x[0-9a-fA-F]{64}):(\d+)", event)
    transaction = row.get("transactionHash")
    if not match or not isinstance(transaction, str) or transaction.lower() != match[2].lower():
        raise FeedError("Invalid event identity")
    block, index = int(match[1]), int(match[3])
    stamp = row.get("timestamp")
    if type(row.get("blockNumber")) is not int or row["blockNumber"] != block or block <= 0 or index > 1_000_000:
        raise FeedError("Invalid event block")
    if type(stamp) is not int or not 0 < stamp <= now + 10:
        raise FeedError("Invalid or future trade timestamp")
    if row.get("side") not in {"buy", "sell"} or row.get("venue") not in {"curve", "pool"}:
        raise FeedError("Unknown trade side or venue")
    amounts = []
    for key in ("tokenAmount", "quoteAmount"):
        text = row.get(key)
        if not isinstance(text, str) or not re.fullmatch(r"[0-9]{1,78}", text):
            raise FeedError("Invalid integer trade amount")
        integer = int(text)
        if not 0 < integer < 2**256:
            raise FeedError("Trade amount outside uint256 range")
        amounts.append(integer / 10**18)
    # A transaction can emit several swaps. Include the log index in the key.
    key = f"4663:{block}:{match[2].lower()}:{index}"
    return Trade(hashlib.sha256(key.encode()).hexdigest(), block, index, stamp,
                 row["side"], row["venue"], *amounts)


def public_market_snapshot(rows: list[dict], *, now: float | None = None) -> dict:
    """Return the fixed token's aggregate public window without account or transaction data."""
    now = time.time() if now is None else now
    trades = sorted((parse_trade(row, now) for row in rows), key=lambda trade: (trade.block, trade.log_index))
    unique = {}
    for trade in trades:
        previous = unique.get(trade.event_id)
        if previous is not None and previous != trade:
            raise FeedError("Conflicting source events")
        unique[trade.event_id] = trade
    trades = sorted(unique.values(), key=lambda trade: (trade.block, trade.log_index))
    latest = trades[-1] if trades else None
    return dict(
        schema_version=1,
        kind="wormbrain-token-market",
        status="connected",
        source=dict(provider="pons-public-indexer", token=TOKEN, chain_id=4663,
                    quote_symbol="GOOGL", coverage="recent-indexed-window"),
        recent=dict(events=len(trades),
                    buy_events=sum(trade.side == "buy" for trade in trades),
                    sell_events=sum(trade.side == "sell" for trade in trades),
                    price_quote=(latest.quote_amount / latest.token_amount) if latest else None,
                    latest_trade_at=latest.timestamp if latest else None,
                    latest_block=latest.block if latest else None),
    )


class TradeFeed:
    def __init__(self):
        self.seen = OrderedDict()
        self.latest_id = None
        self.high_water = (-1, -1)
        self.prices = []
        self.total_events = 0
        self.gap_count = 0
        self.latest_timestamp = None

    def ingest(self, rows: list[dict], *, now: float | None = None) -> tuple[dict, dict]:
        now = time.time() if now is None else now
        trades = sorted((parse_trade(x, now) for x in rows), key=lambda t: (t.block, t.log_index))
        by_id = {}
        for trade in trades:
            if trade.event_id in by_id and by_id[trade.event_id] != trade:
                raise FeedError("Conflicting source events; monitoring paused")
            by_id[trade.event_id] = trade
            if trade.event_id in self.seen and self.seen[trade.event_id] != trade:
                raise FeedError("Source event changed; restart the session for a new baseline")
        initial = self.latest_id is None
        gap = bool(trades and self.latest_id and self.latest_id not in by_id)
        late = [t for t in by_id.values() if t.event_id not in self.seen and (t.block, t.log_index) <= self.high_water]
        new = [t for t in by_id.values() if t.event_id not in self.seen and (t.block, t.log_index) > self.high_water]
        # Commit deduplication state only after the whole response validates.
        for trade in by_id.values():
            self.seen[trade.event_id] = trade
        while len(self.seen) > 10000:
            self.seen.popitem(last=False)
        if trades:
            newest = trades[-1]
            if (newest.block, newest.log_index) >= self.high_water:
                self.high_water = (newest.block, newest.log_index)
                self.latest_id = newest.event_id
            self.latest_timestamp = max(t.timestamp for t in trades)
        if gap:
            self.gap_count += 1
        self.total_events += len(new)
        fresh = [t for t in new if now - t.timestamp <= MAX_AGE_SECONDS]
        buys = sum(t.quote_amount for t in fresh if t.side == "buy")
        sells = sum(t.quote_amount for t in fresh if t.side == "sell")
        volume = buys + sells
        flow = (buys - sells) / volume if volume else 0.0
        price = self.prices[-1] if self.prices else None
        frame = dict(return_z=0.0, liquidity_change=0.0, flow=flow, drawdown=0.0,
                     price_impact_bps=0.0, quality=1.0 if fresh else 0.0)
        if fresh:
            price = fresh[-1].quote_amount / fresh[-1].token_amount
            previous = self.prices[-1] if self.prices else price
            returns = [math.log(b / a) for a, b in zip(self.prices, self.prices[1:])]
            median = statistics.median(returns) if returns else 0.0
            mad = statistics.median(abs(r - median) for r in returns) if returns else 0.0
            frame["return_z"] = clip((math.log(price / previous) - median) / max(1.4826 * mad, .01), -3, 3)
            frame["drawdown"] = 1 - price / max([price] + self.prices)
            self.prices = (self.prices + [price])[-64:]
        currents = live_encode(frame, buys / volume if volume else 0.0)
        summary = dict(observed_at=int(now), new_events=len(new), stimulated_events=len(fresh),
                       total_events=self.total_events, buy_events=sum(t.side == "buy" for t in fresh),
                       sell_events=sum(t.side == "sell" for t in fresh), quote_volume=volume,
                       buy_quote=buys, sell_quote=sells, flow=flow, price_quote=price,
                       latest_trade_at=self.latest_timestamp, latest_block=self.high_water[0] if trades else None,
                       coverage="partial-initial" if initial else "gap-detected" if gap or late else "overlap-observed",
                       gap_count=self.gap_count, ignored_late_events=len(late),
                       feed_status="observed-trades" if fresh else "no-fresh-trades",
                       event_digest=digest([t.event_id for t in new]), features=frame,
                       liquidity_verified=False, price_impact_verified=False)
        return summary, currents
