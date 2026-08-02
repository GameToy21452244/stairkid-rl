# Conveyor v1 Gate Report

日期：2026-07-31

## 結論

**PASS（僅 mechanism gate）**。

本階段只完成左右輸送帶的落地速度、事件、observation/info、renderer、
Oracle normal-platform preference 與 calibration interface。一般 generator
仍不生成輸送帶，沒有建立 mixed dataset，也沒有訓練模型。

## 凍結規格

- `enable_conveyor=false` 預設關閉。
- kinds：`conveyor_left`、`conveyor_right`。
- landing velocity delta：左 −80、右 +80 px/s，受 max speed clipping。
- events：`conveyor_contact` 與方向 kind。
- renderer：左藍、右紫。
- 同層 normal alternative 存在時，Oracle 優先 normal。
- version：`ns-shaft-sim-v0.2+conveyor-v1`。

80 px/s 是 provisional mechanism value，沒有真實 telemetry 支持，不能標為
calibrated simulator fidelity。

## Gate 結果

| Gate | 樣本／條件 | 結果 |
|---|---:|---|
| Left velocity/event | 100 fixed seeds | PASS |
| Right velocity/event | 100 fixed seeds | PASS |
| Oracle normal preference | 100 fixed seeds | PASS |
| Feature disabled behavior | unit test | PASS |
| Direction renderer | pixel tests | PASS |
| Calibration validation | unit test | PASS |
| No-spawn equivalence | 100 seeds | PASS |

Feature off 與 enabled-but-not-spawned 的 baseline 平均皆 34.68 floors；
終止原因皆為 top 57、bottom 39、time_limit 4，episode results 完全相同。

可重現 artifact：`artifacts/conveyor_gate_v1.json`。

## 下一步

凍結 conveyor-v1，不將它加入 generator 或 training distribution。下一個
獨立 curriculum 機制為彈簧，需另行定義彈力、固定場景、renderer、Oracle、
calibration 與 no-spawn equivalence gate；不得同時實作翻板或啟動長訓。
