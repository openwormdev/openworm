# Validation evidence

The reproducible checks target Python 3.12, Java 17, GCC/G++, Make, and Node 22 or newer. CI uses Python 3.12 and Node 22. These are functional and numerical checks, not evidence of investment performance.

| Check | Observed result |
|---|---|
| Python feature, decoder, risk, feed and API tests | 34 passed; the native integration gate was skipped locally |
| JavaScript contracts, URL handling and recording integrity | 6 passed |
| Current reader generation | Pinned Cook 2019 cache hash verified; generated 302 populations and 5,905 projections; all 22 requested readouts, all feedback targets, and seven existing ASE-to-AIA/AIY paths were present |
| Decoder and paper loop | Unit tests cover forward/reverse/pause transitions, paper fills, vetoes, cooldown, latching kill switch, and unfilled exits without the legacy two-tick margin trigger |
| Plasticity and feedback | Unit tests cover bounded depression/recovery and bounded PVC/DVA-style fill/veto feedback; the native continuous observer applied the requested named-path gains between ticks |
| Continuous token observer | Native Linux/Java/NEURON workflow completed three linked ticks on the fixed WORMBRAIN token: 302 dynamically reported populations, 5,905 projections, 22 public voltages, seven plastic paths, nonzero live sensory currents, REVERSE → PAUSE → REVERSE states, and risk blocks for unverified liquidity/impact |
| Bundled model runs | The three public recordings remain valid legacy-reader artifacts and are accepted as schema v1; they are not evidence for the new reader |
| Backend comparison | The committed 18-cell comparison is explicitly labeled `legacy-reader-baseline`; it does not validate the current model identity |
| Public build | Eleven allowlisted assets; replay and continuous-observer hashes checked before copying |
| Publication review | Privacy scan covers credentials, contact data, user paths, location clues, device metadata, analytics IDs and wall-clock timestamps; optional upstream donor labels are removed from model metadata |

## Live observer extension

The current inexpensive suite passed 34 Python unit/API tests and 6 JavaScript tests. The expensive reference API test remains opt-in. The public build contains 11 allowlisted assets, including the hash-pinned continuous observer recording and live observer controls.

The Cook 2019 reader, RIM/RIB recordings, native ASE-family conductance mutation, and feedback inputs were exercised by the continuous Linux/Java/NEURON session. Its public artifact contains relative tick and biological time only. It is a real bounded observer run, not a claim of complete chain coverage or strategy performance.

Exact market-event counts, prices, block heights, wall-clock timestamps, session hashes, and raw runtime exports are intentionally excluded from Git. Local reports contain only the requested token and quote contract addresses, with no trader accounts or raw transaction identifiers, and belong under the ignored `runs/` directory.

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

The normal GitHub Actions workflow runs the inexpensive checks. The manually triggered reference workflow runs the real model gate. A workflow definition does not mean that GitHub has already run it successfully.

No browser visual inspection, Docker image build or Vercel deployment was performed for this validation. Vercel serves static recordings and observation controls; fresh simulations require the separate worker. Long-horizon backend equivalence, current connectome accuracy, complete live-market coverage and comparative strategy performance remain unvalidated. Refer to the model card before interpreting the neural responses.
