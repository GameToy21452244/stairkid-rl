# Calibration Gate Report

- records: 187
- clean records: 155
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -479.99998927116394
- right_acceleration_px_s2: 308.363676071167
- release_velocity_ratio_per_step: 0.05185185457938783
- screen_gravity_px_s2: 77.25972021745892
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 3.298
- one_step_y_mae_px: 13.934
- one_step_vx_mae_px_s: 26.724
- one_step_vy_mae_px_s: 112.771
- 10_step_x_mae_px: 31.202
- 10_step_y_mae_px: 792.059
- 10_step_windows: 68
- 30_step_x_mae_px: None
- 30_step_y_mae_px: None
- 30_step_windows: 0

## Fitted one-step error

- one_step_x_mae_px: 2.186
- one_step_y_mae_px: 5.828
- one_step_vx_mae_px_s: 17.779
- one_step_vy_mae_px_s: 47.872

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
