# Calibration Gate Report

- records: 418
- clean records: 355
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -477.8431451018189
- right_acceleration_px_s2: 462.20350545676996
- release_velocity_ratio_per_step: 0.037037037835496014
- screen_gravity_px_s2: 112.42371797561646
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 5.296
- one_step_y_mae_px: 13.903
- one_step_vx_mae_px_s: 43.069
- one_step_vy_mae_px_s: 112.587
- 10_step_x_mae_px: 54.678
- 10_step_y_mae_px: 793.273
- 10_step_windows: 154
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 3.311
- one_step_y_mae_px: 7.178
- one_step_vx_mae_px_s: 26.917
- one_step_vy_mae_px_s: 58.626

## Gates

- [x] left_clean_samples_30
- [x] right_clean_samples_30
- [ ] release_nonzero_samples_20
- [x] free_motion_samples_30
- [ ] landing_events_20
- [x] one_step_x_mae_le_6
- [x] one_step_y_mae_le_8
- [x] one_step_vx_mae_le_50
- [x] one_step_vy_mae_le_60
- [ ] landing_precision_recall_measured
- [ ] ten_step_rollout_threshold
- [ ] thirty_step_rollout_threshold

未通過全部門檻前，不開始 learnability probe、BC 或 RL 長訓。
