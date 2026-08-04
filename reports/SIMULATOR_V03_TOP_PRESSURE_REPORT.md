# Simulator v0.3 Top-Pressure Departure-Commit Report

日期：2026-08-03  
狀態：`FAIL_STOP_ORACLE_DEVELOPMENT`

## 人工驗收前置

使用者已觀看 `real_vs_simulator_v03_edge_departure.mp4`，確認新版基本左右離台
看起來較正常，可繼續下一個 bounded 階段。此驗收只通過視覺語意，不代表
pixel-perfect 1:1、長期 Oracle 或特殊平台通過。

## 候選與證據

v3 seed 13009 在 support floor 5 向右離台時，top-pressure 將 target 由 floor 6
改成 floor 8；stateless Oracle 因新目標改走 LEFT，step 50 仍留在來源平台並 top death。

唯一候選 `oracle-full-v5-committed-edge-top-pressure` 在同一 support tenure 鎖定
來源平台與出口方向，離邊後才解除；最後一步仍可使用「預測可清邊」的反向煞車。
候選沒有修改物理、速度、場地、頂刺、生成分布或 Gate 門檻。

新增測試固定重現 seed 13009：target 切到 floor 8 時仍保持 RIGHT，該 step 必須出現
`support_departed`。相關14 tests通過。

## Formal development 結果

Artifact：`artifacts/simulator_v03_edge_fidelity_gate_v4.json`

| 指標 | v3 | v4 committed | 判定 |
|---|---:|---:|---|
| mean deepest floor | 8.72 | 8.93 | 小幅改善 |
| reach floor 3 | 100% | 100% | PASS |
| reach floor 10 | 48% | 48% | **FAIL，門檻95%** |
| top deaths | 52 | 52 | 無改善 |
| edge invariant violations | 0 | 0 | PASS |

top death 分布由 v3 的 floor 5/6/7/8/9=`1/10/16/19/6`，移到 v4 的
floor 6/7/8/9=`2/19/20/11`。候選確實延後部分死亡並移除 floor-5 top death，
但沒有增加成功回合，因此不可通過。

## 停止結論

- Baseline development 未執行。
- holdout 14000～14099 未使用。
- 沒有產生 Dataset，沒有執行 BC、DAgger、PPO、DQN、NEAT。
- 沒有啟動或操作原版遊戲。

離台方向承諾是正確的局部修正，但不是主要瓶頸。剩餘問題是長期 sequence planning：
Oracle 必須同時估計離邊耗時、頂刺剩餘時間、空中橫向可達區與可能跳過的中間平台，
而不是只用當下 target center 與固定 lookahead。下一個候選應是 bounded、
action-conditioned 的短視窗 route planner；必須另凍結協議，不能繼續堆第二個
top-pressure heuristic 或靠放寬95%門檻通過。

## 驗證

- targeted support／edge／Oracle：14 passed。
- 完整 pytest：491 passed in 101.25s。
- formal artifact可解析且確認Baseline為null、holdout未使用；compileall與
  `git diff --check`皆PASS（僅既有LF→CRLF提示）。
