# Flipping v1 Gate Report

日期：2026-07-31

## 結論

**PASS（僅 mechanism gate）**。

本階段完成翻板週期、碰撞、active observation/info、renderer、Oracle filtering
與 calibration interface。一般 generator 不生成 flipping，沒有建立 mixed
dataset，也沒有訓練模型。

## 凍結規格

- `enable_flipping=false` 預設關閉。
- kind：`flipping`。
- 暫定週期：active 1.0 秒、inactive 1.0 秒。
- active 可碰撞；inactive 直接穿過。
- observation/info 暴露 `active`；renderer 為 active 青色／inactive 灰色。
- Oracle 排除 inactive；同層 normal alternative 優先。
- version：`ns-shaft-sim-v0.2+flipping-v1`。

同步 1／1 秒是 provisional mechanism value，沒有真實 telemetry 支持，不能
標為 calibrated fidelity。

## Gate 結果

| Gate | 樣本／條件 | 結果 |
|---|---:|---|
| Active collision/event | 100 fixed seeds | PASS |
| Inactive passthrough | 100 fixed seeds | PASS |
| Oracle normal preference | 100 fixed seeds | PASS |
| Feature disabled behavior | unit test | PASS |
| Active/inactive renderer | pixel tests | PASS |
| Calibration validation | unit test | PASS |
| No-spawn equivalence | 100 seeds | PASS |

Feature off 與 enabled-but-not-spawned 的 baseline 平均皆 34.68 floors；
終止原因皆為 top 57、bottom 39、time_limit 4，episode results 完全相同。

可重現 artifact：`artifacts/flipping_gate_v1.json`。

## 下一步

五項特殊機制皆已完成工程 gate。下一階段先選單一特殊平台，以低比例加入
generator，為翻板增加 seeded phase offset，重新通過 3-floor reachability、
Oracle 與 baseline gates；通過後才生成新版 Teacher Dataset，不直接混合
全部平台或啟動長訓。
