# Reverse-Braking Calibration Review

- Date: 2026-08-03
- Final status: **STOPPED — DIAGNOSTIC ONLY**
- Teacher/Student training performed: **no**
- Live controller changed: **no**

## Why this experiment was attempted

The previous action-conditioned audit had only 7 LEFT-while-moving-right and 8 RIGHT-while-moving-left rows in natural Teacher trajectories. The bounded calibration therefore used a deterministic two-frame RIGHT / two-frame LEFT cycle to isolate the immediate velocity response to an opposite command. It had a 20-second hard cap, foreground/F8/related-window guards, missing-player RELEASE, inward wall override, and special-contact RELEASE.

This is system identification, not training and not an attempt to descend floors.

## What happened

Three completed runs produced 125 transitions. After excluding events, screen edges, missing player, and vertical motion-boundary rows, 84 strict rows remained:

| Included run | Raw rows | Strict rows | LEFT reverse | RIGHT reverse | End |
|---|---:|---:|---:|---:|---|
| `025027_504563` | 38 | 25 | 6 | 7 | terminal, validator pass |
| `025124_827516` | 56 | 36 | 12 | 8 | phase change, validator pass |
| `025202_671564` | 31 | 23 | 5 | 6 | terminal, validator pass |
| **Total** | **125** | **84** | **23** | **21** | diagnostic only |

A fourth run (`025236_563731`) was stopped immediately after the user correctly questioned the distribution. Its 57 raw / 40 strict rows are retained for provenance but explicitly excluded from all audit totals and qualification. LEFT and RIGHT key states were verified released after interruption.

## Evidence judgment

The fixed-platform cycle is useful for one narrow question: an opposite command produces a measurable short-horizon response. It is not representative evidence for the actual failure we need to repair:

- no natural target selection;
- little variation in landing distance and safe interval;
- no reliable support/airborne/recovery controller context sidecar;
- repeated states from one local platform;
- no evidence that a different prediction changes landing success or lower-tail floors.

Reaching 30/30 by repeating this setup would create a numerically larger but distributionally narrow dataset. Those rows must not unlock action-conditioned live control, receding horizon, Teacher Gate, or P4.0.

## Decision

Stop further fixed-platform reversal collection. Keep the three completed runs as `diagnostic-only`; exclude the interrupted fourth run. The primary deployment check remains based on natural Teacher trajectories and stays at LEFT 7 / RIGHT 8, so `shadow_model_eligible=false` and `live_deployment_approved=false`.

## More representative next experiment

Use one bounded three-episode natural Teacher run with the current controller unchanged. It must save MP4, transitions, controller sidecars, timing, target/safe-interval fields, support/special/recovery context, and terminal reasons. The candidate dynamics model may be evaluated only offline/shadow after the run; it must not choose actions.

This single run can simultaneously:

1. collect natural braking/release examples near actual landing decisions;
2. verify the current short release projection in closed loop;
3. verify the EXIT reset fix;
4. re-evaluate Normal/Spring/Spike/Restart Gates without inventing a separate training task.

If it does not add representative reversal cases or improve lower-tail reliability, stop and revisit the observation/control formulation instead of repeating real runs.
