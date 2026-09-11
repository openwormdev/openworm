# Validation evidence

The initial release was checked on Linux with Python 3.12, Java 17, GCC/G++, Make, and Node 24. The web code requires Node 22 or newer; CI is configured for Node 22. These are functional and numerical checks, not evidence of investment performance.

| Check | Observed result |
|---|---|
| Python feature, decoder, risk and API tests | 17 passed |
| JavaScript contracts, URL handling and recording integrity | 4 passed |
| Actual worker API integration | A submitted job completed a full c302 C1 replay; 302 neurons, NEURON backend, finite varying sensory activity, report hash and every decision-chain hash verified |
| Bundled model runs | Three independent real simulations: trend, reversal and liquidity shock; each includes 302 neurons and 3,363 projections |
| Paper outcomes | All three bundled simulations generated zero fills at the frozen thresholds |
| Independent execution tests | Prescribed decoder outputs exercise entry confirmation, buys, sells, costs, external vetoes, cooldown, a latching kill switch and unfilled exits |
| Backend comparison | 60 ms full-network smoke comparison, 18 recorded neurons; maximum absolute voltage error approximately 0.149 mV, below the predeclared 1 mV limit |
| Public build | Eight allowlisted static assets; recording hashes checked before copying |
| Publication review | Source scanned for keys, access tokens, email addresses and machine paths; optional upstream donor labels removed from model metadata |

## Live observer extension

The extension passed 24 Python unit/API tests and 5 JavaScript tests. The original expensive reference API test remains opt-in. The public build now contains 10 allowlisted assets, including the live observer controls.

A real one-minute observation session initialized all 302 neurons and 3,363 projections, read 100 distinct events reported by the Pons indexer and used 44 fresh events in its sensory mapping. Four consecutive 200 ms neural episodes advanced the same initialized state from 300 ms to 1,100 ms. Duplicate, stale and unavailable-source batches supplied zero external current. The largest current was approximately 4.412 pA, and measured sensory voltages varied. Every decision-frame hash and the complete chain root were checked.

One source outage and incomplete windows occurred during the check and are retained in the evidence. Receipt verification was unavailable. The result establishes a functioning indexer-to-neural-input integration, not a complete feed, biological validity or trading performance. `live-validation.json` contains the measured summary. Raw runtime exports were excluded from Git; the checked report contains only the requested token and quote contract addresses, with no trader accounts or raw transaction identifiers.

Reproduce the inexpensive checks after installing the Python requirements and project:

```bash
python -m unittest discover -s tests -p 'test_*.py'
npm test
npm run check
npm run build
```

The real API test is skipped by default because it invokes Java export, native compilation and NEURON. Run it explicitly:

```bash
WORM_RUN_INTEGRATION=1 python -m unittest discover -s tests -p 'test_reference.py'
python scripts/compare_backends.py
```

The normal GitHub Actions workflow runs the inexpensive checks. The manually triggered reference workflow runs a real model replay. A workflow definition does not mean that GitHub has already run it successfully.

No browser visual inspection, Docker image build or Vercel deployment was performed for this validation. Vercel serves static recordings and observation controls; fresh simulations require the separate worker. Long-horizon backend equivalence, current connectome accuracy, complete live-market coverage and comparative strategy performance remain unvalidated. Refer to the model card before interpreting the neural responses.
