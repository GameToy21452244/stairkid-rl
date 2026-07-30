# Simulator Learnability Probe P1 v1

- probe pass: **True**
- train seeds: [31011, 31012, 31013]
- timesteps per algorithm/seed: 8192
- held-out eval seeds: 20

## Baselines

| Candidate | Floors | Return | Collapse |
|---|---:|---:|---:|
| random | 0.700 | -4.436 | False |
| release | 0.900 | -4.246 | True |
| baseline | 1.650 | -3.526 | False |

## Learners

| Algorithm | Train seed | Floors | Return | Max share | Collapse |
|---|---:|---:|---:|---:|---:|
| ppo | 31011 | 1.500 | -3.675 | 0.477 | False |
| ppo | 31012 | 1.950 | -3.243 | 0.519 | False |
| ppo | 31013 | 0.900 | -4.246 | 0.650 | False |
| sb3_dqn | 31011 | 1.000 | -4.151 | 0.483 | False |
| sb3_dqn | 31012 | 1.200 | -3.959 | 0.418 | False |
| sb3_dqn | 31013 | 1.300 | -3.861 | 0.536 | False |

## Gates

- [x] baseline_mean_floors_gt_random
- [x] all_training_runs_completed
- [x] at_least_one_algorithm_pass
- ppo: pass=True, mean floors=1.450, mean return=-3.722
- sb3_dqn: pass=True, mean floors=1.167, mean return=-3.990

Next: Stop local budget expansion; validate Colab runtime.

SB3-DQN is explicitly not Double DQN.
