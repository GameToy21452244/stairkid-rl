# Simulator v0.5 Normal Fidelity Manual Candidate

日期：2026-08-07  
狀態：`READY_FOR_USER_MANUAL_RETEST_3`（manual-only，非 formal Gate）

## 目標

本候選只處理普通平台，特殊平台暫不加入。前兩輪回饋已累積：

1. v0.5-r1：60 Hz 改善流暢度，但起步仍有阻力、水平移動過於線性。
2. v0.5-r2：引入非線性加速曲線；平台96 px明顯太寬；下墜重力不足。
3. v0.5-r3（本輪）：引入 startup impulse、brake-then-impulse 反轉、分離 RELEASE 減速；平台縮至72 px；gravity -320；max fall speed 420；scroll 恢復實機值 96 px/s。

## 參考與限制

主要實機視覺參考：

- https://youtu.be/vjeleK5T6T0

公開遊玩畫面可用來判斷普通平台的比例、下降節奏與街機式修正感，但沒有同步 keypress
timestamp，不能單靠影片聲稱正式 Simulator／Real Alignment PASS。

已分析的實機量測資料（alignment audit v3）：

| 項目 | 值 | 來源 |
|------|-----|------|
| 實機 cadence | 125 ms | 量測 |
| LEFT delta-vx (125ms) | -44.0 px/s | 量測 |
| RIGHT delta-vx (125ms) | +63.3 px/s | 量測 |
| scroll speed | 96 px/s | 量測 |
| 平台寬度 | 72 px | 視覺估算（無 bounding box 資料）|
| gravity | 320 px/s² | 使用者回饋 + 影片節奏估算 |

## v0.5-r3 預設值

獨立入口：

```text
scripts/run_simulator_manual_v05.py
```

預設：

| 參數 | v0.5-r3 值 | v0.4 值 |
|------|-----------|---------|
| control fps | 60 Hz | 10 Hz |
| physics hz | 60 Hz | 60 Hz |
| display fps | 120（可改） | — |
| base horizontal acceleration | 420 px/s² | 560 px/s² |
| low-speed startup multiplier | 2.4× | 無 |
| acceleration curve exponent | 2.0 | 無（線性）|
| max horizontal speed | 230 px/s | 230 px/s |
| air control multiplier | 0.85 | 0.85 |
| release deceleration | 960 px/s² | 960 px/s² |
| reverse_brake_multiplier | 1.0（session override） | 1.25 |
| startup impulse speed | 60 px/s（session） | — |
| reversal brake speed | 30 px/s（session） | — |
| normal platform width | **72 px** | 96 px |
| gravity magnitude | **320 px/s²** | 192 px/s² |
| max fall speed | **420 px/s** | None |
| scroll speed | **96 px/s** | 80 px/s |

> **注意**：`reverse_brake_multiplier`、`startup impulse`、`brake-then-impulse` 屬於 `ResponsiveManualSession.step_once()` session-level override，不會影響 `ShaftSimulator` 的基礎測試。

## 水平手感架構

```text
低速 (|vx| < startup_impulse_speed=60):
  立即設定 vx = ±startup_impulse_speed（startup impulse）

反轉（方向相反且 |vx| > reversal_brake_speed=30）:
  1. 先 brake：清零 vx
  2. 再 impulse：設定 vx = ±startup_impulse_speed

正常加速（非線性曲線）:
  speed_ratio = |vx| / max_speed
  effective_accel = base_accel × (startup_mult × (1 - speed_ratio^exp) + speed_ratio^exp)
  ≈ 低速：420 × 2.4 ≈ 1008 px/s²
  ≈ 中速：逐步下降
  ≈ 接近最高速：420 px/s²

RELEASE（獨立）:
  deceleration = 960 px/s²，不觸發反轉邏輯
```

## 重測啟動方式

先更新 worktree：

```powershell
git pull
```

反轉與起步測試：

```powershell
& "C:\Users\jeffr\Downloads\NS Shaft│小朋友下樓梯\ai-stair-agent\.venv\Scripts\python.exe" `
  ".\scripts\run_simulator_manual_v05.py" `
  --scenario reverse_braking `
  --seed 900001 `
  --display-fps 120 `
  --show-debug `
  --record
```

普通平台自由遊玩：

```powershell
& "C:\Users\jeffr\Downloads\NS Shaft│小朋友下樓梯\ai-stair-agent\.venv\Scripts\python.exe" `
  ".\scripts\run_simulator_manual_v05.py" `
  --scenario normal_baseline `
  --seed 900001 `
  --display-fps 120 `
  --show-debug `
  --record
```

## 不修改程式的調參方式

每次只調一組相關參數，不要同時改所有值。

**平台仍偏寬**（感覺比原版寬）：
```powershell
--platform-width 64
```

**平台太窄**（感覺比原版窄）：
```powershell
--platform-width 80
```

**起步仍太慢**（按鍵後還是有延遲感）：
```powershell
--startup-acceleration-multiplier 2.8
```

**起步太衝**（一按就飛）：
```powershell
--startup-acceleration-multiplier 2.0
```

**高速仍過於線性**：
```powershell
--acceleration-curve-exponent 2.6
```

**下墜仍太飄**（重力感不足）：
```powershell
--gravity 380 --max-fall-speed 480
```

**下墜太重**（感覺太快碰底）：
```powershell
--gravity 270 --max-fall-speed 360
```

**scroll 仍偏快**（畫面移動太急）：
```powershell
--scroll-speed 80
```

## 人工驗收順序

按以下順序逐項確認，每項以 OK / FAIL / PARTIAL 記錄：

1. **起步反應**：按下方向鍵時是否立即有速度，不再像推重物。
2. **加速曲線**：持續按鍵是否由快起步平滑進入最高速，而非全程固定斜率。
3. **方向反轉**：LEFT→RIGHT 或 RIGHT→LEFT 後，舊方向是否立即清除、新方向立即開始。
4. **RELEASE 行為**：放開方向鍵時是否平滑減速、不會突然逆向。
5. **平台寬度**：72 px 普通平台是否接近實機畫面比例（不偏寬、不偏窄）。
6. **下墜感**：離開平台後下墜是否比 v0.4 更快更有重量。
7. **穿透測試**：空中修正後是否仍能正確落台且不穿透。
8. **scroll 速度**：96 px/s 的捲軸是否接近實機速度感（可對比 `--scroll-speed 80`）。

## 測試涵蓋（自動化）

v0.5 測試套件：`tests/test_simulator_v05_normal_fidelity.py`

| 測試群組 | 驗證項目 |
|---------|---------|
| `TestV03FrozenConfig` | v0.3 預設 10 項不變 |
| `TestV04ProfileUnchanged` | v0.4 after-profile 6 項不變 |
| `TestV05IndependentProfile` | v0.5 只能透過明確 60Hz flag 啟用 |
| `TestV05NormalOnly` | 無特殊平台 flag |
| `TestDisplayFPSIndependence` | 60/120 display fps 物理結果相同 |
| `TestFirstInputResponse` | 第一 tick 立即有速度 |
| `TestReversalNoLongSlide` | 反轉在 35 tick (0.58s) 內完成 |
| `TestReversalNoInstantMirror` | 反轉不瞬間跳到對向最高速 |
| `TestReleaseSeparateFromReversal` | RELEASE 獨立減速、不逆向 |
| `TestPlatformWidthConsistency` | 物理寬度 = config 值 |
| `TestGravityFalling` | 落速單調遞增、不超過 max_fall_speed |
| `TestSweptLanding` | swept collision 仍能正確落台 |
| `TestDeterministicReplay` | 相同 seed + action 結果完全相同 |
| `TestSpecialPlatformsDisabled` | 無 spikes/spring/conveyor/flipping |

最新執行結果：**42/42 PASSED**

## 工程檢查

PR 合併前在 Windows 執行：

```powershell
.\ai-stair-agent\.venv\Scripts\python.exe scripts\run_simulator_manual_v05.py --list-scenarios
.\ai-stair-agent\.venv\Scripts\python.exe -m compileall -q src scripts tests
.\ai-stair-agent\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

若完整 pytest 有 FAIL，不要合併；保留第一個 traceback。

## 研究隔離

- v0.3 與 v0.4 原始 profile 未改寫（tests 驗證）。
- 60 Hz 只允許 manual fidelity candidate。
- Phase C 維持 FAIL。
- Holdout 未使用。
- 不生成 Dataset v2。
- 不訓練 Student。
- 不宣稱 Alignment PASS 或 COLAB_READY。

## 版本紀錄

| 版本 | 日期 | 狀態 | 主要變更 |
|------|------|------|---------|
| v0.5-r1 | 2026-08-05 | USER_CONFIRMED_PARTIAL | 60Hz 改善流暢，起步仍有阻力 |
| v0.5-r2 | 2026-08-06 | READY_FOR_USER_MANUAL_RETEST_2 | 非線性加速，平台 72px，gravity 320 |
| v0.5-r3 | 2026-08-07 | READY_FOR_USER_MANUAL_RETEST_3 | startup impulse，brake-then-impulse 反轉，RELEASE 分離，42 tests PASS |
