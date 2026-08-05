# Simulator v0.5 Normal Fidelity Manual Candidate

日期：2026-08-05  
狀態：`READY_FOR_USER_MANUAL_RETEST_2`（manual-only，非 formal Gate）

## 目標

本候選只處理普通平台，特殊平台暫不加入。第一輪60 Hz版本已改善整體流暢度與方向
反轉延遲；使用者第二輪回饋指出：

1. 起步仍有阻力，固定加速度過於線性。
2. 普通平台96 px明顯太寬。
3. 下墜重力不足，角色偏飄。

## 參考與限制

主要實機視覺參考：

- https://youtu.be/vjeleK5T6T0

公開遊玩畫面可用來判斷普通平台的比例、下降節奏與街機式修正感，但沒有同步keypress
timestamp，不能單靠影片聲稱正式Simulator／Real Alignment PASS。

使用者manual session中，已排除太短、沒有方向輸入、reset／focus異常與明顯誤操作的
紀錄。第一輪v0.5的結論只採用使用者直接人工回饋：流暢度改善，但起步、平台尺寸與
下墜感仍不接近實機。

## 第二輪v0.5預設

獨立入口：

```text
scripts/run_simulator_manual_v05.py
```

預設：

- control：60 Hz
- physics：60 Hz
- display：120 FPS（可改60；不改模擬結果）
- base horizontal acceleration：420 px/s²
- low-speed startup multiplier：2.4
- acceleration curve exponent：2.0
- max horizontal speed：230 px/s
- air control multiplier：0.85
- release deceleration：960 px/s²
- normal platform width：72 px（v0.4為96）
- gravity magnitude：320 px/s²（v0.4為192）
- max fall speed：420 px/s
- scroll speed：80 px/s

## 水平手感

不再採固定線性加速度。低速時使用較強起步加速，接近最高速度時平滑收斂：

```text
低速：約420 × 2.4 = 1008 px/s²
中速：倍率逐步下降
接近最高速：約420 px/s²
```

這保留快速街機式起步，又避免整段速度都以固定斜率增加。方向反轉時仍先清除舊方向
vx，再從新方向低速曲線開始，不會把滿速直接鏡射到另一側。

## 平台與重力

- 每個現有normal platform在v0.5 session建立時重建為72 px寬。
- 高度、中心位置、生成順序與v0.4相同。
- gravity由-192提高為-320 px/s²。
- max fall speed設為420 px/s，避免無上限加速。
- collision仍使用v0.4 swept top-surface crossing。

## 第二次重測

先更新worktree：

```powershell
git pull
```

反向與起步：

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

平台仍偏寬：

```powershell
--platform-width 64
```

平台變得太窄：

```powershell
--platform-width 80
```

起步仍太慢：

```powershell
--startup-acceleration-multiplier 2.8
```

起步太衝：

```powershell
--startup-acceleration-multiplier 2.0
```

速度後段仍過於線性：

```powershell
--acceleration-curve-exponent 2.6
```

下墜仍太飄：

```powershell
--gravity 380 --max-fall-speed 480
```

下墜太重：

```powershell
--gravity 270 --max-fall-speed 360
```

每次只調一組相關參數，不要同時改所有值。

## 人工驗收順序

1. 起步是否立即有反應、不再像推重物。
2. 持續按鍵時是否由快起步平滑進入最高速，而非固定線性。
3. LEFT／RIGHT反轉是否立即開始新方向。
4. 普通平台寬度是否接近實機畫面比例。
5. 離開平台後的下墜是否更快、更有重量。
6. 空中左右修正後是否仍能正確落台且不穿透。

## 工程檢查

PR建立端沒有完整private repository runtime。合併前在Windows執行：

```powershell
.\.venv\Scripts\python.exe scripts\run_simulator_manual_v05.py --list-scenarios
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

若完整pytest有FAIL，不要合併；保留第一個traceback。

## 研究隔離

- v0.3與v0.4原始profile未改寫。
- 60 Hz只允許manual fidelity candidate。
- Phase C維持FAIL。
- Holdout未使用。
- 不生成Dataset v2。
- 不訓練Student。
- 不宣稱Alignment PASS或COLAB_READY。
