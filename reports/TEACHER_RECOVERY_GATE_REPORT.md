# Teacher Recovery and Floor-10 Reliability Gate Report

日期：2026-07-31

## 結論

Teacher-observable recovery 與普通下樓梯 floor-10 reliability Gate 均已通過。
正式未參與診斷的 holdout seeds 1800～1899，低血量與滿血到達第 10 層皆為
94%，deepest-floor Q25 皆為 30，0 health death，超過預先固定的 90% 門檻。

本輪只修改可觀測規則 Teacher，未啟動 BC、DAgger、PPO、DQN 或真實遊戲。

## 指標語意修正

原 `success_rate_floor_10` 計算的是 `floor_descended` 事件數達 10 的比例，不是
角色實際到達 floor index 10。策略可以合法跳層，因此事件數會低估進度。現在：

- 保留 `success_rate_floor_*` 作歷史相容的 successful-descents 指標；
- 新增 `deepest_floor`、`reach_rate_floor_*`、`mean_deepest_floor`、
  `median_deepest_floor` 與 `deepest_floor_quantile_25`；
- reliability 與 checkpoint Gate 一律使用 `reach_rate_floor_10`；
- 舊 summary 沒有新欄位時才 fallback 到歷史欄位。

修正指標後，尚未做可靠度修正的 1600～1699 實際 reach-floor-10 是 92%，
不是事件計數顯示的 88%。初次 1700～1799 audit 則為 87%（事件計數 84%），
仍確實低於 90%，所以沒有因指標修正而跳過策略問題。

## 原因與修正

失敗重播確認兩個可泛化原因：

1. 畫面中已有下一個平台，但保守 reachability／最小垂直間距暫時判定不可達時，
   Teacher 會過早 `RELEASE_ALL`；現在會朝可見安全平台靠近，沒有安全平台且
   health 足夠時才把尖刺當作避免必然落底的緊急候選。
2. 落地反彈後的 `launch_escape` 原本只朝當前平台最近邊緣移動，可能與下一層
   平台方向相反；現在優先朝畫面內下一個 recovery／safe／可承受 spike 平台
   的方向離台，沒有後續可見目標時才沿用最近邊緣規則。

低 health 時仍只把 normal 視為回血平台，保留 direction-change braking；
health 不足時不會把尖刺列為緊急落點。新增單元測試涵蓋上述三項安全邊界。

## 固定 Gate 結果

| Seed partition | 用途 | reach floor 10 | successful descents 10 | mean deepest floor | deepest-floor Q25 | bottom | health death | Gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1600～1699 | development | 95% | 93% | 44.42 | 29.00 | 10 | 0 | PASS |
| 1700～1799 | diagnosis/audit | 96% | 93% | 43.26 | 29.00 | 12 | 0 | PASS |
| 1800～1899 | untouched holdout | 94% | 94% | 47.31 | 30.00 | 11 | 0 | PASS |

三組 low-health 與各自 full-health reference 的 reach-floor-10 相同；Q25 均
通過至少保留 reference 80% 的門檻。Recovery safety/non-regression sub-gate
全部通過。1700～1799 曾用於失敗分類，
因此第二次結果只能當診斷證據，不能冒充 holdout；正式泛化結論只取一次執行的
1800～1899。

## Reliability-first checkpoint protocol

候選 checkpoint 排序固定為：no collapse／no health death、reach-floor-10、
fewer bottom deaths、deepest-floor Q25、median deepest floor、rollout Gate、
mean deepest floor，最後才以 validation loss／較早 epoch tie-break。

Final Gate 另要求 reach-floor-10 至少保留 baseline 90%、bottom death 不高於
baseline、deepest-floor Q25 至少保留 baseline 80%。本輪尚未觸發新訓練。

## 下一步

Reliability blocker 已解除。下一階段可凍結新的 Spike Teacher Dataset 版本與
全新 dataset／selection／final seed partitions，再執行 bounded BC0；不得重用
已作 evidence 或診斷的 1500～1899。第二輪舊 Spike DAgger、長訓練與實機
rollout 仍維持 No-Go。

## 驗證

- `python -m pytest -q`：296 passed in 68.51s。
- 三組 recovery Gate artifact 均可解析。
- 未啟動遊戲、未送真實輸入、未訓練模型。
