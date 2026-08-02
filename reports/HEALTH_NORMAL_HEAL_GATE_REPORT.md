# Health / Normal-platform Heal Gate Report

日期：2026-07-31

## 範圍

本階段只加入可校正血量、普通平台回血、observation/event/reward component、
HUD renderer、Oracle 固定場景與 feature-off regression gate。尖刺、輸送帶、
彈簧、翻板仍保持關閉，未加入訓練分布。

## 設計

- `enable_health=false` 為預設。
- max／initial health：12／12 segments。
- normal-platform heal：每次有效落地 +1。
- full health 不發出假的 `health_gained`。
- `health_gain_reward_per_segment` 預設 0，機制 gate 不偷改既有 reward。
- feature-on version：`ns-shaft-sim-v0.2+health-v1`。
- `HealthCalibration` 可覆寫 max、initial 與 heal segments。

## Gate

| Gate | 結果 | 狀態 |
|---|---|---|
| Feature flag 預設關閉 | `false` | PASS |
| 100 low-health fixed Oracle landing seeds | 100/100 正確 +1、0 failures | PASS |
| Full-health cap | 12→12，無假事件 | PASS |
| Observation/event/info | segments、delta、event 正確 | PASS |
| Reward component | 可重算，預設值 0 | PASS |
| Renderer | filled／empty HUD pixel test | PASS |
| Calibration interface | valid 套用、invalid range 拒絕 | PASS |
| Feature off/on full-health equivalence | 100 seeds 完全相同 | PASS |
| Existing normal physics | position／velocity／platform sequence 相同 | PASS |

Feature off/on 的 100-seed baseline 都是平均 34.68 floors，terminal reasons
完全相同：top 57、bottom 39、time limit 4。滿血且沒有傷害來源時，health
feature 不改變普通平台 policy、物理或 episode 結果。

## 結論

Health＋normal-platform heal mechanism gate：**PASS**。

本階段沒有訓練模型。下一個候選是尖刺，但必須另開獨立工作包，先完成
damage／death、固定場景、renderer、Oracle 與 calibration gate；不得同時混入
輸送帶、彈簧或翻板。
