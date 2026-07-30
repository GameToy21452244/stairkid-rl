# Training Strategy Report V2

日期：2026-07-30

決策：調整策略；停止把「真實遊戲單畫面、單步、on-policy PPO」當主路線。

## 為什麼目前訓練幫助不大

問題不只是 timesteps 太少，而是資料產生方式與 learning signal 不匹配：

1. **資料吞吐太低**：真實環境約 6–7 steps/s，PPO 需要大量 on-policy rollout，
   且每次失敗都消耗 reset/menu/focus 時間。
2. **狀態分布太窄**：短回合反覆看到開局與死亡附近狀態，安全落台、回復與危險
   組合的覆蓋不足。
3. **credit assignment 模糊**：一次短按的效果延遲到後續畫面，legacy data 沒有
   command/effective timestamps，模型可能把錯的 observation 配到 action。
4. **reward shaping 過多且會漂移**：floor 是稀疏成功訊號，其餘 shaping 的尺度、
   延遲與偵測錯誤可能讓「不動」或「單方向」成為局部最優。
5. **已觀察到 collapse**：最新 5120-step PPO deterministic evaluation 連續
   128 次 RELEASE；其他 checkpoint 也曾 128 次 RIGHT。
6. **舊資料不能直接模仿**：不是完整 transition，baseline 也尚未被證明為 expert。

因此，單純增加真實 PPO steps 大概率只會更昂貴地強化同一個偏差。

## 類似 NS-SHAFT 專案

找到一個公開的 [NS-SHAFT-with-NEAT 專案](https://github.com/libao3128/NS-SHAFT-with-NEAT)
及其[專案報告](https://hackmd.io/@libao3128/S1tc3yGnO)。它不是以畫面控制原始
executable，而是建立可直接存取遊戲物件的自製環境，再用 NEAT 進化網路。其輸入
包含 player／鄰近平台狀態，輸出是左右移動；fitness 以樓層為主，加上生命、
尖刺傷害項。報告稱經長時間、多 generation 搜尋後，訓練最高曾到 60 層，
所附模型在 50 次測試最高 42 層。

它帶來的重點不是「改用 NEAT 就會成功」，而是：

- 訓練發生在可快速重設、可大量平行取樣的環境；
- 用結構化 player/platform 狀態，不只是一張孤立畫面；
- 以樓層、生命與 hazard 建立可解釋 fitness；
- 大量 generation 後仍會學到脆弱固定策略，顯示需要跨場景評估。

該專案直接存取自製遊戲 state；我們不會把這種方法搬到原始 executable，因為本
專案安全界線禁止 memory/API hack。可借鏡的是「另建 simulator 供大量資料」。

## 文獻對策略的支持

- 原始 DAgger 工作指出純 BC 的 learner 會進入 expert data 沒覆蓋的狀態；
  dataset aggregation 透過在 learner 自己遇到的狀態上重新取得 expert label
  改善分布偏移，並曾用於 Super Mario Bros. 等序列控制
  （[Ross et al.](https://arxiv.org/abs/1011.0686)）。
- DQfD 把示範的 supervised large-margin loss 與 1-step／n-step Double-Q loss
  結合，先 demo pretrain，再混合 demo 與 agent replay；原研究強調小量示範能
  改善資料效率（[Hester et al.](https://arxiv.org/abs/1704.03732)）。
- 若人工 correction 成本太高，ThriftyDAgger 顯示可把 query 集中在 novelty
  或 risk 高的狀態，而不是每一步都請人標註
  （[Hoque et al.](https://proceedings.mlr.press/v164/hoque22a.html)）。

這些研究支持「先把資料品質與 simulator 建好，再做 BC/DAgger/DQfD」，但不代表
現在就應一次實作所有演算法。

## 確認的新實驗方案

### E0：資料與 simulator engineering gate（現在）

不是訓練實驗。完成 transition writer、legacy quarantine、latency schema，
以及 simulator 的 fixed seed／100k smoke／check_env。此骨架本次已完成大部分，
writer 與校正仍待做。

成功條件：

- validator errors = 0；
- reward 可由 components 重算；
- terminal/truncated 與 episode continuity 正確；
- simulator random/baseline 不 crash，固定 seed 可重現。

### E1：真實動力有限校正

只收集少量、明確確認的人工或 baseline telemetry，不更新模型。分別量測：

- RELEASE 下的重力／bounce；
- LEFT／RIGHT 的加速度、限速、release drag；
- platform scroll／spacing；
- command → effective action → next observation latency。

每項都設時間／回合上限，原始資料先 validator，再擬合 simulator profile。

### E2：simulator benchmark

固定 seeds 比較：

- random；
- RELEASE-only；
- `SafePlatformPolicy`；
- 1／4／8／16 同步與非同步 env throughput。

主要指標：floors、survival steps、return、death reason、action distribution、
longest streak。baseline 若沒有穩定優於 random，不開始學習實驗，先修 observation
或 physics。

### E3：短 learnability probe

只有 E1/E2 通過後才允許。用小型固定 budget 比較：

- DQN 或 Double DQN；
- PPO 僅作同預算對照。

這一階段不使用舊 checkpoint，不接真實 executable。設 early stop；若 action
collapse 或未優於 random/baseline，不追加長訓。

### E4：乾淨 BC

後續才做。教師只可來自 human、corrected 或 baseline_verified。先做 action
classification、class balance、confusion matrix，再跑固定 simulator eval。
BC 不通過 action diversity 與 rollout gate，不進 DAgger。

### E5：DAgger / Residual / DQfD-lite

依序而非同時：

1. DAgger 先收集 learner failure states 的小量 correction。
2. baseline + bounded residual 測試能否保留安全 fallback。
3. 最後才用 Double DQN／DQfD-lite 混合 validated demo 與 agent replay。

每一步都需 ablation，否則無法知道改善來自何處。

## 建議的最小評估矩陣

| 比較 | seeds | episodes/seed | budget | gate |
|---|---:|---:|---:|---|
| random vs release vs baseline | 5 | 20 | 無訓練 | baseline floors/survival 顯著較好 |
| PPO vs Double DQN probe | 5 | 20 | 相同 env steps | 無 collapse，至少優於 random |
| BC vs baseline | 5 | 20 | 相同 demo set | BC 不低於教師容許界線 |
| BC vs DAgger | 5 | 20 | 報 correction 數 | recovery 提升且人工成本可接受 |
| residual / DQfD-lite | 5 | 20 | 相同 interaction budget | 多 seed 優於 baseline |

所有數字都是 protocol 初值，不是成功保證；應先用 E2 benchmark 估計合理 episode
長度，再凍結正式比較。

## 最終建議

目前最大問題是「資料與 transition 的可信度」加上「真實 on-policy throughput」，
不是模型網路太小。新的最合理方向是：

`乾淨資料 + 可校正 simulator + 固定 benchmark → BC → 小量 DAgger → value-based fine-tuning`

2026-07-30 更新：simulator v0.1 benchmark、sample／一步／landing calibration
與 seeded distribution fidelity gate 已通過。下一步只批准固定 seed、固定步數
的短 simulator learnability probe；長 PPO、BC、DAgger、Residual、DQfD 與新增
實機 rollout 仍為 No-Go。
