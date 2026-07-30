# Calibration Gate Report

- records: 316
- clean records: 264
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -477.8431451018189
- right_acceleration_px_s2: 418.8368394970894
- release_velocity_ratio_per_step: 0.0625
- screen_gravity_px_s2: 187.06976547122105
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 4.979
- one_step_y_mae_px: 13.636
- one_step_vx_mae_px_s: 40.586
- one_step_vy_mae_px_s: 110.944
- 10_step_x_mae_px: 57.653
- 10_step_y_mae_px: 783.875
- 10_step_windows: 111
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 3.334
- one_step_y_mae_px: 7.493
- one_step_vx_mae_px_s: 27.149
- one_step_vy_mae_px_s: 61.410

## Gates

- [x] left_clean_samples_30
- [x] right_clean_samples_30
- [ ] release_nonzero_samples_20
- [x] free_motion_samples_30
- [ ] landing_events_20
- [x] one_step_x_mae_le_6
- [x] one_step_y_mae_le_8
- [x] one_step_vx_mae_le_50
- [ ] one_step_vy_mae_le_60
- [ ] landing_precision_recall_measured
- [ ] ten_step_rollout_threshold
- [ ] thirty_step_rollout_threshold

未通過全部門檻前，不開始 learnability probe、BC 或 RL 長訓。
