# P4.0 State-Aliasing Audit

日期：2026-08-03T04:17:55.750310+08:00

狀態：**PASS**

## 結論

Causal deployable memory 對跨回合近鄰衝突有穩定且達門檻的改善，因此只解鎖 P4.1 的公平 S0/S1/S2/S3 smoke ablation；仍未授權長訓練。

本報告只使用已通過 Gate v11 的 10 回合實機 Teacher natural run，不送出任何遊戲
按鍵，也沒有啟動 Student 訓練。主資料共 10 回合、753
筆、每筆 268 維。動作數為
`{"RELEASE_ALL": 296, "LEFT": 222, "RIGHT": 235}`。

## 最重要的時間序發現

`controller_memory` 是 `policy.choose(observation)` 完成後才寫入 sidecar。同一步的
`previous_action` 已等於本步 label，`controller_phase` 也由本步 Teacher reason 產生；
把它直接當 Student 輸入會洩漏答案。因此：

- 正式比較使用 episode 內 `memory[t-1] -> decision[t]`；
- 每回合第 0 步使用空白／reset memory；
- 同一步 post-decision memory 只列為 leakage ceiling，完全排除 Gate；
- raw platform/track ID 全部排除，避免不可部署的 ID 對齊。

## 預先固定的 Audit protocol

- kNN：k=5，鄰居只能來自其他回合；
- 距離：各 feature z-score，observation 與 memory block 各佔 0.5；
- Gate：衝突相對下降至少 10%，paired episode bootstrap 95% CI 下界不得為負，
  並且 entropy 至少下降 0.05 bits 或 action accuracy 至少增加 3 percentage points；
- bootstrap：2000 次，seed=20260803。

## 整體結果

| representation | action disagreement | entropy (bits) | kNN action accuracy | memory dims |
|---|---:|---:|---:|---:|
| observation_only | 56.20% | 1.0402 | 48.07% | 0 |
| causal_action_history | 42.76% | 0.7806 | 65.34% | 14 |
| causal_target_context | 53.55% | 0.9887 | 52.46% | 26 |
| causal_phase_and_recovery | 52.80% | 1.0125 | 54.45% | 49 |
| causal_support_context | 49.75% | 0.9457 | 56.97% | 29 |
| causal_full_memory | 45.39% | 0.8529 | 61.09% | 121 |
| post_decision_leakage_ceiling | 11.42% | 0.2600 | 92.83% | 121 |

Causal full memory 的相對衝突改善為
**19.23%**，entropy 改善
**0.1873 bits**，accuracy 改善
**13.01 percentage points**。episode-level paired
bootstrap 的平均 disagreement 改善為 0.1192，95% CI
[0.0979, 0.1411]。

Post-decision leakage ceiling 的 disagreement 為
11.42%；這個數字只能顯示 sidecar 洩漏有多強，
不能作為模型可部署能力。

## Exact 與 near conflict

- 完全相同 observation：0 個重複群、
  0 個跨回合動作衝突群；
- round-to-3-decimal：0 個重複群、
  0 個跨回合動作衝突群；
- 每個 observation kNN 中出現不同 Teacher 動作的 query 已輸出至
  `artifacts/teacher_action_conflicts.csv`。

## Rare / control branch

| branch | rows | >=10 rows | observation disagreement | causal disagreement |
|---|---:|:---:|---:|---:|
| aligned | 206 | yes | 57.38% | 46.50% |
| brake | 40 | yes | 63.00% | 57.00% |
| conveyor | 25 | yes | 57.60% | 45.60% |
| flip | 97 | yes | 56.29% | 47.01% |
| launch | 13 | yes | 67.69% | 63.08% |
| move | 84 | yes | 60.48% | 40.24% |
| recovery | 67 | yes | 59.70% | 50.75% |
| special_escape | 46 | yes | 65.22% | 50.00% |
| spike | 38 | yes | 65.26% | 48.42% |
| spring | 56 | yes | 61.79% | 50.71% |
| support_departure | 281 | yes | 50.46% | 41.49% |
| wall_guard | 12 | yes | 53.33% | 38.33% |

少於 10 筆的 branch 僅列描述，不作方向性決策。branch 可重疊，例如 spike 同時可能是
special_escape 或其他 phase。

## Phase / target predictability

| target | kNN accuracy | neighbor agreement | entropy (bits) |
|---|---:|---:|---:|
| phase_from_observation | 42.23% | 35.67% | 1.2136 |
| phase_from_observation_plus_causal_memory | 52.86% | 45.39% | 1.0410 |
| target_kind_from_observation | 70.92% | 64.83% | 0.5440 |
| target_kind_from_observation_plus_causal_memory | 76.76% | 72.72% | 0.4500 |
| target_direction_from_observation | 45.68% | 42.60% | 1.0556 |
| target_direction_from_observation_plus_causal_memory | 58.57% | 51.24% | 0.9178 |

## Feature audit

- observation active / zero-variance dims：
  248 / 20；
- 重複 active column groups：0；
- 排除的 raw identifier fields：
  `["special_contact_episode_id", "special_escape_destination_platform_id", "special_source_platform_id", "support_departure_abort_source_id", "support_departure_destination_id", "support_departure_source_id", "support_platform_id", "target_platform_id"]`；
- causal full memory columns：121；
- observation 只保留 4-frame action history；本 run median loop rate 為
  5.814 Hz，約覆蓋
  0.688 秒，不足以代表 2–4 秒的長期控制狀態；
- `time_since_landing` 沒有直接欄位，目前只有 lagged support/aligned dwell proxy。

## Gate checks

- PASS：`source_gate_passed`
- PASS：`ten_episodes`
- PASS：`minimum_500_rows`
- PASS：`observation_dim_268`
- PASS：`finite_observations`
- PASS：`cross_episode_neighbors_only`
- PASS：`raw_track_ids_excluded`
- PASS：`post_decision_memory_excluded_from_gate`
- PASS：`relative_disagreement_reduction_at_least_10pct`
- PASS：`episode_bootstrap_ci_lower_nonnegative`
- PASS：`entropy_or_accuracy_supporting_improvement`

## Evidence boundary

這是 10 回合、單一 Teacher/controller 版本的描述性 audit。Simulator teacher dataset
沒有相同的逐步 controller-memory timeline，因此不能拿它替代本次 causal-memory 主分析。
本結果不等於 Student 成功率，也不允許直接進行長 BC/DAgger 或 RL。

## 實作驗證

- P4.0 targeted：5 passed；
- repository完整回歸：415 passed；
- compileall、artifact JSON/CSV count validation、`git diff --check`：PASS。
