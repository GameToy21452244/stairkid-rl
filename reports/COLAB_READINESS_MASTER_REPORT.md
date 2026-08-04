# Colab Readiness Master Report

日期：2026-08-04  
總體狀態：`BLOCKED_WITH_EVIDENCE`

## Manual calibration update（不改formal readiness）

v0.4 calibration candidate已完成before／after engineering evidence並準備使用者人工重測。
FPS invariance與swept edge collision診斷PASS；控制、scroll與normal layout候選均隔離在manual
`after` profile。Frozen v0.3 default、production Oracle與formal artifacts未被改判或覆寫。
本更新不解鎖下表Phase D～I；holdout、Dataset與training仍未使用。

| Phase | Gate | 目前狀態 | Evidence | 解鎖下一階段 |
|---|---|---|---|---|
| Manual-only | Simulator calibration | READY FOR USER RETEST（NON-GATE） | before／after metrics＋FPS／collision tests＋headless smoke | 否 |
| 0 | State reconstruction / Engineering | PASS | 529 full tests；66 targeted；compileall；diff check | 是 |
| 1/2 | Oracle v8 development | FAIL | `simulator_oracle_v8_terminal_guard_development_v1.json` | 否 |
| 2F | Offline Oracle failure design review | COMPLETE | `simulator_oracle_v8_phase2f_review_v1.json` | 只支持新protocol設計 |
| A | Branch-preservation protocol review | PASS | `simulator_oracle_branch_preservation_protocol_v1.json` | 是，test-first implementation |
| B | Test-first implementation | PASS | 559 tests；compileall；diff check；implementation artifact | 是，new development |
| C | Branch-preservation development | FAIL | reach10 93% < 95%；formal artifact | 否 |
| D | Candidate one-time holdout | NOT RUN | 19000～19099 `used=false` | 否 |
| E | Simulator / Real alignment | NOT RUN | 上游development FAIL | 否 |
| F | Observable Teacher | NOT RUN | 上游Gate未通過 | 否 |
| G | Dataset v2 | NOT GENERATED | `dataset_generated=false` | 否 |
| H | Student preflight | NOT RUN | `training_started=false` | 否 |
| I | Colab readiness | NOT READY | 上游Gate未通過 | 否 |

## Manual simulator test（不改formal readiness）

`scripts/run_simulator_manual_test.py`已可用Simulator視窗內的LEFT／RIGHT或A／D操作，並
支援reset、pause、固定場景切換、debug overlay、人工rating與session JSON／CSV／錄影。
M01～M15場景可重現；所有特殊平台仍標示`PROVISIONAL`。Manual seed強制>=900000，且
summary固定`formal_evidence=false`、`manual_alignment_only=true`、`holdout_used=false`。

Headless smoke evidence：
`artifacts/manual_simulator_test/manual_20260804_184049_412824/`。此工具沒有解鎖Phase D，
不構成Alignment PASS，也不改變本報告的`BLOCKED_WITH_EVIDENCE`。

## Current blocker

Phase C已完整執行18000～18099。Candidate reach10由paired v6的90%改善為93%，修復
3/4個v6 top failures，v6-success regressions=0，bottom同為6，CVaR25 7.96→8.36，
non-terminal identity、switch、safety、reproducibility與bounds全PASS。

唯一失敗check是凍結的絕對門檻`reach_floor_10_at_least_0.95=false`。93%不得因相對改善
而改判；狀態`FAIL_STOP_BRANCH_PRESERVATION_DEVELOPMENT`。19000 holdout未使用，所有
Alignment、Teacher、Dataset、Student與Colab階段立即停止。

## Evidence

- Development report：`reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_DEVELOPMENT_REPORT.md`
- Formal artifact：`artifacts/simulator_oracle_v8_terminal_guard_development_v1.json`
- Stage journal：`artifacts/colab_readiness_stage_journal.json`
- Phase 2F report：`reports/SIMULATOR_ORACLE_V8_PHASE2F_DESIGN_REVIEW.md`
- Phase 2F artifact：`artifacts/simulator_oracle_v8_phase2f_review_v1.json`
- Branch protocol：`reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md`
- Protocol artifact：`artifacts/simulator_oracle_branch_preservation_protocol_v1.json`
- Seed ledger：`artifacts/simulator_oracle_branch_preservation_seed_ledger_v1.json`
- Implementation：`artifacts/simulator_oracle_branch_preservation_implementation_v1.json`
- Branch development：`artifacts/simulator_oracle_branch_preservation_development_v1.json`
- Branch development report：`reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_REPORT.md`

## Decision

第一個formal Gate已FAIL，最終狀態`BLOCKED_WITH_EVIDENCE`。不執行19000 holdout、不補跑
18100（primary已有4個top failures）、不修改candidate或Gate、不進Alignment及任何下游階段。
