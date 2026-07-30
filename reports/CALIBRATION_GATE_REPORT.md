# Calibration Gate Report

- records: 99
- clean records: 81
- gate pass: **False**

## Estimates

- left_acceleration_px_s2: -479.99998927116394
- right_acceleration_px_s2: 639.9999856948853
- release_velocity_ratio_per_step: 0.31904762612757115
- screen_gravity_px_s2: 104.72726821899414
- effective_to_next_observation_ms_median: 93.99999999914144

## Current simulator one-step error

- one_step_x_mae_px: 4.762
- one_step_y_mae_px: 13.877
- one_step_vx_mae_px_s: 39.301
- one_step_vy_mae_px_s: 113.792

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
- [ ] ten_and_thirty_step_rollout_measured

未通過全部門檻前，不開始 learnability probe、BC 或 RL 長訓。
