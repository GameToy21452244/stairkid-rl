# Simulator v0.3 Oracle Robustness Gate Report

日期：2026-08-04
狀態：`FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT`

## 結論

`oracle-full-v7-receding-route-planner` 已依凍結 protocol 完成 test-first 實作，但在
全新 development 16000～16099 嚴重退化：reach-floor-10 只有 76%，低於固定 95%
門檻，也低於同批 v6 reference 的 96%。Gate 因此在 development 立即停止。

17000～17099 one-time holdout 完全未使用；observable route-intent holdout 也未執行。
不得調參後重跑這批 development 作新正式結論，也不得進 Simulator 特殊平台重驗、
Dataset 或 Student。

## 實作範圍

- 保留 v6 `cached` mode，確保既有 artifact 可重現；
- 新增顯式 opt-in `route_plan_execution="receding"`；
- 只有原 `should_plan` trigger 成立時才規劃；
- 每次只執行當下 plan 第一個 action，不保存其餘序列；
- trigger、12-step horizon、24 beam、score、signature、physics、generator與門檻均未改；
- policy version為`oracle-full-v7-receding-route-planner`；只屬privileged Oracle。

## Test-first Engineering Gate

舊程式先出現4個預期失敗（尚無`route_plan_execution`）；實作後確認：

- trigger前v7與v5 fallback action／target一致；
- trigger後action等於當下plan第一項；
- 不快取剩餘actions，下一decision重新規劃；
- snapshot、RNG、platform identity完整還原；
- horizon=12、beam=24、expanded nodes在固定上限；
- v6 cached行為與既有特殊平台／edge tests保留。

Formal Gate前相關41 tests及compileall PASS。

Formal Gate後完整回歸520 tests PASS（113.83秒）；compileall、artifact JSON、protocol／
source SHA-256 assertions與`git diff --check`均PASS。

## Development Gate

靜態 generator reachability、health safety、reproducibility全部PASS，沒有不可達或不安全
seed。正式同批比較如下：

| 指標 | v6 reference | v7 receding | 門檻／結果 |
|---|---:|---:|---|
| Mean deepest floor | 10.35 | 9.49 | 診斷退化 |
| Reach floor 3 | 100% | 100% | >=99%，PASS |
| Reach floor 10 | 96% | 76% | >=95%，**FAIL** |
| Reach10 vs v6 | — | −20 pp | 不低於v6，**FAIL** |
| Terminal target | 96 | 76 | 診斷 |
| Terminal bottom | 2 | 22 | 明顯退化 |
| Terminal top | 2 | 2 | 無改善 |
| Edge violations | 0 | 0 | 必須0，PASS |
| Max action share | 42% | 44% | 無collapse，PASS |

配對結果：75 seeds兩者都成功、3 seeds兩者都失敗、v7只救回1個v6 failure，卻讓
21個v6 successes變成failure。這否定了「在retired 7 failures救回4例即可泛化」的
假設。v7的新增失敗有20個bottom、1個top；主要表現為把成功軌跡轉成bottom death。

## Gate順序證據

- Source integrity：PASS。
- Development reachability：PASS。
- Development v6 reference：已執行。
- Development v7：FAIL。
- Holdout `used=false`，reachability／Oracle／observable結果皆`null`。
- Dataset、training、real game皆`false`。

## 判斷與下一步

v7候選正式 **REJECT**。程式保留為顯式opt-in以重現失敗artifact，但不得成為預設
Oracle或任何Teacher／Student來源。7-seed taxonomy只找到了局部open-loop風險，卻沒有
涵蓋receding重規劃造成的大量bottom failure，屬於已知失敗案例上的選擇偏差。

下一個允許工作只能使用已曝光的16000～16099做paired decision-trace audit，檢查21個
`v6 success → v7 failure`在首次action divergence後是否出現plan方向切換、短視窗score
不連續或離台承諾被重置。先凍結診斷協議，證據支持前不得提出第二個production候選，
更不得使用17000～17099。

## Artifact

- `artifacts/simulator_oracle_robustness_gate_v1.json`
- Frozen protocol：`reports/SIMULATOR_ORACLE_ROBUSTNESS_PROTOCOL.md`
- Taxonomy來源：`artifacts/simulator_oracle_failure_taxonomy_v1.json`
