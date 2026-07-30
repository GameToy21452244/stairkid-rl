# Calibration Gate Report

- records: 220
- clean records: 185
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -491.4964034810647
- right_acceleration_px_s2: 512.0000839233398
- release_velocity_ratio_per_step: 0.05185185457938783
- screen_gravity_px_s2: 112.42371797561646
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 4.149
- one_step_y_mae_px: 13.713
- one_step_vx_mae_px_s: 33.995
- one_step_vy_mae_px_s: 111.472
- 10_step_x_mae_px: 42.763
- 10_step_y_mae_px: 779.012
- 10_step_windows: 81
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 2.696
- one_step_y_mae_px: 6.489
- one_step_vx_mae_px_s: 22.016
- one_step_vy_mae_px_s: 53.357

## Gates

- [ ] left_clean_samples_30
- [ ] right_clean_samples_30
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
