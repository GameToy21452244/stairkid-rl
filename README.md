# AI Stair Agent：NS-SHAFT 遊戲介面層

本專案以一般 Windows 視窗 API、螢幕擷取及鍵盤輸入控制既有的
`NS Shaft.exe`。目前已完成遊戲介面層、角色／平台／血量事件辨識、Gymnasium
環境，以及具有硬性安全上限的本機 PPO 訓練入口。PPO 仍在短時間實機驗證
階段，尚未產生可用的遊玩模型。

專案不修改、注入、掛鉤、反編譯遊戲，也不讀取遊戲程序記憶體。預設
`auto_launch: false`，任何工具都不會自行執行遊戲；請由使用者手動啟動。

## 安裝

需求為 Windows 10/11 與 Python 3.11。在 PowerShell 進入本目錄後執行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

若 PowerShell 的執行原則不允許啟用環境，可直接使用
`.\.venv\Scripts\python.exe` 代替下方命令中的 `python`。

本專案不需要 editable install；腳本會從本專案的 `src` 載入套件。這也避免
某些繁體中文 Windows 在含特殊字元的路徑建立 editable `.pth` 時遇到編碼問題。

一般擷取、辨識與控制工具不需要 PyTorch。只有進行 PPO 訓練時才另外安裝：

```powershell
python -m pip install -r requirements-rl.txt
```

Windows CPU 版固定使用 PyTorch `2.8.0+cpu`，Stable-Baselines3 使用 `2.9.0`。
PyTorch 2.9 在部分 Windows 環境有 DLL 載入回歸，因此本專案不使用該版本。
這些套件只安裝在 `.venv`，不會修改遊戲或系統 Python，也不會在背景常駐。

## 設定

初次使用時複製範例：

```powershell
Copy-Item config.example.yaml config.yaml
```

此工作區已建立一份被 Git 忽略的 `config.yaml`，並填入已知的
`NS Shaft.exe` 完整路徑。請確認下列集中設定，不要把值寫入程式碼：

- `game.exe_path`：遊戲執行檔完整路徑。
- `game.window_title_contains`：遊戲視窗標題的一部分；目前已確認為 `NS-SHAFT`。
- `game.window_class_name`：選填的 Windows class。此遊戲已確認為
  `NsShaftClass`，可避免把同名終端機或 OpenCV 預覽誤判成遊戲。
- `game.auto_launch`：預設 `false`。只有明確改為 `true` 才會由工具啟動設定的 exe。
- `controls.left_key`、`right_key`、`restart_key`：遊戲按鍵。
- `controls.restart_duration_ms`：重新開始鍵的按住時間，實機測試預設為 200 ms。
- `controls.input_backend`：預設 `pyautogui`；只有遊戲不接受時才改為
  `pydirectinput`。
- `capture`：擷取模式、校正值、輸出尺寸與 FPS。
- `events.landing_contact_gap`：一般落地接觸距離，實機值為 6。
- `events.spring_contact_gap`：彈簧接觸距離；依實際 JSONL 校正為 12。
- `safety.block_on_related_windows`：預設 `true`；同程序或由主遊戲擁有的其他
  可見視窗出現時，禁止所有自動輸入。
- `environment.auto_restart_on_reset`：預設 `false`；只有受限重設實機確認後才
  可考慮開啟。

`config.yaml` 已加入 `.gitignore`，本機路徑不會提交。`client_area` 模式下，
`left`、`top` 是相對於遊戲 client area 左上角的偏移；視窗移動時會重新取得
client area，不依賴固定螢幕座標。`width`、`height` 留空代表使用剩餘完整區域。

## 建議操作順序

先手動啟動 `NS Shaft.exe`，確認遊戲可正常操作，再依序執行以下工具。

### 1. 尋找視窗

```powershell
python scripts/find_window.py
```

工具列出所有可見視窗的標題、完整視窗矩形與 client area，並指出符合
`window_title_contains` 的第一個視窗。若找不到，請從清單複製一段實際標題回
`config.yaml`。工具不會在 `auto_launch: false` 時啟動任何 exe。

### 2. 校正擷取範圍

```powershell
python scripts/calibrate_capture.py
```

預覽會顯示 FPS 與綠色擷取邊界。按鍵如下：

- `H` / `L`：擷取範圍向左／右移。
- `K` / `J`：向上／下移。
- `A` / `D`：縮小／增加寬度。
- `W` / `X`：增加／縮小高度。
- `S`：只儲存當前畫面到 `captures/calibration/`。
- `Enter`：把目前校正值寫入 `config.yaml` 並離開。
- `Esc`：不寫入設定並離開。

每幀都會重新查詢 client area，因此移動遊戲視窗後仍會跟隨。視窗關閉、
最小化或範圍超出 client area 時會顯示明確錯誤。

### 3. 測試畫面擷取

```powershell
python scripts/test_capture.py
```

這個工具只顯示即時畫面，完全不控制遊戲。按 `Esc` 離開。

### 4. 安全測試左右鍵

```powershell
python scripts/test_input.py
```

工具先顯示目標與按鍵，只有手動輸入大寫 `YES` 才繼續。接著嘗試聚焦遊戲、
倒數 3 秒、按左約 300 ms、全部放開、等待 1 秒、按右約 300 ms，再全部放開。
如果 PyAutoGUI 無效，先結束工具，再把 `input_backend` 改成
`pydirectinput` 重試；不要預設替代後端一定較好。

所有送鍵前都要求目標遊戲位於前景。失去焦點、發生例外、按 `F8`、按
`Ctrl+C` 或正常離開時，都會執行 `release_all()`。PyAutoGUI 原生的滑鼠移至
螢幕角落 fail-safe 保持啟用；程式若偵測它被外部關閉，會拒絕啟動控制器。
控制器會在呼叫輸入後端前先登記按住的鍵，因此後端送鍵途中發生例外也能立即
嘗試釋放；`release_all()` 只釋放本程序實際追蹤的鍵，不會在沒有按鍵被按住時
額外送出 LEFT／RIGHT key-up，避免 NS-SHAFT 死亡選單把多餘 key-up 當成焦點
導覽。

### 5. 人工收集遊戲狀態畫面

```powershell
python scripts/collect_frames.py
```

只有按下標記鍵時才會存圖，不會自動大量寫入：

- `1`：`menu`
- `2`：`playing`
- `3`：`game_over`
- `4`：`dialog`（開局與死亡後都會出現的中央小選單）
- `5`：`name_entry`（死亡後偶爾出現、可按 Enter 略過的姓名輸入框）
- `S`：`unclassified`
- `Esc`：離開

圖片存於 `captures/labeled/`。同目錄的 `metadata.jsonl` 逐筆記錄檔名、標籤、
實際擷取區域、原始區域尺寸、儲存後尺寸與含時區時間。現階段
`GameStateDetector` 保守回傳 `UNKNOWN`；收集足夠的三類樣本後，下一階段才
適合實作 template matching 或其他辨識方式。

實機確認 NS-SHAFT 在開局與角色死亡後都會顯示相同類型的中央模態對話框，
因此另設 `DIALOG` 視覺狀態。之後的流程狀態機應根據前一狀態判斷其語意：
程式啟動後的 `DIALOG` 是開局選單，`PLAYING → DIALOG` 則代表回合結束。
在取得多張樣本並確認預設焦點前，不自動對此對話框送出 Enter。

死亡後另有一個非必定出現的 `NAME_ENTRY` 分支。後續安全流程每次只允許送出
一次 Enter，送出後必須重新擷取並確認狀態：若由 `NAME_ENTRY` 回到 `DIALOG`，
才可再考慮下一次 Enter；不可預先連按兩次。

收集樣本後，先框選中央完整白色對話框並建立範本：

```powershell
python scripts/calibrate_dialog.py
```

接著先離線檢查所有已標記圖片，再執行不送按鍵的即時辨識：

```powershell
python scripts/test_state_detection.py --offline
python scripts/test_state_detection.py
```

辨識穩定後，可執行互動式單次 Enter 安全測試：

```powershell
python scripts/test_dialog_action.py
```

工具會先要求輸入大寫 `YES`，接著只進行一次有提示音的 3 秒倒數；看到
`3...` 後請立即手動點選遊戲，之後不要再切換視窗。工具不會在倒數顯示前先
搶走 PowerShell 焦點。只有遊戲位於前景且連續三幀均為 `DIALOG`，才會送出一次
Enter。若按鍵後仍為
`DIALOG`，無論內容是否改變都不會自動送出第二次 Enter；必須重新執行腳本並
再次人工確認。任何時候按 F8、失去焦點或發生例外都會釋放所有按鍵。

單次 Enter 驗證完成後，可安全監看一個完整回合：

```powershell
python scripts/test_session_loop.py --max-seconds 60
```

工具只在起始狀態為 `DIALOG` 時送一次 Enter，完全不控制左右鍵。它使用狀態機
區分首次對話框與 `PLAYING → DIALOG` 的死亡事件；偵測死亡、失焦、F8、
狀態不明或達時間上限時立即停止，且不自動重開第二回合。

## 角色與平台辨識

初版以校正後的遊戲場地 ROI 排除外部 UI。角色使用高飽和暖色遮罩、形態合併與
尺寸／密度篩選；普通亮青色冰平台使用由實際 playing 樣本裁出的模板比對與
非極大值抑制。現在已分別使用實際樣本建立普通、尖刺、綠色特殊與輸送帶
平台範本，重疊候選只保留信心最高的類型。角色追蹤器會從連續畫面估計上升、
下降與畫面速度，並找出角色下方最近且水平重疊的平台。向下翻轉石板已使用
實際 playing 畫面建立薄型與展開型兩個範本；輸送帶也加入另一個動畫相位。

如需重新校正場地與普通平台：

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind normal
```

其他平台可用已標記的 playing 圖片逐類重新框選：

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind spikes
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind spring
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind conveyor
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind flipping
```

輸送帶本身具有動畫，只用一張範本時，分數可能在門檻附近上下波動而造成框線
閃爍。程式現在會將短暫漏判保留 2 幀，並支援同類型的多個動畫範本。若仍會
閃爍，請先用 `collect_frames.py` 在不同動畫相位各儲存一張 playing 畫面，再
依序建立額外範本：

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind conveyor --variant 2
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind conveyor --variant 3
```

翻轉石板同樣建議至少擷取水平與翻轉中的不同相位：

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind flipping --variant 1
.\.venv\Scripts\python.exe scripts\calibrate_objects.py --kind flipping --variant 2
```

每次可用 `--sample captures/labeled/檔名.png` 指定包含該動畫相位的畫面。校正
結果寫入本機 `config.yaml`，圖片位於被 Git 忽略的 `captures/templates/`。

先執行離線檢查，再執行不送按鍵的即時預覽：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_game_objects.py --offline
.\.venv\Scripts\python.exe scripts\inspect_game_objects.py
```

綠框代表角色、青框代表普通平台、紅框代表尖刺、黃框代表彈簧平台、
洋紅框代表輸送帶、橘框代表翻轉石板，灰框代表可遊玩場地 ROI。即時工具同時顯示角色
座標、移動狀態、下方最近平台、距離及平台數量；它只在 `PLAYING` 狀態執行
物件辨識，對話框出現時不會輸出假的角色或平台結果。

彈簧被踩下時外觀會短暫改變，因此單張模板的黃框可能消失。即時流程會保留
彈簧最近 2 幀的位置，並使用連續條件「角色下降且接近彈簧 → 數幀內轉為上升」
輸出 `spring_bounce` 事件。這比只依賴壓縮後的外觀可靠，也讓後續 AI 知道角色
將獲得一小段向上速度。實機觀測的反彈接觸距離為 9–10 像素，因此彈簧門檻
獨立設為 12；一般落地仍維持 6，避免提早判定。事件只描述遊戲狀態，不會替
玩家送出任何按鍵。

目前 `collect_frames.py` 的標記鍵由 OpenCV 預覽視窗接收，點擊預覽會使遊戲
失去前景，因此動畫瞬間較難擷取。現有翻轉石板與輸送帶樣本已足夠；若後續仍
需大量補圖，再加入不搶遊戲焦點的全域截圖熱鍵，並避開 F8 緊急停止鍵。

## 跨幀平台與遊戲事件

即時流程現在會替每個平台配置回合內的 `track_id`，框線標籤會顯示例如
`#7 normal`。平台移動後仍保留相同 ID；新進入畫面的平台取得新 ID。多個成功
配對平台的垂直速度中位數會成為 `scroll`，用來估計整體畫面向上捲動，避免把
捲動全部誤認成角色自身速度。

目前事件定義如下：

- `landed`：角色下降接近平台後轉為穩定或上升。
- `floor_descended`：落到與上一次不同的有效平台 ID；第一次落地只建立基準。
- `spring_bounce`：接近彈簧後數幀內轉為上升。
- `health_gained`：LIFE 的有效相鄰觀測增加。
- `spike_damage`：近期接觸尖刺且 LIFE 淨變化不大於 `−4`。
- `damage`：有掉血但沒有足夠畫面證據歸因到尖刺。

尖刺同時伴隨下降回血時可能看到 `−4`，所以 `spike_damage` 接受這個淨變化；
若沒有尖刺接觸證據仍維持 generic `damage`。這些規則是可檢查的畫面推論，不是
讀取遊戲內部資料，也不會把不確定事件強制分類。

即時預覽底部改為三行半透明面板，確保事件、血量、角色速度、捲動速度、最近
平台與平台數量都留在畫面內。只讀預覽：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_game_objects.py
```

若要保留之後建立 RL 環境所需的結構化觀測，可明確加入參數：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_game_objects.py --record-jsonl
```

省略路徑時，每次執行會建立新的
`logs/observations_YYYYMMDD_HHMMSS_ffffff.jsonl`，不會把不同執行混在同一
檔案；也可在參數後指定新路徑。若指定檔案已存在，工具會拒絕覆寫或追加。
每筆包含角色位置／速度、平台 ID／類型／矩形、最近平台、血量、畫面捲動速度
及當幀事件。不加參數就不會逐幀寫入硬碟。整個 `logs/` 已被 Git 忽略。

終端事件會附帶來源平台，例如
`成功下降至新平台(flipping)`、`角色落地(conveyor)`；傷害則會附帶原始
`delta`，方便分辨平台分類與血量證據。

## Gymnasium 環境介面

單幀觀測編碼器把既有辨識結果轉為 64 個 `float32` 特徵，範圍固定在
`[-1, 1]`：
角色是否存在、位置、速度、升降狀態、血量、平台捲動速度、最近平台距離與
類型，以及普通／尖刺／彈簧／輸送帶／翻轉平台的可見數量。後續 48 維代表
最多 8 個優先平台，每個平台包含存在遮罩、相對 X、相對 Y、寬、高與類型；
因此策略與模型能知道平台位於角色左側或右側。`max_observation_platforms`
可在設定檔調整。

Gym 觀測 v3 預設由 `environment.observation_history_frames: 4` 堆疊最近 4 個
單幀特徵，並在每幀附加造成該觀測的 RELEASE／LEFT／RIGHT 三維 one-hot。
總維度為 `4 × (64 + 3) = 268`。reset 時以相同初始幀填滿歷史，動作欄保持
全零，因此不會把補零誤解為角色消失。`include_action_history: false` 可關閉
動作欄，此時預設維度為 256；改動歷史幀數或平台槽數會同步改變
observation space。動作空間為：

- `0`：`RELEASE_ALL`，不按方向鍵。
- `1`：`LEFT`，按左鍵一個設定中的短時間步。
- `2`：`RIGHT`，按右鍵一個設定中的短時間步。

第一版獎勵只採用已驗證、容易解釋的訊號：每次 `floor_descended` 加
`environment.floor_reward`；掉血按實際格數乘
`damage_penalty_per_segment` 扣分；回合終止再扣 `death_penalty`。每個控制步
另扣很小的 `environment.step_penalty`，避免角色站在正下方平台時把長期
`RELEASE_ALL` 當成零成本策略。預設 `0.01` 遠小於下樓的 `+1` 與死亡的 `−5`。
為降低短訓練時常見的左右抖動，LEFT 與 RIGHT 若在
`direction_change_window_steps`（預設 2 個控制步）內直接反轉，另扣
`direction_change_penalty`（預設 `0.02`）；超過時間窗的正常路線修正不扣。
若角色下方最近的水平重疊平台是尖刺，且距離不超過
`spike_contact_max_gap`（預設 12 像素），連續接觸超過
`spike_dwell_grace_steps`（預設 2 步）後，每步另扣
`spike_dwell_penalty`（預設 `0.03`）。離開尖刺接觸區會立刻清除停留計數。
連續選擇 `RELEASE_ALL` 時，前 `idle_action_grace_steps`（預設 2 步）不扣分，
第 3 步起每步另扣 `idle_action_penalty`（預設 `0.02`）；任何 LEFT 或 RIGHT
都會立刻清除 idle 計數。這讓角色仍可短暫等待正下方平台，但不鼓勵在彈簧或
其他平台長期原地反覆跳躍。
同一個最近平台 `track_id` 持續位於角色下方、距離不超過
`platform_dwell_max_gap`（預設 80 像素）時，也會累計平台停留步數；超過
`platform_dwell_grace_steps`（預設 12 步）後，每步扣
`platform_dwell_penalty`（預設 `0.02`）。換到新平台或原平台不再位於角色
下方時立即清零。若畫面事件同時顯示掉血，會先清除舊平台停留歷史，避免把
最上方尖刺造成的強制下墜／穿越平台誤判成模型仍停在原平台。
角色中心高度進入畫面頂端 `top_danger_y_ratio`（預設前 33%）且超過
`top_danger_grace_steps`（預設 2 步）時，每步另扣
`top_danger_penalty`（預設 `0.03`），讓策略在真正撞到頂端尖刺前就有離開
高風險區的學習訊號。
這些項目都只是小幅 shaping，不取代實際掉血與死亡懲罰，也不加入容易鼓勵原地
拖時間的存活獎勵。

每次 Gym `step()` 的 `info["reward_components"]` 會分別記錄反向切換、尖刺
接觸步數、idle 步數、同平台停留、頂端危險區及各項 reward，方便後續量化
抖動率與危險停留。這些
控制 shaping 只在具有 LEFT／RIGHT／RELEASE 動作的 Gym 控制步生效；人工與離線逐幀稽核
沒有等價控制頻率，因此不套用，避免把 15 FPS 畫面誤算成控制步。
回血與
`spring_bounce` 會保留在觀測／事件資訊，但不重複加獎勵。這可避免「下樓回血」
被同一事件計分兩次，也不會讓模型只為了彈簧獎勵偏離主要目標。

先執行完全離線的 mock 相容性檢查：

```powershell
.\.venv\Scripts\python.exe scripts\check_gym_env.py
```

這個預設模式不尋找遊戲、不載入鍵盤後端，也不操作鍵盤或滑鼠。如要人工確認
真實環境的接線，先手動開啟遊戲並進入角色正在遊玩的畫面，再執行：

```powershell
.\.venv\Scripts\python.exe scripts\check_gym_env.py --live
```

實機模式會先列出完整動作並要求輸入大寫 `YES`，接著倒數 3 秒，依序執行
「放開、短按左、放開、短按右、放開」。它不會按 Enter、不會自動重開、不會
執行隨機動作。若 reset 畫面不是 `PLAYING`，會立即停止。F8、失焦、例外與
正常結束都會釋放方向鍵。

時序堆疊完成後，可在死亡對話框或 PLAYING 狀態執行專用實機檢查：

```powershell
.\.venv\Scripts\python.exe scripts\test_temporal_observation.py
```

它最多在起始 reset 對主遊戲對話框送一次 Enter，然後只執行上述固定 5 個
動作，逐步核對 268 維形狀與最新動作 one-hot。死亡後不會重開第二回合。

本階段應在本機 Windows 驗證，因為 Colab 無法直接看到本機遊戲視窗或安全地
送出本機按鍵。後續若改成離線資料訓練才適合考慮 Colab；需要與遊戲互動的
online RL 訓練仍應在本機執行。

### 短回合軌跡與 reward 稽核

正式訓練前，先重播既有結構化觀測，確認 reward 規則與事件一致：

```powershell
.\.venv\Scripts\python.exe scripts\audit_rewards.py --offline logs\observations_檔名.jsonl
```

離線模式不尋找遊戲，也不載入或操作鍵盤。它會列出有事件或非零 reward 的
步驟，最後彙總成功下降、傷害、彈簧等事件數量及總 reward。若要另外產生含
64 維特徵的稽核軌跡，可加上尚不存在的輸出路徑：

```powershell
.\.venv\Scripts\python.exe scripts\audit_rewards.py `
  --offline logs\observations_檔名.jsonl `
  --output logs\offline_reward_audit.jsonl
```

實機人工遊玩稽核則執行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_rewards.py --max-seconds 30
```

工具會先確認視窗並要求輸入大寫 `YES`。倒數後請點選遊戲，接著由你親自使用
左右鍵遊玩；程式只旁觀畫面，不會送左右鍵、Enter 或任何隨機動作。每一幀的
人工動作標記為 `manual`，並記錄 phase、血量、事件、64 維特徵、單步 reward、
累計 reward 與終止狀態至新的 `logs/reward_audit_時間戳.jsonl`；精簡統計另存
為同名 `.summary.json`。既有檔案一律拒絕覆寫。

死亡對話框、未知狀態、時間上限、失焦、F8 與 Ctrl+C 都會安全結束；F8、失焦、
例外及正常結束仍會釋放所有方向鍵。這個工具用來檢查獎勵，不會訓練模型。

### 受限的回合重設

`environment.auto_restart_on_reset` 預設為 `false`，一般 Gymnasium 環境不會
擅自從對話框開始下一回合。受限 reset 的規則是：

- 穩定狀態已是 `PLAYING`：不送 Enter，只清除跨回合追蹤資料。
- 每個左右動作前重新確認仍是 `PLAYING`；若死亡選單已出現，立即釋放方向鍵，
  避免最後一次 LEFT／RIGHT 改變選單焦點。
- 連續 3 幀穩定為主遊戲 `DIALOG`，且右側單人「開始」按鈕具有校正後的焦點
  外框：最多短按一次設定中的 `restart_key`。
- 焦點明確位於中央雙人模式：先再次釋放控制器實際追蹤的方向鍵（不送新的
  key-down），再唯讀等待最多 `reset_focus_max_observation_frames`
  （預設約 15 秒），因為實機確認這可能只是死亡對話框重繪期間的暫態。只有
  單人開始焦點連續穩定後才允許 Enter。等待逾時時，僅在
  `controls.menu_focus_correction_key` 已經實機校正的情況下，才最多短按該鍵
  一次並再次驗證；目前預設為 `null`，因此逾時會停止。全程不連按或循環。
- 焦點位置不明或按鈕 ROI 未校正：停止且不送方向鍵或 Enter。

自動焦點修正鍵預設為 `null`，因此未校正時遇到雙人焦點只會停止。可先執行
下列工具；它不會自行製造雙人焦點，只有目前真實停在中央雙人時才測試一次
候選鍵，全程不按 Enter：

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_menu_focus.py `
  --candidate-key tab
```

只有工具在真實畫面回報成功後，才把
`controls.menu_focus_correction_key` 設為該鍵。
若雙人焦點只在訓練程序內維持、程序結束後又回到單人開始，可執行不按
Enter 的往返校正：

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_menu_focus.py `
  --candidate-key tab `
  --round-trip-from-start `
  --focus-target
```

此模式在目前為單人開始、中央雙人，或焦點可能位於名稱欄／終了按鈕時，逐次
送出最多四次 Tab；每次都重新確認仍是同一個 DIALOG，辨識到單人開始便立刻
停止，辨識到中央雙人則只再測試一次候選鍵。任一步辨識失敗都會停止，全程
不按 Enter。
`--focus-target` 與訓練工具相同，只在倒數後嘗試一次切換並驗證已知遊戲視窗；
Windows 拒絕切換時不會送出 Tab。
- Enter 後必須重新辨識為 `PLAYING` 才算成功。
- Enter 後仍是對話框、狀態不明、失焦、F8 或例外：立即停止，不補按第二次。
- 不搜尋、不聚焦，也不對另一個螢幕上的未知姓名輸入視窗送鍵。
- 任一與遊戲同程序或由遊戲擁有的額外可見視窗都視為阻擋視窗；即使主畫面
  像素仍看起來是 `PLAYING`，也會禁止 Enter 和左右鍵。

按鈕 ROI 位於 `detection.menu_start_button_*` 與
`detection.menu_two_player_button_*`，座標以 `detection.reference_width`、
`reference_height` 為基準。目前本機 `634×431` client 已依實際截圖校正；
焦點守門器同時辨識按鈕粗深色預設外框與內側鍵盤虛線框，鍵盤焦點優先。
其他版本或尺寸不可直接猜測，必須重新擷取選單畫面校正。

第一次實機驗證請保持 `auto_restart_on_reset: false`，只使用有明確回合上限的
互動工具：

```powershell
.\.venv\Scripts\python.exe scripts\test_episode_reset.py `
  --cycles 2 `
  --max-seconds-per-round 30
```

工具先顯示最多回合數並要求大寫 `YES`，倒數後才開始。它完全不控制左右鍵；
角色可自然死亡，或由你親自操作。每個回合只在起始 reset 時依上述規則決定
是否送一次 Enter，最後一個回合死亡後一定停止，不會繼續重開。`--cycles`
硬性限制為 1–3，避免測試意外成為無限循環。

### 單回合規則基準（不是訓練）

在安裝 RL 訓練器前，可使用可解釋的基準策略檢查 268 維時序觀測與連續左右
控制。它只考慮角色下方、設定距離內且類型位於
`baseline.safe_platform_kinds` 的平台；尖刺預設不在安全清單。策略會先依
垂直距離估計平台是否可達，再朝平台最近的安全落腳區短按左／右；已位於落腳
區或沒有可達落點時使用 `RELEASE_ALL`。修正版會鎖定
同一個平台；低更新率造成 `track_id` 改變時，會依類型與相近畫面位置重新取得
同一目標。要求反轉方向時先插入一個 RELEASE 控制步，避免每幀 LEFT／RIGHT
互切。角色剛從腳下平台上升時，策略會記住該平台的左右邊界並持續移出邊界；
若下一平台尚未出現，最多用兩個控制步（含必要的換向煞車）回到校正後的遊戲
區水平中心，以降低未知
平台從左右任一側出現時的最壞距離，不依賴被踩下後可能消失的彈簧黃色外觀。
角色下降且腳下即將接觸尖刺時也會先離開尖刺邊界。
尖刺不再觸發「盲目往反方向跳」；
移動方向必須對應實際可達的安全落點。只有角色逼近上方尖刺、完全沒有安全
落點且剩餘血量足以承受時，才允許把下方尖刺平台當作緊急落點。進入畫面
頂端危險區後，安全落點會改以「下降深度減去橫向移動成本」評分，避免在
彈簧鏈上原地等待直到碰到頂端尖刺。
它不會學習、不更新權重，也不執行隨機動作。

```powershell
.\.venv\Scripts\python.exe scripts\run_baseline.py `
  --max-steps 300 `
  --max-seconds 30
```

工具要求大寫 `YES` 與 3 秒倒數，只執行一回合；死亡、300 步、30 秒、F8、
失焦、額外遊戲視窗或例外任一條件成立就停止，死亡後不會重開第二回合。每步
決策、決策前觀測、動作後 268 維時序觀測、reward 與事件會寫到新的
`logs/baseline_時間戳.jsonl`，摘要另存 `.summary.json`。命令列硬上限為
1000 步與 120 秒，且所有輸入仍通過前景、related-window 與 release_all 防線。
JSONL 也會記錄每步的 `policy_decision`，包括原因、鎖定平台 ID／類型及水平
差距，方便離線檢查是否因 `avoid_nearby_spikes` 避讓或
`direction_change_brake` 暫停換向。

## 受限 PPO 訓練

先執行完全離線、使用 mock 環境的 smoke test；它不會擷取畫面或送出按鍵：

```powershell
.\.venv\Scripts\python.exe scripts\check_ppo.py
```

確認遊戲已手動開啟、位於前景並進入可開始回合的畫面後，才可執行受限訓練：

```powershell
.\.venv\Scripts\python.exe scripts\train_ppo.py `
  --timesteps 128 `
  --max-episodes 3 `
  --max-seconds 45 `
  --focus-target
```

工具要求輸入大寫 `TRAIN` 並倒數 3 秒。PPO 初期是探索策略，可能快速換向、
踩刺或摔落；這不代表模型已學會遊戲。步數必須是 `training.n_steps` 的整數倍，
避免 Stable-Baselines3 為完成 rollout 而超過核准的送鍵數。回合數、時間或
步數任一上限到達便停止；最後一個核准回合結束時不會自動多按一次 Enter。
F8、失焦、額外姓名視窗、例外與 Ctrl+C 都會停止並釋放方向鍵。
`--focus-target` 只在倒數後嘗試一次 Windows 前景切換並立即驗證；若 Windows
拒絕切換便停止。省略此旗標時仍要求使用者手動保持遊戲前景。

模型與 checkpoint 存於 `models/ppo/時間戳/`，整個 `models/` 已由 Git 忽略。
目前只允許 CPU 訓練；短期目標是先驗證資料流與安全重設，不以這次短訓練的
遊玩成績判斷 PPO 效果。

訓練完成後，使用 deterministic 動作進行相同硬上限的受限評估：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_ppo.py `
  --max-steps 128 `
  --max-episodes 3 `
  --max-seconds 45 `
  --focus-target
```

未指定 `--model` 時會選擇 `models/ppo/` 下最新的 `final_model.zip`。也可傳入
專案 `models/` 內的特定 `.zip`；工具拒絕載入該目錄以外或非 zip 的檔案。
開始前必須輸入大寫 `EVAL` 並倒數 3 秒。評估不更新模型，結果會存成模型旁的
`evaluation_時間戳.json`，同樣不會提交到 Git。
`--focus-target` 的行為與訓練工具相同：倒數後只嘗試一次聚焦並立即驗證，
失敗便停止且不送評估動作。

related-window 列舉可能比單次按鍵昂貴，因此現在由安全背景監控每 0.25 秒更新
快取；每個控制步只讀快取，不再同步列舉所有視窗。一旦背景偵測到額外遊戲
視窗，停止狀態具有黏性，該次程序即使視窗稍後消失也不會恢復送鍵。這項最佳化
不會關閉姓名視窗防線。

## LIFE 血量辨識與遊戲機制

`hud` 設定集中保存 LIFE 第一格位置、每格尺寸、間距與最大 12 格。辨識器只讀取
畫面像素，輸出目前可見血格及相鄰有效觀測的原始差值。已知遊戲規則為：

- 成功下降一階會回復 1 格。
- 碰到尖刺會損失 5 格。
- 平台持續向上捲動，最上方整排尖刺碰到時也會損失 5 格。

同一小段時間可能同時發生「尖刺 −5」與「下降成功 +1」，畫面觀測會呈現淨
變化 `−4`。因此目前診斷層只可靠記錄 `delta`，不把單一差值硬猜成特定事件；
下一階段會結合角色／平台接觸、跨越樓層與數個連續畫面才做事件分類。平台向上
捲動也表示角色的畫面座標速度不等於世界座標速度，後續狀態特徵必須使用相對
平台距離或估計捲動量補償。

目前本機校正值是以 `634x431` client area 為參考：
`life_left=49`、`life_top=32`、單格 `6x14`、間距 `8`、共 12 格。若遊戲版本或
介面不同，請修改 `config.yaml` 的 `hud` 區段，不要把座標散落到程式碼。

## 觀察外部姓名輸入視窗

姓名輸入框可能出現在另一個螢幕，而且不是每回合都出現。因為它不在遊戲
client area 內，主畫面的模板辨識看不到它。可在正常遊玩前先開啟唯讀監看：

```powershell
.\.venv\Scripts\python.exe scripts\watch_game_windows.py --seconds 120
```

若姓名框出現，先不要輸入，等待工具列出 `RELATED` 或 `NEW` 視窗的 PID、class、
標題、owner 與座標，並自動寫入 `logs/window_watch_時間戳.jsonl`。日誌可能
包含其他新開視窗的標題，因此整個 `logs/` 都被 Git 忽略，不會推送到遠端。
此工具不聚焦、不擷取其他視窗內容，也不送出按鍵。在取得實際資訊前，不會對
未知的外部視窗自動按 Enter。一般輸入控制現在也會主動列舉遊戲的 related
windows；發現任何額外可見視窗便停止並釋放按鍵，不依賴它是否搶走前景焦點。
若該視窗不屬於遊戲程序且沒有 owner 關係，仍可能只能由失焦條件攔截，因此
現階段不會嘗試自動處理姓名輸入流程。

## 測試

```powershell
pytest -q
```

所有自動化測試均使用 mock 視窗、mock MSS grabber 與 mock 輸入後端，不會真的
操作鍵盤、滑鼠或啟動遊戲。

## 安全與已知限制

- `F8` 是輸入控制的全域緊急停止鍵；觸發後該控制器不可繼續送鍵。
- 遊戲必須保持可見、未最小化，且自動輸入期間必須是前景視窗。
- 與遊戲同程序或由遊戲擁有的額外可見視窗會阻擋所有自動輸入；此防線預設
  開啟，不應為了訓練而關閉。
- 某些 Windows 前景鎖定規則可能拒絕程式切換焦點；此時工具會停止並回報，
  不會持續亂送按鍵。
- OpenCV 預覽視窗需要桌面工作階段；無 GUI 的 CI 只能執行 mock 測試。
- 已確認主視窗標題／class、PyAutoGUI 左右鍵與單次 Enter 可用；外部姓名輸入
  視窗的出現條件、標題與 class 尚待實際出現時確認。
- 不會執行來源不明檔案；`auto_launch` 僅允許設定中經驗證為 `.exe` 的單一路徑。
- `captures/`、`logs/`、exe、模型與影片均由 `.gitignore` 排除。

受限 reset 已實機通過連續兩回合。規則基準的實機紀錄陸續暴露方向抖動、缺少
尖刺避讓、控制更新慢與彈簧重複落點；目前已改成可達落點優先、起跳平台邊界
脫離、危急踩刺與保留 fail-safe 的低延遲 PyAutoGUI 呼叫。Stable-Baselines3
與 PPO 安全訓練入口已加入，但外部姓名輸入視窗仍不會被自動處理，模型也尚未
經過足夠訓練；目前成果不能視為會自動通關的代理。
