# Calibration Gate Report

- records: 582
- clean records: 505
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -403.93504773731337
- right_acceleration_px_s2: 437.0795496079347
- release_velocity_ratio_per_step: 0.037037037835496014
- screen_gravity_px_s2: 108.42037200927734
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 5.919
- one_step_y_mae_px: 13.271
- one_step_vx_mae_px_s: 48.216
- one_step_vy_mae_px_s: 108.181
- 10_step_x_mae_px: 64.358
- 10_step_y_mae_px: 782.216
- 10_step_windows: 207
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 3.900
- one_step_y_mae_px: 6.560
- one_step_vx_mae_px_s: 31.859
- one_step_vy_mae_px_s: 53.873

## Landing classifier

- true_positive: 17
- false_positive: 4
- false_negative: 1
- precision: 0.8095238095238095
- recall: 0.9444444444444444
- death_misclassifications: 0

## Gates

- [x] left_clean_samples_30
- [x] right_clean_samples_30
- [x] release_nonzero_samples_20
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
