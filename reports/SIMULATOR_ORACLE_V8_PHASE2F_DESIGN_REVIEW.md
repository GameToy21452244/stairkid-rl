# Simulator Oracle v8 Phase 2F Offline Failure Design Review

日期：2026-08-04  
狀態：`COMPLETE`  
Formal v8結果：`FAIL_STOP_V8_DEVELOPMENT`（不變）  
專案狀態：`BLOCKED_WITH_EVIDENCE`

## 1. 範圍與證據完整性

本輪只重播16002、16030的Simulator snapshot並建立離線診斷工具；沒有修改production
Oracle、planner、physics、generator、score、horizon、beam或凍結protocol。沒有遊戲輸入、
訓練、Dataset、Student checkpoint或Colab bundle。17000～17099維持`used=false`。

凍結證據在診斷開始與主artifact建立時均通過hash檢查：

| Frozen item | SHA-256 |
|---|---|
| v8 formal development artifact | `b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166` |
| v8 protocol | `78df06c393ff8123d559a98657fadbd791eee3ce3f532aa6a3fabe2cc3f5289e` |
| Oracle production source | `18018669ed6e97056be20bf07642afd766dfa0b3c0bf4e232e476c26c295cbbb` |
| Bounded planner source | `c52671e08c607d919e8c83b5f63b5c0faaf8b92541322996bdc736b66444a394` |

Formal both-failure seeds與artifact一致：top為16002、16030；bottom為16009、16086。

## 2. 核心結論

v8的20次`terminal_risk_replan`確實執行，另外有2次terminal-risk entry search；22/22
selected actions也確實寫入並送入Simulator。但每次共享24-beam搜尋都重新產生與v6
cached suffix完全相同的RELEASE序列：

- 22/22 first action與v6 cache相同。
- `SAME_FIRST_ACTION_DIFFERENT_SUFFIX`為0/22；不是首動作相同、後綴不同。
- 100/100 formal episodes的完整action sequence相同。
- state、RNG、platform identity snapshot/restore與v6/v8每步state equality全部PASS。

真正原因是共享beam的中間剪枝。按首動作隔離、但仍使用相同12-step／24-beam bounds時，
RIGHT可產生存活／進樓方案；把這些方案的精確prefix放回production共享beam追蹤，14/14條
最終可完整reach10的路徑都在depth 4被剪掉。它們當時的unique rank為35～39，低於
beam=24的保留範圍，且score全低於當層cutoff。最終selector因此從未看見這些成功候選，
只能從剩餘terminal candidates中再次選出RELEASE。

主要分類：

- `BEAM_PRUNING_LIMITATION`
- `SURVIVING_CANDIDATE_EXISTS_BUT_SCORE_REJECTS_IT_AT_INTERMEDIATE_PRUNING`

限定解讀：`NO_SURVIVING_CANDIDATE_WITHIN_CURRENT_SEARCH`對production共享beam的最後輸出成立，
但不是相同12/24 bounds或物理上無解；成功分支先被剪掉。`SCORE_REJECTS_IT`也只在
intermediate beam ranking成立，不是final completed-candidate comparison選錯。

以下分類由證據排除：

- `TRIGGER_TOO_LATE`
- `SAME_FIRST_ACTION_DIFFERENT_SUFFIX`
- `REPLAN_RESULT_OVERWRITTEN_OR_NOT_COMMITTED`
- `SNAPSHOT_OR_RESTORE_SEMANTIC_ISSUE`
- `HORIZON_LIMITATION`
- `FAILURE_NOT_REPAIRABLE_BY_ACTION_PLANNING`

## 3. Top failures與Trigger Timing

| Seed | Formal結果 | v8 entry | 最後可救step | 首個持續無解step | Entry領先無解 | 可救首動作 | 根因 |
|---:|---|---:|---:|---:|---:|---|---|
| 16002 | floor 5 top | 39 | 46 | 47 | 8 decisions | RIGHT | depth-4 shared-beam pruning |
| 16030 | floor 7 top | 51 | 56 | 57 | 6 decisions | RIGHT | depth-4 shared-beam pruning |

因此binary terminal flag沒有晚於survival margin；它在兩個failure分別早8與6個decision
steps出現。Raw artifact中`decisions_from_last_rescuable_to_v8_entry`的負號表示entry早於
last-rescuable step，不表示lag。沒有證據支持以更早threshold修復本問題。

每個trigger的player／support狀態、cached suffix、terminal原因、三種first-action候選的
score、terminal step、deepest floor、survival、headroom、landing／support結果、production
選擇、commit與snapshot結果，均保存在per-trigger JSON；CSV提供扁平索引，SVG顯示時間線。

## 4. Forced-first-action反事實

共審查22個terminal-plan calls × RELEASE／LEFT／RIGHT = 66個固定首動作搜尋：

- 18個分支在相同12/24 bounds內nonterminal或完成floor progress。
- 14個不同於production的首動作，commit該隔離搜尋分支後再接回fresh frozen v8，最終
  完整reach floor 10；全部為RIGHT。
- 16002的step 39～46共8個可完整救回；最終deepest floor 10～14。
- 16030的step 51～56共6個可完整救回；最終deepest floor均14。
- production在上述14個trigger全部選RELEASE。
- 沒有「不同第一步只延後死亡」案例；這14個是完整成功，不只是terminal step後移。

這是`不同第一步可救回`的直接證據，但仍只是development-seed離線counterfactual，不能
改判v8 PASS，也不能當作新候選的formal development結果。

## 5. Horizon／Beam最小診斷

依限制，只有當某trigger在三個forced-first 12/24 branches全為terminal時才跑extended
diagnostic；已存在survivor的repairable states不做擴大搜尋。

| Diagnostic | 適用的晚期all-terminal calls | Survivor |
|---|---:|---:|
| 12-step／24-beam formal bound | 8 | 0 |
| 24-step／24-beam | 8 | 0 |
| 12-step／96-beam | 8 | 0 |
| 24-step／96-beam | 每seed最後1個，共2 | 0 |

Horizon不是主因：成功方案已在12 steps內進樓並可完整reach10；增加到24也沒有救回已進入
all-terminal的晚期states。Beam pruning是主因，但不能從本輪斷言「beam=96即可修復」：
規則不允許對已有forced survivor的repairable state跑12/96，而rank 35～39只證明beam 24
會剪除該prefix，不證明加寬後路徑能一路留下。結構化first-action lane比單純放大beam有
更直接證據。

Extended runs因從接近terminal的states開始而大量early-stop，observed runtime不能公平
推估一般成本。理論search cap相對12/24為：24/24約2倍、12/96約4倍、24/96約8倍；
完整observed nodes/runtime保留在per-trigger artifact。

## 6. 候選方向判定

| 方案 | 判定 | 主要理由 | v7式switch風險 | Magic threshold | Real alignment可否校正 |
|---|---|---|---|---|---|
| A Uncertainty-aware event-triggered cached planner | `REJECT` | 本次為deterministic search pruning，非uncertainty；trigger已夠早 | 高 | 是 | 只可部分校正pose/cadence，現有audit仍FAIL |
| B Survival-margin trigger | `REJECT` | trigger早6～8步；margin仍會繼承shared-beam錯誤 | 高 | 是 | 可換算時間尺度，不能驗證margin正確性 |
| C Score function修正 | `INSUFFICIENT_EVIDENCE` | score確實造成中間剪枝，但尚無非magic feature/weight，且可能破壞96 successes | 中高 | 目前是 | 只能限制物理scale，無privileged ranking label |
| D Forced first-action diversity／branch preservation | `SUPPORTED_FOR_NEW_PROTOCOL` | 同bounds產生14個完整救回；結構性保留lane直接對應根因 | 中 | 否 | 根因不依賴packet；後續可校正cadence/dynamics |
| E 增加horizon | `REJECT` | 12步內已有救回；24步不救late states | 中 | 否 | 只能校正秒數，不能修剪枝 |
| F 增加beam | `INSUFFICIENT_EVIDENCE` | rank 35～39提示可能有用，但未證明一路保留且成本上限約4倍 | 中 | 否，屬算力超參數 | 不可校正beam width |
| G Commitment／cooldown／hysteresis | `INSUFFICIENT_EVIDENCE` | 可作D的switch safeguard，但v8目前零inflation，且單獨不會恢復RIGHT branch | 低～中 | 是 | 可換算時間，不能定義安全window |

方案D的最小可驗證實作應只有一個production變因：在terminal-only search中按
RELEASE／LEFT／RIGHT保留first-action lanes，再以預先凍結的commit語意選擇一次；所有
non-terminal paths維持v6。新protocol必須保留reach/tail/bottom/safety/reproducibility、
v6 success non-regression、direct與RELEASE-bridged reversals、action-switch inflation Gate。

任何獲准的新production候選都必須使用全新partition。建議在seed ledger確認後，另凍結
18000～18099 development與19000～19099 one-time holdout；本review沒有批准、生成或使用
這些seeds，也沒有轉用17000～17099。

## 7. 科學判斷

選擇A：v8是安全但無效的no-op candidate，正式淘汰，只保留重現用途。

`repair_at_least_one_top_failure`不是本次可事後放寬的過嚴Gate。它正確辨識v8沒有任何
因果改善，而且同一12/24 bounds下的branch-preserved counterfactual已實際救回兩個top
failures。沒有足夠證據採用B，也沒有足夠證據把privileged Oracle Gate從Student上游
前置條件移除。

證據足以建立一份全新的、只審查方案D的protocol；不等於方案D已PASS，更不授權立即
實作production、跑development或使用holdout。

## 8. Artifacts

- 主結論：`artifacts/simulator_oracle_v8_phase2f_review_v1.json`
- 完整per-trigger：`artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.json`
- Trigger索引：`artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.csv`
- Trigger時間線：`artifacts/simulator_oracle_v8_phase2f_trigger_timeline.svg`
- 完整episode counterfactual：`artifacts/simulator_oracle_v8_phase2f_counterfactuals_v1.json`
- Shared-beam pruning trace：`artifacts/simulator_oracle_v8_phase2f_branch_pruning_v1.json`

SVG已足以顯示trigger／可救窗口／不可避免點，故未生成不必要的MP4。

## 9. 下一步限制

1. 先撰寫並審查terminal-only first-action branch-preservation的新protocol與seed ledger。
2. 經使用者另行批准後，才可test-first實作唯一候選；不得沿用v8結果或邊跑邊改。
3. 新development PASS前，17000～17099與任何新holdout、Dataset、Student、Colab及實機
   均維持blocked。
