# Model card

## What the runtime actually does

The reference adapter invokes c302 0.12.0 with `ParameterisedModel` from `parameters_C1`, no selected neuron subset, no muscles, no connection-number scaling, no polarity overrides, and no hidden global offset current. Every population produced by the chosen reader participates. The recorded subset is the 18 named sensory and command neurons; recording fewer columns does not remove the other neurons from the simulation.

C1 defines conductance-based single-compartment cells, graded chemical synapses, and electrical gap junctions. It is not a generic NumPy graph or a trained surrogate. The default engine uses the official `jNeuroML -neuron -nogui` exporter and compiles its generated NMODL mechanisms for NEURON 9.0.2. The generated NEURON script runs without hand-written replacement equations. Numerical integration timestep is 0.05 ms. The whole replay is continuous; a new replay is reset.

The pure Java interpreter is retained as an explicit backend in `brain.simulate`, but is too slow for the default interactive worker. The backend change is not a claim of bitwise numerical identity. A bounded 60 ms comparison over all 302 simulated neurons and 18 recorded cells passed a predeclared maximum-error threshold of 1 mV; the observed worst difference was approximately 0.149 mV. This does not validate long-run dynamics or trading decisions. Reproduce it with `PYTHONPATH=src python scripts/compare_backends.py`; details are in `backend-validation.json`.

The default replay uses 300 ms of pre-stimulus warmup and 200 ms per market observation. Pulses begin 20 ms into each observation and last 140 ms; readout uses its last 40 ms. Ten fictional observations therefore map to 2,300 ms of simulated biological time. This clock mapping is an engineering choice.

## Historical reader limitation

The adapter uses the exact default reader in c302: `cect.readers.SpreadsheetDataReader`. Its upstream description explicitly marks the source spreadsheet as legacy/reference-only and advises against using it as a current dataset. This release uses it to reproduce the default c302 reference pipeline, not to claim modern anatomical completeness.

The total population count comes from the generated network. Never equate the repository name with a guarantee that a selected reader represents every adult hermaphrodite neuron. Report the actual count and the reader.

Switching to a newer reader is not just changing a string: reader method signatures, non-neuronal cells, morphology coverage, neurotransmitter assignments, and connection semantics must be reconciled and tested. It must create a new model identity and new baselines.

## Input/readout assumptions

- Market gradients and “danger” are engineered metaphors, not validated neural encodings of financial concepts.
- All C1 upstream conductances and synapse dynamics are left intact. Many are labeled `BlindGuess` by the upstream model.
- For each output neuron, the runtime measures mean membrane voltage over the final readout window, subtracts its pre-stimulus baseline, divides by a fixed 10 mV engineering span, and clips to [0,1].
- Forward score is the mean of AVBL, AVBR, PVCL, PVCR. Reverse score is the mean of AVAL, AVAR, AVDL, AVDR, AVEL, AVER. Their difference is not a probability of profit.
- Entry/exit thresholds and 0–5 pA stimulus bounds are fixed prototype settings, not optimized or behaviorally validated parameters.
- The baseline may itself be a transient. Changing the warmup, timestep, or voltage span requires regenerating recordings and comparing stability.
- There is no Sibernetic body, muscle feedback, realistic sensation, proprioception, neuromodulation calibration, or P&L learning.

The model may produce no trades, a constant bias, or unsuitable directional responses. Do not tune the mapping until one handpicked market story looks profitable and then call that validation.

## Reproducibility and audit

Reports contain engine versions, parameter configuration, stimulus currents, sampled membrane traces, model file hashes, each feature frame, original worm intent, risk reasons, paper fill/costs, and the complete decision-chain root. A report hash identifies one serialized Python report. File SHA-256 values in the bundled manifest protect the exact published bytes.

Hashes are integrity/provenance aids, not signatures proving who ran a simulation. An imported report can be forged and is explicitly labeled origin-unverified. Do not compare Python JSON hashes by naïvely reserializing with JavaScript; number formatting can differ.

## Required research before performance claims

Run no-trade, momentum, matched-frequency random, shuffled-input, command-cell ablation, ASH ablation, and rewired-connectome controls on held-out observations with realistic costs and latency. Report all seeds and negative results. These scientific studies have not been performed by this prototype.
