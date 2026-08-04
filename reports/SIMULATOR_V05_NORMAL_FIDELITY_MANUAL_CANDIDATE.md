# Simulator v0.5 Normal Fidelity Manual Candidate

日期：2026-08-04  
狀態：`READY_FOR_USER_MANUAL_RETEST`（manual-only，非 formal Gate）

## 目標

本候選只處理普通平台的第一優先問題：

1. 顯示設為60或120 FPS時仍有10 Hz狀態跳格感。
2. LEFT直接切RIGHT（或反向）時，角色會先花數個control steps抵銷舊速度。
3. 使用者希望移除方塊式慣性，讓新方向在下一個physics tick就開始生效。

特殊平台（spring、conveyor、spikes、flipping）不在本輪範圍內。

## 依據

### Repository現況

v0.4 manual profile使用：

- control：10 Hz
- physics：60 Hz
- render：使用者可選60或120 FPS
- horizontal acceleration：560 px/s²
- air control multiplier：0.85
- max horizontal speed：230 px/s
- release deceleration：960 px/s²
- reverse brake multiplier：1.25

因此把render從60提高到120不會增加每秒的控制／模擬狀態更新次數。

### 使用者manual session

已排除太短、沒有方向輸入、reset／focus異常與明顯操作失誤的session。有效v0.4
normal-baseline資料中，直接方向反轉通常需要約0.3～0.4秒才跨過vx=0。這與使用者
描述的「按右後仍短暫往左」一致。

### 實機視覺參考

主要參考：

- https://youtu.be/vjeleK5T6T0

此影片用於確認原版普通平台的整體節奏、左右修正感、落台與垂直捲動外觀。本候選沒有
把影片當成精確按鍵時間資料；沒有可見keypress timestamp時，不宣稱已完成正式
Simulator／Real Alignment。

## v0.5做法

新增獨立入口：

```text
scripts/run_simulator_manual_v05.py
```

只在此manual runner中：

- control與physics同為固定60 Hz。
- display可為60或120 FPS，但不改變模擬結果。
- LEFT／RIGHT反轉時先清除舊方向vx，再由新方向從0開始加速。
- 不把完整速度直接鏡射到另一方向。
- RELEASE仍使用既有線性減速度。
- collision、scroll、normal generator沿用v0.4。
- N只循環M01～M08普通平台場景。
- B不切換profile，避免本session混入v0.3／v0.4。

`ShaftEnvConfig`只在`allow_manual_60hz_control=true`時允許`fps=60`；正式policy路徑仍只
允許8／10／12 Hz。

## 建議第一次執行

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_v05.py `
  --scenario reverse_braking `
  --seed 900001 `
  --display-fps 120 `
  --show-debug `
  --record
```

接著執行自由遊玩：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_v05.py `
  --scenario normal_baseline `
  --seed 900001 `
  --display-fps 120 `
  --show-debug `
  --record
```

輸出：

```text
artifacts/manual_simulator_test/v05/<session_id>/
```

## 可調參數

不修改程式即可嘗試：

```text
--horizontal-acceleration
--air-control-multiplier
--max-horizontal-speed
--release-deceleration
--scroll-speed
```

先固定其他值，每次只改一個參數。

建議順序：

1. 先確認方向反轉延遲是否消失。
2. 再確認起步是否太快／太慢。
3. 再確認空中修正是否太強／太弱。
4. 最後才調RELEASE與scroll。

## 人工驗收

至少確認：

- LEFT直接切RIGHT後，下一個畫面更新就開始往右。
- RIGHT直接切LEFT同理。
- 反向不再有約0.3～0.4秒的舊方向滑行。
- 角色不會瞬間從滿速LEFT變成滿速RIGHT。
- 空中反轉不會穿透normal platform。
- 60／120 display FPS只改流暢度，不改落台結果。
- normal平台密度與scroll仍維持v0.4候選範圍。

## 建議工程檢查

本PR建立端沒有完整repository runtime，因此需在Windows專案目錄執行：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_v05.py --list-scenarios
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

若完整pytest有FAIL，不要合併；把第一個FAIL traceback貼回PR。

## 研究隔離

- v0.3與v0.4原始profile未改寫。
- Phase C維持FAIL。
- Holdout未使用。
- 不生成Dataset v2。
- 不訓練Student。
- 不宣稱Alignment PASS或COLAB_READY。
