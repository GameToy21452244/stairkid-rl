# NS-SHAFT Agent Project Master Plan

更新日期：2026-08-03

目前執行關卡：P4.1 bounded S0／S1／S2／S3 ablation 準備

目前結論：P3.6 Gate v11 與 P4.0 State-aliasing Audit PASS；只解鎖公平短消融，
不得直接進入 rare-branch dataset 或擴大模型訓練

## 1. 文件目的與權威順序

本文件提供從目前狀態到最終實機自主遊玩的完整執行藍圖，讓每次工作階段都能
回答四個問題：目前在哪裡、下一步做什麼、何時可以前進、什麼情況必須停止。

規格衝突時依下列順序處理：

1. `../CODEX_SEQUENCE_CONTROL_STRATEGY_UPDATE.md`；
2. repository 的實際程式、最新 log、artifact 與測試結果；
3. `docs/CURRENT_STATUS.md`；
4. 本文件；
5. 其他歷史報告與舊 checkpoint。

本文件不回溯改寫歷史數據。新 artifact 若推翻舊結論，必須保留舊 provenance，
並更新 CURRENT_STATUS、Gate report、decision 與 risk register。

### 2026-08-02 Repair v9 addendum

v9 以 Gate v4 EP2／EP3 數值建立 regression：airborne landing horizon 由固定0.25秒
改成依垂直距離／速度、最多0.55秒；support departure 保留獨立離台規則；special
escape 優先更深可達落點，並以12 px edge／40 px/s outward momentum guard 提早反向。
Gate v5 新增 controller telemetry availability，但 v4 的 safety 與 lower-tail 門檻
完全保留。379 tests、compileall、no-input dry-run PASS；下一步唯一允許一次 supervised
bounded 3-episode Gate v5。

### 2026-08-02 Gate v4 live addendum

Fresh run HUD／影片 floors `9,2,2`；36 checks 中 35 PASS，唯一 blocking check 是
reach-3 只有1/3（要求2/3）。v8 的 dropout、departure timeout、wall 與 safety
修復均在這次樣本通過，但 EP2 late-braking overshoot 與 EP3 destination-unaware
special escape 暴露 landing lower-tail 缺陷。依 Gate 規則不進 P4.0；下一步只做
bounded Repair v9 與 recorded-scenario regression，再執行一次 fresh Gate v5。

### 2026-08-02 Repair v8 addendum

Gate v3 fresh run parser floors `2,4,10`，但 EP2 25-step dropout＋departure timeout、
EP3 16-step dropout，整體 FAIL。v8 把 timeout 後永久 source block 改成2-step
cooldown retry；建立每回合最多6組 lossless raw/mask/component forensic；Gate v4
收緊 recovered dropout<=8、要求 forensic manifest 與 cooldown<=2。下一步唯一允許
一次 supervised bounded 3-episode Gate v4。

### 2026-08-02 Repair v7 addendum

Gate v2 後兩次 fresh 3-episode runs floors `1,4,1` 與 `7,5,2` 均 FAIL。v7 修正
wall exit 後 cooldown RELEASE 造成 re-entry，以及 top-pressure observation dropout
期間 RELEASE 停頓；後者只允許最近可靠危險 context 的同方向 bridge 最多 2 steps，
一般 missing 仍 RELEASE。Gate v3 要求 bridge bounded、exhausted=0。369 tests 與
最近三片 counterfactual replay PASS，但新 action 尚未閉迴路實測，因此 P3.6 不放行；
唯一工作是一次 supervised bounded 3-episode Gate v3。

### 2026-08-01 Gate v2 addendum

Repair v6 新真機 3 回合已達 parser floors `5,3,10`、3/3 reach-3、2/3 reach-5、
0 safety event。舊 Gate v1 把同平台 settle、special escape reversal 與全程 RELEASE
且恢復的 observation dropout 誤列為 blocking failure。Gate v2 改量 actionable
support target、active wall-safety context 與 bounded release-only recovery；同一
controller sidecar 重分類全項 PASS。這不是獨立新 runner 驗證，因此目前仍留在
P3.6；這是當時 v2 的歷史判定，已由上方 2026-08-02 v7 addendum 取代。

## 2. 最終目標

建立一個不修改遊戲、不讀取遊戲記憶體，只依靠真實畫面與一般鍵盤輸入，能在
原版 Windows NS-SHAFT 中穩定、安全、自主遊玩的 agent。

成功不能只用單次最高樓層定義。正式排序為：

1. 安全事件；
2. health death；
3. bottom death；
4. Q25／CVaR25；
5. reach floor 3／5／10；
6. median；
7. mean；
8. 單次最高樓層。

最終系統必須保留：唯一前景視窗、F8 emergency stop、失焦停止、例外與程序結束
清鍵、受限回合／步數／時間，以及可稽核的影片、transition 與 controller sidecar。

## 3. 系統分層

```text
原版遊戲畫面
  -> 畫面擷取與視窗安全
  -> 玩家／平台／HUD 偵測與時序追蹤
  -> 可部署 observation + memory
  -> Teacher 或 Student sequence policy
  -> bounded held-action controller
  -> 一般 LEFT／RIGHT／RELEASE 鍵盤輸入

模擬器
  -> 機制與物理校正
  -> Teacher／Oracle gate
  -> sequence dataset／擾動恢復資料
  -> BC／DAgger／bounded RL 候選模型
  -> 原版遊戲 micro gate 驗證
```

模擬器不是最終驗證，也不取代原版遊戲。它負責大量、便宜、可重現的資料與
消融；原版遊戲負責 transfer、視覺、延遲和安全性的最後裁決。

## 4. 不變工程原則

- 不注入、反編譯、掛鉤或讀取遊戲記憶體。
- Teacher 只能使用部署端可取得的畫面資訊與可重建短期記憶。
- Oracle-full 只用於模擬器上界，不得成為真機 Teacher 或資料標籤來源。
- Gate 未通過就停止後續階段；不得用 epochs、timesteps 或最高分掩蓋失敗。
- train／validation／checkpoint-selection／final seeds 必須隔離。
- 任何 dataset 都要保留 schema、environment version、seed、episode 與來源。
- 真機只做有硬上限的 micro／bounded evaluation，不做長時間探索式訓練。
- 舊 PPO collapse checkpoint 與 invalid legacy JSONL 只供稽核，不續訓。
- 每次控制修復先以既有影片重播與固定情境測試驗證，再要求使用者重跑遊戲。

## 5. 已完成能力

### 5.1 Repository 與資料基礎

- 永久上下文、roadmap、決策、風險、實驗協議與資料 schema 已建立。
- `ns-shaft-transition-v1`、JSONL writer、validator 與 provenance 已建立。
- 舊資料已 audit／quarantine；未把 invalid 資料誤升格為訓練資料。

### 5.2 Gymnasium／Pymunk 模擬器

- normal、health/heal、spikes、conveyor、spring、flipping 機制骨架與 gate 已建立。
- 60 Hz physics、8／10／12 Hz policy、固定 seed、快速 reset、持續生成與 renderer
  已建立。
- Oracle-full 與 Teacher-observable 已分離。
- Reachability、Oracle、baseline、spike curriculum 與多項 mechanism gate 已完成。

### 5.3 模型與資料實驗

- hard-label BC0、rollout-selected checkpoint 與 balanced DAgger0 實驗已完成。
- Spike BC0 的正式三初始化曾通過，但 Spike DAgger0 因 tail risk、bottom death 與
  health death 退化而停止。
- 已確認單步 MLP 的主要限制是 covariate shift、Teacher memory observability 與
  sequence/state aliasing，而不是單純 epoch 不足。

### 5.4 真機安全鏈與 Teacher micro pipeline

- 真機錄影、transition、controller sidecar、HUD floor、physical latency、終止分類、
  dry-run、F8／失焦／例外清鍵均已建立。
- 普通平台操作曾人工到第 8 層，動作流暢度曾顯著優於早期 PPO。
- 特殊平台、角色 dropout、貼牆狀態與落點控制仍未達可接受門檻。

## 6. 目前 P3.6 的實際狀態

2026-08-01 最新四組真機測試共 18 回合、721 control steps：

- floor max：`3,1,1,2,3,3,1,1,1,1,5,2,2,2,2,4,3,4`；
- mean 2.28、median 2；
- 13/18 bottom death（72.2%）；
- 6/18 只到第一層即死亡；
- 14/18 episode 的 observation validity 失敗；
- 70/721 steps 為 `player_not_detected`；
- `escape_launch_platform` 262/721 steps（36.3%）；
- outward wall push 為 0，但最新 EP4 有 12 次快速左右反轉；
- 四份 Teacher Real-Game Gate 均 FAIL。

因此 wall-safety repair v4 的「outward count=0」只是必要條件，不是充分條件。
它阻止持續向牆外壓，卻沒有取消衝突的 persistent launch state，導致 guard 與舊方向
互相搶控制權。P3.6 維持 FAIL／STOP。

## 7. 目前立即工作包：P3.6 Repair v5

Repair v5 依資訊與安全價值排序，不先修改模型。

### 7.1 V5-A：Player Vision Continuity

目標：角色肉眼可見、受傷閃爍或短暫色彩變化時，不能被當成長時間不存在。

工作：

- 以最新 18 支 MP4 建立 frame-level dropout audit；
- 擴充受傷／閃爍 sprite 的可驗證偵測分支；
- tracker 只允許短期、bounded extrapolation，不在死亡／dialog 後虛構角色；
- sidecar 記錄 raw detection、tracked/extrapolated、missing streak 與 confidence；
- 玩家重新出現時平滑重建速度，避免單幀超大 velocity。

離線 Gate：

- 已知肉眼可見片段的 false missing 顯著下降；
- active-play missing streak 不超過 2 control steps；
- terminal／dialog 不保留 ghost player；
- 不增加明顯 false positive；
- 所有既有 object detection／tracking／terminal tests 通過。

### 7.2 V5-B：Latched Wall Evacuation

目標：貼牆時不是只改寫單一步，而是完成一次不可被其他 controller 打斷的向內撤離。

工作：

- guard 觸發時取消／改寫 launch、special、aligned-dwell 的 outward direction；
- 設定 enter／exit 不同邊界的 hysteresis；
- 撤離狀態保持向內，直到位置與速度都回到安全條件；
- 解除後加入短 cooldown，禁止立刻重建同一 outward plan；
- 方向改變仍保留一幀 brake；reset／player missing／terminal 必須清 state。

離線 Gate：

- outward count=0；
- wall re-entry cycle=0；
- 同一 wall episode 不出現 guard／舊 launch 反覆搶權；
- 最新 EP4 的兩段 oscillation replay 必須消失；
- 左右牆、spring、spikes、launch、recovery 固定情境全部通過。

### 7.3 V5-C：Risk-Aware Landing Control

目標：從「盡快離開上一平台」改成「先確認可存活落點，再做有限承諾與煞車」。

工作：

- 以 player x/vx、候選平台 safe interior、預估接觸時間建立 projected landing x；
- 只有連續觀測確認的可行落點才允許 launch commit；
- commit 期間持續重算落點，過衝前 RELEASE／brake，而不是固定推到離開 source bounds；
- 沒有可信安全落點時，優先保留／回到 source platform interior；
- 對第一層與畫面底部加入 early-bottom risk；
- normal/heal 優先級與 spike emergency 規則保持既有安全語意。

離線／固定情境 Gate：

- 不再重現第一層「4～6 步單向推到錯過落點」；
- projected landing 落在 target safe interior；
- 過衝時能在死亡前 brake；
- 不以增加 RELEASE collapse 換取表面安全；
- special/recovery regression 不退化。

### 7.4 V5-D：Support Contact 與 Edge Hesitation

目標：區分「合理等待落點」、「平台接觸」、「平台邊緣假對齊」與「真的卡住」。

工作：

- 建立 deployable support-platform latch，不依賴單幀 target track ID；
- 以位置、速度、接觸 gap 與平台幾何計算 dwell；
- 記錄 support edge distance、stationary streak、aligned-release streak；
- 邊緣假對齊時只做一次受控內移，不反覆左右切換；
- 將 player missing 與真實 stationary 分開統計。

Gate：

- active aligned RELEASE streak 有明確原因且不超過固定上限；
- edge hesitation 不形成左右 oscillation；
- 沒有玩家時不宣稱 support contact；
- 既有影片中未被證實的「卡死」維持 uncertain，不以猜測標註。

### 7.5 V5-E：Gate 與 Telemetry 補強

新增或明確化：

- `player_detection_available`、`player_missing_step_count`、
  `max_player_missing_streak`；
- `wall_evacuation_count`、`wall_reentry_cycle_count`；
- `rapid_direction_reversal_count`、最大 reversal burst；
- `aligned_release_streak`、`support_edge_distance`；
- `early_bottom_death` 與 `floor_1_bottom_death_count`；
- launch commit／abort／brake 與 projected landing margin。

Repair v5 離線完成門檻：

- 最新 18 支 MP4 replay 全部可解析；
- 已知 wall oscillation 分支為 0 re-entry cycle；
- active-play vision missing streak 達標；
- 早期過衝 fixed scenarios 全通過；
- targeted、完整 pytest、compileall、dry-run、JSON 與 diff check 全 PASS。

## 8. P3.6 新真機 Gate

目前 repair v6／Gate v2 完成後，使用者手動執行一次全新 3 回合確認：

- safety event=0；
- observation、target、controller memory、telemetry 完整；
- recoverable observation dropout <=20 steps、unrecovered=0、dropout 期間
  directional action=0；
- outward push=0、wall re-entry cycle=0；
- wall guard／evacuation active 時 reversal burst<=2；special／launch escape 與
  全域換向只作 telemetry；
- distinct target 已存在時 actionable support aligned RELEASE=0；同平台 settle
  只作 telemetry；
- floor-1 bottom death=0；
- 至少 2/3 reach floor 3；
- 至少 1/3 reach floor 5；
- 無 action collapse。

任一條失敗即留在 P3.6。三回合全項 PASS 才進 P4.0 State-aliasing Audit；不以
最高樓層覆蓋 lower-tail 或安全失敗，也不連續重跑直到碰巧通過。

## 9. P4.0：State-Aliasing Audit

進入條件：P3.6 真機 Gate 通過。

狀態（2026-08-03）：**PASS**。Gate v11 的10回合／753 rows以跨episode 5-NN比較；
observation-only conflict 56.20%，`memory[t-1]` causal full memory為45.39%，相對改善
19.23%，entropy改善0.1873 bits，accuracy改善13.01 points，episode bootstrap CI
`[0.0979,0.1411]`。同一步 sidecar 是 post-decision label leakage，只作 ceiling；raw
track IDs 全部排除。causal action-history單組42.76%優於full memory，P4.1優先比較
compact S1。完整證據見 `reports/STATE_ALIASING_AUDIT.md`。

分析 observation 近鄰 action conflict、conditional entropy、phase／target 可預測性，
並比較加入 previous actions、held duration、target lock age、phase、time since landing、
braking、recovery、support state 後的衝突下降量。

輸出：

- `reports/STATE_ALIASING_AUDIT.md`；
- `artifacts/state_aliasing_summary.csv`；
- `artifacts/teacher_action_conflicts.csv`。

若可部署 memory 能明顯降低衝突，前進 P4.1；否則回到 observation、label timing 或
Teacher consistency，不能直接訓練 sequence model。

## 10. P4.1：S0／S1／S2／S3 Sequence Ablation

- S0：現有 268 維 stack + MLP 對照；
- S1：explicit deployable state + MLP；
- S2：full observation + GRU；
- S3：compact deployable observation + GRU；
- optional S4：action + phase／target／brake auxiliary loss。

使用相同 episode splits、frozen seeds、更新預算與多初始化。模型只能由 closed-loop
安全與 tail-risk 指標選擇，不能只看 offline accuracy／loss。

Gate：至少一個 sequence／memory 方案在 health、bottom、Q25、CVaR25、reach-10、
oscillation 上穩定優於 S0，且多 seeds 方向一致。

## 11. P4.2：Rare-Branch Sequence Dataset

資料單位改成完整 episode 或連續 chunk，重點覆蓋：late brake、wrong launch、
missed landing recovery、wall+velocity、platform edge、low-health spike、conveyor、
spring、flip 與 vision dropout recovery。

在模擬器中加入 bounded perturbation，再由 Teacher 接管恢復。按 episode／seed 分割，
保存 phase、target、support、confidence、perturbation、events 與成功／失敗。

Gate：主要 branch 都有最低 episode/sequence 覆蓋，rare branch 不被 normal rows
淹沒，同一平台序列不跨 split，validator 0 error。

## 12. P4.3：Conservative Sequence DAgger

初始只允許 80% 原 Teacher／安全資料 + 20% learner corrections。Correction 必須是
高 confidence sequence，按 phase／branch 分層，並保留固定 safety replay set。

只有 health 不增加、bottom 不惡化、Q25/CVaR 改善、reach-10 不下降、mean/median
不明顯退化且多 seeds 一致才接受。失敗即停止，不自動進第二輪。

## 13. P4.4：Compact NEAT Fair Comparison

NEAT 只作固定預算比較：feed-forward compact、recurrent compact 與 compact GRU
使用相同 seeds、horizon、environment steps、控制頻率與 fitness。若 Q25、CVaR 和
死亡率無明顯優勢，不擴大 population 或 generations。

## 14. P5～P8：候選策略、Bounded RL 與最終轉移

### P5：Closed-Loop Candidate Selection

從 explicit FSM、GRU sequence BC／DAgger、compact NEAT 中選出最穩定候選。保留
baseline/Teacher safety fallback，建立模型版本、hidden-state lifecycle 與部署 smoke。

### P6：Bounded RL Fine-Tuning

只有 sequence Student 已穩定超過 S0、Teacher Real Gate 通過、tail risk 可重現時，
才比較 BC/DAgger、BC 初始化 PPO、recurrent replay RL 或 residual policy。更新步數、
reward version、early stop 與 replay provenance 都要固定；不在真機長時間探索。

### P7：Special-Platform Curriculum 與 Domain Randomization

依 normal -> spikes/recovery -> conveyor -> spring -> flipping 分階段加入。每項先通過
mechanism、reachability、Oracle、Teacher、dataset coverage、Student regression，最後
才混合。Randomize 物理、平台比例、延遲、觀測噪音與短 dropout，但範圍必須有真機
校正依據。

### P8：擴大真機評估

由 3 -> 5 -> 20 個 bounded episodes 漸進。每次升級都要求 safety=0、tail risk 不退化、
失敗 taxonomy 可解釋、影片與 sidecar 完整。最終才進人工監看下的長回合展示。

## 15. 本機、Colab 與真實遊戲分工

- 本機：程式修改、測試、影片 replay、資料 audit、短 smoke、真機 bounded Gate。
- Colab：多 seed 模型訓練、sequence ablation、較大量模擬 evaluation；不控制真實遊戲。
- 原版遊戲：只做 Teacher/Student transfer 與最終 bounded evaluation。

目前 Repair v5 是規則、視覺與 replay 工作，本機已足夠，不需要 Colab；只有進入
P4.1 之後才需要 GPU sequence model 實驗。

## 16. 全域停止條件

任何階段遇到以下情況立即停止後續擴張：

- 安全事件、失焦仍輸入、按鍵未釋放；
- health death 由 0 增加；
- bottom death 或 Q25/CVaR 明顯退化；
- observation validity、vision continuity 或 schema 失敗；
- action collapse、牆邊震盪或長時間無原因 RELEASE；
- train/eval seed 洩漏或 artifact provenance 不完整；
- 連續多輪只提升 mean／最高樓層，tail risk 無改善；
- simulator 改善無法在小型真機 Gate 重現。

## 17. 每階段固定交付

每個 Gate 至少交付：

- 可重現 command 與固定設定；
- machine-readable artifact；
- 影片／transition／sidecar（若適用）；
- 指標、失敗 taxonomy、PASS／FAIL；
- targeted 與 full regression；
- CURRENT_STATUS、DECISIONS、RISK_REGISTER、implementation report 更新；
- 下一步只保留通過 Gate 後真正允許的工作。

## 18. 目前下一步

1. Gate v4 floors `9,2,2` 的唯一 failure 是 reach-3 只有1/3；EP2 late brake 與
   EP3 destination-unaware special escape 已轉成 v9 regression。
2. Repair v9 完成 adaptive airborne intercept、departure phase isolation、visible
   destination／edge momentum special escape 與 Gate v5 telemetry；離線驗證全過。
3. 下一步唯一允許的是使用者監督的一次 bounded 3-episode Gate v5。全項 PASS
   才能進 P4.0；FAIL 即留在 P3.6 分析新 sidecar／影片。完整證據見
   `reports/P36_REPAIR_V9_REPORT.md`。

本階段禁止開始 P4.0、S0～S3 訓練、rare-branch dataset、DAgger、PPO、DQN、NEAT
或長時間真機操作。
