# Training Strategy Report V2

日期：2026-07-30

決策：調整策略；停止把「真實遊戲單畫面、單步、on-policy PPO」當主路線。

## 2026-07-31 Sequence-control 最高優先修訂

直接核對 artifacts 後，最新 Prompt 的主要數值一致：Teacher holdout 1800～1899
reach-floor-10 94%、deepest-floor Q25 30、0 health death；Spike Dataset v1 為
60 episodes／3,529 rows、validator 0 error；BC0 v1 final mean deepest 45.5、
Q25 7.75、reach-floor-10 60%、bottom 14，baseline 分別 49.7、30、100%、1。
舊 Spike DAgger mean 28.57→38.75，但 reach-floor-10 86.67%→75%、bottom
15→27 且有 1 health death。沒有發現需推翻策略的數值差異。

Prompt 中「Teacher／Baseline mean 約 49.7」需作 partition 語意釐清：49.7 是
BC0 final 2200～2219 的 baseline mean deepest；Teacher holdout 1800～1899 的
mean deepest 為 47.31。這不是結果衝突，但後續報告不得混用兩個 seed partition。

因此主線改為 P3.6 Teacher Real-Game Micro Gate → P4.0 state-aliasing →
P4.1 S0/S1/S2/S3 → P4.2 rare-branch sequence dataset → P4.3 conservative
sequence DAgger → P4.4 compact NEAT。單步 MLP 只保留為 S0；在真機 Gate 未
實際通過前，後續 Gate 一律停止。真機 event-based floor count 與 simulator
`deepest_floor` 必須分開報告。

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

目前最大問題是「資料與 transition 的可信度」、「v0.1 未保證可解」及
「Oracle 與可觀測教師尚未分離」，不是模型網路太小。新的最合理方向是：

`Data Resource Audit → v0.2 reachability → Oracle-full／Teacher-observable
→ 8/10/12 Hz → BC0 → DAgger0 → special-platform curriculum
→ residual／value-based fine-tuning`

2026-07-30 更新：simulator v0.1 benchmark、sample／一步／landing calibration
與 seeded distribution fidelity gate 已通過。下一步只批准固定 seed、固定步數
的短 simulator learnability probe；長 PPO、BC、DAgger、Residual、DQfD 與新增
實機 rollout 仍為 No-Go。

## 2026-07-30 最新策略修訂

Colab pipeline 已通過，但 768-step checkpoint deterministic 全 RIGHT；因此
不再把「pipeline 能訓練」誤作「策略有效」。本輪先逐筆稽核 649 筆 calibration
與 2,912-row legacy 資料，接著讓 Simulator v0.2 保證連續平台序列具安全可達
路徑。Oracle-full 只驗證環境，Teacher-observable 才能產生 BC label。
Reachability、Oracle、Baseline 及 control-frequency gates 全部有獨立門檻；
只有通過後才准許小型 BC0 與至多一輪 DAgger0 smoke。

## 2026-07-31 BC0／DAgger0 實證更新

Soft-target BC0 的 learner-state disagreement 為 41.01%，rollout 僅 20.95
floors。相同資料改 hard-label CE 後，三 seeds 為 29.80／30.10／25.95，
全部通過 80% baseline gate。現階段 soft target 應保存作 uncertainty audit，
不直接當 loss target。

一輪 DAgger0 加入 1,634 個等權 corrections 後反而降至 23.20 floors。這表示
「更多 learner-state labels」本身不保證改善；correction ratio、相關性與
failure-cluster balance 必須先設計。本輪依規格停止，不啟動第二輪或長訓。

後續經使用者確認只做一次預先固定 ablation：corrections cap 為原 train 25%，
維持原 action ratio，並跨 12 state clusters／failure categories round-robin。
結果 frozen 63.15、fresh 62.90 floors，fresh baseline 31.25。這支持
「少量、平衡、覆蓋 failure modes」而非全量 aggregation。Easy normal-platform
已飽和，主線可在人工確認後前進到血量＋普通平台回血，但不得直接混合 hazards。

Health＋normal heal 已以預設關閉的 feature 完成 mechanism gate：低血量
Oracle 固定落台 100/100 通過，滿血 feature off/on 的 100-seed episodes
完全相同。這一階段沒有訓練；下一項只能是獨立尖刺 gate。

## 2026-07-31 尖刺機制 Gate

尖刺以 `enable_spikes` 獨立 feature flag 實作，預設關閉且依賴 health
機制。固定情境已驗證非致死傷害、生命耗盡終止、尖刺與普通平台回血互斥、
Oracle 在同層可選平台中優先避開尖刺，以及 renderer／calibration 行為。
100 seeds 全部通過；一般平台生成器刻意尚未產生尖刺，因此另以 100 seeds
確認只開啟功能但不生成尖刺時，trajectory、樓層與終止原因完全一致。

此結果只代表機制正確，不代表含尖刺策略已學會。依逐項 curriculum 原則，
目前不生成含尖刺 Teacher Dataset、不重訓 BC/DAgger。下一步先做輸送帶的
獨立 mechanism gate；待特殊平台逐項驗證後，再凍結混合分布與訓練門檻。

## 2026-07-31 輸送帶機制 Gate

輸送帶以左右 platform kind 與獨立 `enable_conveyor` 實作，落地時施加
方向性水平速度增量。左右速度、方向事件、renderer、calibration interface
及 Oracle 同層普通平台優先均已通過；正式 fixed gates 左右與 Oracle 各
100/100。功能開啟但不生成輸送帶時，100 seeds 與 feature-off trajectory
完全一致，兩者平均皆 34.68 floors。

目前 ±80 px/s 未經真實輸送帶 telemetry 校正，只能證明程式機制可控。一般
generator、Teacher Dataset、BC/DAgger 都未改動。下一步是彈簧獨立 gate；
特殊平台混合比例與訓練成功門檻仍須等各機制完成後另行凍結。

## 2026-07-31 彈簧機制 Gate

Spring v1 將落地垂直速度由普通平台的 95 px/s 提高到暫定 190 px/s。
stronger-bounce、事件、renderer、calibration interface 與 Oracle 同層普通
平台優先均通過；正式 fixed gates 彈跳與 Oracle 各 100/100。功能開啟但
不生成 spring 時，100 seeds 與 feature-off 完全一致，平均皆 34.68 floors。

190 px/s 尚無真實 telemetry 支持，只代表機制可測。一般 generator、
Teacher Dataset 與模型都未更動；下一項是翻板獨立 mechanism gate。

## 2026-07-31 翻板機制 Gate

Flipping v1 使用暫定 active／inactive 各 1 秒的同步週期；inactive 時不碰撞，
active state 對 observation 可見，Oracle 會排除 inactive 候選。active
collision、inactive passthrough、renderer、calibration interface 與 Oracle
均通過，三個正式 fixed gates 各 100/100。功能開啟但不生成翻板時，
100 seeds 與 feature-off 完全一致，平均皆 34.68 floors。

五項特殊機制至此只完成可測的工程層。下一個實驗不能直接混合所有平台或長訓；
應先選一種特殊平台、設定低比例與 seeded phase，重新跑 reachability、
Oracle、baseline，再決定是否生成新的 Teacher Dataset。

## 2026-07-31 Spike curriculum v0

第一個特殊平台課程只加入尖刺：proposal 10%、前 3 層普通平台、尖刺間至少
5 個普通平台。1,000 initial seeds 的實現比例為 5.11%，幾何與 health
reachability 全 PASS。Oracle 100% 到第 10 層；baseline 33.07 floors，
相對 plain 34.68 保留 95.36%，99% 到第 3 層且沒有 health death。

Gate 通過後才以未參與 Gate 的 seeds 1000～1059 生成 60 episodes／3,541
rows。Validator 0 error，包含 16 spike contacts、37 health gains，最低 health
為 7。這代表資料 pipeline 可進 spike BC0，不代表模型已學會尖刺；下一步先
凍結 fresh-seed 評估與 bounded smoke，正式多-seed重訓才使用 Colab。

後續 coverage audit 顯示 test split 有 232 spike-visible rows。本機 seed 0、
5-epoch interface smoke 為 27.0 floors，保留 baseline 85.58%，0 health death；
overall／spike-visible accuracy 74.75%／75.43%。因此准許進 Colab 三-seed
bounded BC0。Spike-target emergency subset 僅 10 rows／40%，必須持續列為
風險，不因 rollout PASS 而省略。
## 外部 NS-Shaft NEAT 專案比較（2026-07-31）

使用者提供的專案把平台、玩家、碰撞、血量、生成器與 fitness 直接寫入其
`GameObject.py`／`main.py`，以 12 個內部結構化特徵、2 個輸出與 population
50 演化網路拓撲。它不是以螢幕擷取控制本專案的封閉 Windows 遊戲；本質上也
是在自製、可讀內部狀態的環境訓練。

NEAT 可避開 Teacher label bias，且適合小型結構化網路；但該報告也明列長達
上萬 generations、高 seed／平台運氣變異、過半初始死亡、彈簧／牆邊失敗、
fitness healing exploit 與模型難重現。其 60 層 training record／50 次測試
最高 42 層不是 mean、Q25 或成功率，不能直接與本專案 Gate 比較。

因此 NEAT 可保留為 compact-observation bounded baseline，而非取代現有
simulator calibration、holdout、lower-tail safety 與最終實機驗證。任何 NEAT
實驗必須讓每個 genome 使用多個 common seeds，並依 reach-floor-10、Q25、
bottom／health death 排序，不得只最大化單次最高樓層。
