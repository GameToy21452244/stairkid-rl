# P3.6 Teacher Real Micro Gate v2 語意修正報告

日期：2026-08-01

狀態：**RECORDED SIDECAR RECLASSIFICATION PASS／FRESH REAL CONFIRMATION PENDING**

## 結論

Repair v6 的 3 回合真機紀錄不是嚴重的平台離台卡死。舊 Gate v1 的 FAIL 主要來自
三個量測定義把正常或安全行為列為 blocking failure：同平台 settle、特殊平台脫困
換向，以及全程 RELEASE 且之後恢復的短暫視覺失聯。

Gate v2 已以測試先行修正。控制策略、鍵盤 action、wall/special/departure safety
均未變更。既有 sidecar 用新語意重算為 PASS，但依實驗協議仍須一次全新 3 回合
確認，才能解除 P3.6 HOLD 並進入 State-aliasing Audit。

## 來源證據

- 原始 Gate：
  `logs/teacher_real_micro_20260801_225518_153636/teacher_real_game_micro_gate.json`
- 回合 steps：`111,55,300`，共 466 steps。
- 舊 HUD parser floors：`5,3,10`；3/3 reach-floor-3、2/3 reach-floor-5。
- 使用者觀察最高第 13 層；影片尾段可見約第 12～13 層，floor parser 有 lag／
  unstable，故本報告不把 parser 的 10 宣稱為真實最高值。
- safety events 0、outward wall push 0、wall re-entry 0。
- support departure exits 46；median 3 steps、max 5 steps；same-support restart 0、
  target switch 0、timeout 0、edge RELEASE 8/75（10.67%）。

## v1 誤判與 v2 定義

### 1. 平台 settle 與真正卡邊

v1 只要 `support_contact + aligned RELEASE` 連續超過 3 steps 就失敗。最新 EP1
steps 4～7 雖連續 RELEASE 4 steps，但 `target_platform_id == support_platform_id`
且 edge distance 約 23～37 px；step 8 取得不同下層目標後立即進入 departure。

v2 只有下列條件同時成立才算 actionable support stall：

- support contact active；
- action 是 RELEASE；
- reason 是 aligned；
- target 與 support 都存在且 `target != support`。

同平台 settle 仍計數，但只作 telemetry。這次共有 13 個 settle RELEASE、
actionable RELEASE 0。

### 2. Wall oscillation 與特殊平台脫困

v1 的 wall-corridor reversal burst 會跨越 `special_escape` 累積。最新 EP3 的
burst 3 是 move LEFT → special escape RIGHT → move LEFT，不是 wall guard／
evacuation 反覆互搶；同一回合 outward push 與 wall re-entry 都是 0。

v2 blocking metric 只量 wall guard 或 wall evacuation active 的方向反轉，且
special／launch escape 會切斷 burst。舊 corridor/global 指標保留為診斷 telemetry。
本次 active-wall reversal max 0。

### 3. Observation dropout 與盲目控制

v1 要求任何回合所有 decision observation confidence 都大於 0，且 missing streak
不得超過 2。這會把遊戲捲動、角色動畫或特殊平台短暫遮蔽直接當成控制失敗。

v2 要求：

- recoverable dropout 最長不超過 20 steps；
- dropout 期間 LEFT／RIGHT action 必須為 0，只能 RELEASE；
- 非 terminal dropout 必須後續恢復；
- terminal dropout 單獨分類，不和遊玩中未恢復混用。

本次重分類有 29 invalid steps、4 次 recovered dropout、max 15 steps、blind
directional action 0、unrecovered 0。context 為 dynamic transition 2、scroll
progress 1、ordinary recovered 1。

## 實作

- `ObservationDropoutTracker`：記錄 recovered／terminal／unrecovered、最大 streak、
  blind action 與 entry phase/floor context。
- `SupportAlignedStallTracker`：分離同平台 settle 與不同目標 actionable RELEASE。
- `DirectionOscillationTracker.update(..., eligible=...)`：允許 Gate 在非 wall-safety
  或 special/launch context 明確切斷 burst。
- `reclassify_real_micro_episode(...)`：由不可變 controller sidecar 重建 v2 指標。
- real runner 在寫出每回合結果前套用相同分類器，避免 offline/live 定義分岔。
- `scripts/reclassify_teacher_real_micro_gate.py`：只讀舊 Gate 與 sidecar，不啟動遊戲、
  不載入輸入 backend、不送鍵，且拒絕覆寫既有 artifact。

## Gate v2 重分類結果

Artifact：
`artifacts/p36_teacher_real_gate_v2_reclassification_20260801_225518.json`

所有 checks PASS，包括：

- observation telemetry available；
- recoverable dropout bounded；
- unrecovered dropout 0；
- blind directional action 0；
- outward push／wall re-entry 0；
- active-wall reversal burst ≤2；
- actionable support RELEASE 0；
- departure restart／target switch／timeout 0；
- edge RELEASE ratio ≤25%；
- reach-floor-3／5 與 action distribution Gate。

## 驗證

- Gate／policy／live targeted：98 passed。
- 完整 `pytest -q`：363 passed in 85.93s。
- `python -m compileall -q src scripts tests`：PASS。
- Gate v2 no-input dry-run：PASS／Gate status PENDING。
- `git diff --check`：PASS；只有既有 Windows LF→CRLF 提示。
- 本次真實遊戲啟動：0。
- 本次真實輸入：0。
- 本次模型訓練：0。

## Go／No-Go

- **PASS**：既有實機 sidecar 的 Gate v2 語意重分類。
- **HOLD／STOP**：P3.6 正式完成狀態；重分類不是獨立新 runner 驗證。
- **唯一下一步**：使用 Gate v2 runner 再執行一次受監督、硬上限 3 回合真機確認。
- **No-Go**：確認前不得開始 P4.0、S0～S3、rare-branch dataset、DAgger、PPO、
  DQN 或 NEAT。
