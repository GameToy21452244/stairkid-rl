# Codex Start Here

最後更新：2026-08-04

這是下一個Codex對話的精簡入口。不要先重讀全部歷史報告、舊prompt或完整
`CURRENT_STATUS.md`；遇到最新source、formal artifact或frozen protocol互相矛盾時，才按需
向下追查。

## 1. 專案目標

NS-SHAFT AI專案要建立可重現、可稽核的Simulator／Teacher／Student研究流程，最終交付
可在Colab執行的訓練bundle，並以少量、受監督的真實遊戲測試驗證。

目前重點不是追求Simulator平均分數，而是：

- 保持physics、generator、Oracle、Dataset與Student證據隔離。
- 每個formal Gate使用預先凍結的protocol與seed partition。
- 先看安全與lower-tail，再看平均表現。
- 人工手感與離線反事實只能作診斷，不能冒充formal PASS。

## 2. 權威證據優先順序

衝突時依序採信：

1. repository目前source、tests與formal artifacts。
2. frozen protocols與seed ledgers。
3. `reports/NEXT_WORK_DELTA_2026-08-04.md`。
4. `docs/CURRENT_STATUS.md`最上方區塊。
5. `reports/COLAB_READINESS_MASTER_REPORT.md`。
6. 歷史報告。
7. 對話文字與舊prompt。

不要因舊對話提過某結果，就假設工作樹仍相同。

## 3. 目前正式狀態

整體formal狀態：`BLOCKED_WITH_EVIDENCE`。

- Branch-preservation Phase C已完整執行18000～18099。
- Paired v6／candidate reach10為90%／93%。
- Candidate修復3/4個v6 top failures，沒有v6-success regression。
- 唯一failed check是candidate reach10 93%低於frozen 95%。
- 正式結果維持`FAIL_STOP_BRANCH_PRESERVATION_DEVELOPMENT`。
- 不得因相對改善、人工手感或後續debug而事後改判。

正式artifact：

```text
artifacts/simulator_oracle_branch_preservation_development_v1.json
```

正式protocol：

```text
reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md
```

## 4. 已完成階段

- Token-efficient delta audit。
- Oracle v8 protocol、implementation與formal development。
- Oracle v8 Phase 2F offline failure design review。
- Branch-preservation Phase A protocol review。
- Branch-preservation Phase B test-first implementation。
- Branch-preservation Phase C formal development；結果FAIL並停止。
- Simulator manual keyboard test工具與M01～M15 fixed scenarios。
- Manual calibration cleanup／baseline／candidate工作以最新top status為準。

這些階段不應在新對話中從頭重做。

## 5. 當前blocker

唯一正式blocker仍是Branch-preservation candidate未達絕對reach10 95%。因此以下階段沒有
解鎖：

- Candidate one-time holdout。
- Simulator／Real Alignment新Gate。
- Observable Teacher Gate。
- Dataset v2。
- Student preflight／training。
- Colab-ready package。

Simulator manual calibration是獨立、非formal工作，不會解除上述blocker。

## 6. Seeds與holdouts

| Partition | 用途 | 狀態 |
|---|---|---|
| 16000～16099 | v7／v8 development | USED；不可再作新evaluation |
| 17000～17099 | v8 one-time holdout | UNUSED；禁止轉用 |
| 18000～18099 | branch-preservation development | USED；不可重跑調參 |
| 18100～18199 | 條件式development extension | UNUSED；條件未觸發 |
| 19000～19099 | branch-preservation holdout | UNUSED；Phase C FAIL後禁止使用 |
| >=900000 | manual-only工具 | 可用；`formal_evaluation_allowed=false` |

任何新formal candidate都必須另立protocol與全新seed ledger。Manual seed、舊development
seed與offline counterfactual都不能作formal PASS。

## 7. 當前最高優先工作

Simulator v0.4 calibration candidate工程已完成，目前只待使用者人工重測：

- 保守整理文件，不刪除未知或formal evidence。
- before／after artifacts已保存，render FPS invariance與swept collision tests已通過。
- `after` profile包含新controls、collision、scroll與layout；`B`可切回`before`。
- 下一步是使用者操作manual simulator並提供六項主觀rating。

Calibration candidate不是新的Oracle、Alignment或Student Gate。

## 8. Manual simulator

啟動：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_test.py `
  --scenario normal_baseline `
  --seed 900001 `
  --profile after `
  --show-debug `
  --record `
  --fps 60
```

主要控制：

- LEFT／A與RIGHT／D：方向。
- 未按方向鍵或視窗失焦：`RELEASE_ALL`。
- R：reset。
- N：下一個fixed scenario。
- B：切換before／after profile並重設場景。
- P／Space：pause。
- F1：debug overlay。
- F2：recording。
- F3：manual rating。
- ESC：安全保存並結束。

Manual sessions寫入：

```text
artifacts/manual_simulator_test/<session_id>/
```

這些session預設由`.gitignore`排除，不是formal evidence。

## 9. 特殊平台現況

Spring、conveyor left/right、spikes、flipping active/inactive與normal-platform healing已有
固定manual scenario，但Simulator／Real Alignment未PASS，所以全部仍為`PROVISIONAL`。

專案沒有獨立`healing` platform kind；只有normal-platform healing，不能宣稱獨立healing
mechanism已完成。

本輪normal calibration不得啟用新的special-platform generation distribution。

## 10. 必讀檔案（最多8個）

新對話依序讀：

1. `AGENTS.md`
2. `docs/CODEX_START_HERE.md`
3. `docs/CURRENT_STATUS.md`最上方區塊
4. `reports/NEXT_WORK_DELTA_2026-08-04.md`
5. `reports/MANUAL_SIMULATOR_CALIBRATION_REPORT.md`
6. `src/stair_agent/simulator/state.py`
7. `src/stair_agent/simulator/physics.py`
8. 與當前修改直接相關的tests

只有發生矛盾或測試FAIL時，才開啟對應歷史protocol／artifact。

## 11. 常用驗證指令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
git diff --check
```

Manual headless smoke：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_test.py `
  --headless-smoke `
  --seed 900002 `
  --smoke-steps 6
```

查看場景：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_test.py --list-scenarios
```

## 12. Git branch與push

- 目前branch：`agent/simulator-learnability-colab`。
- Remote：使用repository已設定的`origin`。
- Upstream：`origin/agent/simulator-learnability-colab`。
- Push只能使用一般`git push`，不得force push。
- 不得reset、restore或clean使用者工作樹。
- Commit前檢查status、diff stat、diff check、秘密與大型暫存檔。
- Manual MP4、logs、models、checkpoints與本機config不得commit。

## 13. 不得執行

- 不得重跑Branch Phase C來調參。
- 不得使用17000或19000 holdout。
- 不得執行Oracle development／holdout。
- 不得生成Dataset v2。
- 不得訓練BC、DAgger、PPO、DQN、NEAT或Student。
- 不得啟動或自動操作原版`NS Shaft.exe`。
- 不得把manual rating改寫成formal Alignment PASS。
- 不得修改或覆寫frozen protocol、seed ledger、formal artifact。
- 不得刪除用途不明文件或唯一證據。
- 不得force push或改寫published history。

## 14. 新對話最小啟動方式

可直接告訴新Codex：

> 先完整閱讀AGENTS.md與docs/CODEX_START_HERE.md，再只讀CURRENT_STATUS最上方和目前
> calibration source／tests。不要重做已完成Gate，不要讀完整歷史，不要使用holdout、
> training或原版遊戲。先核對working tree與formal hashes，再從最新calibration狀態繼續。
