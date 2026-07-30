# Calibration Gate Report

- records: 357
- clean records: 301
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -350.92159090914004
- right_acceleration_px_s2: 444.4070365435372
- release_velocity_ratio_per_step: 0.037037037835496014
- screen_gravity_px_s2: 154.00347113609314
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 5.133
- one_step_y_mae_px: 13.646
- one_step_vx_mae_px_s: 41.905
- one_step_vy_mae_px_s: 111.319
- 10_step_x_mae_px: 55.889
- 10_step_y_mae_px: 783.015
- 10_step_windows: 126
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 3.326
- one_step_y_mae_px: 7.354
- one_step_vx_mae_px_s: 27.172
- one_step_vy_mae_px_s: 60.382

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
