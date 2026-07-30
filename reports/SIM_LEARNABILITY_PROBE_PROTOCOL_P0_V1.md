# Simulator Learnability Probe Protocol P0 v1

## Scope

離線 simulator-only pipeline smoke。不得載入舊 PPO checkpoint，不接真實
executable，不送 Windows input，不自動擴大 budget。

## Frozen protocol

- experiment id：`sim_learnability_p0_v1`
- train seed：31001
- held-out eval seeds：41001–41020
- PPO：4 vector envs、4096 total steps、128-step rollout
- SB3-DQN：4096 steps；明確不是 Double DQN
- 每個演算法 wall limit：60 秒
- evaluation：deterministic、每 seed 最多 120 steps
- baselines：random、RELEASE-only、`SafePlatformPolicy`
- action share ≥ 0.98：collapse

## P0 pass

1. baseline mean floors 必須高於 random；
2. PPO／DQN pipeline 必須完成並保存模型；
3. 至少一個 learner：
   - 不 collapse；
   - mean floors 不低於 random；
   - mean return 不低於 random。

若 P0 FAIL，不追加 timesteps；先診斷 reward、observation 與 action distribution。
P0 PASS 也只允許設計 bounded P1 multi-seed probe，不代表可開始長訓。
