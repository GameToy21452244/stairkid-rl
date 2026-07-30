# Decisions

## D-001：長期規格是永久恢復來源

- 日期：2026-07-30
- 決策：父目錄 `CODEX_NS_SHAFT_PROJECT_REFACTOR_PROMPT.md` 優先於短期 handoff。
- 理由：避免 context 壓縮後重新回到真實遊戲單步 PPO。

## D-002：保留真實安全鏈，另建 simulator package

- 決策：不改寫 `LiveGameAdapter`／`InputController` 的責任；模擬器放在
  `simulator/` 與 `envs/`，只重用 observation encoder。
- 理由：自動測試與 Colab 必須從架構上無法送真實輸入。

## D-003：觀測相容基準為 268 維 v3

- 決策：模擬器重用 64 維 `FeatureEncoder` 和 4 幀 + 3-action history，
  schema id 為 `stair-observation-v3-268`。
- 理由：避免真實／模擬器 feature drift；日後變更需升版。

## D-004：舊 JSONL 全部先 quarantine

- 決策：缺欄位的舊 observations／audit／baseline 不做「猜值 migration」。
- 理由：缺少 next observation、episode boundary 與 action timing 時，無法證明
  transition 與 label 正確。

## D-005：塌縮 PPO 不續訓

- 決策：最新 5120-step PPO 只作負面比較。
- 理由：deterministic 128-step evaluation 全為 RELEASE_ALL；繼續加步數不會
  解決資料效率、狀態分布與 reward credit assignment。

## D-006：simulator v0 僅 normal platform

- 決策：先用核心動力、單向落台、捲動與終止建立可測骨架，不提前做 v1/v2。
- 理由：未校正的複雜 hazard 只會增加 simulator exploitation 風險。

## D-007：測試中保留 100k smoke

- 決策：完整 pytest 包含 100,000-step headless smoke。
- 理由：提早發現長步進、reset、資源釋放與獨立 episode 問題；目前約 24 秒，
  尚可接受。

## D-008：Calibration telemetry 不作示範

- 日期：2026-07-30
- 決策：固定左右量測序列一律標 `policy_source=invalid`，即使 schema validator
  通過也不升格。
- 理由：校正動作不是最佳策略，validator-clean 只代表資料結構與 continuity
  正確，不代表 action label 適合 BC。

## D-009：多步 fidelity 使用 seeded distribution，不偷看未來平台

- 日期：2026-07-30
- 決策：保留 10／30-control-step exact x/y/vx/vy 作診斷；但當 horizon
  依賴初始 viewport 外的隨機平台時，不以 exact screen-y 作 simulator Go
  gate。操作 gate 改為一步 fidelity、landing classifier、水平多步穩定性與
  seeded landing／floor rate 的兩比例檢定。
- 證據：episode-held-out endpoint predictor 的樂觀下界仍為 10-step y
  52.3 px、30-step y 95.4 px；初始 state 未包含第 4／8 step 才進入畫面的
  平台。詳見 `reports/PARTIAL_OBSERVABILITY_AUDIT.md`。
- 防作弊：不得 teacher-force 未來平台、motion 或 event；不得放寬碰撞框來
  宣稱 exact rollout 通過。
- 範圍：只允許短 simulator learnability probe；BC、DAgger、Residual、
  DQfD、長 RL 與新增實機 rollout 仍為 No-Go。

## D-010：P1 通過後停止本機擴訓，轉入 Colab 驗證

- 日期：2026-07-30
- 決策：P0／P1 simulator learnability probes 通過後，不在本機自動追加
  timesteps。下一個 gate 是 Colab runtime、throughput、checkpoint、resume
  與 MP4 artifact 驗證。
- 證據：P1 使用 3 個 fresh train seeds、每演算法 8,192 steps、20 個
  held-out eval seeds。PPO 三 seed 平均 1.45 floors，SB3-DQN 1.167，
  random 0.70；六個模型皆未 collapse 且左右方向 coverage 通過。
- 限制：PPO variance 仍大，SB3-DQN 明確不是 Double DQN，兩者平均都未超過
  baseline 1.65 floors。
- 範圍：准許 Colab pipeline validation，不准長訓、BC、DAgger、Residual、
  DQfD 或新增實機 rollout。
