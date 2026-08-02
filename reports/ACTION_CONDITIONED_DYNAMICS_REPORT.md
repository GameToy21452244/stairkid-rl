# Action-Conditioned Dynamics Report

- generated at: 2026-08-02T19:14:57.043544+00:00
- real transitions read: 1075
- strict normal-motion rows: 475
- held-out episodes: 15
- shadow model eligible: **False**
- live deployment approved: **False**

This report is offline-only. It reuses the horizontal coefficient form already present in `CalibratedObservationModel`; it does not add a second live dynamics subsystem.

## Episode-held-out one-step error

| Regime | n | model x MAE | carry x MAE | model vx MAE | carry vx MAE |
|---|---:|---:|---:|---:|---:|
| OVERALL | 475 | 4.442 | 9.110 | 32.258 | 66.573 |
| RELEASE | 202 | 3.410 | 7.317 | 23.625 | 53.967 |
| LEFT | 117 | 5.397 | 10.405 | 40.438 | 76.757 |
| RIGHT | 156 | 5.062 | 10.459 | 37.304 | 75.258 |

## Action-history regimes

| Regime | n | model x MAE | carry x MAE |
|---|---:|---:|---:|
| first_release_after_left | 40 | 4.433 | 12.737 |
| first_release_after_right | 50 | 4.297 | 10.263 |
| left_from_low_speed | 16 | 5.487 | 13.160 |
| left_hold | 83 | 5.001 | 8.353 |
| left_reverse_braking | 11 | 8.261 | 21.063 |
| left_transition | 7 | 5.390 | 11.686 |
| repeated_release | 112 | 2.649 | 4.067 |
| right_from_low_speed | 31 | 4.938 | 12.745 |
| right_hold | 101 | 4.678 | 7.661 |
| right_reverse_braking | 15 | 7.168 | 23.145 |
| right_transition | 9 | 6.296 | 12.834 |

## Actual-action rollout audit

| Horizon | windows | model x MAE | carry x MAE |
|---:|---:|---:|---:|
| 2 | 294 | 7.408 | 19.452 |
| 3 | 185 | 10.982 | 30.226 |
| 4 | 120 | 15.486 | 43.978 |
| 5 | 81 | 21.449 | 56.941 |

## Release evidence

- non-zero release rows: 138
- absolute displacement median / max: 6.000 / 24.500 px
- old `vx × 0.25 s` x MAE: 23.357 px
- short `vx × 0.05 s` x MAE: 4.906 px

## Acceptance checks

- [x] at_least_8_held_out_episodes
- [x] each_action_has_30_samples
- [ ] reverse_braking_each_has_30_samples
- [x] overall_x_beats_carry_baseline
- [x] overall_vx_beats_carry_baseline
- [x] each_action_x_beats_carry_baseline
- [x] two_to_five_step_rollouts_beat_carry

Result: action-conditioned dynamics remains a supported research direction, but failed checks block live deployment. In particular, reverse-braking coverage and/or held-out sequence quality must be repaired before controller integration.

## Historical calibration coverage check

- files / strict continuous rows: 17 / 534
- excluded interrupted files: ['calibration_v1_reverse-braking_20260803_025236_563731.jsonl']
- reverse LEFT / RIGHT: 24 / 21
- first release after LEFT / RIGHT: 37 / 27
- controller sidecar context: unavailable; these rows are not merged into the primary deployment Gate

The fixed-platform archive confirms that action reversal changes short-horizon motion, but it cannot close the natural landing-context evidence gap. Further fixed-platform oscillation is stopped. The next representative source must be bounded natural Teacher trajectories with full controller sidecars; the candidate model remains offline and cannot affect those actions.
