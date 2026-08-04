# Simulator Observation-Schema Probe Report

日期：2026-08-03  
最終狀態：**INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE**

## 結論

本輪沒有達到進入新 Simulator Teacher、fresh reliability、Dataset v2 或 Student
訓練的門檻。固定的 launch-handoff counterfactual 在 400 個獨立 episodes 中只改善
1 個、退化 29 個、365 個終局不變；另 5 個從頭到尾沒有 action divergence，補充重播
確認 base/candidate 最深樓層也完全相同。這不是「需要更多 epochs」的問題，而是待學的
介入幾乎沒有正向 label，且該介入本身整體有害。

因此停止 launch-handoff 系列，不新增 heuristic、不使用保留的 6000～6099 fresh
seeds，也不產生 Dataset v2。下一個合理工作改為蒐集小型、同步且可重建的真機
alignment packet，先確認模擬器 target／action timing 與真機困難分支是否同義。

## 凍結設計與範圍

- 執行前協定：`reports/SIMULATOR_OBSERVATION_SCHEMA_PROBE_PROTOCOL.md`
- 協定 SHA-256：`e49c52075bea8e8974f86454d22394f0304613353546988a6682ab0c048bee3c`
- development：7000～7199；validation：7200～7299；test：7300～7399。
- base：`departure_delayed`；counterfactual：
  `departure_delayed_launch_handoff`。
- 只記錄 decision 前、真機可重建的欄位；沒有 raw platform identity、deepest floor
  或 privileged simulator phase 作特徵。
- 本輪沒有訓練、沒有修改 controller action、沒有開啟原版遊戲。
- test split只執行本次一次；6000～6099完全未使用。

Machine-readable artifact：
`artifacts/simulator_teacher_observation_schema_probe_v1.json`。

## Closed-loop 結果

| 指標 | Delayed2 base | Launch-handoff | 差值 |
|---|---:|---:|---:|
| episodes | 400 | 400 | 0 |
| mean deepest floor | 9.0500 | 8.6125 | -0.4375 |
| median | 10.0 | 10.0 | 0.0 |
| Q25 | 10.0 | 8.0 | -2.0 |
| CVaR25 | 5.14 | 4.04 | -1.10 |
| reach floor 10 | 76.25% | 69.25% | -7.00 pp |
| bottom death | 23.75% | 30.75% | +7.00 pp |
| health death | 0% | 0% | 0 pp |
| reversal／100 steps | 8.2825 | 9.6235 | +1.3410 |

相較先前 60-seed Gate，本次更大的獨立分區得到相同方向：handoff 降低 reach、提高
bottom death，並惡化 lower tail 與反轉。不能以單一 seed 7358 的改善推翻整體結果。

## First-divergence 證據

| split | improved | regressed | unchanged | 無 action divergence |
|---|---:|---:|---:|---:|
| development | 0 | 17 | 181 | 2 |
| validation | 0 | 5 | 94 | 1 |
| test | 1 | 7 | 90 | 2 |
| 合計 | 1 | 29 | 365 | 5 |

- 共有 395/400 episodes 產生首次 action divergence。
- 384/395 divergence rows 有可見且成功配對的 target geometry（97.22%）。
- 唯一改善是 test seed 7358；development 完全沒有 improved reference。
- 無 divergence seeds 是 7082、7168、7205、7301、7377；補充重播的
  base/candidate floors 分別為 `6/6`、`2/2`、`2/2`、`5/5`、`1/1`。

## Schema Gate

四個固定 schema 的 feature dimensions 為 25／35／43／53。所有 deployable 欄位均
完整有限，artifact 也沒有 raw identity 或 privileged feature；但 evidence Gate 已先
失敗：changed只有30（門檻40）、improved只有1（門檻10），validation沒有 improved，
test也只有1個 improved。由於 development reference 只有單一類別，5-NN balanced
accuracy及opposite-neighbor rate均為 **unavailable**，不能把 `null` 誤寫成0分或PASS。

### 協定／實作偏差

凍結協定將 screen-coordinate vx/vy 列入 `phase_basic`；實際執行版本的
`phase_basic`只含 vy，vx只出現在`causal_action`與`combined`。這是必須公開記錄的
protocol deviation，因此本 artifact 不得被引用為「basic vs combined可分性」的正式
比較。沒有重跑 test split，避免事後修規格再重用 holdout。

此偏差不改變本輪停止結論：improved/regressed、closed-loop reach、bottom、Q25、CVaR
都由固定 controller trajectories 決定，feature vector不參與 action；而 Gate 在進入
任何分類指標前就因正向介入只有1例而失敗。

## Gate 決策

| Gate | 結果 | 理由 |
|---|---|---|
| 400/400首次分歧 | FAIL | 395/400；其餘5個同終局且同最深樓層 |
| deployable fields完整有限 | PASS | 395 rows均可建向量 |
| 無raw identity／privileged input | PASS | artifact掃描通過 |
| changed ≥ 40 | FAIL | 30 |
| improved／regressed各 ≥ 10 | FAIL | 1／29 |
| validation兩類各 ≥ 2 | FAIL | 0／5 |
| test兩類各 ≥ 2 | FAIL | 1／7 |
| held-out separability | NOT EVALUABLE | development沒有 improved class |
| 新Teacher候選 | BLOCKED | 上游Gate未通過 |
| fresh100／Dataset v2／Student | BLOCKED | 上游Gate未通過 |

## 下一個最小實驗

不再對 launch delay、handoff threshold 或同一組 simulator seeds 做參數搜尋。下一個
實驗先建立少量真機 alignment packet，每筆需同步保存：

- 原始影格／解析後 observation 與 action command/apply/next-observation timestamps；
- decision 前 previous action、held duration、landing recency及causal state；
- Teacher選定 target 的safe interval、signed offset、kind與confidence；
- ordinary edge hesitation、spring、spikes、wall recovery各自的完整短序列；
- 人類或已驗證 Teacher 的實際 action，以及可核對的episode boundary與終局。

單純影片可供視覺查證，但沒有時間對齊的 action label，不能單獨成為 sequence Teacher
dataset。取得上述封包後，先做 simulator/real target與timing alignment audit；只有觀測
語意對齊且預先凍結的新 Gate 通過，才設計一個全新的 hierarchical target＋low-level
controller 候選。這需要下一次由使用者明確開啟遊戲並監督 bounded run，本輪不自動執行。

## 驗證

- Schema／Teacher相關：14 tests passed in 6.04s。
- 完整回歸：457 tests passed in 162.51s。
- Artifact JSON parse、協定 SHA、source fingerprint、compileall及`git diff --check`：
  PASS。
