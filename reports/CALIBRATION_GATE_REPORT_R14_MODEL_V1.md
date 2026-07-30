# Calibration Gate Report

- records: 649
- clean records: 562
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -336.1467719078064
- right_acceleration_px_s2: 511.9999647140503
- release_velocity_ratio_per_step: 0.0344827612507624
- screen_gravity_px_s2: 112.73396015167236
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 6.112
- one_step_y_mae_px: 13.146
- one_step_vx_mae_px_s: 49.883
- one_step_vy_mae_px_s: 107.393
- 10_step_x_mae_px: 65.275
- 10_step_y_mae_px: 780.009
- 10_step_windows: 230
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 3.985
- one_step_y_mae_px: 6.833
- one_step_vx_mae_px_s: 32.669
- one_step_vy_mae_px_s: 56.167

## Landing classifier

- true_positive: 22
- false_positive: 4
- false_negative: 1
- precision: 0.8461538461538461
- recall: 0.9565217391304348
- death_misclassifications: 0

## Gates

- [x] left_clean_samples_30
- [x] right_clean_samples_30
- [x] release_nonzero_samples_20
- [x] free_motion_samples_30
- [x] landing_events_20
- [x] one_step_x_mae_le_6
- [x] one_step_y_mae_le_8
- [x] one_step_vx_mae_le_50
- [x] one_step_vy_mae_le_60
- [x] landing_precision_recall_measured
- [ ] ten_step_rollout_threshold
- [ ] thirty_step_rollout_threshold

未通過全部門檻前，不開始 learnability probe、BC 或 RL 長訓。
