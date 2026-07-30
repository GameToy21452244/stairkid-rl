# Calibration Gate Report

- records: 155
- clean records: 132
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -479.99998927116394
- right_acceleration_px_s2: 639.9999856948853
- release_velocity_ratio_per_step: 0.31904762612757115
- screen_gravity_px_s2: 112.73396015167236
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 3.029
- one_step_y_mae_px: 13.506
- one_step_vx_mae_px_s: 25.030
- one_step_vy_mae_px_s: 110.695
- 10_step_x_mae_px: 16.710
- 10_step_y_mae_px: 772.317
- 10_step_windows: 55
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Gates

- [ ] left_clean_samples_30
- [ ] right_clean_samples_30
- [ ] release_nonzero_samples_20
- [x] free_motion_samples_30
- [ ] landing_events_20
- [x] one_step_x_mae_le_6
- [ ] one_step_y_mae_le_8
- [x] one_step_vx_mae_le_50
- [ ] one_step_vy_mae_le_60
- [ ] landing_precision_recall_measured
- [ ] ten_step_rollout_threshold
- [ ] thirty_step_rollout_threshold

未通過全部門檻前，不開始 learnability probe、BC 或 RL 長訓。
