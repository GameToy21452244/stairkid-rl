# Experiment Protocol

## 每個實驗必填

- experiment id、git commit／dirty diff fingerprint、日期與執行平台；
- observation schema、reward version、environment config；
- policy source／初始化 checkpoint 及其 validation 狀態；
- seed 清單、train/eval 分離方式、步數／回合／時間硬上限；
- action counts、longest same-action streak、direction switches；
- floors descended、episode return、episode length、death reason、health loss；
- checkpoint、TensorBoard、影片與 summary 的保存路徑。

## 固定評估

- 開發 smoke 可用單 seed；決策比較至少 5 個固定 seeds。
- 每個候選策略至少 20 個 simulator evaluation episodes；訓練 seeds 與評估
  seeds 不重疊。
- 評估採 deterministic policy 時必須同時報 action distribution；單一動作
  比例 ≥ 98% 視為 collapse，除非環境 oracle 明確證明該策略合理。
- random、RELEASE-only、既有 `SafePlatformPolicy` 是最低比較基準。
- 報平均值、中位數、標準差、最差 seed，不只報最佳 checkpoint。
- 所有正式 gate 另報 95% bootstrap confidence interval、成功到達
  1／3／5／10 層比例，以及相同 seed 的 paired differences。
- 失敗需使用 v0.2 固定 taxonomy；另報 missed-platform、brake-too-late、
  wall、top／bottom death、action streak／switch 與 simulator steps/s。

## BC checkpoint selection

- Spike Teacher Dataset v1 固定 dataset 2000～2059、selection 2060～2079、
  final 2200～2219；1500～1899 與舊 v0 partitions 全部禁止重用。

- 不得再以最低 offline validation loss 直接指定閉迴路控制 checkpoint。
- 候選 epoch 必須在訓練前固定；spike BC0 v1 為 3／5／8／11／14／17。
- Teacher dataset、rollout checkpoint-selection、final-evaluation seeds
  三者必須非空且完全不重疊，程式遇到重疊即中止。
- spike BC0 v1 固定 dataset 1000～1059、selection 1060～1079、
  final 1200～1219；1100～1119 是已污染診斷集。
- 選模順序固定為 collapse／health death、`reach_rate_floor_10`、bottom
  deaths、deepest-floor Q25、median deepest floor、rollout gate、mean
  deepest floor；offline validation loss 只作最後 tie-break。
- `success_rate_floor_*` 只代表 successful-descents 事件計數，禁止再當作實際
  到達樓層；正式 reach Gate 必須使用 simulator `deepest_floor`。
- Final Gate 另要求 reach-floor-10 至少保留 baseline 90%、bottom death
  不得高於 baseline、deepest-floor Q25 至少保留 baseline 80%。
- final seeds 只能在 checkpoint 已凍結後評估一次；final FAIL 不得回頭調整
  epoch 或門檻後重用同一組 final seeds。

## Simulator v0.2 分層 gate

1. Reachability：easy 先 100 seeds，確認每個生成點有安全候選、2～3 層
   look-ahead、序列可重現且無已知不可達；通過後擴至 1,000 seeds。
2. Oracle-full：easy 至少 95% 回合達到 10 層，所有失敗均已分類。
3. Baseline：明顯優於 random／RELEASE，平均至少 5 層且至少 90% 回合達 3 層。
4. Frequency：固定 60 Hz physics，以相同 seeds 比較 8／10／12 Hz。
5. 前述 gate 與 dataset validator 通過前，不得產生 BC teacher dataset。

## Simulator Go gate

開始任何 learnability probe 前必須全部通過：

1. `pytest`、`check_env`、fixed-seed、rgb_array 與 100k headless smoke。
2. 1／4／8／16 env benchmark 已記錄，能選出不過度消耗 CPU／RAM 的 env count。
3. baseline 與 random benchmark 有固定 artifact。
4. reward component 總和可重算，terminated 與 truncated 分開。
5. 物理與真實 telemetry 的差異已列入 calibration report。

## Calibration fidelity gate

- LEFT／RIGHT 各至少 30 筆不靠牆、無事件干擾的 transition。
- 非零水平速度下的 RELEASE 至少 20 筆；自由落下至少 30 筆；normal landing
  至少 20 次。
- action effective → next observation latency 的 simulated error 不超過一個
  control step。
- 單步 MAE：x ≤ 6 px、y ≤ 8 px、vx ≤ 50 px/s、vy ≤ 60 px/s。
- 可觀測水平 rollout：10-step x ≤ 25 px、30-step x ≤ 60 px。
- exact screen-y 診斷仍報 10-step 30 px／30-step 70 px；若 horizon 依賴
  初始 viewport 外的隨機平台，依 D-009 不得 teacher-force 未來平台來過關，
  改用下列 seeded distribution gate。
- distribution gate 至少使用 300 real steps、1,000 simulator steps與
  100 個固定 simulator episodes；baseline landing／floor rate 各自的
  two-proportion test 必須 |z| ≤ 1.96。
- normal landing precision 與 recall 均 ≥ 0.80；top/bottom death 不得誤判。
- 未量測的項目一律算 FAIL，不可用工程 smoke 代替 fidelity gate。

## 資料 Go gate

- validator error 必須為 0；warning 必須逐項人工接受或 quarantine。
- 不允許 terminal 後 transition、episode 跨界、時間倒退、NaN／Inf 或無效動作。
- `policy_source=baseline_verified` 必須有對應人工／規則驗證紀錄。
- old PPO、legacy baseline 與 manual audit 預設為 quarantine，不能只補預設值就升格。

## 實機 protocol

- 需使用者明確輸入確認並顯示倒數。
- 開始前驗證唯一目標視窗、foreground 與遊戲 phase。
- 設定 step／episode／seconds 三種硬上限；達任一上限即停止。
- 失焦、額外相關視窗、F8、Ctrl+C、unknown phase 或例外立刻
  `release_all()`。
- 不得在自動測試或 Colab 中執行；不得自動增加回合數。

## Teacher Real-Game Micro Gate

- dry-run 必須是預設模式，且不得建立 live adapter、載入輸入 backend 或送鍵。
- 實際模式需明示 `--execute`、輸入固定確認字串並倒數；smoke 僅 3～5 回合，
  episode/total step/seconds 三種硬上限同時生效。
- 每步保存 canonical transition 與 controller sidecar：phase、target lock/age、
  previous action/streak、braking、launch、recovery、observation confidence、
  command/effective/next-observation timestamps、loop Hz。
- 每回合保存 MP4；影片無法建立時該回合不算完整 Gate evidence。
- 真機 `reach floor N` 只以校正後 HUD counter 的 episode max 判定；landing／
  track ID 不再推算樓層。HUD 值仍不能冒充 simulator privileged `deepest_floor`，
  報告必須標出語意差異。
- Sidecar 必須分開 command dispatch latency 與 visual motion-onset latency；
  physical latency Gate 至少要有 LEFT／RIGHT 各一個有效樣本。
- smoke PASS 至少要求安全事件 0、三個完整回合、無 ≥98% 單動作 collapse、
  target/memory/observation 記錄完整、至少各一個 reach 3 與 reach 5 案例，且
  terminal/failure 可映射至共同 taxonomy。未實際執行時狀態只能是 PENDING。

## Sequence-control 模型選擇

- 正式排序：安全事件 → health death → bottom death → Q25 → CVaR25 →
  reach 3/5/10 → median → mean → maximum。
- S0/S1/S2/S3 必須使用相同 episode splits、frozen seeds、更新與環境步數預算。
- controller sidecar 是 `policy.choose` 後的 post-decision snapshot；同一步欄位不得
  作 action label 的模型輸入。explicit state 一律以 `memory[t-1] -> decision[t]`
  重建，episode 第0步 reset，並排除 raw platform/track IDs。
- sequence chunk 不得跨 episode；padding/mask/burn-in 與 reset hidden state 必須測試。
- DAgger correction 以 sequence 為單位，初始最多占 20%，保留 safety replay；
  health death 從 0 增加或 Q25/CVaR25 明顯下降即拒絕。

## P4.0 State-aliasing Gate（已通過並凍結）

- primary data：Gate v11實機10回合／753 rows；每筆268維且sidecar alignment完整；
- 5-NN只可跨episode；feature z-score，observation/memory distance各權重0.5；
- causal memory相對observation-only的disagreement reduction至少10%；
- paired episode bootstrap 95% CI下界不得為負；
- entropy至少改善0.05 bits或kNN action accuracy至少改善3 percentage points；
- post-decision leakage ceiling與raw IDs不得參與Gate。

實測relative reduction 19.23%、entropy改善0.1873 bits、accuracy改善13.01 points、
bootstrap CI `[0.0979,0.1411]`，全部PASS。這只解鎖bounded P4.1消融，不等於模型
或closed-loop Gate通過。

## P4.1 Frozen bounded ablation protocol

- Dataset：`spike_teacher_dataset_v1.jsonl`，60 episodes／3,529 rows；只接受manifest
  SHA-256 `fa3e111a6204ac53767824e8d71d1ccf841637976427c410c1e14dff308c7a0a`。
  Current Teacher source重建結果不同，因此Colab不得重建或重新命名冒充原資料。
- S0：268→256→128→3 MLP；S1：268＋9維past-action causal state→同型MLP；
  S2：268維sequence→GRU-128→3；S3：22維latest compact observation＋9維causal
  state→GRU-128→3。
- 9維state只由`action<t`更新，decision t前snapshot；episode reset全零。當步sidecar、
  Teacher phase/target私有memory、future observation、simulator state與raw IDs禁止。
- Sequence length 24、burn-in 8；chunk不跨episode，padding mask與loss mask分離；每個
  row label只計入一次。GRU deployment hidden在每回合reset。
- Hard CE、Adam 1e-3；四組相同300 optimizer updates、candidate updates
  100／200／300、initialization seeds 0／1／2。MLP batch 112；sequence batch最多
  8 chunks。凍結train split下兩者都是21 updates完整看完2,327 labels一次；每update
  實際label數仍隨artifact保存。
- Development interface seeds 3900／3901永久退休；checkpoint selection只用
  4000～4019；架構與checkpoint凍結後，4100～4139 final seeds每個checkpoint只跑一次。
- Selection及final都先拒絕collapse／health regression，再依reach-10、bottom、Q25、
  CVaR25、oscillation、median、mean排序；offline loss只作最後tie-break。
- Final Gate要求候選相對S0在每個主要指標至少2/3 initialization方向非負，平均至少
  Q25 +1 floor、CVaR25 +0.5 floor、reach-10 +0.05、bottom death rate -0.025、
  direction switches/100 steps -0.10，並維持0 health death與無action collapse。
- 若selection沒有任何S1/S2/S3通過，不使用final seeds；若final FAIL，保存artifact後
  停止。科學FAIL是正常完成，runner回傳0；只有runtime/schema錯誤才非零中止。

## 當前結論

P3.6 Gate v11與P4.0 State-aliasing Gate已PASS。目前唯一 **Go** 是設計並執行
bounded P4.1 S0/S1/S2/S3公平短消融；split、seed、update budget與causal schema
必須先凍結。rare-branch dataset、正式BC/DAgger、長PPO/DQN/DQfD/NEAT及未授權
實機rollout仍為No-Go。
