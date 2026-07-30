# Training Roadmap

## 原則

每一階段都必須保留固定評估集、版本化 observation/reward、seed、設定、checkpoint
與結果摘要。前一 gate 未通過，不得以「再多訓練」取代診斷。

| 階段 | 工作 | 進入下一階段的 gate |
|---|---|---|
| 0. 稽核與安全 | 模組、資料、checkpoint、控制鏈、測試盤點 | 全部風險與未知量有文件；測試綠燈 |
| 1. 資料基礎 | transition writer、validator、quarantine、時間校正 | 無 schema error；episode/action/time continuity 可證明 |
| 2. Simulator v0 | normal platform、核心物理、共用觀測、benchmark | check_env；100k smoke；fixed seed；baseline 優於 random |
| 3. 模擬校正 | 用有限真實 telemetry 擬合動力與延遲 | 核心曲線誤差在預設容許範圍，且不靠 hazard 特例 |
| 4. BC | 只用 human／baseline_verified／corrected | 固定 seeds 上 action distribution 不塌縮，優於 baseline gate |
| 5. DAgger | 小批量 correction、版本化聚合 | correction rate 下降，未降低 safety metrics |
| 6. Residual | baseline action + bounded correction | 明確優於 baseline 且 correction 幅度受限 |
| 7. Double DQN / DQfD-lite | demo margin + TD，模擬器為主 | 多 seed 穩定、ablation 支持收益 |
| 8. 實機驗證 | 少量回合、確認／倒數／硬上限 | 只報告，不自動擴大 rollout |

## PPO 的位置

PPO 只允許：

- simulator v0 是否可學的短 probe；
- BC 初始化與隨機初始化的小型對照；
- 與離散 value-based 方法的固定預算比較。

PPO 不允許：

- 在真實遊戲逐步長訓；
- 續訓 action-collapsed checkpoint；
- 以不增加觀測／動作多樣性的方式反覆追加 timesteps。

## 目前停點

階段 0、1 完成；階段 2 的 v0.1 骨架、smoke、正式 benchmark 與 seeded
distribution gate 完成；階段 3 的 sample／一步／landing calibration 完成。
階段 3→4 之間的 P0／P1 simulator learnability probes 已通過。現在停在
Colab pipeline validation：pytest／check_env、vector throughput、
checkpoint／resume 與 video。BC、DAgger、Residual 與 DQfD 全部尚未進入，
長訓仍為 No-Go。
