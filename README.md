# AI Stair Agent：NS-SHAFT 遊戲介面層

本專案以一般 Windows 視窗 API、螢幕擷取及鍵盤輸入控制既有的
`NS Shaft.exe`。目前只完成「遊戲介面層」：尋找視窗、擷取畫面、安全測試
左右鍵、校正擷取區域及人工收集畫面。**尚未建立 Gymnasium 環境，也尚未開始
訓練強化學習模型。**

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
將獲得一小段向上速度；事件只描述遊戲狀態，不會替玩家送出任何按鍵。

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

預設寫到 `logs/observations.jsonl`；也可在參數後指定其他路徑。每筆包含角色
位置／速度、平台 ID／類型／矩形、最近平台、血量、畫面捲動速度及當幀事件。
不加參數就不會逐幀寫入硬碟。整個 `logs/` 已被 Git 忽略。

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
未知的外部視窗自動按 Enter；遊戲失去前景時既有輸入流程仍會停止並釋放按鍵。

## 測試

```powershell
pytest -q
```

所有自動化測試均使用 mock 視窗、mock MSS grabber 與 mock 輸入後端，不會真的
操作鍵盤、滑鼠或啟動遊戲。

## 安全與已知限制

- `F8` 是輸入控制的全域緊急停止鍵；觸發後該控制器不可繼續送鍵。
- 遊戲必須保持可見、未最小化，且自動輸入期間必須是前景視窗。
- 某些 Windows 前景鎖定規則可能拒絕程式切換焦點；此時工具會停止並回報，
  不會持續亂送按鍵。
- OpenCV 預覽視窗需要桌面工作階段；無 GUI 的 CI 只能執行 mock 測試。
- 已確認主視窗標題／class、PyAutoGUI 左右鍵與單次 Enter 可用；外部姓名輸入
  視窗的出現條件、標題與 class 尚待實際出現時確認。
- 不會執行來源不明檔案；`auto_launch` 僅允許設定中經驗證為 `.exe` 的單一路徑。
- `captures/`、`logs/`、exe、模型與影片均由 `.gitignore` 排除。

下一階段會先以實際完整回合驗證 `floor_descended`、`spike_damage` 與
`scroll`，再將目前的結構化觀測封裝成 Gymnasium 環境。本階段仍不包含
Gymnasium、Stable-Baselines3 或任何模型訓練。
