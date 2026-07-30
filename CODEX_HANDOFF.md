# Codex 交接紀錄

更新時間：2026-07-30（Asia/Taipei）

新對話開始後，請依序完整閱讀：

1. `AGENTS.md`
2. `README.md`
3. 本文件
4. `git status --short` 與 `git diff`
5. 現有測試，尤其是本文件列出的失敗測試

目前沒有 Python 訓練程序正在執行。不要自行啟動遊戲、訓練或實機輸入測試。

## 1. 目前最終目標

在 Windows 10/11、Python 3.11 與專案 `.venv` 中，建立一個只透過 Windows
視窗查找、遊戲 client area 螢幕擷取及一般鍵盤輸入控制既有
`NS Shaft.exe` 的安全強化學習專案。

永久安全邊界：

- 不修改、注入、掛鉤、反編譯遊戲，也不讀取程序記憶體。
- 不繞過安全或反作弊機制。
- 不自動執行來源不明的 `.exe`；`auto_launch` 預設並維持 `false`。
- 自動輸入只能在已驗證的 `NS-SHAFT / NsShaftClass` 視窗位於前景時執行。
- `F8`、`Ctrl+C`、PyAutoGUI fail-safe、失焦／例外時 `release_all()` 不可移除。
- 只允許操作遊戲視窗，不可點擊或控制其他程式。
- 測試必須使用 mock，不可真的操作使用者鍵盤、滑鼠或啟動遊戲。

原始需求的「第一階段：遊戲自動化控制與畫面擷取基礎」已完成，專案後來已
進展到畫面物件辨識、事件、Gymnasium 介面、規則基準與本機受限 PPO 實驗。

目前立即目標不是繼續盲目增加 PPO 步數，而是：

1. 完成目前半成品的「目標平台方向動作 reward」並恢復全綠測試。
2. 驗證 reward 分量是否真的提供足夠方向訊號。
3. 重新決定訓練策略；優先考慮「規則／人工示範預訓練，再用 PPO 微調」，
   而不是讓單一真實遊戲從純隨機動作開始跑數萬步。
4. 只有短訓練量化指標確實改善後，才允許進入 10,000 步以上長訓練。

### 原始規劃與目前進度

| 階段 | 內容 | 狀態 |
|---|---|---|
| 1 | 視窗尋找、client area、DPI | 已完成 |
| 2 | MSS 擷取、校正、FPS、Unicode 路徑存圖 | 已完成 |
| 3 | PyAutoGUI/PyDirectInput 抽象、F8、前景與按鍵釋放 | 已完成 |
| 4 | menu/playing/dialog/name-entry 狀態與資料收集 | 已完成初版 |
| 5 | 角色、普通／尖刺／彈簧／輸送帶／翻轉平台辨識 | 已完成初版 |
| 6 | 血量、落地、下降、彈簧、傷害等事件 | 已完成初版 |
| 7 | 268 維時序 Gymnasium 觀測與三動作環境 | 已完成 |
| 8 | 規則基準、reward 稽核、受限回合重設 | 已完成，但基準策略仍非可通關代理 |
| 9 | PPO smoke test 與 128～5,120 步實機實驗 | 已執行，效果不合格 |
| 10 | 10,000～100,000 步正式長訓 | 尚未開始，不應直接開始 |

## 2. 已完成的修改

### 已提交到本機 Git

目前分支為 `main`，HEAD：

```text
c4cd571 降低 PPO 單向策略塌縮
```

`main` 比 `origin/main` 多 10 個本機 commit；遠端目前停在：

```text
f3aae72 校正單人選單焦點並強化安全重設
```

本機 commit 尚未 push。不要在未檢查敏感資料與未取得使用者指示前 push。

截至 `c4cd571` 已包含：

- 第一階段完整視窗、擷取、輸入、校正、資料收集工具。
- 遊戲狀態、對話框、姓名視窗防護。
- 角色、平台、HUD、事件與跨幀追蹤。
- Gymnasium 環境與 268 維時序觀測。
- 規則基準策略與 reward 稽核工具。
- 受限 PPO 訓練／評估入口、模型路徑限制及 checkpoint。
- step、方向反轉、尖刺停留、idle、同平台停留、頂端危險與撞牆 shaping。
- 輸入控制器只釋放實際追蹤的按鍵，避免 phantom key-up 改動死亡選單。
- PPO 舊模型的 `n_steps`、`batch_size`、`n_epochs`、`learning_rate`、
  `ent_coef` 相容性防護（目前未提交 diff 又增加 `target_kl` 防護）。

### 工作樹中已實作、實機或測試確認，但尚未提交

目前有 18 個已修改檔案，約 728 行新增、50 行刪除。主要內容：

- `window_manager.py`
  - `SetForegroundWindow` 被 Windows 無聲拒絕時，只對已驗證的相同 hwnd
    使用 `SwitchToThisWindow` 備援。
  - mock 測試確認備援只操作指定 hwnd。
- `dialog_handler.py`、`calibrate_menu_focus.py`、`live_env.py`
  - 支援最多 1～4 次的有界焦點修正。
  - 每次只在仍為穩定 `DIALOG` 時送候選鍵；只有重新連續辨識為右側單人開始
    才允許 Enter。
  - 實機校正結果：中央雙人焦點需 3 次 `Tab`；前兩次為 `UNKNOWN`，第 3 次
    才回到單人開始。
  - 本機被忽略的 `config.yaml` 使用
    `menu_focus_correction_key: "tab"` 與
    `reset_focus_correction_max_presses: 3`。
  - `config.example.yaml` 仍保持修正鍵 `null`、最多 1 次，其他電腦不可沿用。
  - 三次 Tab 重設已讓一次受限訓練跨過原本會停止的死亡選單，完成到累計
    5,120 步。
- `rl_training.py`、`rl_evaluation.py`、訓練／評估腳本
  - 記錄 RELEASE／LEFT／RIGHT 次數、最長同動作連續步數、左右切換數。
  - 彙總各 reward component，方便診斷局部策略。
  - PPO 目前參數改為：
    `learning_rate=0.0002`、`n_epochs=4`、`ent_coef=0.03`、
    `target_kl=0.01`、`seed=2`。
  - 載入舊模型時增加 `target_kl` 相容性檢查。
- `gym_env.py`
  - 已實作同一安全平台的水平距離進度 reward。
  - 安全平台為 normal、spring、conveyor、flipping；spikes 排除。
  - 上升時排除距離內最可能是起跳原點的平台，避免彈簧反覆回原位。
- `README.md`
  - 已記錄上述實機結果、PPO 參數、動作與 reward 診斷。

## 3. 尚未完成的項目

### 最高優先：目前工作樹測試不是全綠

最後一次中斷前開始加入：

```yaml
environment:
  platform_target_action_reward: 0.05
```

設計意圖：

- 下一安全平台在右側：RIGHT `+0.05`、LEFT `-0.05`、
  RELEASE `-0.025`。
- 下一安全平台在左側：反向處理。
- 已位於平台安全落點區間內：不強迫移動。
- 仍只使用畫面辨識出的角色／平台資料。

目前只完成：

- `EnvironmentConfig` 與 YAML 欄位。
- 設定驗證。
- 5 個參數化測試。

尚未完成：

- `RewardCalculator.__init__()` 尚未接受
  `platform_target_action_reward`。
- `_platform_alignment()` 只回傳絕對水平距離，尚未回傳目標在左或右的
  signed offset。
- `calculate()` 尚未計算／記錄 `platform_target_action_reward` component。
- `StairAgentEnv` 尚未把 config 值傳入 `RewardCalculator`。
- README 尚未描述這個尚未完成的 reward；不要在完成前聲稱已生效。

### 訓練策略尚未解決

目前純 PPO 從隨機策略起步沒有得到可用模型：

- 1,024 步模型曾 deterministic 偏向 LEFT。
- 累計 5,120 步模型 deterministic 評估變成 128/128 都是 RELEASE_ALL。
- 平均回合長度約 50～52 步，平均 reward 約 `-8`，未隨步數改善。

推薦下一方向：

1. 先完成方向 action reward 並驗證 component 數量級。
2. 加入「目標方向符合率、平均下降階數、平均傷害、死亡率」評估摘要。
3. 研究從 `baseline` 或人工遊玩軌跡建立 observation→action 示範資料。
4. 先以監督式／行為克隆預訓練基本左右判斷，再用單一真實環境 PPO 微調。
5. 不要直接續跑目前 5,120 步的 RELEASE_ALL 模型。

尚未實作行為克隆、離線資料集訓練、world model 或平行模擬器。

## 4. 關鍵設計決策與不能改動的部分

### 安全決策

- 永遠不修改、注入、掛鉤、反編譯或讀取遊戲程序記憶體。
- 不關閉 PyAutoGUI fail-safe。
- F8 必須立即觸發停止並釋放按鍵。
- 失焦、例外、Ctrl+C、額外 related window、正常結束都必須釋放按鍵。
- 左右鍵不可同時長期按住；換向必須先釋放另一方向。
- 不可為了長訓取消前景驗證、related-window 防護或選單焦點驗證。
- 不可自動處理另一螢幕上尚未可靠識別的姓名輸入視窗。
- 不可自動啟動遊戲；使用者手動啟動。
- 實機工具需明確確認字串、倒數與硬性步數／回合／時間上限。
- 使用者特別要求只能操作遊戲畫面，不可操作其他視窗。

### 設定與資料決策

- 真實 `config.yaml` 被 Git 忽略，包含本機路徑，不可提交。
- `captures/`、`logs/`、`models/`、exe、DLL、影片、模型權重都被忽略。
- 不把遊戲 UI 座標散落在程式碼；使用校正與設定。
- 使用 Unicode 安全的 `diagnostics.save_image()`，不要直接依賴
  `cv2.imwrite()` 寫含特殊字元的 Windows 路徑。
- `config.example.yaml` 必須保持可公開，不可放本機路徑或本機限定的 Tab=3。

### 為何不能像常見 Mario 專案同時跑很多角色

目前環境是單一真實 Windows `.exe`：

- 系統鍵盤是全域輸入，且只有一個視窗能是前景。
- 安全規則禁止對背景視窗送鍵。
- 每份遊戲還需要獨立 reset、視窗關聯與姓名對話框處理。
- 目前約 6～7 control steps/s，瓶頸是遊戲畫面與真實互動，不是 PyTorch GPU。

常見 Mario 專案通常使用 emulator/vectorized environment，可直接傳虛擬手把、
save-state、headless、高速及多程序執行；本專案在現有安全邊界下不具備這些
能力。可行替代是：

- 單一真實遊戲收集軌跡，再離線批次預訓練。
- 長期另建只由螢幕／動作資料學得的簡化模擬器，再平行訓練；這是大型新階段，
  且須處理 sim-to-real 誤差。

## 5. 修改過的重要檔案

### 核心介面與安全

- `src/stair_agent/config.py`
- `src/stair_agent/window_manager.py`
- `src/stair_agent/screen_capture.py`
- `src/stair_agent/input_controller.py`
- `src/stair_agent/dialog_handler.py`
- `src/stair_agent/episode_reset.py`
- `src/stair_agent/live_env.py`

### 辨識、觀測與事件

- `src/stair_agent/game_state.py`
- `src/stair_agent/object_detection.py`
- `src/stair_agent/object_tracking.py`
- `src/stair_agent/hud_detection.py`
- `src/stair_agent/game_events.py`
- `src/stair_agent/observation.py`
- `src/stair_agent/diagnostics.py`

### RL 與策略

- `src/stair_agent/gym_env.py`
- `src/stair_agent/baseline_policy.py`
- `src/stair_agent/trajectory.py`
- `src/stair_agent/rl_training.py`
- `src/stair_agent/rl_evaluation.py`

### 目前未提交 diff 涉及的腳本

- `scripts/calibrate_menu_focus.py`
- `scripts/train_ppo.py`
- `scripts/evaluate_ppo.py`

### 目前未提交 diff 涉及的測試

- `tests/test_config.py`
- `tests/test_dialog_handler.py`
- `tests/test_gym_env.py`
- `tests/test_rl_evaluation.py`
- `tests/test_rl_training.py`
- `tests/test_window_manager.py`

## 6. 目前測試結果

最後實際執行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

結果：

```text
169 passed, 5 failed
```

5 個失敗全部是：

```text
tests/test_gym_env.py::test_reward_teaches_action_toward_safe_platform[...]
```

共同原因：

```text
TypeError: RewardCalculator.__init__() got an unexpected keyword argument
'platform_target_action_reward'
```

其他檢查：

```text
PPO mock smoke test：通過
compileall：通過
git diff --check：通過（只有 LF→CRLF 警告）
```

在加入最後 5 個半成品測試之前，完整測試曾為 `169 passed`；但這不是目前工作
樹的權威結果。目前權威結果是 `169 passed, 5 failed`。

所有上述測試都是離線／mock，未操作真實鍵盤或滑鼠。

## 7. 下一步應執行的命令

先進入專案並確認狀態：

```powershell
cd ai-stair-agent
.\.venv\Scripts\Activate.ps1
git status --short
git diff --check
```

先閱讀失敗測試與 reward 實作：

```powershell
Get-Content tests\test_gym_env.py
Get-Content src\stair_agent\gym_env.py
Get-Content src\stair_agent\config.py
```

完成 `platform_target_action_reward` 後，依序執行：

```powershell
python -m pytest -q tests\test_gym_env.py tests\test_config.py
python -m pytest -q
python scripts\check_ppo.py
python -m compileall -q src scripts tests
git diff --check
```

在測試全綠前：

- 不執行 `train_ppo.py`。
- 不評估或續訓舊模型。
- 不 commit、不 push。

全綠後，先只做新的短訓練，不載入 5,120 步 RELEASE_ALL 模型：

```powershell
python scripts\train_ppo.py `
  --timesteps 1024 `
  --max-episodes 50 `
  --max-seconds 180 `
  --focus-target
```

工具會要求輸入大寫 `TRAIN`。完成後明確指定新模型評估：

```powershell
python scripts\evaluate_ppo.py `
  --model models\ppo\新時間戳\final_model.zip `
  --max-steps 128 `
  --max-episodes 3 `
  --max-seconds 45 `
  --focus-target
```

只有以下指標改善才考慮擴大步數：

- deterministic 不再是 100% 單一動作。
- 平均下降階數增加。
- 平均傷害／死亡下降。
- reward component 中方向教師訊號有合理量級，且不是淹沒 floor/death。
- 平均回合長度與總 reward 至少其中一項有可重現改善。

## 8. 已知問題與注意事項

### 最新模型效果不合格

最新重要模型（Git 忽略）：

```text
models/ppo/20260730_031722_603433/final_model.zip
```

它由先前 checkpoint 接續，累計約 5,120 步。最後 2,048 步訓練動作：

```text
RELEASE_ALL=751, LEFT=480, RIGHT=817
最長連續同動作=8
completed_episodes=42
```

128 步 deterministic 評估：

```text
RELEASE_ALL=128, LEFT=0, RIGHT=0
completed_episodes=2
total_reward=-22.1722
```

reward components：

```text
step_penalty=-1.28
floor_reward=+1.0
damage_penalty=-7.6
death_penalty=-10.0
idle_action_penalty=-2.44
platform_dwell_penalty=-0.72
top_danger_penalty=-1.14
platform_alignment_reward=+0.00783
```

結論：水平距離 reward 太小，死亡與傷害完全主導；模型學成 RELEASE_ALL
局部策略。不要直接增加到 10,000 步。

### 選單重設

- 死亡可能發生在方向鍵仍按住的 80 ms 內；安全 key-up 可能讓舊遊戲選單移到
  中央雙人焦點。
- 單次 RIGHT 與單次 Tab 實機校正都失敗。
- 從雙人焦點最多 3 次 Tab 實機校正成功，前兩次為 UNKNOWN，第 3 次為 START。
- 多 Tab handler 已用 mock 測試，並在一次長訓中成功跨過長等待選單。
- 本機 Tab=3 是機器／遊戲版本限定校正，不可放進範例預設。
- 姓名輸入外部視窗仍不自動處理；related window 或失焦時停止。

### 訓練與效能

- 真實環境約 6～7 steps/s；選單長等待時整體 fps 會降到約 3～4。
- 10,000 步約需至少 25～30 分鐘，實際會因重設等待更久。
- GPU 不是目前瓶頸。
- PPO 的 entropy 曾保持約 1.02～1.10、KL 約低於 0.0033；沒有更新爆炸，
  但策略效能沒有提升。
- 不要把「訓練探索動作分布平衡」誤認為 deterministic 策略已可用。

### Git 與敏感資料

- 工作樹很髒，18 個檔案尚未提交；不要 reset、checkout 或覆蓋使用者修改。
- `CODEX_HANDOFF.md` 是本次新建的交接文件，尚未提交。
- 本機 `main` ahead `origin/main` 10 commits。
- 不要提交 `config.yaml`、`captures/`、`logs/`、`models/`、exe、DLL、影片或權重。
- GitHub remote 為使用者先前提供的 `stairkid-rl` repository；未經明確要求，
  不 push。
