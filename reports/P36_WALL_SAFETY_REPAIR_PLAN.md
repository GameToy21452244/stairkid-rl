# P3.6 Wall-Safety Repair Plan

日期：2026-08-01

## 狀態與範圍

本文件凍結 Teacher Real-Game Micro Gate 的 wall-safety 修復範圍。P3.6 仍為
FAIL／STOP；在本文件的 Gate 由全新真機 artifact 通過前，不進入 P4.0
State-aliasing Audit，不生成 sequence dataset，也不啟動 BC、DAgger、PPO、DQN
或 NEAT。

長期狀態仍以 `docs/CURRENT_STATUS.md`、`docs/TRAINING_ROADMAP.md`、
`docs/DECISIONS.md` 為準；歷次真機證據見
`reports/TEACHER_REAL_GAME_MICRO_GATE.md`。

## 實測證據

來源 run：

- `teacher_real_micro_20260801_035120_340142`：3 回合 artifact floors 5/2/1。
- `teacher_real_micro_20260801_035223_571410`：5 回合 artifact floors 2/1/3/3/7；
  使用者人工看到 terminal 附近第 8 層。

正向證據：5 回合 run 的安全事件為 0、三動作 118/110/105、physical latency
已量測、所有 transition/controller/MP4 完整，且有 reach-floor-3／5 案例。

阻擋證據：

- 5 回合 EP1 spring escape 在 steps 10～21、23～27 持續 LEFT；角色已在
  `x≈54–56` 仍向牆外輸入，共 17 個 special LEFT actions。
- 5 回合 EP4 spikes escape 在 steps 22～33 持續 RIGHT；角色由 `x=326.5`
  移到 `x≈410`，共 12 個 special RIGHT actions。
- 現行 special escape 只有離開 source bounds、safe landing 或 12-step cap 才停止。
  特殊平台貼牆時，沿原方向離開在幾何上不可能，故 hard cap 會變成撞牆等待。
- 最新 5 回合 Gate 仍為 FAIL；5 回合中 4 回合 observation invalid，EP5 有
  連續 player-missing 區間。最高樓層不能覆蓋 safety／observation failure。

## 固定實作

### 1. 共用 wall guard

- Baseline config 明確保存真機 playfield left/right 與 wall margin，不從 artifact
  反推、不使用 simulator privileged state。
- 角色中心位於左側 guard zone 時，任何 LEFT desired action 改為 RIGHT；位於右側
  guard zone 時，任何 RIGHT desired action 改為 LEFT。
- Guard 位於所有策略輸出的共同出口，因此必須覆蓋 special-contact escape、
  launch escape、aligned-dwell escape、recovery、top-danger 與一般 target move。
- 方向切換仍走既有 brake；第一次可 RELEASE，下一個 decision 必須向場內。
- Guard 不放寬 F8、foreground、watchdog、terminal 或 release-all 安全鏈。

### 2. Controller telemetry

每個 controller row 新增：

- `wall_guard_active`
- `wall_guard_side`
- `wall_guard_original_action`
- `outward_wall_push`
- `outward_wall_push_streak`

`outward_wall_push` 以 decision observation 的 player x、playfield bounds、margin 與
實際 action 計算；player 缺失時不得猜測。

### 3. Gate

新增固定 checks／metrics：

- `outward_wall_push_count == 0`
- `max_outward_wall_push_streak == 0`
- wall guard 至少可在 fixed scenarios 證明 special、launch、dwell 三條路徑都向內。

舊 artifact 只作 development evidence；不得以缺少新欄位冒充 PASS。

## 測試順序

1. 先寫 left/right wall、方向 brake、special、launch、dwell fixed tests。
2. 先寫 wall telemetry 與 summary Gate 的 failing tests。
3. 實作共用 wall guard 與 telemetry。
4. 用兩段舊 MP4 離線 replay；修正版不得再於 guard zone 輸出向牆外 action。
5. 執行 targeted tests、完整 pytest、compileall、dry-run、artifact JSON 與
   `git diff --check`。

## 進入 P4.0 的唯一門檻

修復後只跑一個全新 bounded 3-episode Teacher Real Micro Gate。必須同時滿足：

- Gate artifact `passed=true`；
- safety events 0；
- transition/controller/MP4 完整；
- observation 與 floor telemetry Gate 通過；
- LEFT／RIGHT physical latency 均有樣本；
- 有 reach-floor-3 與 reach-floor-5 案例；
- 無 action collapse；
- `outward_wall_push_count=0` 且 `max_outward_wall_push_streak=0`；
- 人工影片未見持續撞牆或 spring/spike trap。

任一項失敗即停在 P3.6，記錄 failure branch，不進 P4.0。這次修復不要求重新訓練，
也不因單次最高樓層提高而降低 safety Gate。
