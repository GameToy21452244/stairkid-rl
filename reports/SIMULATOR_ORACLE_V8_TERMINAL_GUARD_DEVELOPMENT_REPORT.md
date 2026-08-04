# Simulator Oracle v8 Terminal-Risk Guard Development Report

日期：2026-08-04  
最終狀態：`FAIL_STOP_V8_DEVELOPMENT`  
總體交付狀態：`BLOCKED_WITH_EVIDENCE`

## 執行邊界

- Frozen protocol：`reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_PROTOCOL.md`
- Development partition：16000～16099，100 seeds。
- Paired reference：`oracle-full-v6-bounded-route-planner`。
- Candidate：`oracle-full-v8-terminal-risk-guard`。
- Holdout 17000～17099：未使用。
- Dataset／Student／training／real game：均未啟動。
- Production Oracle、planner、Gate helper與frozen protocol的交接 SHA-256 全部一致。

## 執行紀錄

- Attempt 1：模擬完成後，artifact runner將 `EdgeEpisode` 誤當成有
  `to_dict()` 的物件，依規則記為 `INCOMPLETE`。沒有formal artifact，
  holdout未使用。
- 只修正記錄層為 `asdict(item)`，未改 planner、physics、score、horizon、
  beam或Gate。修正後18個targeted tests、compileall與diff check通過。
- Attempt 2：從頭完整執行16000～16099，本報告以此次formal artifact為準。

## Formal Development 結果

| Metric | v6 | v8 |
|---|---:|---:|
| reach floor 3 | 100% | 100% |
| reach floor 10 | 96% | 96% |
| mean deepest floor | 10.35 | 10.35 |
| median | 10.00 | 10.00 |
| Q25 | 10.00 | 10.00 |
| CVaR25 | 9.44 | 9.44 |
| bottom death | 2 | 2 |
| top death | 2 | 2 |
| health death | 0 | 0 |
| RELEASE share | 16.253% | 16.253% |
| RELEASE / LEFT / RIGHT | 1001 / 2603 / 2555 | 1001 / 2603 / 2555 |
| action switch count | 2301 | 2301 |
| direct LEFT↔RIGHT reversals | 1144 | 1144 |
| RELEASE-bridged reversals | 239 | 239 |
| route planning count | 262 | 282 |
| terminal-risk replan count | 0 | 20 |
| terminal-plan exposure | 2 episodes / 2 plans | 2 episodes / 22 plans |

v8 safety violations為0，三動作皆使用，max action share為0.4226，無collapse。

Paired outcomes：

- both-success：96
- v6-only-success：0
- v8-only-success：0
- both-failure：4

100/100 paired action sequences完全一致；first-divergence taxonomy為
`identical: 100`。v8在2個terminal-risk episodes多執行20次replan，但動作、
switch、reversal、終局與lower-tail全部不v6相同。

Reproducibility checks：

- v6重播逐seed與既有formal reference一致：PASS。
- v8診斷重播逐seed與本次formal evaluation一致：PASS。
- planner bounds、non-terminal path identity、action-switch inflation checks：PASS。

Runtime：reachability 0.107 s；formal v8 evaluation 52.347 s；paired replay
135.239 s；總計187.692 s。

## Gate 判定

Frozen protocol checks只有一項FAIL：

- `v6_top_failures_repaired_at_least_one=false`

v8沒有救回任一個v6 top failure，因此即使reach10、bottom、安全、
collapse、switch與reproducibility全部合格，仍必須判定
`FAIL_STOP_V8_DEVELOPMENT`。不得使用17000～17099。

## Evidence

- Formal artifact：`artifacts/simulator_oracle_v8_terminal_guard_development_v1.json`
- Artifact SHA-256：`b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166`
- Stage journal：`artifacts/colab_readiness_stage_journal.json`
- Artifact含100組per-seed v6／v8結果、paired outcome、switch／replan、
  terminal exposure、first-divergence、reproducibility與runtime。

## Stop / Next

立即停止在Phase 2 development。不建立v9、不掃參數、不使用holdout、
不生成Dataset且不訓練Student。下一步只允許Phase 2F的offline design
review：判定是否有足夠paired evidence支持新protocol，不直接實作新heuristic。
