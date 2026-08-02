# Spring v1 Gate Report

日期：2026-07-31

## 結論

**PASS（僅 mechanism gate）**。

本階段只完成彈簧落地速度、事件、observation/info、renderer、Oracle
normal-platform preference 與 calibration interface。一般 generator 不生成
spring，沒有建立 mixed dataset，也沒有訓練模型。

## 凍結規格

- `enable_spring=false` 預設關閉。
- kind：`spring`。
- landing jump velocity：190 px/s；普通平台為 95 px/s。
- events：`spring_contact`、`spring_bounce`。
- renderer：橘色。
- 同層 normal alternative 存在時，Oracle 優先 normal。
- version：`ns-shaft-sim-v0.2+spring-v1`。

190 px/s 是 provisional mechanism value，沒有真實 telemetry 支持，不能標為
calibrated simulator fidelity。

## Gate 結果

| Gate | 樣本／條件 | 結果 |
|---|---:|---|
| Stronger bounce/event | 100 fixed seeds | PASS |
| Oracle normal preference | 100 fixed seeds | PASS |
| Feature disabled behavior | unit test | PASS |
| Renderer | pixel test | PASS |
| Calibration validation | unit test | PASS |
| No-spawn equivalence | 100 seeds | PASS |

Feature off 與 enabled-but-not-spawned 的 baseline 平均皆 34.68 floors；
終止原因皆為 top 57、bottom 39、time_limit 4，episode results 完全相同。

可重現 artifact：`artifacts/spring_gate_v1.json`。

## 下一步

凍結 spring-v1，不將它加入 generator 或 training distribution。下一個獨立
curriculum 機制為翻板，需定義 active/inactive 週期、碰撞時序、renderer、
Oracle、calibration 與 no-spawn equivalence gate；不得啟動長訓。
