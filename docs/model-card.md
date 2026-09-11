# Model card

## What the runtime actually does

The reference adapter invokes c302 0.12.0 with `ParameterisedModel` from `parameters_C1`, no selected neuron subset, no muscles, no polarity overrides, and no hidden global offset current. Every population produced by the chosen reader participates. The public readout keeps the original 18 sensory and command cells and adds RIML/RIMR and RIBL/RIBR when the reader produces them. Recording fewer columns does not remove the other neurons from the simulation.

C1 defines conductance-based single-compartment cells, graded chemical synapses, and electrical gap junctions. It is not a generic NumPy graph or a trained surrogate. The default engine uses the official `jNeuroML -neuron -nogui` exporter and compiles its generated NMODL mechanisms for NEURON 9.0.2. The generated NEURON script runs without hand-written replacement equations. Numerical integration timestep is 0.05 ms. The whole replay is continuous; a new replay is reset.

The pure Java interpreter is retained as an explicit backend in `brain.simulate`, but is too slow for the default interactive worker. The backend change is not a claim of bitwise numerical identity. The committed comparison artifact belongs to the earlier legacy-reader baseline and must not be presented as validation of the Cook 2019 reader. A new comparison must be generated before making numerical-equivalence claims for this model identity.

The default replay uses 300 ms of pre-stimulus warmup and 200 ms per market observation. Pulses begin 20 ms into each observation and last 140 ms; readout uses its last 40 ms. Ten fictional observations therefore map to 2,300 ms of simulated biological time. This clock mapping is an engineering choice.

## Pinned connectivity reader

The adapter uses `cect.readers.Cook2019HermReader` from CECT 0.3.4. It verifies the packaged `Cook2019HermReader.json` cache against SHA-256 `98bdafffce1341d3443a83066a6225a977c8218c28c27d69e4bd465782bd4cc8` before model execution. The CECT wheel remains version-pinned in `requirements.lock`. Changing either value creates a different model identity.

The total population count comes from the generated network. Never equate the repository name with a guarantee that a selected reader represents every adult hermaphrodite neuron. Report the actual count and the reader.

## Input/readout assumptions

- Market gradients and “danger” are engineered metaphors, not validated neural encodings of financial concepts.
- All C1 upstream conductances and synapse dynamics are left intact. Many are labeled `BlindGuess` by the upstream model.
- For each output neuron, the runtime measures mean membrane voltage over the final readout window, subtracts its pre-stimulus baseline, divides by a fixed 10 mV engineering span, and preserves signed activity in [-1,1].
- Forward is AVBL/AVBR/PVCL/PVCR; reverse is AVAL/AVAR/AVDL/AVDR/AVEL/AVER. RIM and RIB are retained separately when available. A small state machine publishes `FORWARD`, `REVERSE`, or `PAUSE`; the legacy two-tick margin rule is not used.
- ASEL/ASER, AWA/AWC, and ASH have separate saturating pA transfer curves. The complete equation, anchors, parameters, and calibration hash are included in the model identity.
- The baseline may itself be a transient. Changing the warmup, timestep, or voltage span requires regenerating recordings and comparing stability.
- The persistent live worker applies one engineered dopamine-proxy depression/recovery gain, bounded to [0.25,1], to the existing ASE-to-AIA/AIY chemical family between ticks. C1 cell equations and synaptic kinetics remain unchanged. This is not a claim of endogenous dopamine physiology.
- Paper fill or veto results become bounded next-episode currents on PVC/DVA-style targets. There is no Sibernetic body, muscle feedback, realistic sensation, wallet, or real execution.

The model may produce no trades, a constant bias, or unsuitable directional responses. Do not tune the mapping until one handpicked market story looks profitable and then call that validation.

## Reproducibility and audit

Reports contain engine versions, reader-cache and generated-model hashes, calibration and plasticity definitions, actual population count, stimulus and feedback currents, sampled membrane traces, decoder state, risk reasons, paper fill/costs, and the complete decision-chain root. A report hash identifies one serialized Python report. File SHA-256 values in the bundled manifest protect the exact published bytes.

Hashes are integrity/provenance aids, not signatures proving who ran a simulation. An imported report can be forged and is explicitly labeled origin-unverified. Do not compare Python JSON hashes by naïvely reserializing with JavaScript; number formatting can differ.

## Required research before performance claims

Run no-trade, momentum, matched-frequency random, shuffled-input, command-cell ablation, ASH ablation, and rewired-connectome controls on held-out observations with realistic costs and latency. Report all seeds and negative results. These scientific studies have not been performed by this prototype.
