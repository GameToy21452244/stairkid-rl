# Project Context

## 恢復上下文

本專案目前最高優先規格是 repository 父目錄的
`../CODEX_SEQUENCE_CONTROL_STRATEGY_UPDATE.md`；前一版訓練規格為
`../CODEX_UPDATE_TRAINING_STRATEGY_AND_CONTINUE.md`，原始架構規格是
`../CODEX_NS_SHAFT_PROJECT_REFACTOR_PROMPT.md`。任何新工作階段或 context
壓縮後，必須依 `AGENTS.md` 完整重讀兩者。本文件是摘要，不能取代規格。

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

## 目前最高優先主路線

1. 先用 3～5 個有硬上限的真實遊戲回合驗證 Teacher-observable、視覺、延遲、
   target lock 與 controller memory；未實際通過前不得做 Student 新訓練。
2. 量化 observation/action conflict 與 deployable memory 的 entropy reduction。
3. 以相同資料、seed 與更新預算比較 S0 MLP、S1 explicit-state MLP、
   S2 full-observation GRU、S3 compact-observation GRU。
4. 建立帶 controller-state timeline 與可控擾動的 rare-branch sequences。
5. 只有 sequence smoke 通過，才做至多一輪 80/20 conservative sequence DAgger，
   並以 health/bottom death、Q25、CVaR25、reach rate 作 Gate。
6. NEAT 只作 common-seed、fixed-budget 公平對照；bounded RL 更後置。

舊版已完成的資料 audit、Simulator v0.2、Teacher 分離與特殊平台機制仍是有效
基礎，不重新實作；只是訓練停點已被新的 sequence-control Gate 取代。

2026-08-03目前停點：P3.6與P4.0已PASS；P4.1的本機causal/sequence介面與短smoke
PASS，下一步才是Colab三初始化bounded scientific Gate。P4.1固定使用hash鎖定的
3,529-row Spike Dataset v1；current Teacher source重建結果不同，故不得在Colab重建。
只有P4.1 final Gate通過才可建立P4.2 rare-branch sequence dataset。

## 已完成的基礎路線

1. Data Resource Audit 先判斷既有資料可作 demo、replay、dynamics 或 relabel。
2. Simulator v0.2 以持續生成、回收與 2～3 層 reachability 保證基本可解。
3. 分離可看完整 state 的 Oracle-full 與只看學生觀測的 Teacher-observable。
4. 固定 60 Hz 物理步進，比較 8／10／12 Hz policy control。
5. gates 通過後才建立小型 teacher dataset、BC0 與一輪 DAgger0 smoke。
6. 基本下樓合格後才依序加入回血、尖刺、輸送帶、彈簧、翻板。
7. 再評估 residual、Double DQN／DQfD-lite 與 domain randomization。
8. 僅把通過 gate 的候選策略帶回有限、可停止的實機驗證。

PPO 僅保留為模擬器 learnability 與小型比較工具。

目前已確認真實遊戲角色在左右邊界會停止；不採 Windows VM，最終驗證以使用者
可直接觀看的真實遊戲受限回合為準。
