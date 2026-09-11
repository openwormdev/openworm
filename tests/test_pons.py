import json
import unittest
from dataclasses import asdict
from unittest.mock import patch

from wormbrain.pons import FeedError, TradeFeed, parse_trade, public_market_snapshot


def event(block=10, log=0, *, side="buy", quote=2, tokens=10, timestamp=1000):
    tx = "0x" + "a" * 64
    return dict(id=f"4663:{block}:{tx}:{log}", transactionHash=tx, blockNumber=block,
                timestamp=timestamp, side=side, venue="pool", account="discard-this-account-field",
                tokenAmount=str(tokens * 10**18), quoteAmount=str(quote * 10**18))


class PonsTests(unittest.TestCase):
    def test_public_market_snapshot_is_aggregate_only(self):
        snapshot = public_market_snapshot([event(log=0), event(log=1, side="sell")], now=1001)
        self.assertEqual(snapshot["status"], "connected")
        self.assertEqual(snapshot["recent"]["events"], 2)
        self.assertEqual(snapshot["recent"]["buy_events"], 1)
        self.assertEqual(snapshot["recent"]["sell_events"], 1)
        self.assertNotIn("account", json.dumps(snapshot))
        self.assertNotIn("transactionHash", json.dumps(snapshot))

    def test_amounts_are_in_quote_units_and_accounts_are_discarded(self):
        trade = parse_trade(event(), 1001)
        self.assertEqual(trade.quote_amount, 2)
        self.assertEqual(trade.token_amount, 10)
        self.assertNotIn("account", json.dumps(asdict(trade)))
        summary, currents = TradeFeed().ingest([event()], now=1001)
        self.assertEqual(summary["price_quote"], .2)
        self.assertGreater(currents["AWAL"], 0)
        self.assertLess(currents["AWAL"], 1.8)

    def test_multiple_swaps_in_one_transaction_and_duplicates(self):
        feed = TradeFeed()
        first, _ = feed.ingest([event(log=0), event(log=1)], now=1001)
        duplicate, zero = feed.ingest([event(log=1), event(log=0)], now=1002)
        self.assertEqual(first["new_events"], 2)
        self.assertEqual(duplicate["new_events"], 0)
        self.assertEqual(duplicate["coverage"], "overlap-observed")
        self.assertTrue(all(x == 0 for x in zero.values()))

    def test_gap_and_late_events_are_exposed(self):
        feed = TradeFeed()
        feed.ingest([event(block=10)], now=1001)
        gap, _ = feed.ingest([event(block=12)], now=1002)
        self.assertEqual(gap["coverage"], "gap-detected")
        late, zero = feed.ingest([event(block=11)], now=1003)
        self.assertEqual(late["ignored_late_events"], 1)
        self.assertEqual(late["new_events"], 0)
        self.assertTrue(all(x == 0 for x in zero.values()))

    def test_stale_and_future_events_cannot_stimulate(self):
        summary, currents = TradeFeed().ingest([event()], now=1100)
        self.assertEqual(summary["stimulated_events"], 0)
        self.assertTrue(all(x == 0 for x in currents.values()))
        with self.assertRaises(FeedError):
            TradeFeed().ingest([event(timestamp=2000)], now=1001)

    def test_sell_pressure_has_input_even_before_a_price_baseline(self):
        summary, currents = TradeFeed().ingest([event(side="sell")], now=1001)
        self.assertEqual(summary["flow"], -1)
        self.assertGreater(currents["ASER"], 0)
        self.assertGreater(currents["ASHL"], 0)
        self.assertEqual(currents["ASEL"], 0)
        self.assertEqual(currents["AWAL"], 0)

    def test_malformed_or_changed_events_do_not_poison_seen_state(self):
        feed = TradeFeed()
        bad = event();bad["quoteAmount"] = "1.5"
        with self.assertRaises(FeedError):
            feed.ingest([event(), bad], now=1001)
        self.assertEqual(feed.total_events, 0)
        feed.ingest([event()], now=1001)
        with self.assertRaises(FeedError):
            feed.ingest([event(quote=3)], now=1002)
        self.assertEqual(feed.total_events, 1)

    def test_live_api_auth_and_exclusion(self):
        import os
        from fastapi.testclient import TestClient
        from wormbrain.api import app, jobs
        jobs.clear()
        client = TestClient(app)
        with patch.dict(os.environ, {"WORM_WORKER_TOKEN": "test-only-not-a-real-credential"}):
            for method, path in [("get", "/api/live"), ("post", "/api/live/start"), ("post", "/api/live/stop")]:
                self.assertEqual(getattr(client, method)(path).status_code, 401)
        jobs["test"] = dict(status="running")
        self.assertEqual(client.post("/api/live/start").status_code, 429)
        jobs.clear()
        with patch("wormbrain.api.monitor") as monitor:
            monitor.active = False
            self.assertEqual(client.post("/api/live/start").status_code, 202)
            monitor.start.assert_called_once_with(seconds=3600)
            self.assertEqual(client.post("/api/live/stop").status_code, 200)
            monitor.stop.assert_called_once()
            monitor.active = True
            self.assertEqual(client.post("/api/jobs", json={"scenario": "trend"}).status_code, 429)


if __name__ == "__main__":
    unittest.main()
