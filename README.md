# AI Stair Agent：NS-SHAFT 遊戲介面層

> 新對話請先讀`docs/CODEX_START_HERE.md`。2026-08-04最新工程更新是manual-only v0.4
> calibration candidate已準備人工before／after重測；formal狀態仍是
> `BLOCKED_WITH_EVIDENCE`，holdout與training均未使用。

本專案以一般 Windows 視窗 API、螢幕擷取及鍵盤輸入控制既有的
`NS Shaft.exe`。目前已完成遊戲介面層、角色／平台／血量事件辨識、Gymnasium
環境，以及具有硬性安全上限的本機 PPO 訓練入口。舊 PPO 與 Colab
512／768-step checkpoint 已出現單一動作塌縮，不是可用模型，也不得續訓。

> 最新 Simulator 阻擋（2026-08-04）：v7 receding Oracle已test-first實作，但全新
> 16000～16099 development只有76%到第10層，低於95%門檻與v6 reference 96%；
> bottom death由2增至22，故正式REJECT並`FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT`。
> 17000～17099 one-time holdout完全未使用，Dataset與Student仍未解鎖。詳見
> `reports/SIMULATOR_ORACLE_ROBUSTNESS_REPORT.md`。

目前最高優先策略為：Teacher 真實遊戲 Micro Gate → State-aliasing Audit →
S0／S1／S2／S3 memory/sequence 消融 → rare-branch sequence dataset →
conservative sequence DAgger → compact NEAT 公平對照。前一 Gate 未通過即停止，
不以長 BC、PPO、DQN 或大型 NEAT 掩蓋表示／資料問題；權威進度見
`docs/CURRENT_STATUS.md`。最新完整 10 回合 natural run 經同 run MP4 終局影格稽核後
floors 為 `8,11,4,2,2,5,4,4,8,2`；Gate v11 以不可變 sidecars 重分類後全部 checks
PASS。P4.0 已對10回合／753筆實機資料完成 State-aliasing Audit：跨episode 5-NN
action conflict由observation-only的56.20%降至lagged causal memory的45.39%，相對
改善19.23%，episode bootstrap下界亦為正，Gate PASS。P4.1 的 causal schema、資料
manifest、S0～S3介面及Colab三初始化bounded selection均已完成，但結果為
`FAIL_STOP_SELECTION`。S1提高mean與Q25，卻使CVaR25、reach-10與bottom death退化；
S2/S3可靠性更差。修正risk-first排序與跨RELEASE reversal後重播既有S0/S1 checkpoints，
Gate仍為`FAIL_STOP_SELECTION_CONFIRMED`；S1 reversal平均也較差。Final seeds未使用，
Dataset v2 Gap Audit確認current Teacher同種子只有75% reach／25% bottom；分離後的
Simulator Teacher profile Gate中最佳delayed2也只有81.67%／18.33%，仍為
`FAIL_STOP_SAME_SEED_RELIABILITY`。後續唯一launch-handoff候選又退化至75%／25%，
狀態`FAIL_STOP_LAUNCH_HANDOFF_SAME_SEED`；Fresh100未執行。Phase observability
audit再發現首次介入只有2改善／6退化／52不變，且同一可部署簽章同時出現改善與
退化，狀態`INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL`。其後依凍結協定完成400回合
observation-schema probe：launch-handoff只有1改善／29退化／365不變，reach由
76.25%降至69.25%、bottom由23.75%升至30.75%，狀態
`INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE`。同步真機alignment packet其後以308 records
通過Integrity／Coverage，但Simulator／Real Audit發現一般模擬分布缺spring、conveyor、
flipping，且真機rising-support最長11步、確認造成departure timeout／restart，狀態
`FAIL_STOP_SIMULATOR_REAL_ALIGNMENT`。下一步先補分布Gate與離線phase-aware shadow
replay；P4.2與BC、DAgger、PPO、DQN、NEAT長訓練仍禁止。
第一個分布補充已選spring：工程、Reachability及2.70% spawn ratio通過，但Oracle
在100個新seeds只有71%到第10層；35個遇spring回合中29個top death，狀態
`FAIL_STOP_ORACLE`。Baseline依序未跑；下一步先做spring failure trace/fidelity audit，
不直接訓練或放寬Gate。
後續trace確認是重複contact時Oracle持續RELEASE；不改190 px/s，只加入privileged
spring clearance後，development與untouched holdout均100%到第10層，Baseline retention
101.35%、reach3 94%，Spring Simulator Gate已PASS。真機Teacher沒有因此修改，下一步仍
是conveyor/flipping分布與support shadow；離線Gate完成前不需要重跑實機。
當步controller sidecar含post-decision label leakage，不得當
同一步模型輸入。Alignment packet v1的writer、validator、coverage Gate與真機runner
旁路已完成，dry-run及完整462 tests PASS；受監督3回合packet也已通過，但它只解鎖
alignment audit，不代表Simulator fidelity或Teacher資料已通過。

最新 Spike Teacher Dataset v1 有 60 episodes／3,529 rows、validator 0 error；
但單步 BC0 v1 的 final mean deepest 45.5 雖接近 baseline 49.7，Q25 只有
7.75（baseline 30）、reach-floor-10 只有 60%（baseline 100%），bottom death
14（baseline 1），因此正式 Gate FAIL。下一步不是增加 epochs，而是先驗證
Teacher 真機轉移及以 causal memory／sequence 表示能否在閉迴路穩定超過單步 S0。

特殊平台 curriculum 已完成第一個 mechanism gate：可選 health state 與普通
平台回血。功能預設關閉，100 個固定 Oracle 落台及 100-seed feature equivalence
通過；尚未加入模型訓練。

專案不修改、注入、掛鉤、反編譯遊戲，也不讀取遊戲程序記憶體。預設
`auto_launch: false`，任何工具都不會自行執行遊戲；請由使用者手動啟動。

## 完整實驗路線圖：從舊 PPO 到最終實機自主遊玩

本節是給人快速恢復專案上下文的主路線，優先於 README 後方依日期累積的歷史
敘述。精確的最新數字仍以 `docs/CURRENT_STATUS.md` 與對應 artifact 為準；長期規格
與停止規則以 `../CODEX_SEQUENCE_CONTROL_STRATEGY_UPDATE.md`、
`docs/PROJECT_MASTER_PLAN.md`、`docs/EXPERIMENT_PROTOCOL.md` 為準。

### 目前走到哪裡

| 階段 | 狀態 | 結論 |
|---|---|---|
| 舊真機 PPO | FAIL／封存 | 出現全 `RELEASE_ALL` 或全 `RIGHT` 的 action collapse，不續訓 |
| P0 Repository、schema、安全基礎 | PASS | 永久文件、validator、Gymnasium 骨架與安全控制鏈完成 |
| P1 Simulator v0.1、校正、Colab 管線 | 工程 PASS | 證明管線可跑；短 PPO 塌縮，不是策略成功 |
| P2 Simulator v0.2、Reachability、Teacher 分離 | PASS | easy curriculum、Oracle-full、Teacher-observable、8/10/12 Hz 比較完成 |
| P3 Easy BC0／DAgger0 與特殊平台機制 | 部分 PASS | normal easy 已飽和；各機制可運作，但混合與 fidelity 尚未全通過 |
| P3.5 Spike curriculum | 最終 STOP | BC 曾通過，但 DAgger／新版 BC lower-tail 失敗，不再加 epochs |
| P3.6 Teacher Real-Game Gate | PASS | Gate v11 十回合通過；Teacher 仍有 lower-tail 風險 |
| P4.0 State-aliasing Audit | **PASS** | causal memory 顯著減少動作衝突 |
| P4.1 S0／S1／S2／S3 bounded ablation | **FAIL_STOP_SELECTION_CONFIRMED** | S1只改善mean/Q25；tail、reach、bottom與反轉未過，final seeds未使用 |
| Dataset v2 Gap Audit | **FAIL_STOP_BEFORE_V2_GENERATION** | current Teacher同種子reach 75%、bottom 25%；先分離Simulator Teacher |
| Simulator Teacher Profile Gate | **FAIL_STOP_SAME_SEED_RELIABILITY** | delayed改善至81.67% reach／18.33% bottom，仍未達門檻；fresh未跑 |
| Launch-Handoff Gate | **FAIL_STOP_LAUNCH_HANDOFF_SAME_SEED** | 單一候選退化至75% reach／25% bottom；改做phase audit |
| Phase Observability Audit | **INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL** | 僅8個changed outcomes且有同簽章相反結果；先升觀測稽核 |
| Observation-Schema Probe | **INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE** | 400回合僅1改善、29退化；拒絕handoff方向，先做真機alignment |
| Real Alignment Packet | **PASS（限診斷資料）** | 3回合／308 records，完整性與分支coverage通過，不可直接訓練 |
| Simulator／Real Alignment Audit | **FAIL_STOP_SIMULATOR_REAL_ALIGNMENT** | 缺3種平台分布，且真機support phase alias造成timeout／restart |
| Spring curriculum v0 | **PASS（Simulator）** | Oracle dev/holdout 100%；Baseline retention101.35%，但真機physics尚未校正 |
| P4.2～P8 | BLOCKED | 必須逐 Gate 解鎖，不可直接跳階段 |

### 共通規則：每一個 Gate 都怎麼做

每個階段一律依下列順序，不因單次最高樓層很好看而跳步：

1. 先凍結問題、資料來源、版本、seed、split、評估指標、成功門檻與停止條件。
2. 先寫最小失敗重現或單元測試，再修改程式。
3. 先跑本機 unit／integration／schema／artifact 檢查。
4. 需要模型計算時才進 Colab；Colab 只跑 simulator，不控制原版遊戲。
5. selection seeds 只用來選 checkpoint，final seeds 只評估一次且不得回饋選模。
6. 先看 safety、health death、bottom death、Q25、CVaR25、reach，再看 median／mean；
   maximum 只能列出，不能單獨決定 PASS。
7. Gate FAIL 就停止下一階段，分析 observation、label timing、資料 coverage 或控制
   邏輯；不能用追加 epochs、timesteps 或反覆重跑直到幸運通過來掩蓋問題。
8. 每次保存 machine-readable artifact、報告、測試結果、失敗 taxonomy 與 provenance，
   並更新 CURRENT_STATUS、DECISIONS、RISK_REGISTER 及 implementation report。

### 歷史起點：為什麼放棄直接真機 PPO

最初路線是從單張／短 stack 遊戲畫面直接選 LEFT、RELEASE、RIGHT，再讓 PPO 依
reward 更新。它有三個核心問題：真機每秒樣本太少、reward 與死亡訊號稀疏，而且
同一畫面在「起跳、煞車、離台、恢復」階段可能需要不同動作。實際 checkpoint
出現 128/128 `RELEASE_ALL` 或全 `RIGHT`，所以既有 PPO 只保留為失敗證據，禁止
續訓。這也是後續先建 simulator、Teacher 與 sequence state 的原因。

### P0：Repository Audit、永久上下文與資料安全

目的：在開始新訓練前，先知道現有程式、資料與 checkpoint 到底能不能用。

執行步驟：

1. 稽核 source、scripts、tests、notebook、logs、models、captures 與歷史報告。
2. 建立 PROJECT_CONTEXT、CURRENT_STATUS、TRAINING_ROADMAP、DECISIONS、
   RISK_REGISTER 與 PROJECT_MASTER_PLAN。
3. 定義 268 維 observation、transition timestamps、episode boundaries、action、
   reward components、terminated／truncated 與版本欄位。
4. 實作 validator 與 legacy quarantine；無法證明時序或來源的舊 JSONL 不可當教師。
5. 保存視窗唯一性、foreground、F8、三種硬上限與例外 `release_all()` 安全鏈。

Gate：validator 能拒絕 NaN、無效 action、時間倒退、跨 episode、terminal 後續寫與
schema drift；自動測試不得送真實鍵盤輸入。此階段已 PASS。

### P1：Simulator v0.1、有限真機校正與 Colab 管線

目的：建立不需要安裝原版遊戲、可高速 reset 與固定 seed 的 Gymnasium／Pymunk
近似環境，先驗證資料流與基本可學性。

執行步驟：

1. 建立角色、重力、水平控制、普通平台、碰撞、落台、畫面捲動與終局骨架。
2. 以有限、受監督的真機 calibration 量 x/y/vx/vy、動作反應與 landing；校正資料
   只算 dynamics，不可冒充 expert demonstration。
3. 跑 fixed seed、`check_env`、headless、render、100k-step smoke 與 vector env
   throughput。
4. 在 Colab 驗證私人 repository ZIP 上傳、依賴安裝、checkpoint/resume、TensorBoard
   與 MP4 打包流程。
5. 跑短 P0／P1 learnability probe，只判斷管線是否能學，不宣稱會玩原版遊戲。

結果：工程與 Colab pipeline PASS；768-step PPO deterministic 全 `RIGHT`，所以策略
Gate FAIL。結論是「模擬器可執行」，不是「PPO 已學會下樓」。

### P2：Data Resource Audit 與 Simulator v0.2

目的：讓環境可持續生成樓層、保證基本可達，並把「驗證環境可解」與「產生可部署
標籤」分開。

執行步驟：

1. 逐檔、逐 episode、逐 row 將資源分類為 verified demo、replay、dynamics、
   needs relabel 或 invalid。
2. v0.2 加入持續平台生成／回收、easy/calibrated/hard profile、2～3 層 look-ahead
   reachability 與 deterministic seed。
3. Oracle-full 可讀 simulator privileged state，只用來證明環境可解。
4. Teacher-observable 只能讀與 Student 相同的 observation，不得讀未來平台或完整物理
   state；只有它的合格輸出可以成為 BC label。
5. 在固定 60 Hz physics 下比較 policy 8／10／12 Hz，凍結控制頻率後才產生資料。
6. 依序執行 Reachability、Oracle、Baseline gates；任一失敗都不可產生 Teacher
   Dataset。

結果：v0.2 easy gates 與 Teacher 分離已 PASS；原始遊戲與 simulator 的 reality gap
仍存在，因此後續必須用小型真機 Gate 驗證 transfer。

### P3：Easy Teacher Dataset、BC0、DAgger0 與特殊平台機制

目的：先證明完整 supervised／closed-loop pipeline，再逐項加入遊戲機制。

執行步驟：

1. 用 episode／seed／platform-sequence 隔離的 split 產生 easy Teacher Dataset。
2. BC0 以 hard-label cross entropy 做短訓練；offline accuracy 只作診斷，模型必須
   回 simulator 做 closed-loop evaluation。
3. naive DAgger0 失敗後，只做一次 correction cap、action ratio、cluster/category
   分層的 balanced ablation；通過後停止，因 easy normal curriculum 已飽和。
4. 特殊機制不一次混合，依序實作 health＋normal heal、spikes、conveyor、spring、
   flipping；每項預設關閉。
5. 每個機制先過 unit、fixed scene、renderer、Oracle 與 no-spawn equivalence；未有
   真機 telemetry 的速度、彈力、週期只能標 provisional。

結果：easy BC／balanced correction 與五個 mechanism engineering gates 已完成；這
不代表五種平台已可一起訓練，也不代表 simulator fidelity 已完全對齊原版遊戲。

### P3.5：Spike curriculum、checkpoint selection 與停止結論

目的：用低比例單一特殊平台檢查 Student 是否能保留 normal 能力並處理 hazard。

執行步驟：

1. 使用前 3 層 normal、10% spike proposal、尖刺間至少 5 層 normal 的 generator。
2. 重跑 Reachability／Oracle／Baseline，再以獨立 seeds 產生 spike dataset。
3. 發現最低 validation loss 的 epoch 17 closed-loop 很差後，改成預先固定候選 epoch，
   使用 selection seeds 選模，再對 untouched final seeds 評估一次。
4. 三 initialization BC0 Gate 通過後，執行一輪 balanced Spike DAgger0。
5. DAgger 雖提高 mean floors，卻降低 reach-floor-10、增加 bottom death 並出現 health
   death，依協議 FAIL／STOP。
6. 修復 Teacher health recovery 與 reach-floor-10 語意，untouched holdout 達 94%、
   0 health death；重新產生 Dataset v1。
7. Dataset v1 BC smoke 的 mean 尚可，但 reach-floor-10 60%、Q25 7.75、bottom 14，
   顯示單步 BC lower-tail 仍失敗，因此停止加 epochs 與第二輪 DAgger。

結論：主要問題不是資料量不足，而是單步 observation 無法穩定重建 Teacher 的
launch／brake／recovery／target memory。這直接導向 P3.6 真機 Teacher 與 P4.0
State-aliasing Audit。

### P3.6：Teacher Real-Game Micro Gate

目的：不訓練 Student，先證明規則 Teacher 在原版遊戲能安全、連續且可記錄地操作。

實際修復鏈包含：special contact lifecycle、spring/spike escape、持續按鍵、wall
guard、player vision continuity、projected landing、support-departure latch、bounded
dropout recovery、release projection、重開 focus、terminal HUD frame 與 Gate 語意。

最終 Gate v11 步驟：

1. 使用者手動開啟原版遊戲；runner 明示 `--execute`、確認字串、倒數與硬上限。
2. 完成單次自然 10 回合，不挑 episode、不失敗後反覆重跑。
3. 每步保存 canonical transition、controller sidecar、timing、phase、target、support、
   special lifecycle 與 MP4。
4. 用同一 run 的 MP4 稽核 terminal HUD counter；只允許可信的 terminal-frame 向上
   修正，不覆寫原始 artifact。
5. Gate 要求 safety=0、floor-1 bottom=0、至少 7/10 reach-3、4/10 reach-5、
   early-bottom 不超過 reach-3 miss budget、無 collapse、無 blind/outward/wall
   re-entry，以及 observation/departure/special telemetry 完整。

結果：floors `8,11,4,2,2,5,4,4,8,2`；reach-3 7/10、reach-5 4/10、
mean/median/Q25/CVaR25=`5/4/2.5/2`、安全事件 0，Gate v11 PASS。因 early-bottom
剛好壓線，這是進 P4.0 的資格，不是 Teacher 完美或正式部署許可。

### P4.0：State-Aliasing Audit（已完成）

問題：268 維 observation 相近時，Teacher 是否因隱藏控制階段而選不同動作？加入
真正可部署的歷史 state 是否能明顯降低衝突？

執行步驟：

1. 凍結 Gate v11 的 10 回合／753 rows，不新增或挑選實機資料。
2. 驗證 observation=268 維、有限值、transition/controller 筆數、step 與 action
   完全對齊。
3. 發現 sidecar 是 `policy.choose` 後才寫入：同一步 `previous_action` 已等於 label，
   phase 也由本步 reason 產生，因此當步 memory 只能當 leakage ceiling。
4. 正式 representation 使用 episode 內 `memory[t-1] -> decision[t]`；第 0 步 reset，
   raw platform/track/contact IDs 全排除。
5. 用 cross-episode 5-NN 比較 observation-only、causal action history、target、phase、
   support、full memory 與 post-decision leakage ceiling。
6. 預先固定 Gate：衝突相對下降至少 10%；paired episode bootstrap 95% CI 下界
   不得為負；entropy 至少降 0.05 bits或accuracy至少增3 percentage points。

結果：observation-only conflict 56.20%，causal full 45.39%，相對改善 19.23%；
entropy 改善 0.1873 bits、accuracy 增 13.01 points、bootstrap CI
`[0.0979,0.1411]`，P4.0 PASS。causal action history 單組 42.76%，甚至優於 121 維
full memory，因此 P4.1 優先 compact S1。Post-decision ceiling 11.42% 是答案洩漏，
永遠不能當 Student 輸入。完整報告見 `reports/STATE_ALIASING_AUDIT.md`。

### P4.1：S0／S1／S2／S3 公平 bounded ablation（正式 selection FAIL）

目的：確認「明確 causal state」或「sequence model」是否真的在 closed-loop 穩定優於
原本的單步 MLP，而不是只提高 offline accuracy。

預定模型：

- S0：現有 268 維 observation stack＋MLP，作單步基準；
- S1：268 維＋compact deployable causal action/control state＋MLP；
- S2：完整 observation sequence＋GRU；
- S3：compact deployable observation/state sequence＋GRU；
- S4 只有在前四者資料與 Gate 穩定後，才可考慮 phase／target／brake auxiliary loss。

目前已凍結的第一版實作如下：

- 資料固定為 Spike Teacher Dataset v1 的 60 episodes／3,529 rows，SHA-256
  `fa3e111a6204ac53767824e8d71d1ccf841637976427c410c1e14dff308c7a0a`；
- S1 的 9 維 causal state 只由 `action<t` 重建：前一動作、是否有前一動作、最後
  非 RELEASE 方向、同動作 streak、RELEASE streak、最近方向切換率；
- S3 的 compact observation 為最新一幀16個核心特徵＋最近平台6個特徵，再加上述
  9維 causal state，共31維；不含 raw ID、Teacher phase或當步sidecar；
- S2／S3固定 sequence length 24、burn-in 8、GRU hidden 128；每筆label只計loss一次，
  chunk不跨episode，padding／loss mask分離；
- 四組都用hard CE、Adam 1e-3、300 updates、candidate updates 100／200／300、
  MLP batch 112、sequence batch 8 chunks；兩者在2,327-row train split都是21 updates
  完整看完一次資料。Initialization seeds 0／1／2；selection seeds 4000～4019，
  final seeds 4100～4139；
- final seeds只在架構與checkpoint凍結後使用一次。科學FAIL會正常保存JSON並停止，
  不再以非零exit code讓Colab只留下`CalledProcessError`。

目前程式無法由current source bit-exact重建舊Dataset v1：重建結果為3,571 rows且
SHA-256不同，因Teacher控制程式後續已變更但policy version未升版。為隔離representation
效果，P4.1禁止重建，改由本機專用bundle攜帶凍結JSONL；完整證據見
`artifacts/p41_dataset_regeneration_drift.json`。

必須依序執行：

1. 先凍結 P4.1 dataset manifest、Teacher/controller version、episode split、所有 seeds、
   sequence length、burn-in、padding/mask、初始化數、更新次數及 early-stop 規則。
2. 做 causal schema preflight：任何輸入只能在 decision 當下取得；memory 用 `t-1`；
   episode reset 不 carry；同一步 sidecar、未來 observation、privileged simulator state、
   raw tracker ID 全部拒絕。
3. S0～S3 使用相同 training episodes、selection/final seeds、optimizer budget 與環境
   evaluation steps；不能讓某模型多看資料或多訓練。
4. 先跑 dataset loader、chunk boundary、hidden-state reset、mask、determinism、保存／
   載入與 action-collapse tests。
5. 本機只跑超短 interface smoke；多 initialization bounded 訓練才放到 Colab GPU。
6. Offline loss／accuracy、各 action confusion、phase/branch accuracy全部記錄，但不作
   最終選模依據。
7. 每個候選回 simulator 做相同 fixed-seed closed-loop evaluation，記錄 health death、
   bottom、Q25、CVaR25、reach-3/5/10、median、mean、action share、oscillation、wall、
   spring/spike dwell 與 failure taxonomy。
8. selection seeds 選出單一 checkpoint 後，untouched final seeds 只跑一次；至少三個
   initialization 的方向需一致。

P4.1 Gate：至少一個 S1/S2/S3 在 safety 不退化的前提下，對 Q25、CVaR25、
reach-floor-10、bottom 與 oscillation 穩定優於 S0，而且不是 action collapse。若只有
offline accuracy 提升、只有 mean／maximum 提升，或多 seeds 不一致，立即 FAIL／STOP，
回到 causal schema、sequence length、label timing或資料 coverage；不得直接進 P4.2。

本機 interface smoke 已完成：四組各4 updates、development seeds 3900／3901、
checkpoint save/load與closed-loop兩回合都PASS；這些seeds永久只作介面診斷。S2在兩個
短回合曾有mean deepest 9.5，但四組bottom rate均為1.0，樣本也只有兩回合，因此不得
當作S2優勝或P4.1 PASS。完整結果見`artifacts/p41_local_interface_smoke.json`與
`reports/SEQUENCE_MODEL_ABLATION.md`。

正式 Colab selection 已完成並停止：S1雖提高mean/Q25，但CVaR25、reach-10、bottom
與release-bridged reversal都不如S0；S2/S3的bottom death更高。狀態為
`FAIL_STOP_SELECTION_CONFIRMED`，final seeds 4100～4139未使用，P4.2不得開始。

後續 Dataset v2 Gap Audit 又發現current Teacher在相同60 seeds只有45次成功、15次
bottom，遠差於凍結v1的56/4；舊coverage Gate卻仍PASS。所以下一步不是再跑Colab或
增加資料，而是分離Simulator Teacher profile，bounded比較support-departure current／
delayed／disabled。詳細門檻見`reports/P41_DATASET_V2_GAP_AUDIT.md`；同種子與fresh
reliability未過前，不生成正式Dataset v2、不訓練Student。

三profile實測已完成：current/delayed2/disabled reach為75%/81.67%/76.67%，bottom
為25%/18.33%/23.33%，全部FAIL且fresh6000～6099未使用。Delayed將首次分歧由step1
延到median step6，但53/60由舊`escape_launch_platform`變成新
`aligned_with_safe_platform`。下一個只測Simulator-only support-aware launch handoff，
不掃更多delay；詳見`reports/SIMULATOR_TEACHER_PROFILE_GATE_REPORT.md`。

該單一handoff候選已實測並被拒絕：reach由81.67%降到75%、bottom由18.33%升到25%、
CVaR25由6.27降到4.2；launch rows增加，但support departure被完全吃掉且wall guard
上升。下一步不再改controller，先稽核decision-level phase是否能由deployable events、
motion、vy、gap與geometry辨識。完整負結果見
`reports/SIMULATOR_TEACHER_LAUNCH_HANDOFF_GATE_REPORT.md`。

Phase audit已完成並停止：60個首次分歧只有2次改善、6次退化、52次終局不變；8種
可部署簽章中有一種同時包含改善與退化。Privileged post-bounce phase與last-landed
identity亦無法可靠分開結果，所以不能再由現有欄位追加heuristic。當時只允許的
bounded observation-schema probe已在下一段完成。完整phase證據見
`reports/SIMULATOR_TEACHER_PHASE_OBSERVABILITY_AUDIT.md`。

Schema probe以7000～7399共400回合完成：395個首次分歧只有1 improved、29 regressed、
365 unchanged；其餘5個無分歧且補充重播終局相同。Launch-handoff reach由76.25%降至
69.25%、bottom由23.75%升至30.75%，development沒有正向class，故狀態為
`INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE`。不再調launch heuristic；下一步先建立同步
真機alignment packet，對齊target geometry、action timing及特殊平台短序列。完整結果見
`reports/SIMULATOR_OBSERVATION_SCHEMA_PROBE_REPORT.md`。

### P4.2：Rare-Branch Sequence Dataset

只有 P4.1 PASS 才執行。資料單位改成完整 episode 或不跨 episode 的連續 chunk，重點
覆蓋 late brake、wrong launch、missed-landing recovery、wall＋velocity、platform edge、
low-health spike、conveyor、spring、flip 與 vision dropout recovery。

步驟：凍結 branch 定義與最低 sequence coverage；在 simulator 加 bounded perturbation；
由 Teacher 接管恢復；保存 causal phase/target/support/confidence/perturbation/events；按
episode、seed、platform sequence 隔離 split；validator 必須 0 error。若 normal rows
淹沒 rare branch、timeline 不完整或 split 洩漏，Gate FAIL，不進 DAgger。

### P4.3：Conservative Sequence DAgger

只有 P4.2 dataset Gate PASS 才執行一輪。起始 aggregate 固定為 80% 原 Teacher／安全
資料＋最多 20% learner corrections；correction 必須是高 confidence sequence，按 phase
與 branch 分層並保留 safety replay。

接受條件：health death 不增加、bottom 不惡化、Q25/CVaR25 改善、reach-10 不下降、
mean/median 不明顯退化且多 seeds 一致。FAIL 即停止，不自動開始第二輪。

### P4.4：Compact NEAT 公平對照

NEAT 不是替代所有前置工作，而是 bounded baseline。比較 feed-forward compact、
recurrent compact 與 compact GRU；使用相同 seeds、horizon、environment steps、控制
頻率與總計算預算。fitness 必須包含 safety 與 lower-tail，不能用單次最高樓層選 genome。
若 Q25、CVaR、死亡率與重現性無優勢，不擴大 population 或 generations。

### P5：Closed-Loop Candidate Selection

從 explicit-state MLP、GRU sequence Student、sequence DAgger、compact NEAT 中選一個
最穩定候選。建立統一 checkpoint metadata、observation/causal schema version、hidden
state reset lifecycle、fallback Teacher 與部署 smoke。所有候選用同一 evaluation matrix，
仍先看 safety 與 tail risk。

### P6：Bounded RL Fine-Tuning

只有 sequence／memory Student 已穩定超過 S0，且 simulator failure taxonomy 能重現
真機問題時，才比較純 BC/DAgger、BC 初始化 PPO、recurrent replay RL 或 residual
policy。凍結 reward version、更新步數、replay、early stop 與 seeds；只在 simulator／
Colab 做 bounded 實驗，不在原版遊戲長時間探索。沒有多 seed closed-loop 增益就停止。

### P7：特殊平台 Curriculum 與 Domain Randomization

依 normal → spikes/recovery → conveyor → spring → flipping 分階段加入。每一項都重新
通過 mechanism、reachability、Oracle、Teacher、dataset coverage、Student regression；
最後才允許低比例混合。物理、比例、延遲、觀測噪音與短 dropout 的 randomization
範圍必須有真機 telemetry 依據，不可任意擴大來製造表面泛化。

### P8：漸進式真機 Student Gate 與最終展示

真機不是訓練場，而是 transfer／最終驗證。依 3 → 5 → 10 → 20 個 bounded episodes
漸進；每次都由使用者手動開遊戲並監看，保留 foreground/F8/release-all/step/seconds/
episode 上限、transition、sidecar、MP4 與 HUD audit。

升級條件：安全事件 0、無 action collapse／牆邊震盪／無原因長 RELEASE、lower-tail
不退化、special branch 可解釋、影片與 sidecar 完整。任何一級 FAIL 就回 simulator
做最小修復與固定重現，不在真機探索。20 回合穩定通過後，才進人工監看的較長展示，
最終目標才是實際觀看代理在原版 NS-SHAFT 自主遊玩。

### 本機、Colab、Simulator 與原版遊戲各自負責什麼

- 本機：程式修改、pytest、schema/artifact audit、影片 replay、短 interface smoke、
  使用者監督的 bounded 真機 Gate。
- Colab：S0～S3 多 initialization 訓練、大量 simulator fixed-seed evaluation、
  checkpoint 與結果 ZIP；不安裝也不控制原版 Windows 遊戲。
- Simulator：高速、可 reset、可固定 seed 的近似遊戲，用來訓練與做因果消融；它不是
  原版遊戲本身，因此所有成功最後都要過真機 transfer Gate。
- 原版遊戲：只收有限校正、Teacher／Student transfer 與最終 bounded evaluation；
  保留完整安全機制，不做長時間線上探索。

P4.1 的一般 GitHub source ZIP 不含被 ignore 的凍結 JSONL，因此不能用來跑正式消融。
本機在 clean commit 後建立專用 Colab bundle：

```powershell
.\.venv\Scripts\python.exe scripts\package_p41_colab.py
```

將父目錄產生的 `ai-stair-agent-p41-colab.zip` 手動上傳 Colab，依序跑 setup、pytest、
`check_env`，最後只把 notebook 最後一格 `RUN_P41_ABLATION` 改為 `True`。舊的
`RUN_SPIKE_BC0` 與 `RUN_COLAB_PIPELINE_VALIDATION` 保持 `False`。

### Repository 與本機實驗資料保留政策

GitHub 保存 source、tests、notebook、永久文件、報告，以及足以重建結論的 JSON／CSV
summary。大型 JSONL、checkpoint、logs、captures 與 MP4 預設由 `.gitignore` 隔離，
不是因為不重要，而是它們有不同的保存與隱私／容量需求。

2026-08-03 發布前完成一次引用與用途稽核，移除 237.82 MiB 可再生或已封存資料：

- 三個舊 Colab ZIP；
- 已判定 action collapse、禁止續訓的舊 PPO／probe 權重；
- 舊 BC／DAgger `.pt` checkpoints；
- 已被 clean easy dataset 或 Spike Dataset v1 取代的 correction／aggregate JSONL；
- 五個無引用且已有 v2 的重複 Gate／影片 audit JSON；
- 舊 PPO／pip 啟動 log 與 Python／pytest cache。

刻意保留：`teacher_dataset_v0.jsonl`、`spike_teacher_dataset_v1.jsonl`、Gate v11
十回合 transitions／sidecars／MP4、有限真機 calibration、vision templates、所有
結論 summary 與失敗報告。被刪除的歷史模型不得續訓；若需重現資料管線，應由版本化
script、seed 與 summary 重新生成，不可把舊 checkpoint 當成新實驗起點。

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
- `controls.action_duration_ms`：每次決策在擷取下一觀測前的最短控制間隔，預設
  80 ms；連續同方向不再於每個 decision tick 強制放鍵。
- `controls.max_continuous_hold_ms`：方向鍵 lease watchdog，預設 500 ms；控制
  迴圈若沒有及時更新 lease，背景 timer 會自動放開方向鍵。
- `controls.restart_duration_ms`：重新開始鍵的按住時間，實機測試預設為 200 ms。
- `controls.input_backend`：預設 `pyautogui`；只有遊戲不接受時才改為
  `pydirectinput`。
- `baseline.special_contact_escape_max_steps`：彈簧／尖刺事件觸發後，最多持續
  12 個 decision steps 的離台控制；離開來源邊界或確認落到非特殊平台會提早清除。
- `capture`：擷取模式、校正值、輸出尺寸與 FPS。
- `events.landing_contact_gap`：一般落地接觸距離，實機值為 6。
- `events.spring_contact_gap`：彈簧接觸距離；依實際 JSONL 校正為 12。
- `hud.floor_counter_*`：HUD 樓層數字 ROI。未校正時明確回報 unavailable；本機
  634x431 reference 已由既有影片校正為 `(266,16,112,32)`。真機 reach 使用
  HUD max，不再從 platform track ID 推算。
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
導覽。真機 adapter 對連續同方向 action 採 stateful hold，只有 RELEASE、換向、
非遊玩 phase、安全事件、例外、reset 或 close 才放鍵；每一步都會更新 500 ms
lease，若 capture／decision loop 卡住，watchdog 仍會自動放鍵。

Teacher 只使用螢幕可觀測事件處理特殊平台：`spring_bounce` 或來源 kind 為
`spring`／`spikes` 的 landing 會建立 persistent escape memory。來源 track ID
變動時，只有同 kind、相近水平幾何及相符接觸關係才延續 semantic contact；方向
先短期承諾，可見目的地穩定且顯著更好時最多重規劃一次。一般 escape 最多 12 步，
之後只允許 4 步 forced exit，再未脫離即 safety abort；普通平台 landing、確認離台
或 reset 會清除。離線 encounter audit 另跨短 ID gap 量測完整區段，但不影響控制。

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
playfield 左右界線直接使用 `vision.playfield_left`／`playfield_width` 的校正
結果並依實際觀測尺寸縮放。依 2,765 筆既有實機觀測校正後，角色進入
`wall_margin_pixels`（預設 32 像素）內，
且動作仍朝牆外（左牆按 LEFT、右牆按 RIGHT）時，每步扣
`wall_push_penalty`（預設 `0.08`）；朝場內轉身不扣。此值高於單次方向反轉
懲罰，避免模型為了不反轉而持續撞牆。
為了讓短期訓練能得到方向訊號，角色站穩、上升或下降時會追蹤下方最近的同一個
安全平台；上升時先排除設定距離內、最可能是剛起跳原點的平台，再選下一個
較低平台。水平落點距離縮短時依
`platform_alignment_reward_scale`（預設 `0.5`，按場地寬度正規化）給小幅
獎勵，遠離時等量扣分。只考慮設定清單中的普通、彈簧、輸送帶與翻轉平台，
尖刺不列入；目標 ID 改變或辨識中斷時不計分。這避免在彈簧起跳時反而鼓勵
角色回到原平台，同時讓平台上的左右動作能更早得到方向訊號。
這些項目都只是小幅 shaping，不取代實際掉血與死亡懲罰，也不加入容易鼓勵原地
拖時間的存活獎勵。

每次 Gym `step()` 的 `info["reward_components"]` 會分別記錄反向切換、尖刺
接觸步數、idle 步數、同平台停留、頂端危險區、撞牆方向及各項 reward，方便後續量化
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

### Teacher 控制策略離線證據 audit

要重跑目前的 action-conditioned dynamics、Spring encounter 與 Spike outcome
審查，可執行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_teacher_control_strategy.py --overwrite
```

工具只讀最近四組已保存的 transitions/controller sidecars 與 Gate JSON；不建立
輸入後端、不尋找遊戲視窗、不送按鍵。它以 episode-held-out 方式比較既有
action-conditioned coefficient form 與 carry-velocity baseline，並將短間隔、同類型的
special contacts 聚合為診斷 encounter。Encounter 不等同物理平台 identity，也不會
驅動 live controller。結果寫入：

- `artifacts/teacher_control_strategy_audit_v1.json`
- `reports/ACTION_CONDITIONED_DYNAMICS_REPORT.md`
- `reports/NORMAL_LANDING_GATE.md`
- `reports/SPRING_ESCAPE_GATE.md`
- `reports/SPIKE_ESCAPE_GATE.md`

目前 reverse-braking strict coverage 僅 LEFT 7／RIGHT 8，低於每側 30 的門檻；
因此報告會保持 `shadow_model_eligible=false`，也不代表可部署新模型。

曾執行的固定平台 `reverse-braking` 校正只用於短期物理 response 診斷。三個完成
run 雖產生 LEFT 23／RIGHT 21 strict rows，但因角色只在局部平台反覆左右、缺少
自然 target／landing／controller sidecar context，不能加入 Teacher deployment Gate；
後續固定平台收集已停止。完整判斷見
`reports/REVERSE_BRAKING_CALIBRATION_REVIEW.md`。

### 受限的回合重設

`environment.auto_restart_on_reset` 預設為 `false`，一般 Gymnasium 環境不會
擅自從對話框開始下一回合。受限 reset 的規則是：

- 穩定狀態已是 `PLAYING`：不送 Enter，只清除跨回合追蹤資料。
- 每個左右動作前重新確認仍是 `PLAYING`；若死亡選單已出現，立即釋放方向鍵，
  避免最後一次 LEFT／RIGHT 改變選單焦點。
- 連續 3 幀穩定為主遊戲 `DIALOG`，且右側單人「開始」按鈕具有校正後的焦點
  外框：最多短按一次設定中的 `restart_key`。
- 焦點明確位於雙人模式或 EXIT：先再次釋放控制器實際追蹤的方向鍵（不送新的
  key-down），再唯讀等待最多 `reset_focus_max_observation_frames`
  （預設 24 幀，在 8 Hz 約 3 秒）。只有單人開始焦點連續穩定後才允許 Enter。
  等待逾時時，僅在
  `controls.menu_focus_correction_key` 已經實機校正的情況下，才最多短按該鍵
  `reset_focus_correction_max_presses` 次（預設上限 3）並逐次驗證。每次 Tab 後
  使用獨立的 `reset_focus_correction_max_observation_frames`（預設 12 幀，8 Hz
  約 1.5 秒）；辨識到 START 立即停止巡覽。範例仍將修正鍵設為 `null`，其他
  電腦不可沿用本機 Tab 路徑。未校正修正鍵時逾時仍會停止。
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

目前這台實機已用不按 Enter 的工具確認：中央雙人焦點需要最多 3 次 `Tab`
才能回到右側單人開始，中間會經過兩個 `UNKNOWN` 焦點。因此被 Git 忽略的
本機 `config.yaml` 設為 `menu_focus_correction_key: "tab"` 與
`reset_focus_correction_max_presses: 3`。每次 Tab 後都必須重新確認仍是
`DIALOG`；辨識到單人開始立即停止巡覽，只有連續穩定後才允許 Enter。範例
設定仍是 `null`，但保留最多 3 次的硬上限；其他電腦不可直接沿用。
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
訓練結束時會列出實際送入環境的 RELEASE／LEFT／RIGHT 次數與最長連續同動作，
用來區分模型動作偏向、遊戲慣性及鍵盤釋放問題。
F8、失焦、額外姓名視窗、例外與 Ctrl+C 都會停止並釋放方向鍵。
`--focus-target` 只在倒數後嘗試一次 Windows 前景切換並立即驗證；若 Windows
拒絕切換便停止。省略此旗標時仍要求使用者手動保持遊戲前景。

模型與 checkpoint 存於 `models/ppo/時間戳/`，整個 `models/` 已由 Git 忽略。
目前只允許 CPU 訓練；短期目標是先驗證資料流與安全重設，不以這次短訓練的
遊玩成績判斷 PPO 效果。

實機早期續訓曾出現 deterministic 策略長期只選 LEFT：entropy 從接近三動作
最大值下降，單次更新 KL 也偏高；過度保守的 `0.0001 / 2 epochs` 實機結果則
維持接近均勻亂試，768 步後 deterministic 動作仍全部選 RIGHT。現在預設採用
中間值 `learning_rate=0.0002`、`n_epochs=4`，並把 `ent_coef` 由 `0.01`
提高為 `0.03`；`target_kl=0.01` 會在單次更新過大時提早停止該輪更新。
已經明顯單向塌縮的舊 checkpoint 不應
再續訓；需使用新設定從頭建立模型。固定種子改為 `2`，讓尚未學會前的第一個
rollout 三種動作較接近均衡，避免 `seed=42` 可重現的初期向右淨偏移。

若短訓練已安全完成，可在新的執行目錄續訓同一模型：

```powershell
.\.venv\Scripts\python.exe scripts\train_ppo.py `
  --resume-model models\ppo\既有時間戳\final_model.zip `
  --timesteps 1024 `
  --max-episodes 50 `
  --max-seconds 180 `
  --focus-target
```

`--timesteps` 表示本次額外收集的步數。續訓來源必須是本專案 `models/` 下的
`.zip`；工具拒絕外部路徑，並要求模型的 `n_steps`、`batch_size` 與目前設定
一致；`n_epochs`、`learning_rate`、`ent_coef` 與 `target_kl` 也必須一致，
避免把已經單向
塌縮的舊模型誤接到新設定續訓。來源模型不會被覆寫，續訓結果
存入新的時間戳目錄。

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
`evaluation_時間戳.json`，同樣不會提交到 Git。結果也會記錄
RELEASE／LEFT／RIGHT 次數、最長連續同動作步數與左右切換次數，用來辨識
deterministic 策略是否已塌縮成持續單向移動。
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

## 2026-07 訓練策略重整

目前不再把真實遊戲上的單步 PPO 當主要訓練路線。最新累積 PPO 的 deterministic
評估已塌縮為 128/128 次 `RELEASE_ALL`，不得直接續訓。長期方向、Go/No-Go 與
目前狀態請依序閱讀：

- `../CODEX_NS_SHAFT_PROJECT_REFACTOR_PROMPT.md`
- `docs/PROJECT_CONTEXT.md`
- `docs/CURRENT_STATUS.md`
- `docs/TRAINING_ROADMAP.md`
- `docs/EXPERIMENT_PROTOCOL.md`

已加入不接觸遊戲的 Pymunk simulator v0.1；control step、核心物理與平台
分布已由有限 telemetry 校正：

```powershell
.\.venv\Scripts\python.exe scripts\check_simulator.py --steps 10000
```

以及新版 transition JSONL validator：

```powershell
.\.venv\Scripts\python.exe scripts\validate_dataset.py path\to\data.jsonl
```

舊 `observations`、`reward_audit` 與 `baseline` JSONL 尚未符合
`ns-shaft-transition-v1`，在 migration／人工驗證前一律視為 quarantine，不可
直接作 BC 或 DQfD 示範。Colab 只允許 headless simulator，骨架位於
`notebooks/ns_shaft_colab.ipynb`。

新版資料與離線 benchmark 工具：

```powershell
.\.venv\Scripts\python.exe scripts\quarantine_legacy_data.py
.\.venv\Scripts\python.exe scripts\benchmark_simulator.py
.\.venv\Scripts\python.exe scripts\benchmark_vector_envs.py
.\.venv\Scripts\python.exe scripts\analyze_calibration.py
.\.venv\Scripts\python.exe scripts\evaluate_simulator_fidelity.py
```

有限實機物理校正使用 `scripts/calibrate_dynamics.py`；它要求大寫
`CALIBRATE`、3 秒倒數、唯一前景視窗，且最多一回合／20 秒；各 mode 的步數
上限會在確認前顯示。輸出一律標為 `invalid` calibration telemetry，不可當
expert demo。sample／一步／landing 與 seeded distribution gate 已達標，本階段
不再追加實機 calibration。exact 30-control-step pixel replay 的
partial-observability 結論見 `reports/PARTIAL_OBSERVABILITY_AUDIT.md`。

短 simulator learnability probe：

```powershell
.\.venv\Scripts\python.exe scripts\run_learnability_probe.py
.\.venv\Scripts\python.exe scripts\run_learnability_probe_p1.py
```

P0／P1 artifacts 採 immutable／拒絕覆寫設計；目前兩個 gate 均已通過，
依 `docs/DECISIONS.md` D-010 不再追加本機 timesteps。下一步是 Colab
runtime、throughput、checkpoint／resume 與 MP4 pipeline validation。

目前 Simulator v0.2 的 easy curriculum、Teacher Dataset、BC0 與單輪
DAgger0 smoke 已完成；balanced correction ablation 在 frozen／fresh seeds
均明顯優於 baseline。特殊平台採逐項 feature gate：health＋普通平台回血與
尖刺、輸送帶、彈簧、翻板 mechanism 已通過，全部預設關閉且尚未加入一般生成分布。詳細通過條件與
限制見 `docs/CURRENT_STATUS.md`、`reports/HEALTH_NORMAL_HEAL_GATE_REPORT.md`
、`reports/SPIKE_GATE_REPORT.md` 及 `reports/CONVEYOR_GATE_REPORT.md`；
彈簧與翻板結果見 `reports/SPRING_GATE_REPORT.md`、
`reports/FLIPPING_GATE_REPORT.md`；下一步先設計低比例單一特殊平台 generator，
尚未開始特殊平台訓練。

Spring curriculum v0後續已加入低比例generator，但只通過Engineering、Reachability與
spawn ratio，Oracle為`FAIL_STOP_ORACLE`，所以仍未批准特殊平台資料或訓練。可重現命令
與結果分別在`scripts/run_spring_curriculum_gate.py`、
`reports/SPRING_CURRICULUM_V0_REPORT.md`；正式artifact拒絕覆寫，不應直接重跑。

Failure trace之後的Oracle-only clearance已在全新development與untouched holdout通過，
Baseline亦PASS；最新結論以`reports/SPRING_ORACLE_ESCAPE_GATE_REPORT.md`為準。舊FAIL
artifact保留為根因證據，不覆寫。這仍不授權Dataset v2或真機長訓。

首個低比例 generator 已選 spike curriculum v0，Reachability／Oracle／Baseline
均通過，並以獨立 seeds 生成 3,541-row Teacher Dataset。結果見
`reports/SPIKE_CURRICULUM_V0_REPORT.md`；目前仍未重訓模型，下一步是 bounded
BC0 smoke，正式多-seed 重訓才需要 Colab。

本機 5-epoch spike BC0 interface smoke 已通過；正式三初始化 seed 實驗將使用
Colab。介面結果與限制見 `reports/SPIKE_BC0_INTERFACE_SMOKE_REPORT.md`。
