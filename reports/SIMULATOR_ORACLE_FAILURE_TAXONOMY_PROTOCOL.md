# Simulator Oracle Failure Taxonomy Protocol

日期：2026-08-04
狀態：`EXECUTED_AS_FROZEN`

## 目的與邊界

`artifacts/simulator_observable_route_intent_gate_v1.json` 的第一次正式
holdout 已依規格停止在 `FAIL_STOP_ORACLE_HOLDOUT`：Oracle-full v6 在
14000–14099 的 reach-floor-10 為 0.93，低於 0.95。這份 protocol 只分析
已經曝光且永久退休的 7 個失敗種子，不產生新的正式 Gate 結論，也不得把
這 7 個種子重新當成 holdout。

固定失敗案例如下：

| seed | deepest floor | terminal |
|---:|---:|---|
| 14005 | 7 | bottom |
| 14013 | 6 | top |
| 14025 | 9 | top |
| 14057 | 3 | bottom |
| 14060 | 7 | top |
| 14061 | 9 | bottom |
| 14065 | 7 | bottom |

## 預先限定的診斷矩陣

所有 rollout 固定使用 Simulator v0.3 edge-fidelity config、10 Hz、最多
600 steps、目標第 10 層。除下列差異外，不更動 physics、generator 或
Oracle v5 fallback：

| mode | 規劃觸發 | horizon / beam | 動作執行 |
|---|---|---:|---|
| `current_v6` | 原 `should_plan` | 12 / 24 | 快取整段 plan（正式失敗重現） |
| `receding_current_trigger` | 原 `should_plan` | 12 / 24 | 每個 decision 只執行 plan 第一個 action |
| `always_receding` | 每個 decision | 12 / 24 | 每個 decision 重新規劃並只執行第一個 action |
| `extended_always_receding` | 每個 decision | 24 / 96 | 每個 decision 重新規劃並只執行第一個 action |

最後一項只是固定上限的壓力測試，不是可直接發布的候選策略。所有 planner
呼叫都必須 restore simulator snapshot；單次搜尋的 expanded nodes 必須不
超過 `3 * horizon * beam_width`。

另以相同 14000–14099 執行靜態 generator reachability / health-safety
checker，判斷 Gate failure 是否已被現有 generator checker 認定為不可達。

## 分類規則

每個 seed 同時記錄 phenotype 與第一個能救回 reach-floor-10 的反事實：

- `pre_trigger_bottom`：正式 v6 在死亡前從未產生 route plan。
- `search_found_no_survival`：最後一個 plan 預測 terminal，且沒有預測跨層。
- `post_plan_bottom`：plan 曾預測跨層，之後仍 bottom death。
- `other_current_failure`：不符合前三項，保留原始 evidence。

反事實責任依固定優先序判定：

1. `receding_current_trigger` 救回：`open_loop_execution`。
2. 僅 `always_receding` 救回：`late_trigger`。
3. 僅 `extended_always_receding` 救回：`bounded_search_capacity`。
4. 皆未救回：`unresolved_bounded_search`。

這些分類只表示在固定反事實下的因果線索，不等於能對未見種子泛化。

## 決策規則

- 診斷完成前不得修改 production Oracle、candidate 或 Gate 門檻。
- 若存在單一、較小的預先限定改動可救回所有或明確多數案例，才可把它寫入
  新 robustness protocol；仍須使用全新 development / holdout seeds 驗證。
- 若結果分裂或 extended mode 仍普遍失敗，標記
  `INSUFFICIENT_EVIDENCE_STOP`，先設計更小的補充實驗，不可直接調 score。
- 新 protocol 不得再使用 13000–14099；新的 holdout 只能執行一次。
