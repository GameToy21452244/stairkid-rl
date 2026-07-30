# Calibration Gate Report

- records: 558
- clean records: 484
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -384.0000033378601
- right_acceleration_px_s2: 437.0795496079347
- release_velocity_ratio_per_step: 0.03505291011564612
- screen_gravity_px_s2: 96.99173982824206
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 5.765
- one_step_y_mae_px: 13.388
- one_step_vx_mae_px_s: 46.992
- one_step_vy_mae_px_s: 109.103
- 10_step_x_mae_px: 63.762
- 10_step_y_mae_px: 780.439
- 10_step_windows: 201
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 3.766
- one_step_y_mae_px: 6.520
- one_step_vx_mae_px_s: 30.791
- one_step_vy_mae_px_s: 53.619

## Landing classifier

- true_positive: 16
- false_positive: 4
- false_negative: 1
- precision: 0.8
- recall: 0.9411764705882353
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
