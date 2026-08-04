# Manual Simulator Calibration Report

日期：2026-08-04  
狀態：`READY_FOR_USER_MANUAL_RETEST`（manual-only，非 formal Gate）

## 結論

本輪完成普通平台模擬器的可重現修正前／修正後比較。Render 30／60／120 FPS 在相同
12 control steps下均執行72個fixed 60 Hz physics steps，landing、terminal與最終state一致；
平台穿越不是render FPS或physics timestep造成。實際失敗是斜向高速落台時，角色在
top-surface crossing瞬間仍重疊平台，但physics substep結束位置已移出平台，舊版只以結束
位置判斷水平overlap。

修正版使用top-surface time-of-impact的水平位置作swept overlap，diagonal-edge案例由穿透
改為landing。從下方上升仍可穿越平台，這是目前one-way語意；因缺直接實機片段，維持
`UNRESOLVED_ONE_WAY_SEMANTICS`，不宣稱已正式對齊。

## 版本隔離

- `ShaftEnvConfig()`保留凍結`ns-shaft-sim-v0.3`預設與原RNG stream，確保既有Oracle／
  formal seed測試可重現。
- 人工工具的`after` profile明確使用`ns-shaft-sim-v0.4-calibration-candidate`。
- 校準候選不是production Oracle、formal development或alignment PASS。
- Frozen branch artifact SHA-256仍為
  `e4952a8332f7c2a25acb564e28a8b47b9b733e4c4bb073f19eade79501cd9758`；protocol仍為
  `9d4fae44ae6c47714e48a3ebdae4b953f9e6f257c6f6604f8469cfd10859ccbe`。

## Before／After

| 指標 | before v0.3 | after候選 |
|---|---:|---:|
| horizontal acceleration | 1048 px/s² | 560 px/s² |
| airborne multiplier | 1.00 | 0.85 |
| max horizontal speed | 230 px/s | 230 px/s |
| RELEASE：160 px/s一個control step後 | 5.6 px/s | 64 px/s |
| 從最大RIGHT反向到LEFT | step 3 | step 4 |
| scroll | 96 px/s | 80 px/s |
| vertical platform gap median | 48 px | 48 px |
| abs horizontal shift median | 29.78 px | 81.43 px |
| abs horizontal shift Q75 | 45.79 px | 118.08 px |
| shift <12 px | 159/800 | 0/800 |
| conservative impossible transition | 0/800 | 0/800 |
| diagonal edge tunneling | reproduced | fixed in candidate |

控制候選以既有real alignment packet為依據：真機125 ms cadence的LEFT／RIGHT median
delta-vx為-44／+63.27 px/s；RELEASE速度比中位數0.26；abs vx median／Q75為128／172。
因此降低支撐加速度、另設air control、將RELEASE改為線性減速並保留230 px/s上限。

平台垂直間距維持48 px，因真機樣本中位數也是48；密度問題主要來自水平shift過度集中。
候選使用24 px minimum shift與最多8次bounded rejection，median由29.78提升至81.43，接近
真機80 px。特殊平台生成仍全部關閉。

Scroll由96降至80 px/s是回應使用者主觀「太快」的人工候選；既有packet量測值其實是96，
所以此值必須由使用者before／after重測，不能稱為正式校準完成。

## 證據與限制

- Before：`artifacts/manual_simulator_calibration/before/metrics.json`
- After：`artifacts/manual_simulator_calibration/after/metrics.json`
- Comparison：`artifacts/manual_simulator_calibration/comparison/comparison.json`
- 彙總：`artifacts/manual_simulator_calibration/calibration_summary.json`
- 各profile另含M02～M08 CSV traces與acceleration SVG。
- 使用seeds 901100～901199（manual-only）；未使用17000／19000 holdout。
- 沒有啟動原版遊戲、沒有OS-level input、沒有training。

目前仍需：使用者以`B`切換before／after，完成控制、穿透、scroll與密度六項人工評分；
取得rising-from-below直接實機片段；用較長無遮擋實機片段再確認layout distribution。

## Engineering verification

- Calibration／frozen-seed regression：12 passed。
- Simulator／manual targeted：185 passed。
- Full pytest：587 passed。
- `python -m compileall -q src scripts tests`：PASS。
- `git diff --check`：PASS。
- Manual headless smoke：PASS。
