# Next Work Delta — 2026-08-04

## 最高優先更新：v0.4 calibration candidate待使用者人工重測

- Before／after baseline、CSV traces、FPS invariance、collision與layout diagnostics均已保存。
- 30／60／120 render FPS結果一致；穿透根因為斜向edge的end-of-substep水平overlap漏判，
  不是fixed 60 Hz physics timestep。v0.4 candidate以time-of-impact x修復。
- 控制改為560 acceleration、0.85 air control、960 release deceleration、1.25 reverse
  braking；scroll候選80。Generator horizontal shift median 29.78→81.43，spacing維持48。
- Frozen v0.3 default與RNG stream明確隔離保留，manual `B`可切換before／after；正式Oracle
  source與branch artifact／protocol hash未變。
- 185 targeted與587 full tests、compileall、diff check及manual headless smoke全部PASS。
- 下一步只需使用者執行manual retest並填六項rating；formal branch development仍FAIL，
  17000／19000 holdout、Dataset、Student、training與原版遊戲均未使用／未啟動。
- 詳見`reports/MANUAL_SIMULATOR_CALIBRATION_REPORT.md`與
  `artifacts/manual_simulator_calibration/calibration_summary.json`。

本文件是新對話的差異交接，不重述完整專案歷史。Repository audit snapshot：

- Branch：`agent/simulator-learnability-colab`
- HEAD：`745dc70b2bf07044ca16a4b280a7ea2106f6f248`
- HEAD subject：`加入 P4.1 時序模型公平消融管線`
- Working tree（建立本handoff後）：32 modified、110 untracked、0 staged／other；不可reset、
  checkout或清除既有修改。
- Active Python／TensorBoard process：0。`Get-CimInstance Win32_Process`被系統拒絕，
  但`Get-Process`沒有python或tensorboard程序。
- `git diff --check`：PASS。

## Manual-only update：Simulator keyboard test READY（非formal Gate）

- 新工具：`scripts/run_simulator_manual_test.py`；實作：
  `src/stair_agent/simulator/manual_test.py`；runbook：
  `reports/MANUAL_SIMULATOR_TEST_RUNBOOK.md`。
- M01～M15固定場景涵蓋normal控制、acceleration、release、reverse、edge、landing、top／
  bottom及spring／conveyor／spikes／flipping／normal healing。特殊平台全部標記
  `PROVISIONAL`；獨立healing platform kind仍unsupported。
- 僅接受>=900000的manual-only seed；formal與holdout partitions會在建立session前被拒絕。
- CLI headless smoke PASS，輸出在
  `artifacts/manual_simulator_test/manual_20260804_184049_412824/`；這不是人工操作結果或
  Alignment證據。
- Manual＋相關Simulator targeted tests 79 PASS、完整pytest 579 PASS、compileall與
  `git diff --check` PASS。
- 本輪沒有改production Oracle、physics、generator、frozen protocol或formal artifact，
  沒有遊戲input、訓練或holdout使用。Phase C與所有正式下游狀態完全不變。

## 0. Highest-priority update：Branch Development FAIL／STOP

- 新candidate formal development已完整執行18000～18099；v6/candidate reach10為90%／93%，
  top deaths 4／1、bottom 6／6、CVaR25 7.96／8.36。
- Paired為90 both-success、3 candidate-only、0 v6-only、7 both-failure；修復3/4 v6 top
  failures且0 success regressions，non-terminal paths完全相同。
- 唯一failed check為絕對reach10 93% < frozen 95%；不得以相對+3pp改判。
- 狀態`FAIL_STOP_BRANCH_PRESERVATION_DEVELOPMENT`／`BLOCKED_WITH_EVIDENCE`。
- 19000～19099 holdout維持unused；18100未跑（預先條件不成立）；17000仍unused且禁用。
- Alignment、Teacher、Dataset v2、Student preflight與Colab package全部NOT RUN。
- Formal artifact：`artifacts/simulator_oracle_branch_preservation_development_v1.json`
  (SHA-256 `e4952a8332f7c2a25acb564e28a8b47b9b733e4c4bb073f19eade79501cd9758`)；
  report：`reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_REPORT.md`。

### 前一最高優先狀態：Phase B PASS／新Development待執行

- Current-State Verification為`CONSISTENT`；production v8與Phase 2F frozen hashes未變，
  17000～17099仍unused，沒有背景遊戲／Python／training。
- 14/14 cross-lane selector audit以既有`max(score)`選到RIGHT survivor；selector與score
  不需修改，Phase A判`READY_FOR_TEST_FIRST_IMPLEMENTATION`。
- 新protocol只允許terminal-risk三個first-action lanes各自12/24，選定後cache完整suffix；
  normal paths維持v6，不加入cooldown／hysteresis／新threshold。
- Seed ledger已凍結18000～18099 development、條件擴充18100～18199與19000～19099
  one-time holdout，三者先前均未使用；17000不得轉用。
- Phase B已test-first完成；新增19 targeted tests與完整559 tests、compileall、diff check
  全PASS，implementation hashes已凍結。現依One-Pass Prompt自動進Phase C，只先使用
  18000～18099；development PASS前不得碰19000。完整證據見protocol與implementation artifact。

### 前一最高優先狀態：Phase 2F Review COMPLETE／v8正式淘汰

- Offline Oracle Failure Design Review已完成；formal v8結果維持
  `FAIL_STOP_V8_DEVELOPMENT`，不得事後改判。
- 22個terminal-plan calls（2 entry＋20 replans）均重算出與v6 cached suffix完全相同的
  RELEASE序列，且selected action確實執行；不是overwrite、snapshot或commit問題。
- 同一12-step／24-beam bounds按first action隔離時，找到14個RIGHT分支可完整reach10；
  16002 step 39～46共8個、16030 step 51～56共6個。
- 14/14成功路徑在production共享beam的depth 4被剪除，unique rank 35～39，均低於
  beam=24 cutoff。根因為score-induced intermediate shared-beam branch extinction，
  不是trigger太晚或horizon不足。
- 唯一`SUPPORTED_FOR_NEW_PROTOCOL`方向是terminal-only forced-first-action diversity／
  branch preservation；只代表足以撰寫新protocol，不代表candidate已PASS或已批准實作。
- A/B/E為`REJECT`；C/F/G為`INSUFFICIENT_EVIDENCE`。v8是安全但無效的no-op，正式
  淘汰，只保留重現用途。
- 17000～17099仍`used=false`；不得建立新production Oracle、使用holdout、生成Dataset、
  訓練Student或啟動實機。
- 主artifact：`artifacts/simulator_oracle_v8_phase2f_review_v1.json`；report：
  `reports/SIMULATOR_ORACLE_V8_PHASE2F_DESIGN_REVIEW.md`。

### 前一最高優先狀態：Oracle v8 Development FAIL

- Engineering Gate：529 full tests、66 protocol-targeted tests、compileall與diff check全PASS。
- v8 formal development 16000～16099已完整執行；v6/v8 reach10均為96%，
  bottom/top均為2/2，Q25 10，CVaR25 9.44。
- Paired為96 both-success、0 v6-only、0 v8-only、4 both-failure；100/100 action
  sequences identical。v8多20次terminal-risk replans但救回top failure為0。
- Frozen check `v6_top_failures_repaired_at_least_one=false`，正式狀態
  `FAIL_STOP_V8_DEVELOPMENT`，總體為`BLOCKED_WITH_EVIDENCE`。
- 17000～17099仍`used=false`；不得執行holdout、Dataset、Student或實機。
- Formal artifact：`artifacts/simulator_oracle_v8_terminal_guard_development_v1.json`
  (SHA-256 `b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166`)。
- Report：`reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_DEVELOPMENT_REPORT.md`。
- Stage journal：`artifacts/colab_readiness_stage_journal.json`；Attempt 1記錄層例外保留為
  `INCOMPLETE`，Attempt 2為from-scratch完整formal result。

## 1. Current blocker

Branch-preserving Oracle在新development雖修復3個top failures且無regression，但reach10
只有93%，未達凍結95%絕對門檻。這是完整formal FAIL，不是缺artifact或待補跑。

## 2. Current exact phase

`Simulator v0.3 → Phase 2F → Branch protocol PASS → Engineering PASS → New development
FAIL at absolute reach10 → BLOCKED_WITH_EVIDENCE`。

這仍是Simulator／Oracle可靠性階段，不是Dataset或Student訓練階段。下一個正式科學
結果必須來自另行凍結的新候選protocol與全新development partition；不能再稱為v8結果。

## 3. Completed items that new Codex should skip

- 安全控制鏈、transition schema／validator、Gymnasium/Pymunk與Colab執行管線：已完成，跳過。
- P3.6真機Teacher Gate與P4.0 state-aliasing audit：已完成，跳過。
- P4.1 S0～S3與既有BC／DAgger lower-tail判定：已評估並停止，不重跑。
- Simulator v0.3 playfield、support ownership與平台邊緣離台語意：已實作／測試，跳過。
- Oracle v6、observable route-intent development、retired failure taxonomy：已完成，跳過。
- v7 formal development、paired receding audit、terminal-plan incidence audit：已完成，跳過。
- v8 `terminal_guarded` production source、Gate helper、runner與targeted tests：已完成，勿重寫。

## 4. Rejected／retired approaches that must not be repeated

- `oracle-full-v7-receding-route-planner`：development 76% vs v6 96%，bottom 22 vs 2；REJECT。
- Always-receding及24-step／96-beam extended search：retired failures 0/7；REJECT。
- 14000～14099：已作第一次Oracle holdout並用於diagnostic，永久退休。
- 7個14000 failure seeds與16000～16099：只能作development／diagnostic，不得改稱holdout。
- 前次約42秒v8中止run：無artifact、runner不可resume，嚴禁引用為任何Gate結果。
- 不回到collapsed PPO、長BC／DAgger／PPO／DQN／NEAT或以增加epochs繞過Gate。

## 5. Incomplete items

- v8 Engineering Gate與formal development已完成，不重跑；development結果為FAIL。
- 17000～17099 one-time holdout因development FAIL維持未使用，不得執行。
- Phase 2F、branch-preservation protocol freeze、test-first implementation與formal
  development均已完成；formal development因reach10僅93%（門檻95%）而FAIL。
- 18100～18199條件式development extension未觸發，因primary partition的paired v6已有
  4個top failures；19000～19099 one-time holdout未使用且維持BLOCKED。
- Alignment、Teacher Gate、Dataset v2、Student與Colab bundle均未執行。

## 6. Next allowed Gate

沒有已解鎖的下游formal Gate。本輪已在第一個失敗Gate停止並交付
`BLOCKED_WITH_EVIDENCE`。不得執行19000～19099 holdout、Alignment、Teacher、Dataset、
Student或Colab packaging；不得重跑或調整目前候選。任何後續工作都必須另行授權、建立
全新protocol與全新seed partition，且不得把本輪development或Phase 2F離線反事實當成PASS。

## 7. Exact required source／protocol／artifact files

| Role | Path | SHA-256 |
|---|---|---|
| Branch-preservation frozen protocol | `reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md` | `9d4fae44ae6c47714e48a3ebdae4b953f9e6f257c6f6604f8469cfd10859ccbe` |
| Branch-preservation protocol artifact | `artifacts/simulator_oracle_branch_preservation_protocol_v1.json` | `9c006b61fe32f32daefb9f4bca323868cb2eb44ca8ac71d89dc11e2c1cd72e92` |
| Branch-preservation seed ledger | `artifacts/simulator_oracle_branch_preservation_seed_ledger_v1.json` | `9da4b0b725f0ce7f932f6a15cc7819bf3d7471a59262dc8f861156ad58230c54` |
| Branch-preservation formal development | `artifacts/simulator_oracle_branch_preservation_development_v1.json` | `e4952a8332f7c2a25acb564e28a8b47b9b733e4c4bb073f19eade79501cd9758` |
| Current Oracle production source | `src/stair_agent/policies/simulator_teachers.py` | `a015ae5b96056ac6341da403c0b7ce25f91ebed28cc929a80b765573908a0872` |
| Current bounded planner source | `src/stair_agent/policies/simulator_route_planner.py` | `c22a5985d4a784e95efaa50d94d515e21c5df42c10ceda4d76ccfda4befcffb8` |
| Last earlier passing formal Gate | `artifacts/simulator_oracle_robustness_gate_v1.json` | `a8d6bbc14079e477dd99281011a3f4809692d749c3dc17a2266df0f8e74cf63a` |
| v7 frozen protocol | `reports/SIMULATOR_ORACLE_ROBUSTNESS_PROTOCOL.md` | `f4d23903940cfe5f6af228e9e20627f3f72e8957e56b61bf81adccb1c6c564d0` |
| Latest diagnostic evidence | `artifacts/simulator_oracle_terminal_plan_audit_v1.json` | `d4189c59bef8071c57f915cafc2db564242cc4adbed847b28b6a87a6bcce4354` |
| Terminal audit protocol | `reports/SIMULATOR_ORACLE_TERMINAL_PLAN_AUDIT_PROTOCOL.md` | `9a64156e54eba4025b6d01b5eef9cf9ebac9e9167fac275153e132979aa004cd` |
| v8 frozen protocol | `reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_PROTOCOL.md` | `78df06c393ff8123d559a98657fadbd791eee3ce3f532aa6a3fabe2cc3f5289e` |
| Pre-branch Oracle source | `src/stair_agent/policies/simulator_teachers.py` | `18018669ed6e97056be20bf07642afd766dfa0b3c0bf4e232e476c26c295cbbb` |
| Pre-branch planner source | `src/stair_agent/policies/simulator_route_planner.py` | `c52671e08c607d919e8c83b5f63b5c0faaf8b92541322996bdc736b66444a394` |
| v8 Gate helper | `src/stair_agent/training/simulator_oracle_v8_gate.py` | `bcdab11c8bc52ed8de0f773c0efd350a4c7286f204bb7aae8b9bde7056d209cd` |
| v8 runner | `scripts/run_simulator_oracle_v8_gate.py` | `6d4f6f81b14265893ecf05587712408dd35725cae13355143e1c365b7ac16729` |
| Route/v8 behavior tests | `tests/test_simulator_route_planner.py` | `9595ab8d81be91f206207b106b4bed0fa5b1edc30d9a46168fc8a9a96de215fa` |
| v8 Gate tests | `tests/test_simulator_oracle_v8_gate.py` | `74d9b33ddc6e6fc9e8661095c32c8af6fd7def8893f4198fed001c7231243e54` |
| v8 formal development result | `artifacts/simulator_oracle_v8_terminal_guard_development_v1.json` | `b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166` |

Branch-preservation formal artifact、frozen protocol與seed ledger hashes均已重新核對。
正式結果為FAIL，故19000 holdout artifact、Alignment artifact、Dataset／Student與Colab
bundle均不存在；這些缺失是正確的停止行為，不是待補跑項目。

## 8. Seed／holdout usage ledger

| Partition | Role | State |
|---|---|---|
| 13000～13099 | 舊v0.3 development | USED；不可作holdout |
| 14000～14099 | 第一次Oracle holdout／後續diagnostic | USED＋RETIRED；Oracle 93%，observable未跑 |
| 16000～16099 | v7/v8 formal development＋paired／terminal diagnostics | USED DEVELOPMENT；v6 96%、v7 76%、v8 96% FAIL（top repair 0） |
| 17000～17099 | v8 one-time holdout | **UNUSED**；有效artifact顯示used=false，reachability／Oracle／observable皆null |
| 18000～18099 | branch-preservation formal development | **USED DEVELOPMENT**；candidate reach10 93%，FAIL（門檻95%） |
| 18100～18199 | 條件式development extension | **UNUSED**；primary paired v6有4個top failures，條件未觸發 |
| 19000～19099 | branch-preservation one-time holdout | **UNUSED**；development FAIL後禁止使用 |

舊的42秒中止run仍不可使用。本次artifact runner Attempt 1亦因記錄層例外保留為
`INCOMPLETE`；Attempt 2從頭完整執行並產生唯一有效v8 development result。
兩次的holdout均未使用。

## 9. Stop conditions

- Branch-preservation development已命中凍結條件：reach10 93% < 95%。
- Formal artifact保存後立即停止；不得使用19000 holdout、不得調參或重跑候選。
- 任何離線診斷或三個已修復top failures都不能覆蓋此FAIL。
- 因第一個Gate失敗，Alignment、Teacher、Dataset、Student與Colab一律不得開始。

## 10. Whether Dataset／Student／Colab training is currently allowed

**不允許。** Dataset generation、BC、DAgger、PPO、DQN、NEAT、Colab多初始化訓練及
實機rollout目前全部BLOCKED。Colab只在未來上游Simulator／Oracle／observable／特殊平台
與alignment Gate通過、正式進入Student多初始化訓練時才需要。

## 11. Minimal new-chat reading list

依序閱讀：

1. `AGENTS.md`（並遵守其中強制恢復文件；不要重做其歷史工作）。
2. `reports/NEXT_WORK_DELTA_2026-08-04.md`。
3. `docs/CURRENT_STATUS.md`只需先讀最上方最高優先區塊，遇矛盾才讀歷史。
4. `reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md`。
5. `reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_REPORT.md`與
   `artifacts/simulator_oracle_branch_preservation_development_v1.json`。
6. `artifacts/simulator_oracle_branch_preservation_seed_ledger_v1.json`與
   `artifacts/colab_readiness_stage_journal.json`。
7. 只有在分析目前FAIL根因且最新證據不足時，才按需讀Phase 2F與v8歷史。

## 12. A concise prompt for the new Codex conversation

> 請先完整閱讀AGENTS.md並依其恢復規則執行，再讀
> reports/NEXT_WORK_DELTA_2026-08-04.md、docs/CURRENT_STATUS.md最上方區塊、
> reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md及正式development artifact。
> Branch-preservation development已因reach10 93% < 95%正式FAIL；不得重跑、調參、
> 使用19000 holdout或開始Alignment／Dataset／Student／Colab。現況為
> `BLOCKED_WITH_EVIDENCE`，任何後續新研究方向均需另立protocol與全新seed ledger。
