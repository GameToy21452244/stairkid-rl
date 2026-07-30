# Current Data and Success Rate Report

Updated: 2026-07-30

## Executive summary

The current evidence supports proceeding to the Colab pipeline validation gate. It
does **not** yet support claiming that the learned policy beats the scripted
simulator baseline or that it has a measured real-game success rate.

The P1 learnability probe passed its pre-registered gate: all six trained
algorithm/seed combinations avoided action collapse and exceeded the random-policy
floor threshold. Across held-out simulator episodes, PPO reached at least one
lower floor in 76.7% of episodes and SB3-DQN in 71.7%. The scripted baseline
reached at least one lower floor in 85.0%.

## Available data

### Real-game calibration telemetry

- 14 calibration logs
- 649 transitions
- 125 LEFT, 131 RIGHT, and 29 non-zero RELEASE_ALL control samples
- 237 free-motion samples
- 23 landing events
- 325 landing-focused steps, covering 17 landings and 12 descended floors
- One-step fitted error: x MAE 3.99 px, y MAE 6.83 px,
  vx MAE 32.67 px/s, and vy MAE 56.17 px/s
- Landing classifier: precision 0.846, recall 0.957, with zero observed death
  misclassifications in the calibration evaluation

These logs are calibration evidence and remain excluded from Git. They are not a
validated demonstration dataset and are not eligible for BC, DAgger, DQN, or DQfD
training.

### Legacy data

- 23 JSONL files
- 2,912 rows
- 100% quarantined
- 0 rows eligible for BC or DQN training

The legacy rows do not satisfy the current schema/provenance requirements and must
not be silently mixed into later experiments.

### Simulator evidence

- Simulator control interval: 125 ms (8 Hz)
- Baseline benchmark: 2,490 steps, 150 landings, and 150 descended floors
- Landing/floor event rate: 0.0602 per control step
- Real-versus-simulator distribution gate: passed
- Headless throughput check: approximately 3,317 steps/s in the recorded local run

## P1 held-out simulator results

All percentages below use the same 20 held-out environment seeds per trained
model. PPO and SB3-DQN each have three independently trained seeds, for 60
evaluation episodes per algorithm.

| Policy | Episodes | At least 1 floor | At least 2 floors | Mean floors |
|---|---:|---:|---:|---:|
| Random | 20 | 45.0% | 25.0% | 0.700 |
| Always release | 20 | 55.0% | 30.0% | 0.900 |
| Scripted baseline | 20 | 85.0% | 55.0% | 1.650 |
| PPO, three seeds combined | 60 | 76.7% | 50.0% | 1.450 |
| SB3-DQN, three seeds combined | 60 | 71.7% | 40.0% | 1.167 |

Additional gate outcomes:

- Six of six trained seed runs passed the per-seed P1 gate: 100%.
- Two of two algorithm-level probes passed the learnability gate: 100%.
- Neither learned algorithm beat the scripted baseline on average floors.
- PPO had the better learned-policy mean but also higher variation across seeds.
- The Stable-Baselines3 DQN used here is not Double DQN.

## Interpretation of “success rate”

There is no single final success rate yet because the project has not defined and
measured an end-to-end real-game objective such as reaching a target floor,
surviving a fixed duration, or completing a level.

For the current simulator probe, “at least one descended floor before termination”
is a transparent interim episode-success definition. Under that definition the
best learned result is PPO at 76.7%, compared with the scripted baseline at 85.0%.
The 100% gate-pass values describe experiment-health checks, not gameplay success.

These simulator percentages must not be presented as real-game performance.

## Next gate

Run the bounded Colab validation path in `notebooks/ns_shaft_colab.ipynb`:

1. install the repository and execute the test/environment checks;
2. benchmark vectorized throughput;
3. run the 768-step validation-only PPO path;
4. verify checkpoint save, reload, and resume;
5. render the short MP4 and retain `colab_pipeline_gate.json`.

Only after that gate passes should a longer, budgeted simulator training protocol
be frozen. Real-game evaluation should remain a separate, safety-controlled phase
with its own explicit success definition and held-out trials.
