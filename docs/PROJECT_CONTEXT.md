# Project Context

## 恢復上下文

本專案的最高優先長期規格是 repository 父目錄的
`../CODEX_NS_SHAFT_PROJECT_REFACTOR_PROMPT.md`。任何新工作階段或 context
壓縮後，必須先完整重讀該文件，再依 `AGENTS.md` 的順序恢復上下文。本文件是摘要，
不能取代長期規格。

## 專案目標

以「只看畫面、只送一般鍵盤」的方式建立可重現、可稽核且安全的 NS-SHAFT
小朋友下樓梯 agent。重點不是在真實遊戲上堆疊昂貴的單步 PPO 訓練，而是把真實
資料、模擬器與離線／互動式學習拆成可驗證階段。

## 不變界線

- 不修改、注入、掛鉤、反編譯或讀取遊戲記憶體。
- 真實控制只走既有 `WindowManager`、`InputController`、
  `SafetyMonitor`、`LiveGameAdapter` 安全鏈。
- 自動測試與 Colab 永遠不送真實輸入。
- 舊資料及已塌縮 PPO checkpoint 只可稽核或作比較，不可直接續訓。

## 目前架構

- 真實觀測：畫面擷取 → 狀態／物件／HUD 辨識 → tracking／events →
  `GameObservation`。
- 共用觀測：`FeatureEncoder` 產生 64 維單幀，`TemporalObservationStack`
  堆疊 4 幀並附 3 維動作 one-hot，總計 268 維。
- 動作：`0=RELEASE_ALL`、`1=LEFT`、`2=RIGHT`。
- 真實 Gym：`StairAgentEnv` 透過 adapter 隔離 Windows I/O。
- 模擬 Gym：`ShaftEnv` 使用 Pymunk v0 物理並重用相同 encoder／temporal
  stack；不依賴真實遊戲。
- 新資料合約：`ns-shaft-transition-v1`，由
  `stair_agent.data.DatasetValidator` 驗證。

## 長期主路線

1. 建立乾淨 transition 資料與時間校正。
2. 以真實量測校正 simulator v0，先證明 baseline 可跑與環境可學。
3. 在模擬器做 BC；通過固定評估後才做 DAgger。
4. 再評估 baseline + residual 與 Double DQN／DQfD-lite。
5. 僅把通過 gate 的候選策略帶回有限、可停止的實機驗證。

PPO 僅保留為模擬器 learnability 與小型比較工具。
