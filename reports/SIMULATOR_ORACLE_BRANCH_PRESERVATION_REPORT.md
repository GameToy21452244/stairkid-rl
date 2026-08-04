# Simulator Oracle Branch-Preservation Formal Development Report

日期：2026-08-04  
狀態：`FAIL_STOP_BRANCH_PRESERVATION_DEVELOPMENT`  
總體：`BLOCKED_WITH_EVIDENCE`

## 1. Gate與執行範圍

依凍結protocol從頭執行18000～18099，共100個paired v6／branch-preserving episodes，並
完成兩者duplicate replay。Primary v6有4個top failures，因此沒有啟用條件擴充
18100～18199。19000～19099 one-time holdout與17000～17099均未使用。

執行前source、protocol、protocol artifact與seed-ledger hashes全部PASS。沒有啟動遊戲、
Dataset、Student或training。Formal artifact為write-once：
`artifacts/simulator_oracle_branch_preservation_development_v1.json`，SHA-256
`e4952a8332f7c2a25acb564e28a8b47b9b733e4c4bb073f19eade79501cd9758`。

## 2. Formal metrics

| Metric | v6 | Candidate | 判定 |
|---|---:|---:|---|
| reach3 | 96% | 96% | same |
| reach5 | 95% | 96% | +1 pp |
| reach10 | 90% | 93% | +3 pp，但低於95% Gate |
| mean | 9.88 | 10.00 | +0.12 |
| median | 10 | 10 | same |
| Q25 | 10 | 10 | same |
| CVaR25 | 7.96 | 8.36 | +0.40 |
| bottom deaths | 6 | 6 | non-regression |
| top deaths | 4 | 1 | 改善3 |
| health deaths | 0 | 0 | PASS |
| safety violations | 0 | 0 | PASS |
| switches／100 steps | 38.249 | 38.474 | +0.59%，≤5% |
| direct reversals | 1,178 | 1,180 | +2 |
| RELEASE-bridged reversals | 279 | 288 | +9 |

Candidate action distribution為RELEASE 1,032、LEFT 2,522、RIGHT 2,580；最大share
42.06%，無collapse。所有未暴露terminal plan的paths與v6完全相同，v6-success
regressions=0，duplicate replay與planner bounds全部PASS。

## 3. Paired outcomes與branch telemetry

- both-success：90
- candidate-only success：3
- v6-only success：0
- both-failure：7
- v6 top failures repaired：3/4
- branch-preserved searches：4
- selected lanes：RELEASE 1、LEFT 2、RIGHT 1
- branch expanded nodes：total 5,556；mean 1,389；max 1,524（cap 2,379）
- branch runtime：total 4.861 s；mean 1.215 s；max 1.338 s（watchdog 5 s）

三個causal repairs：

| Seed | v6 | Candidate | First divergence |
|---:|---|---|---|
| 18047 | floor4 top | floor10 success | step34 RELEASE→RIGHT |
| 18059 | floor9 top | floor11 success | step60 RELEASE→LEFT |
| 18089 | floor7 top | floor11 success | step52 RELEASE→LEFT |

剩餘top failure為18029：兩者均floor6 top，existing selector選RELEASE且action sequence沒有
分歧。本輪不得據此修改score、selector、lane bounds或建立下一candidate。

## 4. Frozen Gate判定

唯一失敗check：`reach_floor_10_at_least_0.95=false`（實際93%）。以下全部PASS：

- reach10相對v6 non-regression
- v6 success regressions=0
- 至少修復一個新development top failure
- bottom／health／safety
- no collapse
- non-terminal v6 identity
- action-switch inflation≤5%
- deterministic duplicate replay
- planner bounds與reachability

絕對95%門檻不得因相對改善而放寬，故正式FAIL。這不是`INCOMPLETE`，也不是protocol
conflict；它是完整且有效的negative formal result。

## 5. Stop decision

- 19000～19099 holdout：`used=false`，不得執行。
- 18100～18199：未使用；條件只在primary v6 top failure=0時成立，本次為4，故不得補跑。
- Alignment、Observable Teacher、Dataset v2、Student preflight與Colab package：全部NOT RUN。
- 不重跑development、不調參、不修改Gate、不以離線Phase 2F結果覆蓋formal FAIL。

唯一主要阻塞點是branch-preserving candidate的絕對reach10只有93%，低於凍結的95%。
