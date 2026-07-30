# Project Audit Report

日期：2026-07-30

範圍：repository 原始碼、測試、設定、ignored logs／models／captures 與目前 dirty
worktree。稽核只做唯讀檢查，未啟動遊戲或送出輸入。

## Executive summary

現有專案最有價值的資產不是 PPO checkpoint，而是已建立的安全實機介面、畫面
結構化觀測、可解釋 baseline、268 維時序 observation 與大量離線測試。最大的
瓶頸有三個：

1. 真實環境約 6–7 steps/s，單步 on-policy PPO 資料昂貴且狀態覆蓋窄。
2. 舊 JSONL 不是完整 transition，缺少 episode／next observation／action timing
   與版本，不能可靠作 imitation learning。
3. PPO 評估已出現極端 action collapse；最新累積模型 deterministic 128 步全為
   RELEASE_ALL，繼續加 timesteps 沒有合理依據。

結論是保留真實控制與 perception，暫停真實 PPO 主線，先建立資料合約、validator
與可校正 simulator。

## Repository map

### 真實介面與安全

- `window_manager.py`：搜尋、唯一目標、client rect、foreground、related window
  與選擇性 launch。
- `screen_capture.py`：MSS capture、window-relative region、resize。
- `input_controller.py`：`Action`、PyAutoGUI／PyDirectInput backend、foreground
  guard、按鍵狀態、`release_all()`、F8 `SafetyMonitor`。
- `dialog_handler.py`、`episode_reset.py`、`session_controller.py`：menu/dialog
  focus 校正、單次 Enter reset 與 session state。
- `live_env.py`：把 capture、detectors、controller、monitor、resetter 組成
  `LiveGameAdapter`。

### Perception 與結構化狀態

- `game_state.py`：PLAYING／MENU／DIALOG／NAME_ENTRY／GAME_OVER／UNKNOWN。
- `object_detection.py`：player 與 normal/spikes/spring/conveyor/flipping 平台。
- `object_tracking.py`：player velocity/motion、platform identity 與 scroll。
- `hud_detection.py`、`game_events.py`：生命與 landed／floor／damage 事件。
- `observation.py`：`GameObservation` 及 observation-only legacy writer。

### Policy、Gym 與訓練

- `baseline_policy.py`：可達安全落點、target lock、方向 brake、launch escape、
  top danger 與 spike emergency 的規則策略。
- `gym_env.py`：`FeatureEncoder`、`TemporalObservationStack`、`RewardCalculator`
  與 adapter-based `StairAgentEnv`。
- `trajectory.py`：legacy reward audit／trajectory writer。
- `rl_training.py`、`rl_evaluation.py`：SB3 PPO、安全預算 wrapper、checkpoint
  resolve、有限 deterministic evaluation。
- `scripts/train_ppo.py`、`evaluate_ppo.py`、`run_baseline.py`：互動式確認與上限。

### 新增基礎

- `data/`：versioned transition 與 validator。
- `simulator/`：Pymunk player/platform/generator/physics/renderer。
- `envs/shaft_env.py`：headless-first Gymnasium simulator。

## 真實控制 flow

`create_live_environment()` 先用 `WindowManager.require_ready()` 驗證目標，建立
`ScreenCapture`、`LiveObservationPipeline`、`InputController` 與
`SafetyMonitor`，必要時建立 dialog/reset guard，最後包成：

`StairAgentEnv → LiveGameAdapter → InputController → ordinary keyboard backend`

每個 step 在送 action 前檢查 phase／foreground，action 維持設定的毫秒數，finally
釋放方向鍵，再取得下一觀測。失焦、blocking related window、F8、例外與 close
都會釋放。測試以 mock adapter/backend 驗證，沒有真實輸入。

### 保留的安全不變量

- `auto_launch=false` 為預設；
- 唯一 target + verified foreground；
- PyAutoGUI fail-safe 不得關閉；
- F8、Ctrl+C、失焦、unknown／terminal、例外、正常結束都 release；
- 實機腳本有大寫確認、倒數、step／episode／seconds 上限；
- 不使用 process memory、injection、hook 或 reverse engineering。

## Observation audit

`GameObservation` 包含 timestamp、phase、player、health、nearest platform、
platform list、scroll velocity 與 events。`FeatureEncoder` v3：

- player presence/x/y/vx/vy/motion：6；
- health、scroll、nearest presence/gap/kind：5；
- 五種平台 count：5；
- 8 個平台 × presence/dx/dy/width/height/kind：48；
- 單幀合計：64。

預設 temporal stack 是 4 幀，每幀再附 3 維 action one-hot：
`4 × (64 + 3) = 268`。若關閉 action history 則為 256。既有 logs 同時存在早期
16 維與後來 64 維格式，證明 schema version 是必要條件。

## Action、頻率與 timing

- `0=RELEASE_ALL`、`1=LEFT`、`2=RIGHT`。
- backend：PyAutoGUI 或 PyDirectInput。
- action duration 由 `controls.action_duration_ms` 控制；capture 有 target FPS。
- 實機 PPO artifact 顯示 128 steps 約 18.7 秒，即約 6.8 steps/s。
- 目前 legacy writer 只有 nested observation timestamp；沒有 command、effective、
  next observation 四段時間，無法估計 latency 或證明 label alignment。

## Reward audit

真實 `RewardCalculator` 目前包含：

- step、floor、damage、death；
- direction reversal、spike dwell、idle、platform dwell；
- top danger、wall push；
- platform alignment progress；
- falling 時朝安全落點的 target-action shaping。

`info.reward_components` 可在 Gym step 取得。稽核發現 legacy
`RewardAuditor`／writer 只覆蓋部分設定且記錄格式早於新 shaping；舊 reward log
不得被視為 `stair-reward-v2` ground truth。未來應把 reward config 建立集中 factory，
並讓新 transition writer 直接記錄 Gym step 的 component。

## Terminal / truncated audit

- MENU、DIALOG、NAME_ENTRY、GAME_OVER → `terminated=True`。
- UNKNOWN 或 max episode steps → `truncated=True`。
- adapter reset 若不是 PLAYING 會拒絕開始。

舊資料缺少可靠 episode id；即使有 per-row terminal，也無法證明不同檔案與 reset
間沒有跨 episode 污染。新版 validator 已拒絕 terminal 後 transition、step gap 與
episode reappearance。

## Data format audit

本機 ignored artifact：

- `logs/`：84 files，約 5.75 MB；其中約 38 baseline、36 PPO、4 reward audit、
  2 observations。
- `models/`：61 files，約 66.3 MB。
- `captures/`：59 files，約 10.6 MB。

代表格式：

| family | 已有內容 | 關鍵缺口 |
|---|---|---|
| observations | raw structured observation | 無 action/reward/next/episode |
| reward audit | action 字串、reward、16 維 features、observation | manual label、無 next/timing/version |
| baseline | action、policy decision、64 維 features、decision/post observation | 無 episode id、component、四段 timing/version |
| PPO eval | return、episode length、action counts、component totals（新檔） | 非逐 transition demo |

所有 legacy JSONL 應 quarantine；不能藉由補 null／推測時間直接變成訓練資料。

## Baseline audit

`SafePlatformPolicy` 有解釋性 target 與 reason，能作 simulator benchmark，也可在
人工確認後產生候選示範。但「baseline」不自動等於「expert」：

- perception target 可能換 id；
- launch platform／top danger／spring 等策略仍可能失敗；
- 舊 writer 的 decision observation 與 post-action observation 沒有完整 latency；
- action distribution 與成功樓層需逐 episode gate。

因此 policy source 必須先是 `baseline`，只有通過 validator 與品質評估的片段才標
`baseline_verified`。

## PPO / checkpoint audit

最新累積 run：
`models/ppo/20260730_031722_603433/final_model.zip`，累積至約 5120 steps。
其 deterministic evaluation：

- 128 steps、2 completed episodes；
- total reward `-22.17`；
- RELEASE_ALL 128、LEFT 0、RIGHT 0；
- longest same-action streak 128。

先前 checkpoint 也出現 LEFT-only 或 RIGHT-only。這不是合理的 continuation seed，
且證明只用 return 不足以選 checkpoint；action distribution 必須是 hard gate。

## Test audit

原始基線為 174 tests：169 passed、5 failed。5 個失敗全部是 dirty worktree 已加入
測試但尚未接完的 `platform_target_action_reward` constructor/wiring，非新安全回歸。
本次已接完該 shaping，並新增 schema、validator、physics、seed、render、
check_env、baseline 與 100k smoke 測試。所有測試都使用 mock 或 simulator。

## 共享／分離判斷

### 應共享

- `Action` enum；
- `GameObservation` 語意；
- `FeatureEncoder` 與 temporal stack；
- observation/reward schema version；
- evaluation metrics 與資料 validator；
- `SafePlatformPolicy` 作 benchmark。

### 必須分離

- Windows capture、window manager、input backend、dialog/reset；
- Pymunk space、platform generator、renderer；
- Colab workflow 與任何 real-game control。

## Keep / refactor / deprecate

### Keep

安全控制鏈、perception/tracking/events、structured observation、baseline、
adapter-based Gym boundary、mock safety tests、有限實機確認流程。

### Refactor next

- 新 `TransitionWriter` 接上真實／sim step；
- reward factory，消除 `StairAgentEnv` 與 `RewardAuditor` config drift；
- legacy quarantine/migration report；
- calibration profile 與 benchmark runner；
- simulator vector env factory 與 experiment artifact writer。

### Deprecate as training inputs

- observation-only writer；
- legacy `TrajectoryJsonlWriter` 輸出作 BC/DQfD；
- 所有 action-collapsed PPO 作 continuation；
- 在真實 executable 上的 on-policy long training。

## Timing、cross-episode、contamination findings

- observation 與 action effective time 未分離，是目前最嚴重的 label 風險。
- reset/menu/focus correction 可能比正常 step 慢，不能和 playing transition 混合。
- old files 沒有 episode id，無法可靠偵測跨回合。
- 16／64／268 observation 共存，若靠檔名而非 version 選資料會污染。
- reward 定義已演進，舊 cumulative reward 不可與新 component 混用。

## Open unknowns

- 真實 gravity、bounce、horizontal acceleration、drag、max speed；
- action command 到畫面反應的 latency 分布；
- capture/detection timestamp 的實際語意；
- scroll speed 與 floor spacing 分布；
- 高速度落台 crossing tolerance；
- baseline 在固定真實場景的 floors/survival/action distribution；
- 何種 legacy 片段仍能以人工方式重建 provenance。

在這些未知量被量測前，simulator 只能稱為 v0 工程骨架，不能稱為遊戲複製品。
