# Simulator Learnability Probe P0 v1

- probe pass: **True**
- train seed: 31001
- timesteps per algorithm: 4096
- evaluation: 20 held-out seeds × 120 max steps

## Results

| Candidate | Floors | Return | Length | Max action share | Collapse |
|---|---:|---:|---:|---:|---:|
| random | 0.700 | -4.436 | 17.1 | 0.354 | False |
| release | 0.900 | -4.246 | 19.1 | 1.000 | True |
| baseline | 1.650 | -3.526 | 25.9 | 0.523 | False |
| ppo | 1.000 | -4.150 | 20.0 | 0.740 | False |
| sb3_dqn | 1.050 | -4.103 | 20.6 | 0.491 | False |

## Gates

- [x] baseline_mean_floors_gt_random
- [x] ppo_pipeline_complete
- [x] dqn_pipeline_complete
- [x] at_least_one_learner_pass

Next: Design bounded P1 multi-seed probe.

SB3-DQN is explicitly not Double DQN.
