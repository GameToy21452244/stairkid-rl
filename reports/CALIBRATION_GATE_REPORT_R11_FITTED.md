# Calibration Gate Report

- records: 538
- clean records: 465
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -360.07338762283325
- right_acceleration_px_s2: 462.20350545676996
- release_velocity_ratio_per_step: 0.03306878239579622
- screen_gravity_px_s2: 191.99997186660767
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 5.880
- one_step_y_mae_px: 13.742
- one_step_vx_mae_px_s: 48.148
- one_step_vy_mae_px_s: 111.741
- 10_step_x_mae_px: 61.119
- 10_step_y_mae_px: 780.970
- 10_step_windows: 190
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 3.627
- one_step_y_mae_px: 8.018
- one_step_vx_mae_px_s: 29.716
- one_step_vy_mae_px_s: 65.654

## Gates

- [x] left_clean_samples_30
- [x] right_clean_samples_30
- [x] release_nonzero_samples_20
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
