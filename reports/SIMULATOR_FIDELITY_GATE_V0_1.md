# Simulator Fidelity Gate v0.1

- gate pass: **True**
- real: 17/325 landings (0.0523), 12/325 floors (0.0369)
- simulator: 150/2490 landings (0.0602), 150/2490 floors (0.0602)
- landing two-proportion z: -0.569
- floor two-proportion z: -1.698

## Gates

- [x] real_steps_at_least_300
- [x] simulated_steps_at_least_1000
- [x] landing_rate_two_proportion_abs_z_le_1_96
- [x] floor_rate_two_proportion_abs_z_le_1_96
- [x] fixed_seed_benchmark_100_episodes

此 gate 只允許固定預算 simulator learnability probe。它不允許 BC、
DAgger、RL 長訓或新增實機 rollout。
