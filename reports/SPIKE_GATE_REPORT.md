# Spike Mechanism Gate Report

日期：2026-07-31

## 範圍

本階段只完成尖刺碰撞、傷害、致死、事件、renderer、Oracle avoidance 與
calibration interface。一般 generator 仍不生成尖刺，沒有建立 mixed
curriculum，也沒有訓練模型。

## 設計

- `enable_spikes=false` 預設關閉。
- Spikes 必須搭配 `enable_health=true`，否則 config 拒絕。
- 每次有效尖刺落地扣 5 health segments。
- health 歸零時 `terminated=true`、reason=`health_depleted`。
- 事件：`spike_contact`、`damage`、必要時 `health_depleted`。
- 尖刺不觸發普通平台回血。
- `spike_damage_penalty_per_segment` 預設 0，機制 gate 不偷改 reward。
- 尖刺 renderer 使用獨立紅色。
- Oracle 在同層有 normal 候選時優先避開 spikes。
- Feature-on version：
  `ns-shaft-sim-v0.2+health-v1+spikes-v1`。
- `SpikeCalibration` 提供 damage segments 校正接口。

## Gate

| Gate | 結果 | 狀態 |
|---|---|---|
| Feature 預設關閉 | `false` | PASS |
| Dependency validation | spikes without health 被拒絕 | PASS |
| 100 non-lethal fixed landings | 12→7、damage −5、0 failures | PASS |
| 100 lethal fixed landings | 5→0、health_depleted、0 failures | PASS |
| Normal-heal interaction | 100/100 normal landing 8→9 | PASS |
| Oracle avoidance | 100/100 選同層 normal alternative | PASS |
| Observation/event/info | kind、health delta、terminal 正確 | PASS |
| Reward components | damage/death 可重算 | PASS |
| Renderer | red spike pixel test | PASS |
| Calibration interface | valid 套用、invalid 拒絕 | PASS |
| No-spawn feature equivalence | 100 seeds 完全相同 | PASS |

Health-only 與 spikes-enabled-but-not-spawned 的 100-seed baseline 都是平均
34.68 floors，terminal reasons 都是 top 57、bottom 39、time limit 4。

## 結論

Spike mechanism gate：**PASS**。

尖刺目前只可用於固定測試場景，尚未加入 generator、teacher dataset 或訓練。
下一個 curriculum 機制是輸送帶；仍需獨立 feature、fixed scenarios、
renderer、Oracle、calibration 與 feature-equivalence gate。
