# WORMBRAIN transaction awareness

This observer feeds reported executed trades into the real c302 model. “Awareness” means a measurable response to imposed sensory currents; it does not imply consciousness, comprehension of finance or a profitable strategy.

## Target and source

| Field | Value |
|---|---|
| Token | `0x2703295342C5914e0292ADFDB612618Ce24105d1` |
| Network | Robinhood Chain, chain ID 4663 |
| Launch protocol | pons v2 |
| Quote token | GOOGL, `0x2e0847E8910a9732eB3fb1bb4b70a580ADAD4FE3` |
| Decimals | 18 for both token and quote |
| Feed | `https://www.ponsfamily.com/api/pons-v2-market/0x2703295342c5914e0292adfdb612618ce24105d1/trades` |
| Execution authority | None; observation only |

The project token and quote metadata were read from the user-supplied Pons launch page. The public page's JavaScript uses the trade endpoint above. It returns `curve` or `pool` events, buy/sell side, raw integer token/quote amounts, block number, timestamp and a chain:block:transaction:log identifier. The adapter reads only executed-trade observations; ordinary ERC-20 transfers are not treated as buys or sells.

The source is the **Pons public indexer**, not direct RPC logs. The build environment could not reach the mainnet RPC successfully, and the app's RPC proxy rejected the request. No receipt verification, finality guarantee, pool-state proof or exhaustive backfill is claimed. The launch page also warned of delayed backend data during an upgrade. Its cached phase differed from recent pool events, so cached page phase is not used as execution authority.

References: [token page](https://www.ponsfamily.com/launchpad/0x2703295342C5914e0292ADFDB612618Ce24105d1), [pons v2 integration documentation](https://docs.ponsfamily.com/v2), [Robinhood Chain](https://docs.robinhood.com/chain/).

## Exact signal mapping

A poll targets a 15-second cadence. Each completed poll advances the same neural model by 200 ms, even if network latency makes the wall-clock interval longer. The first 300 ms is a zero-input warmup. For each episode the pulse starts at +20 ms, lasts 140 ms, and readout averages the final 40 ms. No neuron or synapse is reset between episodes.

Only new events no more than 60 seconds old contribute to a new stimulus. A source outage, duplicate-only response, stale window or empty window supplies zero external current. Spontaneous neural dynamics continue. This age cutoff is deliberately conservative and is not a statement about transaction finality.

Let B and S be the observed buy and sell volume in GOOGL. Let F=(B-S)/(B+S), and buy share A=B/(B+S). Both are zero if no fresh volume exists. The observed price is quote amount divided by token amount for the last ordered fresh swap; fees and trade size can affect this execution-price proxy. It is not a spot oracle or an executable quote.

The return z-score uses only prior observed batch prices, a 64-price rolling window, median/MAD normalization, a 0.01 scale floor and clipping to [-3,3]. D is drawdown from the maximum of that rolling observed-price window. Define P=max(F,0), N=max(-F,0). All following expressions are clipped to [0,1] before multiplication by 5 pA:

| Neuron(s) | Normalized current |
|---|---|
| ASEL | 0.7 × max(z,0)/3 + 0.3 × P |
| ASER | 0.7 × max(-z,0)/3 + 0.3 × N |
| AWAL, AWAR, AWCL, AWCR | A |
| ASHL, ASHR | 0.6 × D/0.2 + 0.4 × N |

These are engineered prototype settings, recorded as `pons-observation-v1`. They are separate from the frozen synthetic-replay mapping. No calibration to P&L was performed. Unverified liquidity or price-impact values are not invented as neural evidence. All live execution is disabled independently of neural output.

## Continuity and integrity

The adapter builds the full c302 C1 network and compiles the official jNeuroML NEURON export once per session. It uses the generated `NeuronSimulation.advance()` method and changes only the generated pulse generators' amplitudes and timing. It does not replace neural equations. NEURON current units are nA, so the adapter divides pA inputs by 1,000.

Only recording vectors are cleared between episodes to bound memory. Clearing stored samples does not reset voltages, ion channels or synapses. Each frame records stimulus, measured voltages, biological time, source summary, model identity and a hash-linked event. A maximum of 240 frames is retained in memory; a truncated history can begin with a previous hash outside the export.

Deduplication includes log index, so multiple swaps in one transaction remain distinct. Conflicting repeated event IDs reject the response. Late events behind the processed block/log cursor are counted and ignored rather than retroactively rewriting the neural state. The first window is marked `partial-initial`. If a later response no longer overlaps the last observed event, it is marked `gap-detected`. `overlap-observed` establishes overlap only; it does not prove that the provider returned every chain event.

The observed endpoint returned 50 recent trades per request during development. For a busy token this can cover only a few seconds, making gaps likely at the configured poll cadence. Reported counts are lower bounds on observed events, never total market trade counts. Increasing the poll rate cannot guarantee completeness. Complete ingestion requires a reliable RPC or indexer with pagination, canonical receipts/log ordering, bounded block backfill and reorg handling. That upgrade remains outstanding.

## Privacy

Account, sender, recipient, profile, social and fee-recipient data are excluded from live state. Only the requested project and quote contract addresses are in source. Individual transaction identifiers are hashed before report state is formed; reports contain aggregate counts and an event digest, not trader addresses. Runtime exports stay in the ignored `runs/` directory unless explicitly saved elsewhere.

## Running and deployment

`wormbrain watch --seconds 3600` runs a session from the terminal. The dashboard loads aggregate token activity from the public, same-origin `/api/token` route. On Vercel this small function reads the fixed Pons endpoint and removes wallet and transaction identifiers before responding; the local Python server exposes the same response contract. Authenticated `/api/live/start`, `/api/live/stop` and `/api/live` routes remain responsible for the neural observer. Existing worker-token and exact-origin controls apply to those three routes. Start and replay requests share one worker slot. The browser sends no data to Pons directly.

Vercel hosts the controls, charts and sanitized token-data function. The persistent Python/Java/NEURON process must run separately for live neural output. There is no claim that this chat, the Vercel token feed or an exported recording keeps a brain running indefinitely.
