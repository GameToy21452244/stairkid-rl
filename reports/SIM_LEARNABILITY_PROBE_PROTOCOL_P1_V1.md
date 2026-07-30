# Simulator Learnability Probe Protocol P1 v1

## Scope

P0 通過後的離線 multi-seed confirmation。所有模型從零初始化，不續訓 P0，
不接真實 executable，不使用舊 PPO checkpoint。

## Frozen protocol

- experiment id：`sim_learnability_p1_v1`
- fresh train seeds：31011、31012、31013
- held-out eval seeds：41001–41020
- PPO 與 SB3-DQN：每 seed 8192 steps
- 每次訓練 wall limit：60 秒
- evaluation：deterministic、每 seed 最多 120 steps
- baselines：random、RELEASE-only、`SafePlatformPolicy`
- action share ≥ 0.98：collapse
- LEFT 與 RIGHT 各至少占 2%，否則視為 directional coverage failure

## P1 pass

至少一個演算法必須同時：

1. 三個 train seeds 都不 collapse；
2. 至少 2/3 seeds 的 floors 與 return 不低於 random，且左右方向都有覆蓋；
3. 三 seed 平均 floors 至少高於 random 0.2；
4. 三 seed平均 return 不低於 random。

通過後停止本機擴訓，下一步是 Colab runtime／throughput／checkpoint／video
驗證。P1 不授權長訓、BC、DAgger 或真實遊戲 rollout。
