# NS-SHAFT 模擬器人工鍵盤測試 Runbook

日期：2026-08-04  
狀態：`MANUAL_SIMULATOR_TEST_READY`（非 formal Gate）

## 邊界與用途

此工具只操作本機Simulator的Pygame視窗，用來主觀比較`before` v0.3與`after`
v0.4 calibration candidate手感並保存
可重現紀錄。它不載入 Windows 輸入後端、不送出 OS-level 按鍵、不尋找或啟動原版
`NS Shaft.exe`，也不使用 Oracle、formal development或holdout seeds。

人工測試可以發現明顯 mismatch，但人工 PASS 不等於 formal Simulator／Real Alignment
PASS。所有輸出固定標示 `formal_evidence=false`、`manual_alignment_only=true`。

## 如何啟動

在 repository 根目錄執行：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_test.py `
  --scenario normal_baseline `
  --seed 900001 `
  --profile after `
  --show-debug `
  --fps 60
```

同時錄影：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_test.py `
  --scenario horizontal_acceleration `
  --seed 900001 `
  --record `
  --output-dir artifacts/manual_simulator_test/ `
  --show-debug `
  --fps 60
```

列出全部固定場景：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_test.py --list-scenarios
```

`--fps`只控制視窗更新率。Simulator control仍為10 Hz，physics仍為固定60 Hz；工具不會
為了畫面流暢度修改正式 timing。Seed必須大於或等於900000，並固定標記
`role=manual_only`、`formal_evaluation_allowed=false`，因此17000與19000 holdout會在CLI
建立session前直接被拒絕。

## 鍵盤操作

- `LEFT`／`A`：向左。
- `RIGHT`／`D`：向右。
- 沒有按方向鍵，或同時按左右：`RELEASE_ALL`。
- `R`：重設目前固定場景。
- `N`：切換下一個場景。
- `B`：在`before` v0.3與`after` v0.4 candidate間切換，並重設目前場景。
- `P`／Space：暫停或繼續。
- `F1`：顯示或隱藏完整debug overlay。
- `F2`：開始或停止MP4／frame sequence紀錄。
- `F3`：開啟人工評分；再次按`F3`保存並關閉。
- `ESC`：安全結束並保存已完成紀錄。

失去 simulator 視窗focus時，held keys會立即清空，當前動作視為`RELEASE_ALL`。關閉視窗、
Ctrl+C或例外皆由`finally`關閉Pygame與Simulator並保存session。

### F3 人工評分

評分畫面會暫停Simulator：

- `1`～`5`：`very_close`、`close`、`noticeably_different`、
  `very_different`、`unknown`。
- 數字評分同時回答目前校準問題；`Q`切換六項問題（加速、RELEASE、反向、穿透、
  scroll、平台密度）。
- `Up`／`Down`：切換差異標籤。
- Enter：選取或取消目前標籤。
- Tab：進入或離開note輸入；輸入文字，Backspace可刪除。
- `F3`：保存rating、tags與note。
- `ESC`：不等待評分完成，直接安全保存並結束整個session。

## 固定場景

| ID | `--scenario` | 用途 | 狀態 |
|---|---|---|---|
| M01 | `normal_baseline` | normal free play、落下與捲動 | MANUAL ONLY |
| M02 | `horizontal_acceleration` | LEFT／RIGHT加速 | MANUAL ONLY |
| M03 | `release_damping` | 固定初速後RELEASE | MANUAL ONLY |
| M04 | `reverse_braking` | 固定RIGHT初速後反向煞車 | MANUAL ONLY |
| M05 | `platform_edge_departure` | 左右平台邊緣與support departure | MANUAL ONLY |
| M06 | `landing_support` | landing、support與平台跟隨 | MANUAL ONLY |
| M07 | `top_terminal` | top boundary、headroom與terminal timing | MANUAL ONLY |
| M08 | `bottom_terminal` | bottom boundary與terminal timing | MANUAL ONLY |
| M09 | `spring` | spring landing與bounce | PROVISIONAL |
| M10 | `conveyor_left` | 左向conveyor速度變化 | PROVISIONAL |
| M11 | `conveyor_right` | 右向conveyor速度變化 | PROVISIONAL |
| M12 | `spikes` | spike damage與health | PROVISIONAL |
| M13 | `flipping_active` | active flipping collision | PROVISIONAL |
| M14 | `flipping_inactive` | inactive flipping穿越 | PROVISIONAL |
| M15 | `normal_healing` | normal-platform health recovery | PROVISIONAL |

Spring、conveyor、spikes、flipping與normal-platform healing已有獨立mechanism，可固定重現並
人工測試；但 Simulator／Real Alignment 尚未PASS，因此全部明確顯示`PROVISIONAL`。
專案目前沒有獨立的`healing` platform kind，只有normal平台的healing機制；獨立healing
平台為`UNSUPPORTED`，不得由M15冒充。

## 建議測試順序

```text
M02 acceleration
→ M03 release
→ M04 reverse braking
→ M05 edge departure
→ M06 landing/support
→ M07 top
→ M08 bottom
→ M01 free play
→ M09～M15 special mechanisms
```

第一次建議先測M02、M03、M04。這三項能最快分離加速、放開阻尼與反向煞車的主觀差異。

## 與實機比較方法

原版遊戲只能由使用者另行、人工啟動與操作；此工具不會替使用者啟動或送鍵。

1. 先在Simulator執行固定按鍵節奏。
2. 再由使用者於原版遊戲人工做接近的按鍵節奏。
3. 兩邊都錄影。
4. 比較位移、停止時間、反轉時間、離開平台時間、落地時間與scroll壓力。
5. 不要求場景畫面完全相同，只比較控制反應與physics語意。

後續仍須用side-by-side影片、同步時間軸與metrics完成正式Alignment；人工觀察不能取代
support/rising distribution、special mechanisms或reproducibility Gate。

## 紀錄輸出

每次啟動建立獨立資料夾：

```text
artifacts/manual_simulator_test/<session_id>/
```

內容包括：

- `session_summary.json`
- `frame_or_step_log.csv`
- `manual_ratings.json`
- `events.json`
- `README.md`
- `recording.mp4`，或編碼器不可用時的`recording_frames/`（僅在錄影啟用後）

Summary保存Simulator版本、commit、physics／state／manual工具hash、scenario config hash、
geometry、timing、控制mapping、terminal與人工評分。這些紀錄是manual-only，不得合併至
formal artifact或Dataset v2。

## Headless smoke

不開GUI的工程smoke：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_test.py `
  --headless-smoke `
  --seed 900002 `
  --smoke-steps 6 `
  --profile after
```

Headless PASS只驗證場景、控制狀態、focus release、overlay render與log契約；不宣稱已完成
實際人工操作或正式Alignment。
