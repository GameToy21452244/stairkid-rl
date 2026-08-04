# Implementation Progress Report

日期：2026-07-30

## 2026-08-03 Simulator／Real Alignment Audit

- 在新Simulator執行前凍結protocol：主要／次要真機run、8000～8029診斷seeds、時間、
  action response、platform distribution、support alias與反向操作定義。
- Test-first新增`simulator_real_alignment.py`、bounded collector、audit CLI與6個tests；
  原版遊戲未啟動、未送鍵、未訓練，fresh6000～6099未使用。
- 主要真機／Simulator cadence=125／100 ms且左右delta-vx方向一致，相關checks PASS。
- 真機重要kinds有五類，Simulator一般分布只有normal/spikes；spring/conveyor/flipping
  缺失。真機rising-support=40.58%、max11，Simulator=16.92%、max2。
- episode3 step47確認source12有8/8 rising-support persistence並timeout，step50 restart；
  主要run同departure方向反轉5次，Simulator 0。狀態
  `FAIL_STOP_SIMULATOR_REAL_ALIGNMENT`，Dataset v2與所有Student／RL訓練維持BLOCKED。
- 權威產物：`simulator_real_alignment_audit_v3.json`、凍結protocol及完整audit報告。
- 新增6 tests、相關14 tests、完整468 tests PASS（63.52s）；compileall、JSON/source
  fingerprint與diff check PASS。

## 2026-08-03 Real Alignment Packet preflight

- 稽核最新真機run後確認舊transition只有268維encoded observation，controller sidecar是
  post-decision；缺少同一步structured platforms與直接pre-decision memory，不能從MP4
  猜補target safe interval。
- Test-first新增`real-alignment-packet-v1` writer、validator、causal chain與coverage Gate；
  runner每步多寫structured obs/next、pre/post memory、target geometry、timing及frame index。
- Packet固定diagnostic-only/training-ineligible；沒有修改Teacher action、控制率或安全鏈。
- Dry-run不尋找視窗、不載入input backend、不送按鍵，狀態PENDING。
- Alignment/real/transition targeted 50 tests PASS；完整462 tests PASS（71.03s）；
  dry-run JSON、compileall與diff check PASS。
- 工程狀態PASS，下一步限使用者監督的3-episode真機run；實際alignment Gate尚未評估。


## 2026-08-03 Simulator Observation-Schema Probe

- 執行前凍結7000～7199 development、7200～7299 validation、7300～7399 one-time test；
  6000～6099 fresh reliability保持未使用。
- 新增decision前target signed offset輸出、四組deployable feature builder、5-NN held-out
  audit、CLI與3個tests；probe不修改controller action，也不啟動原版遊戲或訓練。
- 400回合base/counterfactual reach=`76.25%/69.25%`、bottom=`23.75%/30.75%`、
  Q25=`10/8`、CVaR25=`5.14/4.04`，確認launch-handoff在較大樣本仍退化。
- 395次首次分歧只有1 improved、29 regressed、365 unchanged；另5個無分歧種子重播
  floors完全相同。Development無improved class，所有separability metrics unavailable。
- 狀態`INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE`；拒絕新Teacher候選、fresh100、正式v2
  與Student。下一步限使用者監督的bounded真機alignment packet。
- 已公開記錄protocol deviation：phase_basic協定列vx/vy，執行版basic只含vy；此偏差不
  影響trajectory evidence FAIL，但禁止解讀basic-vs-combined可分性，也不重跑test。
- 產物：`simulator_teacher_observation_schema_probe_v1.json`、凍結protocol與
  `SIMULATOR_OBSERVATION_SCHEMA_PROBE_REPORT.md`。Schema／Teacher相關14 tests PASS
  （6.04s）；完整457 tests PASS（162.51s）；artifact/protocol/source fingerprint、
  compileall與diff check PASS。

## 2026-08-03 Simulator Teacher Phase Observability Audit

- 新增無控制修改的decision observer、phase signature/audit模組、CLI與測試；decision前
  記錄deployable events、motion、screen-coordinate vy、gap、support、edge與landing
  recency，privileged phase/last-landed只作診斷label。
- Delayed2 base trace SHA、performance與60/60首次action分歧step完整重現前一artifact。
- 首次介入結果為2 improved、6 regressed、52 unchanged；證據量三個固定門檻皆FAIL。
- 8個deployable signatures中一個同時含1 improved、2 regressed與7 unchanged；
  privileged post-bounce及last-landed也無法分離，故停止phase model/controller修改。
- 936個support rows中876為rising，確認support heuristic表示bounce附近重疊，不是可靠
  stable-support phase。Fresh seeds、正式v2、Student訓練與原版遊戲均未使用。
- 產物：`simulator_teacher_phase_observability_audit_v1.json`與
  `SIMULATOR_TEACHER_PHASE_OBSERVABILITY_AUDIT.md`。下一步限bounded schema probe。
- Phase／observer targeted 6、完整454 tests PASS（178.57s）；compileall、artifact
  JSON/source fingerprint與diff check PASS。

## 2026-08-03 Simulator Teacher Launch-Handoff Gate

- Test-first新增Simulator-only support-aware handoff；stable或無reachable future target均
  不觸發，legacy與真機default保持關閉。只建立一個v4 candidate，沒有parameter sweep。
- Delayed2 base的trace SHA、performance與60個floors完整重現前一Gate。
- Candidate reach/bottom/Q25/CVaR/reversal為`75%/25%/9.5/4.2/10.36`，全面差於base
  `81.67%/18.33%/10/6.27/9.06`；同種子Gate FAIL，fresh未執行。
- Launch rows增至991但departure降為0、wall guard升至314，證實廣義handoff過度觸發；
  下一步改做phase observability audit，不再追加controller heuristic。
- 產物：`simulator_teacher_launch_handoff_gate_v1.json`與
  `SIMULATOR_TEACHER_LAUNCH_HANDOFF_GATE_REPORT.md`。
- Related 90與完整451 tests PASS（174.77s）；compileall、artifact JSON、source
  fingerprint與diff check PASS。

## 2026-08-03 Simulator Teacher Profile Gate

- Test-first為SafePlatformPolicy新增可選normal-support departure delay/disable；預設仍
  enabled+delay0，故真機runner未改行為。Simulator Teacher明確分成三個獨立v3 profile。
- 新增bounded runner、同種子v2 readiness Gate、config/source fingerprints、risk-first
  selection與條件式fresh100；scientific FAIL正常保存artifact且return 0。
- 2000～2059：current/delayed2/disabled reach=`75/81.67/76.67%`，bottom=
  `25/18.33/23.33%`；三者health death=0，但reach、bottom與action TV全FAIL。
- selected profile為null，6000～6099完全未使用；沒有正式v2、Student訓練或真機操作。
- 延後使首次分歧由median step1移至step6；53/60由舊launch escape變新aligned，定位
  下一個最小實驗為Simulator-only support-aware launch handoff，不再掃delay。
- 產物：`simulator_teacher_profile_gate_v1.json`與
  `SIMULATOR_TEACHER_PROFILE_GATE_REPORT.md`。
- Related 88與最終完整449 tests PASS（197.56s）；duration診斷中既有100k headless smoke
  163.06s、新6-seed integration 0.62s。compileall、artifact JSON與diff check PASS。

## 2026-08-03 P4.1 Dataset v2 Gap Audit

- 新增唯讀audit module／CLI，對凍結Dataset v1與current Teacher diagnostic做同種子
  outcome、branch、action、release-bridged reversal、split與首次trajectory分歧比較。
- 同2000～2059 seeds：v1為56 target／4 bottom；current為45 target／15 bottom。
  Reach由93.33%降至75%，bottom由6.67%升至25%，health death皆0。
- 60/60在step 1分歧；57次首次reason由aligned變成depart support。RELEASE share
  37.63%→48.42%、reversal 10.14→11.06/100 steps、action TV=0.10787。
- 舊Dataset Gate對兩份資料都PASS，確認false positive；新v2 Gate加入policy/source/config
  provenance、同種子reliability、critical branch coverage與fresh100 reliability。
- Gate結果`FAIL_STOP_BEFORE_V2_GENERATION`、`v2_ready=false`。沒有正式生成v2、
  沒有訓練、沒有使用final seeds、沒有啟動原版遊戲。
- 新增`p41_dataset_gap.py`、`audit_p41_dataset_v2_gap.py`、3個targeted tests、
  machine-readable artifact與`P41_DATASET_V2_GAP_AUDIT.md`。
- 下一步限分離Simulator Teacher並做current/delayed/disabled同種子bounded micro-ablation；
  未過Gate不跑fresh100或Student階段。
- Dataset audit targeted 3、P4.1 related 28、完整441 tests PASS；compileall、artifact
  JSON parse與diff check PASS。26.3 MB diagnostic-only JSONL及其暫存summary在確認未被
  Git追蹤後移除；正式artifact保留完整統計、hash與provenance。

## 2026-08-03 P4.1 Colab bounded selection

- 驗證使用者提供的`20260803T085551Z_p41_ablation.zip`；archive SHA-256為
  `b1fd2291...`，summary、manifest及12個selected checkpoints完整，Dataset仍為
  3,529 rows／hash `fa3e111a...`。
- 正式結果`FAIL_STOP_SELECTION`，沒有selected architecture，4100～4139 final seeds
  未使用。S0/S1/S2/S3三初始化平均bottom death為13.3%／18.3%／50.0%／98.3%。
- S1 mean與Q25改善至62.18／44.25，但CVaR25 17.00、reach-10 85.0%、bottom 18.3%
  均不如S0的18.27／88.3%／13.3%，故維持FAIL；S2/S3淘汰。
- Post-result audit發現selection priority與全域risk-first排序不一致，且現有相鄰方向
  switch metric使0.10 improvement threshold不可達。這兩點不會救回S1的CVaR／reach／
  bottom Gate，故不改判、不碰final seeds。
- P4.2及後續維持BLOCKED。下一步限修telemetry／排序並用既有selection checkpoints
  做不訓練reanalysis，再決定是否建立明確升版且另過reliability／coverage Gate的
  Teacher Dataset v2。

## 2026-08-03 P4.1 Selection-only checkpoint reanalysis

- Test-first新增release-bridged direction reversal：RELEASE不再清除最後方向；舊direct
  switch欄位保留。P4.1 selection改為collapse→health→bottom→Q25→CVaR→reach→
  reversal→median→mean，oscillation由固定改善0.10改為跨初始化與平均皆不退化。
- 新增`p41_reanalysis.py`與`reanalyze_p41_checkpoints.py`；只接受未碰final的
  `FAIL_STOP_SELECTION`來源，驗證ZIP hash、dataset hash、checkpoint metadata與seed隔離。
- S0/S1六個checkpoint在原20個selection seeds重播，舊metrics與逐回合floors完全重現；
  training_started=false、final_seeds_used=false。
- 新reversal平均S0 10.05、S1 10.73/100 steps；S1三初始化delta皆負，修正Gate為
  `FAIL_STOP_SELECTION_CONFIRMED`。下一步限Dataset v2 Gap Audit，不生成資料。
- Targeted 25 tests與完整438 tests PASS；compileall、artifact JSON與diff check PASS。

## 2026-08-03 P4.1 本機 preflight／interface smoke

- 前置狀態：P3.6 Gate v11與P4.0 State-aliasing均PASS；本輪只執行被解鎖的
  P4.1 bounded本機工程，不啟動長訓或真實遊戲。
- 新增`p41-causal-sequence-v1`唯讀資料view：S1/S3的9維state只由past actions重建；
  S3 compact observation 22維；同一步sidecar、未來資訊、privileged state與raw IDs
  全部拒絕。
- 實作S0/S1 MLP、S2/S3 GRU-128、24-step chunks、burn-in 8、padding/loss mask、
  hidden/causal reset、hard CE bounded trainer、closed-loop policy與版本化checkpoint。
- 凍結manifest：3,529-row Dataset v1 hash `fa3e111a...`、300 updates、candidate
  100/200/300、init seeds 0/1/2、selection 4000～4019、final 4100～4139。
- Data provenance audit發現current source重建同名資料為3,571 rows/hash `04417d...`；
  已記錄`p41_dataset_regeneration_drift.json`並決定Colab不得重建。新Teacher dataset
  必須升版另過Gate。
- 本機各4 updates／seeds 3900、3901 interface smoke：12/12工程checks PASS；四組
  bottom rate皆100%，故明確不作科學判定。S2兩回合mean deepest 9.5只列診斷。
- Notebook已新增預設停用P4.1 cell；runner在scientific FAIL時仍保存JSON/ZIP並正常
  return，避免`CalledProcessError`掩蓋結果。Bundle工具只允許clean commit及exact JSONL，
  排除config/EXE/media/weights；dirty dev bundle合成檢查373 entries PASS後已刪除。
- 新增／修改主要檔案：`p41_sequence.py`、`p41_ablation.py`、`p41_bundle.py`、
  `run_p41_ablation.py`、`package_p41_colab.py`、notebook、P4.1 tests、manifest、smoke、
  drift artifact、`SEQUENCE_MODEL_ABLATION.md`及永久docs。
- Gate：Local engineering **PASS**；P4.1 scientific **PENDING**；P4.2及後續仍BLOCKED。
- Targeted 21 tests PASS；完整**432 tests passed in 63.34s**。compileall、三個P4.1
  JSON、notebook JSON／末格syntax、absolute-path manifest preflight及diff check PASS。
  正式clean bundle仍須等本輪commit後建立；沒有把dirty dev bundle交付使用者。
- Git：目前沿用commit `0da7550`且有本輪dirty changes；尚未收到本輪commit/push指示。

## 2026-07-31 Sequence-control 工作包（進行中）

- 已完整恢復三版 Prompt、AGENTS、README、永久 docs、近期 Teacher/BC/DAgger/
  simulator/Colab reports，並檢查 dirty worktree；未還原既有修改。
- 直接核對最新 JSON/CSV artifacts，Prompt 所列 94%、30、3,529、45.5、7.75、
  60%、14 與 disagreement／DAgger 數值一致。
- 已把最高優先主線改為 Teacher Real Micro Gate → state-aliasing → S0–S3 →
  rare-branch sequences；前一 Gate 未通過立即停止。
- 目前正建立 dry-run 預檢、controller-memory sidecar、canonical transition、
  MP4 與 bounded 3～5 episode command。尚未實際操作遊戲，因此 Teacher Real
  Gate 仍為 PENDING，不能宣稱轉移成功，也不能執行後續 sequence Gate。
- 工具與相關測試已完成；targeted regression 為 52 passed。預設 dry-run 已產生
  `artifacts/teacher_real_game_micro_gate_dry_run.json`，確認 0 真實輸入。
- 依第一 Gate 未通過即停止的規則，State-aliasing、S0–S3、rare-branch dataset、
  conservative DAgger 與 NEAT 均未執行；詳見 `TEACHER_REAL_GAME_MICRO_GATE.md`。
- 初次最終回歸：307 passed in 100.58s；真機結果 audit 後最新重跑為
  307 passed in 70.21s；compileall、dry-run JSON 與 diff check PASS。
  未啟動遊戲、未送真實輸入、未執行任何新訓練。
- Git：分支 `agent/simulator-learnability-colab`，HEAD `b73ff2b`；保留原有 dirty
  worktree，未 commit（本輪未收到 commit/push 指示）。

## 2026-08-01 Teacher Real Micro 實測

- 使用者完成 3 回合／146 steps；安全事件 0，三組 transition/controller/MP4
  完整，動作 61 RELEASE／43 LEFT／42 RIGHT，沒有 PPO 式 collapse。
- Gate FAIL：三回合全部 top death；人工影片 HUD 最高 3／2／2，沒有 reach 5。
- 自動 floor events 0／2／2 與 HUD 不一致，證明 real reach telemetry 不可靠。
- Spring 回合有 13 步 aligned RELEASE 與兩次 spring bounce；spike 回合有 16 步
  recovery-aligned RELEASE。問題是特殊 contact/controller memory，而非動作網路。
- Sidecar 0～1 ms latency 只量 dispatch；physical response latency 尚未量測。
- 使用者指出移動呈逐次點按；code audit 確認 adapter 每步 hold 80 ms 後強制放鍵，
  連續同向 action 仍形成約 8 Hz pulses。已列為 P3.6 fidelity failure，修復需採
  bounded stateful hold，而非直接增加 decision frequency。
- 已完成 bounded stateful hold：同向跨 observation 保持、500 ms lease watchdog，
  RELEASE／terminal／例外／reset／close 清鍵；targeted 44 passed、完整
  311 passed in 69.03s。尚未送出真實輸入，故只算 mock Gate PASS。
- 已完成 persistent spring/spike contact escape：保存 deployable source/bounds/
  direction/age，kind 變化時沿用 `(track_id, kind)` 最後可見邊界，並以離台、
  safe landing、12 steps 作終止。6 fixed scenarios PASS；最新 targeted 67 passed、
  完整 317 passed in 64.95s。仍未送出真實輸入，整體 P3.6 保持 FAIL／STOP。
- 已以校正 HUD counter 取代 track-ID floor 推估；舊 3 支 MP4 replay 自動 max
  3/2/2、changes 2/1/1、149 frames 全 available，與人工一致。新增 artifact
  `p36_floor_counter_video_audit.json`。
- 已新增 physical motion-onset latency tracker 與 Gate：dispatch/physical 分欄，
  排除 command 前已存在的同向慣性，LEFT/RIGHT 都須有 sample。最新 targeted
  48 passed、完整 324 passed in 65.15s，
  dry-run PASS。Repair package 為 READY FOR RETEST，但舊 P3.6 結論仍是 FAIL。
- 已更新 Gate 報告、決策、風險與 compact audit artifact；依規格停在 P3.6，
  未進 State-aliasing、S0–S3、資料生成或任何訓練。

### 第二次 retest 與 repair v2

- 新 run `teacher_real_micro_20260801_031907_767286` 留下 71 transitions、71
  controller rows、HUD max 4 與完整 MP4；三動作 38/18/15，雙方向 10 筆 physical
  response 均約 94 ms。使用者確認移動已較線性。
- Run 在第一回合 terminal 後因 runner 誤判安全 no-op 而 aborted，未形成有效
  3 回合 Gate；修正後 non-PLAYING terminal no-op 不再製造 transition 或 exception。
- MP4/observation audit 找到 21-step aligned dwell：接觸尖刺被遮蔽，nearest 被判為
  normal，最後 generic damage 無 source。新增 4-step stable-gap dwell state 與
  persistent edge escape，並把 top-danger 排到 recovery 前。
- 同片離線 replay 由 frame 53 開始 RIGHT escape，舊版會 RELEASE 到死亡；targeted
  75 passed、完整 329 passed in 68.31s，compileall/dry-run/diff check 均 PASS。
  P3.6 仍 FAIL／STOP，repair v2 只達再次 3 回合實測門檻。

### 第三次 retest 與 repair v3

- 完成 3 回合／268 steps，HUD max 5/5/2、mean 4、median 5；兩回合達 floor 5。
  105/81/82 三動作無 collapse、32 physical samples median 94 ms、0 safety event，
  三套 transition/controller/MP4 完整。
- Gate 仍 FAIL：EP1/3 有 player missing；EP2 的 floor-null 只在 terminal dialog，
  runner 已改為只對 active PLAYING frames 要求 HUD telemetry。
- EP3 spring 近距離 gap 週期反彈但 bounce event=0。Repair v3 以 nearest spring/
  spikes gap ≤30 px 直接啟動 persistent escape；同片 replay frame 14 起連續 LEFT。
- Targeted 74 passed、完整 331 passed in 67.55s；compileall、dry-run、audit JSON
  與 diff check 均 PASS。未啟動訓練或新增真機操作，P3.6 保持 STOP。

### Wall-safety repair v4

- 後續 3 回合 artifact floors 5/2/1；5 回合為 2/1/3/3/7，人工最高看到 8。
  最高樓層進步，但兩個 Gate 都因 observation invalid 而 FAIL。
- 5 回合 EP1 spring 在左 guard zone 有兩段共 12 個 outward LEFT；EP4 spikes
  有 12 個連續 RIGHT，x 由 326.5 到約 410。判定為 P3.6 blocking safety bug。
- 修改程式前先建立 `P36_WALL_SAFETY_REPAIR_PLAN.md`，固定共用 wall guard、
  telemetry、零 outward count/streak 與 P4.0 門檻。
- 共用 guard 已覆蓋 special、launch、dwell 與所有一般 decision；playfield
  40～423 px、margin 32 px，向內反轉且保留方向 brake。
- Controller sidecar 與 Gate summary 已新增 wall fields；缺 telemetry 或任何
  applied outward wall action 都不能 PASS。
- 8 支既有 MP4／497 frames replay 為 0 outward；targeted 84、完整 338 tests PASS。
  未啟動訓練或真實輸入，狀態為 repair v4 READY FOR 3-EPISODE RETEST。

### Repair v5：vision continuity、latched evacuation 與 risk-aware landing

- v4 後四組真機 artifact 共 18 episodes／721 steps，全數 Gate FAIL；13 bottom、
  6 floor-1 bottom、14 observation invalid。Mean/median 2.28/2，低於前一版五回合
  3.2/3，故未進 P4.0。
- 修改前建立 `docs/PROJECT_MASTER_PLAN.md`，完整定義 P3.6～P8、Gate、停止條件、
  本機/Colab/真機分工與 Repair v5 工作包。
- Player vision：warm sprite morphological close、component min height 15→14、
  min coloured pixels 12；tracker 最多 extrapolate 2 frames，observation 明標
  raw/tracked/missing 與 streak，不跨 terminal pipeline reset。
- Wall：單步 override 改 latched evacuation；32 px enter、64 px exit、0.2 s vx
  lookahead、觸發即清 launch/special/dwell、退出 cooldown，保留 direction brake。
- Landing：launch commit 最多 3 steps、2-step replan cooldown，候選落點以 vx
  lookahead projected x 對 safe interior 計算；support edge/aligned release 只先記錄，
  因影片沒有證明真正 stationary，不冒險加入未驗證強制移動。
- Gate：新增 player continuity、wall re-entry、global/wall reversal、aligned release、
  floor-1 bottom 與 3/5 episode reliability thresholds。全域換向保留 telemetry；
  wall-corridor burst 才是 blocking check。
- Replay r1 正確 FAIL；r2/r3 用來定位 detector off-by-one 與過寬 oscillation Gate；
  r4 對 18 MP4／729 playing frames 全 PASS：716 raw detection、13 tracked bridge、
  effective missing 0、outward 0、wall re-entry 0、wall burst max 1、aligned max 5。
- Targeted 102 passed；完整 350 passed in 66.51s。未載入 input backend、未操作
  遊戲、未訓練模型。狀態是 OFFLINE PASS／REAL PENDING，P3.6 仍 FAIL／STOP。

## 本次規格範圍

依 `CODEX_NS_SHAFT_PROJECT_REFACTOR_PROMPT.md`，本次只做 audit、永久上下文、
資料 schema／validator、simulator v0、Gymnasium/Pymunk 基礎環境、測試與 Colab
骨架。未開始長時間訓練，也未實作 BC、DAgger、Residual 或 DQfD trainer。

## 完成項目

### 1. Repository audit

- 讀完長期規格、AGENTS、README、handoff 與現有 training strategy。
- 檢查 git status/diff，保留原有 18 個 tracked dirty files 與 2 個 untracked
  handoff/report。
- 盤點真實 control flow、observation dimension、action、reward、
  terminal/truncated、legacy data、baseline、PPO artifact 與測試。
- 產出 `reports/PROJECT_AUDIT_REPORT.md`。

### 2. 永久上下文

新增：

- `docs/PROJECT_CONTEXT.md`
- `docs/CURRENT_STATUS.md`
- `docs/TRAINING_ROADMAP.md`
- `docs/EXPERIMENT_PROTOCOL.md`
- `docs/DATASET_SCHEMA.md`
- `docs/SIMULATOR_SPEC.md`
- `docs/LOCAL_COLAB_WORKFLOW.md`
- `docs/DECISIONS.md`
- `docs/RISK_REGISTER.md`

並擴充 `AGENTS.md`，加入每次 context 恢復順序、Go/No-Go、PPO／legacy data
禁用條件與完成後更新規則。

### 3. Dataset schema / validator

新增：

- `src/stair_agent/data/schema.py`
- `src/stair_agent/data/validator.py`
- `scripts/validate_dataset.py`
- `tests/test_data_schema.py`
- `tests/test_dataset_validator.py`

實作 strict required/unknown fields、版本、NaN/Inf、268 維、action、timestamp、
terminal continuity、episode crossing、step gap、observation jump、action collapse
與 duplicate checks。CLI 拒絕覆寫既有 output。

### 4. Simulator v0 / Gymnasium

新增：

- `src/stair_agent/simulator/{state,player,platform,generator,physics,renderer}.py`
- `src/stair_agent/envs/{shaft_env,reward}.py`
- `scripts/check_simulator.py`
- `tests/test_simulator_env.py`

特性：

- Pymunk player/platform；
- RELEASE/LEFT/RIGHT、重力、acceleration、max speed、release drag；
- normal one-way landing、bounce、bounds、scroll、floor progress、top/bottom death；
- fixed seed、None/human/rgb_array；
- 重用真實 `FeatureEncoder`／`TemporalObservationStack`，輸出 268 維；
- `check_env`、existing baseline smoke、100k headless smoke。

依賴已加入 `pyproject.toml` 與 `requirements.txt`：
`pymunk>=6.8,<8`、`pygame-ce>=2.5,<3`。

### 5. 既有半成品修復

接完 `platform_target_action_reward` constructor、component 與
`StairAgentEnv` config wiring，使開始時已存在的 5 個 failing tests 通過。
未還原或重寫其他 dirty worktree 修改。

### 6. Colab

新增 `notebooks/ns_shaft_colab.ipynb` 骨架，涵蓋 clone/install、Drive、
dummy video driver、pytest/check_env、headless smoke、1/4/8/16 sync/async
benchmark、推薦 env count、TensorBoard、checkpoint/video 與 resume。沒有任何
real executable 或 input backend 操作。

### 7. 報告

- `reports/PROJECT_AUDIT_REPORT.md`
- `reports/TRAINING_STRATEGY_REPORT_V2.md`
- `reports/IMPLEMENTATION_PROGRESS_REPORT.md`

## 驗證結果

- 初始基線：169 passed、5 failed；5 個皆為已知 target-action reward 半成品。
- 新 schema／validator tests：通過。
- simulator `check_env` 與行為 tests：通過。
- 100,000-step headless smoke：通過，約 24.4 秒（單次本機測量）。
- 最終 `python -m pytest -q`：204 passed，26.93 秒。
- `python -m compileall -q src scripts`：通過。
- notebook JSON parse：通過。
- `git diff --check`：通過；只有 Windows LF→CRLF 提示。
- `scripts/check_simulator.py --steps 10000 --baseline-steps 1000`：
  約 4,519 steps/s，check_env 與 baseline smoke 通過。

所有驗證都在 mock／headless simulator 執行，沒有尋找或操作真實遊戲。

## 尚未完成（刻意留待後續 gate）

- 新 transition writer 接到真實與 simulator step；
- legacy migration/quarantine manifest；
- 真實 physics/action/observation latency 校正；
- 正式 random／release／baseline benchmark artifact；
- Colab 實際 runtime benchmark；
- BC、DAgger、Residual、Double DQN／DQfD-lite；
- 長時間訓練或新增實機 rollout。

## 下一個建議工作包

先做「transition writer + quarantine + calibration telemetry」：

1. 讓每一 action 可靠產生符合 v1 schema 的 transition。
2. 逐檔掃描 legacy data，產出可追溯 quarantine manifest，不猜補欄位。
3. 用有限且安全的人工 telemetry 擬合 simulator v0。
4. 建立固定 seeds 的 random／release／baseline benchmark。

完成上述 gate 後，再決定是否准許短 learnability probe。

## 2026-07-30 後續進度

- 新增 `data/writer.py` 與測試；writer 拒絕覆寫、錯誤 reward 加總及 terminal
  後續寫。
- 新增 `data/migration.py`／`quarantine_legacy_data.py`；實際掃描 23 files、
  2,912 rows，全數 quarantine。
- `LiveGameAdapter` 新增 command/effective/next-observation timing，不改變既有
  foreground、F8 或 release 行為。
- 一次實機 calibration 在 56 steps／20 seconds 上限內於死亡前完成 43 步，
  validator 0 error／0 warning，未重開第二回合。
- 新增 `CALIBRATION_REPORT_V0.md`、`SIMULATOR_BENCHMARK_V0.json` 與
  `VECTOR_ENV_BENCHMARK_V0.json`。
- simulator benchmark：baseline 1.46 floors、random 0.76、RELEASE 0；
  每組 5 seeds × 20 episodes。
- 本機 vector benchmark：16 async 約 11,939 steps/s 為最高值；此建議不可
  直接外推至 Colab。
- 沒有開始 BC、DAgger、Residual、DQfD、PPO 或其他模型訓練。
- 後續完整回歸：`python -m pytest -q` 為 209 passed，27.28 秒。
- 第二次 RIGHT-first 實機校正完成 56 筆；總計 99 records，沒有開始訓練。
- 新增自動 calibration gate analyzer 與
  `CALIBRATION_PROFILE_V1.json`／`CALIBRATION_GATE_REPORT_V1.md`。
- 目前 fidelity gate 為 FAIL：clean LEFT/RIGHT 只有 15/11、非零 RELEASE 6、
  landing 2；單步 y/vy 與 10-step x/y error 也超標，30-step 尚無可用 window。
- 因最新唯讀檢查找不到可見遊戲視窗，passive calibration 安全停止於未執行；
  沒有自動啟動遊戲。

## 2026-07-30 Calibration v0.1 完成

- 累積 14 個 calibration JSONL、649 transitions；sample、一步與 landing
  classifier gates 通過，所有 calibration labels 仍為 invalid/quarantine。
- 最終一步 fitted MAE：x 3.99、y 6.83 px、vx 32.67、vy 56.17 px/s。
- landing classifier：23 events、precision 0.846、recall 0.957、
  death misclassification 0。
- 校正 simulator control dt、action impulse、release drag、screen-space
  gravity／bounce／scroll、平台尺寸／間距與水平 shift。
- 發現 exact 30-control-step pixel replay 的 partial-observability blocker；
  未使用未來平台 teacher forcing 或放寬碰撞框過關。
- v0.1 baseline fixed benchmark：100 episodes、2,490 steps、150 landings／
  floors；landing/floor rate 0.0602。
- real landing-focused：325 steps、17 landings、12 floors；
  two-proportion z 分別 −0.569／−1.698，seeded distribution gate 通過。
- Gate 僅開放短 simulator learnability probe；沒有開始 BC、DAgger、
  Residual、DQfD、PPO 或其他訓練。
- v0.1 最終完整回歸：217 passed；`check_env`、10k headless 與 1k
  baseline smoke 通過，約 3,317 headless steps/s。

## 2026-07-30 Simulator learnability P0／P1

- 新增 simulator-only 評估器，保存 floors、return、episode length、
  landing、terminal reason、action distribution 與 collapse 指標。
- P0：PPO／SB3-DQN 各 4,096 steps；held-out floors 1.00／1.05，
  random 0.70、baseline 1.65；兩者均未 collapse。
- P1：3 個 fresh train seeds，每演算法／seed 8,192 steps，20 個 held-out
  eval seeds。PPO floors 1.50／1.95／0.90，平均 1.45；SB3-DQN
  1.00／1.20／1.30，平均 1.167。
- 六個 P1 模型皆未達 98% action collapse；LEFT／RIGHT 各至少 2%。
- P1 gate 通過，但 PPO seed variance 仍大，兩者平均仍未超過 baseline。
- 依 D-010 停止本機擴訓；下一步是 Colab pipeline validation。
- P1 後完整回歸：219 passed；六個 checkpoint 已保存，抽樣 PPO／DQN
  checkpoint 可重新載入並產生合法動作。
- Colab notebook 已由註解 skeleton 升級為預設停用的 bounded pipeline
  validation：512-step PPO、checkpoint load、256-step resume、MP4 與
  `colab_pipeline_gate.json`；仍需在實際 Colab runtime 執行。

## 2026-07-30 最新策略工作包

- 完整核對最新／原始 Prompt、AGENTS、README、長期 docs、既有 reports、
  `git status`／`git diff` 與 simulator/data 實作。
- 確認初始工作樹乾淨；初始完整回歸為 219 passed。
- 更新永久策略：Data Resource Audit → Simulator v0.2 →
  Oracle-full／Teacher-observable → 8／10／12 Hz → 條件式 BC0／DAgger0。
- 修正 CURRENT_STATUS：Colab pipeline 已實際通過，但 768-step deterministic
  全 RIGHT，checkpoint 禁止續訓。
- 本階段只改文件；未啟動遊戲、未送真實輸入、未執行任何訓練。

### Data Resource Audit

- 新增 `data/resource_audit.py`、CLI 與測試，掃描 37 JSONL／3,561 rows。
- 649 calibration rows 全為 `dynamics_only`；legacy 2,912 rows 中 476
  為 `needs_relabel`，2,436 invalid。
- verified BC 與 replay 都是 0；不以舊 action 猜補 expert label。
- 產生 `DATA_RESOURCE_AUDIT.md`、`dataset_inventory.csv` 與 row-level
  `dataset_salvage_manifest.csv`。

### Simulator v0.2、teachers 與 gates

- 實作 fixed 60 Hz physics substeps、8／10／12 Hz policy、持續平台生成／回收、
  easy/calibrated/hard、3-floor reachability、failure taxonomy、overlay 與
  特殊平台 flags（預設關閉）。
- Oracle-full 使用 privileged simulator state／短 rollout diagnostics；
  Teacher-observable API 只接受學生 structured observation。
- 100／1,000 seed reachability、Oracle-full 與 Baseline gates 全 PASS。
- frequency 結果選 simulator 10 Hz；未改真實控制率。

### Teacher Dataset、BC0、DAgger0

- 生成 60 episodes／3,560 rows，按 seed/sequence 分割，validator 0 error。
- Soft-loss BC0：test accuracy 88.79%、rollout 20.95 floors；learner-state
  teacher disagreement 41.01%，確認 offline/rollout gap。
- 只改 hard-label CE 後，三 seeds 為 29.80／30.10／25.95 floors，
  3/3 通過 23.84 gate；BC0 PASS。
- DAgger0 round 1 使用獨立 aggregation seeds 收集 1,634 corrections；
  重訓後降至 23.20，低於 gate，故 FAIL 並停止第二輪。
- 新增 `BC0_DAGGER0_REPORT.md` 與可重現 diagnosis／correction scripts。

### Balanced correction ablation

- Audit 證明 naive corrections 占原 train 69.2%，LEFT label 比例由 27.7%
  偏至 45.5%；exact／rounded duplicate 都是 0。
- 預先固定 25% cap（590 rows）、原 action ratio、12 clusters × failure
  category round-robin，之後只訓練一次。
- Frozen seeds：63.15 floors；fresh seeds 400～419：62.90；
  fresh baseline 31.25。無 collapse，floor-event invariant 通過。
- Easy curriculum 判定飽和；依 Phase F 不自動開始特殊平台或長 RL。

### Health＋normal-platform heal

- 新增 feature-gated health state、普通平台 +1 heal、12-segment cap、
  observation/event/info 與可選 reward component。
- 新增 HUD renderer、`HealthCalibration`、deterministic landing scenario。
- 100/100 low-health Oracle landing PASS；100-seed feature off/on full-health
  episode results 完全相同，平均都是 34.68 floors。
- Health-v1 只完成 mechanism gate，沒有產生新 dataset 或訓練模型。

### Spike mechanism

- 新增 platform kind、feature-gated 5-segment spike damage、health-depleted
  termination、events 與 damage/death reward components。
- 新增 red renderer、`SpikeCalibration`、fixed damage/lethal/choice scenarios，
  並讓 Oracle 在同層優先 normal。
- Non-lethal、lethal、normal-heal interaction、Oracle avoidance 各
  100/100 PASS；100-seed no-spawn equivalence 完全相同。
- Spikes-v1 尚未加入 generator、dataset 或訓練。

### Conveyor mechanism

- 新增預設關閉的左右 conveyor kind、暫定 ±80 px/s landing velocity delta、
  auditable events／info 與 environment version。
- 新增方向色 renderer、`ConveyorCalibration`、fixed landing／choice scenes，
  並讓 Oracle 在同層優先 normal。
- Left velocity、right velocity、Oracle normal preference 各 100/100 PASS；
  100-seed no-spawn equivalence 完全相同，平均皆 34.68 floors。
- Conveyor-v1 尚未加入 generator、dataset 或訓練；速度仍待真實 telemetry
  校正，不宣稱 fidelity。

### Spring mechanism

- 新增預設關閉的 spring kind、暫定 190 px/s landing jump velocity、
  auditable events／info 與 environment version。
- 新增橘色 renderer、`SpringCalibration`、fixed landing／choice scenes，
  並讓 Oracle 在同層優先 normal。
- Stronger bounce 與 Oracle normal preference 各 100/100 PASS；
  100-seed no-spawn equivalence 完全相同，平均皆 34.68 floors。
- Spring-v1 尚未加入 generator、dataset 或訓練；彈力仍待真實 telemetry
  校正，不宣稱 fidelity。

### Flipping mechanism

- 新增預設關閉的 flipping kind、暫定 1 秒 active／1 秒 inactive 週期、
  active-state observation/info 與 environment version。
- inactive 翻板不碰撞；renderer 以青／灰區分，Oracle 排除 inactive 並優先 normal。
- Active collision、inactive passthrough、Oracle normal preference 各
  100/100 PASS；100-seed no-spawn equivalence 完全相同。
- Flipping-v1 尚未加入 generator、dataset 或訓練；同步週期仍待真實 telemetry
  與 seeded phase 設計，不宣稱 fidelity。

### Spike curriculum generator v0

- 新增 10% spike proposal、前 3 層 normal、尖刺間至少 5 normal 的 seeded
  generator；recycling 延續相同 recovery-gap invariant。
- Reachability gate 同時檢查 kind reproducibility、幾何與 health survivability，
  並報 proposal／realized ratio。
- 1,000 seeds realized 5.11%；Reachability、Oracle、Baseline gates 全 PASS。
- Oracle 100% 到 10 層；baseline 33.07 vs plain 34.68，retention 95.36%，
  floor-3 success 99%，health deaths 0。
- 使用獨立 seeds 1000～1059 生成 60 episodes／3,541 rows，validator 0 error；
  16 spike contacts、最低 health 7；test 有 232 spike-visible rows。
- 本機 seed 0／5-epoch interface smoke：27.0 floors vs baseline 31.55，
  retention 85.58%、0 health death、無 collapse，准許進 Colab 三-seed BC0。
- Colab notebook 新增預設停用的 bounded spike BC0 cell：重跑 Gate／dataset、
  seeds 0／1／2、固定 fresh eval、artifact ZIP；任一失敗停止且不跑 DAgger。

### Repository cleanup

- 刪除未被任何檔案引用、且內容已被永久 docs／V2 reports 取代的
  `CODEX_HANDOFF.md` 與 root `TRAINING_STRATEGY_REPORT.md`；兩者仍可從 Git
  history 還原。
- 保留所有 calibration profile／gate report，因它們是不可猜補的實驗 provenance。
- 大型可再生 `teacher_dataset_v0.jsonl` 與 model weight 維持 git ignored；
  只提交 schema、產生器、summary、required CSV 與 gate report。

### 最終驗證

- `python -m pytest -q`：279 passed in 157.08s。
- `python -m compileall -q src scripts tests`：通過。
- simulator／BC0 artifact JSON parse：通過。
- `git diff --check`：通過；只有 Windows LF→CRLF checkout 提示。
- 全程未啟動遊戲、未送真實輸入、未續訓 PPO、未跑長 PPO／DQN。

## 2026-07-31 Spike BC0 checkpoint-selection 修正

- 完整分析 Colab seed 0 診斷包；依最低 validation loss 選出的 epoch 17
  雖有 82.06% test accuracy，實際只有 12.85 floors、17/20 bottom death，
  相對 baseline retention 40.73%，正式 Gate FAIL。
- 與同初始化 epoch 5 比較後確認是閉迴路 covariate shift／checkpoint
  selection 問題：epoch 5 為 27.0 floors、4/20 bottom death。
- 新增 `training/bc_checkpoint_selection.py` 與單元測試，強制 dataset、
  selection、final seed partitions 完全不重疊。
- `run_bc0_smoke.py` 改為保存預先固定候選 epoch，先在 1060～1079
  以 rollout 選模，再於 1200～1219 做一次 final evaluation；1100～1119
  永久列為診斷集。
- 選模排序先保證無 collapse／health death，再比較 rollout gate、mean
  floors、bottom deaths；offline validation loss 只作 tie-break。
- 本機 seed 0／5-epoch bounded smoke：selection epoch 3／5 為
  19.8／24.45 floors，選 epoch 5；final BC 27.85 vs baseline 29.60，
  retention 94.09%，0 health death、無 collapse，pipeline PASS。
- Colab notebook 已改用候選 3／5／8／11／14／17、selection
  1060～1079、final 1200～1219，並封裝各候選 checkpoint。
- 本階段沒有新增空白樓層：generator 仍保證每個 floor 恰有一個平台，
  只允許位置與已通過 gate 的平台類型改變。
- 尚未執行新版三初始化 seed；在 3/3 final gate 通過前，spike DAgger0
  維持 No-Go。
- 本次完整回歸 `283 passed in 65.19s`；compileall、notebook JSON 與
  `git diff --check` 全部通過。

## 2026-07-31 Balanced Spike DAgger0

- Colab spike BC0 3/3 final Gate 通過後，凍結 aggregation 1300～1359、
  selection 1400～1419、final 1500～1519。
- 三個 BC0 source models 共收集 8,076 learner-state disagreements；依 base
  train 25% cap、action ratio、12 clusters × category × source round-robin
  選出 592 corrections，60/60 episodes 有覆蓋。
- 三初始化 DAgger floors 為 43.95／32.20／40.10，相對原 BC0 同 seeds
  27.75／29.00／28.95，平均增加 10.18 floors。
- 但 floor-10 success 由 86.67% 降到 75%，bottom death 15→27；seed 2
  發生 1 health death，因此正式 Gate 只有 2/3，整輪 FAIL。
- 固定失敗重播顯示模型跳過 normal recovery floors，最終連續實際回血不足；
  每層平台生成 invariant 沒有違反。
- 已產生 `SPIKE_DAGGER0_REPORT.md` 與 gate summary；依協議停止第二輪。
- 完整回歸 `285 passed in 72.08s`；compileall 與 `git diff --check` 通過。

## 2026-07-31 Teacher recovery／reliability-first Gate

- Teacher-observable 新增受傷 recovery mode：最近 normal 優先、覆蓋舊 deeper
  lock、保留 direction-change braking；full health 行為不變。
- Evaluation summary 新增 floor Q25；BC checkpoint selection 改為 safety、
  floor-10、bottom death、Q25、median 優先，mean floors 降為後順位。
- 100 low-health seeds 有 4,978 recovery decisions、0 health death、Q25 22、
  floor-10 88%；full-health reference floor-10 同為 88%、Q25 23.75。
- Recovery safety/non-regression PASS，但 absolute 90% reliability Gate FAIL；
  未啟動新 dataset、BC、DAgger 或實機控制。
- 真實資料策略改為 Gate 通過後才收 spike／回血／跳層的小型 verified packet，
  不進行無目標的大量重蒐。
- 完整回歸 `291 passed in 68.20s`；compileall、artifact JSON 與
  `git diff --check` 通過。

## 2026-07-31 Floor-10 reliability correction

- 發現歷史 `success_rate_floor_10` 是 10 次成功下降事件，不等同實際到達
  floor index 10；新增 deepest-floor 與 reach-rate 指標，所有 Gate 改用後者。
- 重播 1700～1799 確認兩個共同原因：暫判不可達時過早 release，以及
  launch escape 朝最近邊緣而非下一個可見平台。
- Teacher 新增 visible safe／recovery／health-safe spike approach，並讓反彈
  離台方向優先對準下一個可見候選；health 不足的 spike 保護維持不變。
- development 1600～1699 reach-floor-10 95%；已診斷 1700～1799 為 96%；
  一次 untouched holdout 1800～1899 為 94%。三組 low/full health 均無
  health death，全部通過 90% reliability Gate。
- 1700 組因參與診斷不再稱為 untouched；正式 holdout 只採 1800 組，執行後
  即凍結。
- 完整回歸 `296 passed in 68.51s`；未啟動遊戲、未送真實輸入、未訓練模型。

## 2026-07-31 Spike Teacher Dataset v1／BC0 smoke

- 凍結 dataset 2000～2059、selection 2060～2079、final 2200～2219；所有已用
  partitions 禁止重用，舊 v0 artifact 未覆寫。
- Dataset v1：60 episodes／3,529 rows、validator 0 error、三動作與三 splits
  coverage PASS；36 spike-visible episodes、33 spike targets、16 damage、
  179 recovery-related decisions、0 health death。
- 每筆 TeacherRecord 新增 policy version／decision reason provenance；新版生成
  強制讀取通過的 Teacher reliability holdout Gate。
- seed 0／5-epoch BC0 final mean deepest 45.5 vs baseline 49.7，但 reach-floor-10
  60% vs 100%、Q25 7.75 vs 30、bottom 14 vs 1，Gate FAIL 並停止。
- Learner-state disagreement 主要在 launch escape、move safe、recovery、brake，
  下一步須處理 branch coverage 與 controller memory observability，不加 epochs。
- 外部 NS-Shaft NEAT 專案確認是自製遊戲內部狀態訓練；只保留為未來 bounded
  compact-observation baseline，不以單次最高樓層取代 lower-tail Gate。
- 完整回歸 `298 passed in 97.85s`；未啟動真實遊戲或長訓練。
## 2026-08-01 P3.6 Support-Departure Repair v6

- 依 v5 兩次真機失敗 sidecar，先建立 source 7→9、source 22→25 的 regression
  tests，再修改 policy。
- `SafePlatformPolicy` 新增 support-departure phase，保存來源、目的與方向；仍接觸
  來源時不接受 landing-aligned RELEASE，support-lost 後才轉回 airborne planner。
- 新增 8-step safety abort、1-frame support-lost confirmation；wall/special/F8 與
  real input safety chain 未變更。
- Runner/Gate 新增 same-support cycles、destination switches、timeout、edge RELEASE
  ratio、exit samples、max steps 與 phase-aware support aligned streak。
- 8 支最新 MP4／476 playing frames offline replay r3 PASS：departure-active 177、
  cycles 0、switches 0、outward 0、wall re-entry 0、support aligned max 3。
- Counterfactual 舊影片有 5 次達 departure hard cap；因新 action 未實際作用，不能
  判斷 support-lost，保留 telemetry 且新真機 Gate 仍要求 timeout 0。
- Targeted 86 passed；完整 357 passed in 83.27s；compileall、dry-run、JSON、
  diff check PASS。未啟動遊戲、未送鍵、未訓練。
- 狀態：repair v6 OFFLINE PASS／REAL PENDING；P3.6 仍 FAIL／STOP。下一個唯一工作
  是使用者監督的一次 bounded 3-episode real Gate。

## 2026-08-01 P3.6 Gate v2 semantic repair

- Repair v6 新實機 3 回合完成：466 steps、parser floors `5,3,10`、3/3 reach-3、
  2/3 reach-5、0 safety event。使用者觀察最高 13，影片尾段也顯示 parser lag。
- 舊 Gate v1 FAIL 原因經 sidecar 定位為三種語意誤判：`target == support` 的正常
  settle 被當卡邊、special escape 方向被併入 wall oscillation、全程 RELEASE 且
  後續恢復的 observation dropout 被當永久失效。
- 新增 `ObservationDropoutTracker`、`SupportAlignedStallTracker`、context-eligible
  direction tracker 與共用 `reclassify_real_micro_episode`；real runner 與離線重算
  使用相同定義，控制 policy 沒有修改。
- 新增不可覆寫 `reclassify_teacher_real_micro_gate.py`。同一 sidecar 重分類結果：
  29 invalid、4 recovered、max 15、blind 0、unrecovered 0、active-wall burst 0、
  actionable support RELEASE 0；Gate v2 全項 PASS。
- Targeted 98 passed；完整 363 passed in 85.93s；compileall、v2 dry-run、artifact
  parse 與 diff check PASS。完整報告見 `P36_GATE_SEMANTICS_V2_REPORT.md`。
- 狀態：Gate v2 RECLASSIFICATION PASS／FRESH REAL CONFIRMATION PENDING；P3.6
  維持 HOLD／STOP，尚未開始 P4.0 或任何訓練。

## 2026-08-02 P3.6 Repair v7／Gate v3

- Gate v2 後兩個 fresh runs floors `1,4,1`、`7,5,2`，均 FAIL；第二個 run 已達
  reach 門檻但有 3 次 wall re-entry，且 sidecar／影片定位到 top-pressure dropout
  RELEASE 停頓分支。
- Test-first 新增 wall cooldown inward continuation、top-pressure 2-step bounded
  direction bridge、ordinary missing RELEASE 與 same-support fast escape。
- Gate v3 新增 bridge count/max streak、exhausted count 與 top-pressure support escape；
  max streak>2 或 exhausted>0 都會阻擋，其他 missing directional action 仍算 blind。
- 最近 7/5/2 三支 MP4 current-policy replay：351 playing frames、outward 0、wall
  re-entry 0、same-support cycle 0、target switch 0，offline PASS。
- 完整 369 tests in 57.61s、compileall、no-input Gate v3 dry-run PASS。未啟動遊戲、
  未送鍵、未訓練。
- 狀態：Repair v7 OFFLINE PASS／FRESH REAL PENDING；P3.6 HOLD／STOP。完整報告見
  `P36_REPAIR_V7_REPORT.md`。

## 2026-08-02 P3.6 Repair v8／Gate v4

- Gate v3 fresh run floors `2,4,10`，影片至少顯示 12、使用者觀察約 13；整體仍因
  25-step dropout 與一次 departure timeout FAIL。
- 定位 EP2 timeout 後永久 source block 造成 17-step RELEASE；v8 改為 abort 後
  2-step cooldown，再依最新 target retry。Timeout 仍是 blocking failure。
- 新增 bounded lossless dropout forensics：milestones 1/3/8/16/24/recovery、每回合
  最多6組 raw PNG、mask PNG、component/threshold JSON。
- Gate v4 將 recovered dropout 20→8，要求 forensic manifest 與 abort cooldown<=2。
- Targeted 112、初次完整 373 tests PASS；compileall、no-input dry-run PASS。舊影片
  counterfactual 因不能回應新 action 而 FAIL，不冒充 closed-loop 結果。
- 當時狀態：CODE／TEST READY；FRESH REAL Gate v4 PENDING；未啟動遊戲或訓練。

### Gate v4 fresh real 結果

- Run：`logs/teacher_real_micro_20260802_021704_107779`；HUD／影片 floors
  `9,2,2`，mean 4.33、median/Q25/CVaR25=2。
- 36 checks 中 35 PASS；唯一失敗是 `reach_floor_3_case`（1/3，門檻2/3）。
- v8 真機目標已通過：dropout max1、forensic available、timeout0、wall re-entry0、
  outward0、same-support cycle0、blind action0、safety event0。
- 新 failure branches 是 EP2 late-braking landing overshoot 與 EP3
  destination-unaware spring／launch escape。P3.6 維持 HOLD；Repair v9 待辦，未進
  P4.0 或訓練。詳見 `P36_REPAIR_V8_LIVE_GATE_REPORT.md`。

## 2026-08-02 P3.6 Repair v9／Gate v5

- 以 Gate v4 EP2 x=231／vx=-208／rising 與 EP3 spring-right-edge 分支先建立 tests。
- Landing prediction 由固定0.25秒改為0.25～0.55秒 adaptive horizon；rising 使用
  最大值，falling 依 delta-y／max(vy,80) 計算。
- Support departure 獨立使用 destination safe interval＋既有動量，避免長 horizon
  反轉已通過的離台方向。
- Special escape 優先 visible deeper reachable landing；無可見落點時，12 px edge
  且 outward velocity>40 px/s 反向；持續 contact 可因新落點 replan。
- Gate v5 新增 landing/special telemetry availability 與4個計數；舊 Gate checks
  全數保留。
- Targeted 107、完整379 tests PASS；compileall、config parse、Gate v5 no-input
  dry-run、diff check PASS。未啟動遊戲或訓練。
- 狀態：CODE／TEST READY；FRESH REAL Gate v5 PENDING；P3.6 HOLD。

## 2026-08-03 P3.6 Natural Gate v9

- 固定平台 reversal 收集依分布疑慮停止；3個 completed runs封存為
  diagnostic-only，第4個中止 run排除，沒有拿來解鎖Teacher Gate。
- 第一次 natural run 因使用者誤切視窗由focus guard安全停止，2回合資料標記
  INVALID／INCOMPLETE；替代run完整3回合 floors `2,9,7`，HUD影片重播PASS。
- 原始v8唯一FAIL為generic edge RELEASE 16/57；sidecar分類為15次同平台settle與
  1次spring brake。Gate v9 test-first分離actionable 0/39與generic 16/57，
  不修改Teacher controller、不放寬25%門檻。
- 相同不可變sidecars重分類51/51 checks PASS；mean/median/Q25/CVaR25=
  `6/7/4.5/2`，safety、dropout、outward、wall re-entry、departure timeout皆0。
- 自然dynamics audit更新為475 strict rows／15 held-out episodes，reverse-braking
  LEFT/RIGHT=`11/15`，仍不符合30/30，shadow/live deployment維持禁止。
- 39 Gate tests、61 related tests、完整402 tests與compileall PASS；10回合no-input
  dry-run PASS。下一步為10回合stability Gate，尚未進P4.0或啟動任何Student訓練。
- 詳細報告：`P36_GATE_V9_NATURAL_MICRO_REPORT.md`。

## 2026-08-03 P3.6 Gate v11 10-Episode Stability Qualification

- 完整 run `teacher_real_micro_20260803_034023_674665` 取得10/10 episodes；原始
  floors `8,11,3,2,2,5,4,4,8,2`，safety event 0、reach-3 7/10、reach-5 4/10。
- 10支MP4逐幀HUD audit PASS，證實EP3 terminal frame為floor4；修正序列為
  `8,11,4,2,2,5,4,4,8,2`。Correction只可向上、來源run必須一致、raw v10
  artifact不覆寫。
- Gate v11移除「所有bottom<=2」的錯誤偏好，改量floor<3 early-bottom，budget
  與reach-3 miss一致；保留total bottom=9與floor-1 bottom=0。Special brake改為
  entry 1＋准許reversal 1、絕對max2；兩個brake=2 contacts均符合，violation=0。
- 相同不可變sidecars重分類全部checks PASS：mean/median/Q25/CVaR25=
  `5/4/2.5/2`，early bottom 3/3 budget，spring/spike contacts 7/9；invalid、blind、
  outward、wall re-entry、departure cycle/switch/timeout、special abort皆0。
- Runner新增video-frame HUD tracker，避免terminal phase timing再漏記；姓名modal只准
  精確same-process owned #32770＋title白名單Enter-once。後者code-tested但本次run
  未觸發，不能列live pass。
- Gate/HUD targeted 51、完整410 tests、compileall、diff check PASS。本輪沒有重跑
  遊戲、送按鍵或啟動訓練。P3.6完成stability qualification；下一步只開放P4.0
  State-aliasing Audit，S0～S3及Student訓練仍blocked。
- 最終reclassification v2同時從來源limits驗證expected episodes=10；另產生Gate v11
  10回合no-input dry-run，確認不找視窗、不載input backend、不送按鍵。
- 詳細報告：`P36_GATE_V11_10EP_STABILITY_REPORT.md`。

## 2026-08-03 P4.0 State-Aliasing Audit

- test-first新增 `stair_agent.state_aliasing` 與 `scripts/audit_state_aliasing.py`；鎖定
  episode內lag-one causal memory、跨episode kNN、raw ID排除與明確action mapping。
- 來源為Gate v11完整10回合／753 transitions；268維、有限值、筆數、step與action
  alignment全部PASS。本輪完全離線，沒有開遊戲、送鍵或啟動Student訓練。
- 發現sidecar是在本步Teacher決策後寫入；當步`previous_action`及phase會洩漏label。
  正式比較只用`memory[t-1]`，當步memory僅作leakage ceiling（disagreement 11.42%）。
- observation-only 5-NN disagreement 56.20%，causal full memory 45.39%，相對改善
  19.23%；entropy 1.0402→0.8529，accuracy 48.07%→61.09%。10個episode改善方向
  全正，paired episode bootstrap 95% CI `[0.0979,0.1411]`。
- 預先固定的資料完整性、10% relative reduction、bootstrap下界及entropy/accuracy
  supporting checks全PASS，P4.0 Gate PASS。action-history單組42.76%優於full memory，
  P4.1 S1應優先compact causal state。
- 產生 `STATE_ALIASING_AUDIT.md`、`state_aliasing_audit.json`、
  `state_aliasing_summary.csv`、`teacher_action_conflicts.csv`。下一步只解鎖bounded
  P4.1公平S0/S1/S2/S3 smoke；尚未開始rare-branch dataset或任何長訓練。
- P4.0 targeted 5、完整415 tests PASS；compileall、artifact JSON/CSV count validation
  與diff check PASS。

## 2026-08-03 README Roadmap 與發布前 Cleanup

- README 新增從舊真機PPO、P0～P3.6、P4.0，到P4.1～P8最終實機展示的完整路線；
  每階段列出目的、步驟、Gate、停止條件與本機/Colab/simulator/原版遊戲分工。
- 發布scope稽核確認大型JSONL、model、logs、MP4由`.gitignore`隔離；source、tests、
  reports與summary artifacts納入GitHub保存，未發現token/password類秘密。
- 清理前逐項驗證workspace絕對路徑、引用與替代版本；移除89個明確檔案、69個舊
  model files及caches，共237.82 MiB。
- 刪除範圍限舊ZIP、禁止續訓的weights、已取代中間dataset/corrections、無引用v1
  duplicate與舊啟動logs；Gate v11、calibration、templates、clean easy dataset、
  Spike Dataset v1、summary與失敗provenance全部保留。

## 2026-08-03 Spring Curriculum v0 Gate

- 先建立`SPRING_CURRICULUM_V0_PROTOCOL.md`，凍結6% spring proposal、3-normal gap、
  seeds 9000～9999／10000～10099與逐Gate停止規則。
- Test-first新增config validation、feature-off RNG equivalence、長序列normal gap、
  platform-kind統計、seed range與per-episode event coverage；第一次5 tests如預期FAIL，
  實作後相關24 tests PASS。
- `ShaftEnvConfig`新增spring curriculum欄位/version；generator在spawn=0時不消耗額外RNG，
  並讓spikes間的health gap只計真正normal。Reachability artifact新增通用kind counts/ratios。
- 正式Gate的Engineering、Reachability 100／1,000與ratio PASS：spring 243/9000=2.70%，
  spikes 432/9000=4.80%，0 unreachable／unsafe。
- Oracle只有71/100 reach-floor-10，29 failures全為top death；65個無spring回合全成功，
  35個spring回合只有6成功，失敗前有2～4次spring contact。狀態`FAIL_STOP_ORACLE`。
- 依protocol未執行Baseline，未生成Dataset、未訓練、未開啟遊戲或送鍵。下一步只允許
  Spring Failure Trace／Fidelity Audit，不直接調190 px/s或追加escape heuristic。
- 相關63 tests與完整475 tests PASS（69.02s）；compileall、artifact JSON、source／
  protocol fingerprint及`git diff --check`全部PASS。

## 2026-08-03 Spring Failure Audit／Oracle Escape Gate

- 凍結failure/fidelity audit，逐step重播舊10000～10099：29 top deaths全部在2～4次
  spring contact後，0 first-bounce direct top；失敗後RELEASE/LEFT/RIGHT=547/73/71。
- 真機308 records有159筆可見spring、7 target-spring，但0 confirmed spring event／
  vertical pairs；拒絕調190 px/s，唯一批准Oracle-only clearance候選。
- Test-first新增aligned source離台、clear後RELEASE、10007 failure repair、branch metrics
  與spike-only exact non-regression。診斷工具另鎖`enable_spring_escape=false`，確保
  Oracle升版後仍可重播歷史失敗。
- Development 11000～11099與untouched holdout 12000～12099均100/100 reach10；spring
  30/30、29/29，top/health death 0。Holdout Baseline 15.76 vs 15.55、retention101.35%、
  reach3 94%、spring early top 0/40，狀態`PASS_SPRING_ORACLE_ESCAPE_AND_BASELINE`。
- 未開遊戲、未送鍵、未生成Dataset或訓練。Spring Simulator分布Gate解除，但實機fidelity、
  conveyor/flipping與support shadow仍阻擋後續Student。
- Spring／Oracle相關36 tests與完整482 tests PASS（70.32s）；compileall、artifact
  JSON、candidate source/protocol fingerprint與`git diff --check`全部PASS。

## 2026-08-03 Simulator v0.3 Edge／Playfield Fidelity

- 由使用者指出新版影片仍從平台中央穿越後，test-first建立support ownership與
  edge-departure invariant；新測試在舊物理4/4失敗，實作後通過。
- 實機alignment packet的2,083個platform detections確認場地x=40～423；影片首幀
  player (232,337.5)、scroll約96 px/s。generator／clamp／renderer／top hazard與初始
  位置全部改用同一實機幾何。
- v1/v2 Gate仍使用全畫布，保留但作廢為fidelity證據。正式v3 Engineering與
  Reachability PASS；Oracle development reach3 100%、reach10 48%、mean8.72、
  52 top deaths、0 edge violations，狀態`FAIL_STOP_ORACLE_DEVELOPMENT`。
- 依序未跑Baseline與14000～14099 holdout；沒有Dataset、Student、RL或實機操作。
- 已產生舊／新、實機片段、兩組並排MP4、montage與manifest；人工驗收後才能進
  bounded top-pressure修正，特殊平台舊PASS不得沿用。
- 完整490 tests、compileall、JSON／MP4 reopen及diff check全部PASS。

## 2026-08-03 Top-Pressure Departure Commit Gate

- 使用者人工確認v0.3基本左右離台影片正常，依新凍結協議解鎖單一bounded候選。
- seed13009證明top-pressure在同一support tenure換target會使stateless Oracle中途反向；
  v5鎖定來源與出口方向，離邊後才重規劃，固定測試PASS。
- Formal v4 mean 8.72→8.93，但reach10仍48%、top deaths仍52；死亡樓層後移但成功數
  不變，狀態`FAIL_STOP_ORACLE_DEVELOPMENT`。
- Baseline與holdout未執行；不追加第二個heuristic。下一步需另凍結action-conditioned
  route planner，而非放寬門檻或開始訓練。
- Targeted 14 tests、完整491 tests PASS。

## 2026-08-03 Bounded Action-Conditioned Route Planner

- 凍結12-step／24-beam協議；planner直接用Simulator snapshot重播三動作，trigger由
  top headroom／scroll時間決定，沒有調physics、場地或門檻。
- snapshot/restore鎖定state、RNG與platform object identity；ordered departure records
  可表達同一control step內landing後再次離邊，event-time clearance可稽核。
- 20-seed micro由v5 reach10 60%改善至v6 95%、top0、edge violation0；seed13009
  固定失敗由floor6 top修復為floor10。
- Formal 100-seed Oracle mean10.20、reach3 100%、reach10 96%、0 violations，PASS。
  Baseline mean5.03但reach3 73%、top88，FAIL；holdout依序未執行。
- 不生成Dataset、不啟動訓練或遊戲。下一步只允許observable route-intent Gate。
- 完整測試套件：`495 passed`（83.13 秒）。

## 2026-08-04 Observable Support-Extent Route Intent

- 凍結單一可部署候選；development audit發現926個premature support handoff steps，
  100/100 episodes與27/27 early failures均受影響。
- 新候選只沿用PlayerTracker／Simulator nearest-platform既有的AABB overlap語意；
  使用獨立opt-in class，沒有改真實Teacher預設，也沒有privileged input。
- Development由舊Baseline mean5.03／reach3 73%／reach10 12%改善為
  8.26／97%／55%，0 violations、無collapse，PASS。
- 首次holdout Oracle reach3 100%、reach10 93%、4 bottom／3 top，未達95%；狀態
  `FAIL_STOP_ORACLE_HOLDOUT`。candidate holdout未執行，14000～14099退休。
- 未生成Dataset、未啟動任何訓練或實機。下一步先做7個Oracle failure taxonomy，
  再另凍結全新seed protocol。
- Targeted 81 tests與完整498 tests PASS（132.51秒）；compileall通過。

## 2026-08-04 Oracle Holdout Failure Taxonomy

- 在執行前凍結7個retired failure seeds與四模式反事實，不修改production Oracle、不使用
  新development／holdout、不啟動訓練或遊戲。
- current v6的7/7 failure floor／terminal精確重現；14000～14099 generator
  reachability、health safety與reproducibility全部PASS。
- 原trigger＋receding first-action救回4/7；always-receding與24-step／96-beam extended
  皆0/7。主要證據為open-loop execution，3/7保持unresolved。
- 所有planner snapshot restoration與固定search bounds PASS；diagnostic artifact狀態
  `EVIDENCE_OPEN_LOOP_PRIMARY`。
- 已凍結唯一v7 candidate與16000～16099 development、17000～17099 one-time holdout。
  尚未實作或執行新Gate；下一步test-first實作，development FAIL即不得碰holdout。
- 新增taxonomy 7 tests與完整505 tests PASS（117.15秒）；compileall及artifact JSON PASS。
- 產物：`SIMULATOR_ORACLE_FAILURE_TAXONOMY_PROTOCOL.md`、
  `SIMULATOR_ORACLE_FAILURE_TAXONOMY_REPORT.md`、
  `SIMULATOR_ORACLE_ROBUSTNESS_PROTOCOL.md`、
  `artifacts/simulator_oracle_failure_taxonomy_v1.json`。

## 2026-08-04 Oracle v7 Robustness Gate

- test-first新增顯式`receding` execution；舊v6 cached維持不變。相關41 tests與
  compileall在Formal Gate前PASS。
- 16000～16099 reachability／health／reproducibility PASS；v6同批reference reach10
  96%、mean10.35、bottom2／top2。
- v7 reach10只有76%、mean9.49、bottom22／top2；絕對95%及相對v6 non-regression
  同時FAIL，狀態`FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT`。
- 配對為75 both success、3 both failure、1 rescued、21 regressions；retired taxonomy
  的局部4/7改善沒有泛化，v7正式REJECT且只保留opt-in供重現。
- 17000～17099 `used=false`；holdout reachability、Oracle與observable均未執行。
  未生成Dataset、未訓練、未操作遊戲。
- 最終完整回歸520 tests PASS（113.83秒）；compileall、artifact JSON／SHA-256 assertions
  與diff check PASS。
- Artifact：`artifacts/simulator_oracle_robustness_gate_v1.json`；報告：
  `reports/SIMULATOR_ORACLE_ROBUSTNESS_REPORT.md`。

## 2026-08-04 v7 Failure Audit／v8暫停點

- Paired audit固定21 regressions、1 rescue、3 both-failure、10 controls；首次分歧
  release/opposite/fallback=`11/5/5`，未達16/21，狀態`INSUFFICIENT_EVIDENCE_STOP`。
- Terminal-plan補充audit重播完整100個v6 development：成功0/96 exposure、top2/2、
  bottom0/2；retired search failures3/3。狀態`EVIDENCE_TERMINAL_RISK_ISOLATION`。
- 依證據凍結並test-first實作v8 terminal-risk guard；正常plan保留v6 cache，只在
  predicted terminal時bounded replan。43 targeted tests與compileall PASS。
- 正式v8 runner執行約42秒後依使用者要求中止；無artifact、無殘留程序，依既有76秒
  development基準判定尚未進17000 holdout。v8正式狀態為未評估，不是PASS／FAIL。
- 完整暫停總結：`reports/PROJECT_STAGE_SUMMARY_2026-08-04.md`。
