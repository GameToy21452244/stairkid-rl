# Project history

This document preserves research context; it is not an active execution guide.
Git history remains intact and was not rewritten.

## Research lineage

### V1

The project began with an early simulator and rule/observation experiments.
These established basic platform, player, capture, and safety abstractions.

### V2

The second model generation added bounded Real control and extensive policy,
calibration, and evaluation experiments. It is retired: no model binary,
runtime option, fallback, training preset, or production/champion concept is
present in the final active project. Its historical model SHA-256 was
`1e29770fb8514014b3dc10e4ba6a1ff5078a59515ceb0dc3eb73b7ca6f03f521`.

### Fresh V3

Fresh V3 moved to a real-anchored 268-D simulator training line with
`Discrete(3)` actions and 8/10/12 Hz policy decisions over 60 Hz physics. The
retained seed17@524288 checkpoint is the stable historical baseline and has 61
Real episodes of descriptive evidence.

### Real/simulator system identification

Capture, detector, action-history, timing, platform geometry, and dynamics
investigations calibrated the simulator against the observed Real system.
Generic results survive in current profiles, runtime code, and regression
tests; one-off diagnostic runners and generated reports were retired.

### Corrected flipping physics

Audit found that global episode elapsed time could override an explicit
flipping-platform `INACTIVE` runtime state. The corrected state machine makes
`_update_flipping_states()` the sole `INACTIVE → READY` owner. Inactive
platforms are noncollidable, provide no support, and render inactive until the
complete inactive duration finishes.

### V3.5 R1 → R2 → R3 → R4

Successive safety-refinement rounds investigated landing, damage, death, bank,
and reward-alignment behavior. The retained R4 method uses corrected flipping,
frozen R1 targeted inputs, and `edge_landing_penalty=1.10`. Round-specific
finalizers, packages, notebooks, and promotion orchestration are not active
architectures; provenance is captured by the R4 config and asset manifest.

### STOP_V3_5

R4 failed its formal simulator gate, was not promoted, and retained unresolved
safety. `STOP_V3_5` remains unchanged. Unified training support is for
reproducibility and experimentation; it does not reopen promotion research.

### R4 exploratory Real20

R4 seed142@655360 completed 20 explicitly exploratory Real episodes:

- mean 5.35, median 5, Q25 3, Q75 8, min 1, max 13
- floor <= 4 rate 45%

Historical Fresh V3 evidence was N=61, mean 4.41, median 4, Q25 2, Q75 6,
and floor <= 4 rate 59.0%. R4 was descriptively stronger on floor distribution,
but statistical superiority was not established and safety remained unresolved.

The audited R4 policy-parameter SHA-256 was
`2bb3910e0f0be001caaafe9e2f8ea2feec186003fca9737988a8d8927a69a104`.
It is retained only as historical provenance. The final runtime uses the
canonical model archive SHA as its sole model integrity gate.

## Final consolidation

The final active system retains:

- Fresh V3 (`STABLE_BASELINE`)
- V3.5 R4 seed142@655360 (`EXPERIMENTAL_FINAL`)
- one corrected simulator used by human and PPO controllers
- one guarded Real runtime
- one unified V3/R4 trainer and one Git-clone Colab notebook
- generic evaluation and current regression tests

Historical branches remain available until the separately gated branch-cleanup
phase. They are not required to use the consolidated project.
