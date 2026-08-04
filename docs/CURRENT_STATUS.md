# Current Status

最後更新：2026-08-04

## 最高優先狀態：v0.4 Calibration Candidate READY_FOR_USER_MANUAL_RETEST

- 修正前v0.3與修正後v0.4 candidate證據已保存；30／60／120 render FPS下固定60 Hz
  physics的landing、terminal與state一致，平台穿越主因不是FPS／timestep。
- 根因是斜向edge crossing時舊碰撞只看substep結束x；候選改以top-surface
  time-of-impact x做swept overlap，診斷案例由穿透改為landing。
- 控制候選：acceleration 1048→560、air multiplier 0.85、RELEASE一個step後速度
  5.6→64、反向進入左移step 3→4；max speed仍230。Scroll 96→80僅待人工確認。
- 平台vertical gap維持48；horizontal shift median 29.78→81.43、Q75 45.79→118.08，
  trivial shift 159/800→0/800，conservative impossible仍0。
- `ShaftEnvConfig()`與舊RNG stream保留凍結v0.3行為；v0.4僅由manual `after` profile
  opt-in，production Oracle hash與formal artifact／protocol hash不變。
- 本輪無game input、無training、holdout仍unused；formal狀態仍
  `BLOCKED_WITH_EVIDENCE`，人工結果不得解鎖Dataset／Student／Colab。
- Engineering verification：185 targeted與587 full tests、compileall、diff check、
  manual headless smoke全PASS。
- Report：`reports/MANUAL_SIMULATOR_CALIBRATION_REPORT.md`；summary：
  `artifacts/manual_simulator_calibration/calibration_summary.json`。

## 前一狀態：Manual Simulator Test READY／Formal仍BLOCKED_WITH_EVIDENCE

- 已新增純Simulator人工鍵盤工具`scripts/run_simulator_manual_test.py`與繁中runbook
  `reports/MANUAL_SIMULATOR_TEST_RUNBOOK.md`；不載入真機input backend、不尋找或啟動
  `NS Shaft.exe`。
- 15個handcrafted場景M01～M15可固定切換；spring、conveyor left/right、spikes、
  flipping active/inactive與normal-platform healing均可測但明標`PROVISIONAL`。專案仍無
  獨立`healing` platform kind，該項為unsupported。
- Manual seed強制>=900000並記錄`role=manual_only`、
  `formal_evaluation_allowed=false`；17000與19000 holdout均未使用。
- Headless CLI smoke PASS；focus-loss release、reset、pause、scenario switch、overlay與log
  全通過。Smoke輸出：
  `artifacts/manual_simulator_test/manual_20260804_184049_412824/`。
- Manual＋Simulator targeted tests 79 PASS、完整回歸579 PASS；compileall與diff check PASS。
- 人工工具不算formal Gate或Alignment PASS。Production Oracle、physics、generator、
  frozen protocol與formal artifacts均未修改；Dataset／Student／Colab狀態不變。

### Formal研究狀態維持：Branch Development FAIL／BLOCKED_WITH_EVIDENCE

- Phase C已從頭完整執行18000～18099；paired v6／candidate reach10為90%／93%，candidate
  修復3/4個v6 top failures，0個v6-success regression。
- Candidate相對改善且top 4→1、CVaR25 7.96→8.36、bottom維持6，但絕對reach10仍低於
  凍結95%門檻；唯一failed check為`reach_floor_10_at_least_0.95=false`。
- 其餘checks全PASS：relative reach、repair、bottom／health／safety、no collapse、
  non-terminal v6 identity、switch inflation≤5%、duplicate replay、bounds與reachability。
- 正式狀態`FAIL_STOP_BRANCH_PRESERVATION_DEVELOPMENT`，artifact SHA-256
  `e4952a8332f7c2a25acb564e28a8b47b9b733e4c4bb073f19eade79501cd9758`。
- 19000～19099 holdout仍unused；18100～18199未執行（primary v6已有4個top failures）；
  17000仍unused且禁止轉用。Alignment、Teacher、Dataset、Student、Colab全部NOT RUN。
- Formal report：`reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_REPORT.md`；artifact：
  `artifacts/simulator_oracle_branch_preservation_development_v1.json`。

### 前一狀態：Phase B PASS／Branch Development即將執行

- Current-State Verification為`CONSISTENT`：branch／HEAD、working tree、核心hashes與
  Phase 2F artifact相符；背景遊戲／Python／TensorBoard／training為0，17000未使用。
- Cross-lane selector audit在14/14 rescue triggers使用既有`max(score)`都選到RIGHT
  survivor；不需修改selector或score。
- 已凍結唯一變因protocol：terminal-risk時RELEASE／LEFT／RIGHT各自完整12-step／24-beam，
  既有selector選winner並cache完整suffix；normal paths必須與v6完全一致。
- Seed ledger確認18000～18099 primary development、條件擴充18100～18199及19000～19099
  one-time holdout從未實際使用。17000仍unused但永久禁止轉用。
- Phase A狀態`READY_FOR_TEST_FIRST_IMPLEMENTATION`；Phase B先確認tests FAIL，再完成最小
  production實作。新增19 targeted tests與完整559 tests、compileall、diff check全PASS。
- Implementation hashes已凍結於
  `artifacts/simulator_oracle_branch_preservation_implementation_v1.json`；現依序進Phase C。
  當時尚未跑新formal seeds、Alignment、Dataset、Student或Colab。
- Protocol：`reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_PROTOCOL.md`；artifact：
  `artifacts/simulator_oracle_branch_preservation_protocol_v1.json`；ledger：
  `artifacts/simulator_oracle_branch_preservation_seed_ledger_v1.json`。

### 前一狀態：Phase 2F COMPLETE／v8 RETIRED／BLOCKED_WITH_EVIDENCE

- Offline Oracle Failure Design Review已完成；v8 formal結果維持
  `FAIL_STOP_V8_DEVELOPMENT`，沒有事後改判。
- 22個terminal-plan calls（2 entry＋20 replans）全都產生與v6 cached suffix完全相同的
  RELEASE計畫；0個same-first/different-suffix，selected actions全數確實執行，snapshot／
  restore與paired state equality全PASS。
- 相同12-step／24-beam bounds按first action隔離後，找到14個RIGHT counterfactual可完整
  reach10：16002為step 39～46，16030為step 51～56。不是只延後死亡。
- 14/14成功路徑在共享beam depth 4因intermediate score rank 35～39而被beam=24剪除。
  根因為`BEAM_PRUNING_LIMITATION`／score-induced branch extinction；trigger在不可避免點前
  8／6 decisions已啟動，horizon、commit、overwrite與snapshot不是主因。
- 方向判定：D first-action diversity／branch preservation為
  `SUPPORTED_FOR_NEW_PROTOCOL`；A/B/E `REJECT`；C/F/G `INSUFFICIENT_EVIDENCE`。
- v8是安全但無效的no-op candidate，正式淘汰、只留重現。下一步僅允許撰寫及審查全新
  branch-preserving protocol；尚未批准production實作或formal Gate。
- 17000～17099仍`used=false`；Dataset、Student、Colab、實機與所有訓練維持BLOCKED。
- Report：`reports/SIMULATOR_ORACLE_V8_PHASE2F_DESIGN_REVIEW.md`；artifact：
  `artifacts/simulator_oracle_v8_phase2f_review_v1.json`。

### 前一狀態：Oracle v8 Development FAIL／BLOCKED_WITH_EVIDENCE

- Engineering Gate完整通過：529 full tests、66 v8/protocol targeted tests、compileall與
  `git diff --check` PASS。
- Oracle v8 formal development已從頭完整執行16000～16099；v6/v8 reach10均為
  96%，mean 10.35、Q25 10、CVaR25 9.44、bottom/top均為2/2。
- Paired outcomes為96 both-success、0 v6-only、0 v8-only、4 both-failure；100/100
  action sequences相同。v8多20次terminal-risk replans，但沒有救回任一top failure。
- Frozen check `v6_top_failures_repaired_at_least_one=false`，因此正式狀態為
  `FAIL_STOP_V8_DEVELOPMENT`。安全、health、reproducibility、collapse、switch、
  non-terminal identity其餘checks全部PASS。
- 17000～17099 holdout仍`used=false`；Dataset、Student、Colab training與實機全部
  BLOCKED。下一步只允許Phase 2F offline design review，不直接建立v9。
- Formal artifact：`artifacts/simulator_oracle_v8_terminal_guard_development_v1.json`；
  report：`reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_DEVELOPMENT_REPORT.md`；
  journal：`artifacts/colab_readiness_stage_journal.json`。

### 前一狀態：DELTA HANDOFF READY；v8正式Gate尚未評估

- Snapshot：branch `agent/simulator-learnability-colab`、HEAD `745dc70`；working tree
  32 modified／110 untracked、無staged changes，既有修改不可還原或清除。
- 無Python／TensorBoard程序；v8 formal artifact不存在。前次中止run無artifact且不可使用。
- Current blocker：v8只有CODE／targeted-test evidence，尚缺post-v8完整pytest與有效formal
  development artifact；v6 holdout 93%，v7 development 76%且已REJECT。
- Current phase：Simulator v0.3 Oracle v8 Engineering Gate待完整回歸；之後才是v8 formal
  development。16000～16099已是development；17000～17099仍UNUSED one-time holdout。
- 已完成只保留一行：基礎安全／schema／Gym／Colab、P3.6、P4.0、P4.1判定、v0.3 edge、
  v6／route-intent development、taxonomy、v7與兩個後續audit均不重做。
- Latest valid formal Gate與terminal-audit的recorded source／protocol hashes全部match；v8
  frozen protocol SHA-256為`78df06c393ff8123d559a98657fadbd791eee3ce3f532aa6a3fabe2cc3f5289e`。
- Dataset／Student／Colab training／實機全部BLOCKED；本輪未執行formal experiment或holdout。
- 權威delta：`reports/NEXT_WORK_DELTA_2026-08-04.md`。

### 前一狀態：Oracle v7 Development FAIL／STOP；新holdout未使用

- `oracle-full-v7-receding-route-planner`已依凍結protocol test-first實作；v6 cached
  mode保留，v7只在原trigger後每decision重算plan並執行第一個action。
- 全新16000～16099 reachability／health safety／reproducibility全部PASS。
- 同批v6 reference reach10 96%、mean10.35、bottom2／top2；v7只有reach10 76%、
  mean9.49、bottom22／top2。絕對95%與相對v6 non-regression兩項均FAIL。
- 配對結果為75 both success、3 both failure、1個v6 failure被救回、21個v6 success
  被v7破壞。retired 7-seed的4/7改善沒有泛化，v7正式REJECT。
- 狀態`FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT`；17000～17099 holdout的used=false，
  reachability／Oracle／observable均未執行。
- 不生成Dataset、不訓練、不開遊戲、不進特殊平台重驗。v7只保留opt-in供artifact重現。
- Gate前相關41 tests PASS；最終完整回歸520 passed（113.83秒）；compileall、artifact
  JSON／SHA-256 assertions全部PASS。
- 下一步限先凍結16000 development paired trace audit，查21個新bottom failures的首次
  action divergence／方向切換／score不連續；證據前不實作第二候選、不碰holdout。
- 詳細報告：`reports/SIMULATOR_ORACLE_ROBUSTNESS_REPORT.md`。

### 前一狀態：Oracle failure taxonomy完成；v7 robustness protocol已凍結

- 第一次正式holdout的7個Oracle v6 failures已全部逐一重現；14000～14099靜態
  reachability、health safety與seed reproducibility全部PASS。
- 固定反事實結果：current v6 0/7；保留原trigger、每decision重算plan為4/7；
  always-receding 0/7；24-step／96-beam extended always-receding仍0/7。
- 因此主要證據支持open-loop cached plan execution是首要責任，不支持提早到每步規劃，
  也不支持擴大搜尋。另有3/7仍unresolved，不能宣稱已完整修復。
- 唯一批准候選為`oracle-full-v7-receding-route-planner`：只改原trigger後的plan執行，
  每個decision重算並只取第一個action；不改trigger／12-step／24-beam／score／physics。
- 新protocol已在實作與執行前凍結：development 16000～16099；只有全部Gate PASS才可
  首次使用holdout 17000～17099。舊14000～14099永久只作diagnostic。
- 本階段未修改production Oracle、未消耗新seed、未生成Dataset、未訓練、未開啟遊戲。
- 診斷targeted tests：7 passed；完整回歸505 passed（117.15秒）；compileall與
  taxonomy artifact JSON驗證通過。
- 下一步是test-first實作v7並先跑全新development Gate；未PASS不得碰新holdout。
- 詳細報告：`reports/SIMULATOR_ORACLE_FAILURE_TAXONOMY_REPORT.md`；下一協議：
  `reports/SIMULATOR_ORACLE_ROBUSTNESS_PROTOCOL.md`。

### 前一狀態：Route Intent Development PASS；Oracle Holdout FAIL／STOP

- development trace 找到926個「Simulator仍supported、policy已判airborne」steps；
  100/100 episodes與27/27 early failures均受影響。根因是policy把tracker既有的AABB
  overlap又縮成player-center-in-platform，造成離台route intent過早解除。
- 獨立候選`teacher-observable-v5-support-extent-route-intent`只沿用可部署的tracker
  overlap，不讀Simulator state/future；真實Teacher預設沒有被切換。
- Candidate development：mean8.26、reach3 97%、reach10 55%、top45、0 violations、
  無collapse，Baseline Gate PASS。
- 首次14000～14099 holdout先跑Oracle；Oracle reach3 100%但reach10只有93%（門檻95%），
  4 bottom／3 top，狀態`FAIL_STOP_ORACLE_HOLDOUT`。
- Observable candidate holdout未執行；這組holdout已退休，Dataset與所有訓練維持blocked。
- 本輪完整測試：`498 passed`（132.51 秒）；compileall通過。
- 下一個唯一工作是對7個retired Oracle failures做bounded taxonomy，再另凍結全新
  Oracle robustness protocol／seed partitions；不得重跑或調低95%門檻。
- 詳細報告：`reports/SIMULATOR_OBSERVABLE_ROUTE_INTENT_REPORT.md`。

### 前一狀態：v0.3 Route Oracle Development PASS；Baseline Development FAIL

- 新的`oracle-full-v6-bounded-route-planner`使用可還原Pymunk snapshot、12-step／24-beam
  action search；trigger由頂刺headroom與scroll時間計算，不改physics或Gate門檻。
- Formal v5 Oracle development：mean10.20、reach3 100%、reach10 96%、top3、bottom1、
  0 edge violations，全部Oracle checks PASS。
- Baseline development：mean5.03達標，但reach3只有73%（門檻90%）、reach10 12%、
  top death 88；狀態`FAIL_STOP_BASELINE_DEVELOPMENT`。
- 依序停止，holdout 14000～14099仍未使用；Dataset與所有Student／RL訓練維持blocked。
- 本輪完整測試套件：`495 passed`（83.13 秒）。
- 下一步必須建立只用學生可觀測player/platform/headroom/causal history的deployable
  route intent，不能把privileged snapshot search當Teacher label。
- 詳細報告：`reports/SIMULATOR_V03_ROUTE_PLANNER_REPORT.md`。

- 使用者已人工驗收實機／v0.3並排影片，確認基本左右離台視覺看起來正常；已解鎖
  bounded top-pressure departure-commit Gate，但不等於1:1或訓練解鎖。
- 唯一v5候選鎖定同一support tenure的出口方向，修掉seed13009因top-pressure retarget
  中途折返；相關14 tests PASS。
- Formal v4 development mean由8.72升至8.93，但reach10仍48%、top deaths仍52；
  只有死亡樓層向後移。狀態`FAIL_STOP_ORACLE_DEVELOPMENT`，Baseline／holdout未執行。
- 下一步不能再堆top-pressure heuristic；需另凍結action-conditioned短視窗route planner，
  同時估計離邊耗時、頂刺時間與跨層可達性。
- 本輪驗證：targeted 14 tests與完整 **491 tests passed in 101.25s**。

- 實機 episode 3 影片與 2,083 個 platform detections 證實舊 Simulator 有兩個
  基礎錯誤：普通平台可直接穿透角色，且把 634 px 全畫布誤當可玩區。
- v0.3 改為 support ownership：接觸時隨平台上捲，完整離開來源平台 AABB 左右緣後
  才下墜；playfield 固定 x=40～423、y=60～416，頂刺下緣 y=88，初始角色
  (231.5,338.5) 對實機 (232,337.5)。
- 正式 v3 Gate：Engineering、Reachability 100／1,000 PASS；Oracle development
  mean 8.72、reach-3 100%、reach-10 48%、52 top deaths、0 edge violations。
  狀態 `FAIL_STOP_ORACLE_DEVELOPMENT`；Baseline與 holdout 14000～14099 未執行。
- 舊 v0.2 Spring／Oracle／Baseline PASS 與 v0.3 v1/v2 全畫布結果均降為歷史診斷，
  不得用於新版訓練解鎖。
- 已輸出新版、舊版、實機片段、兩組並排影片與 montage；下一步先人工驗收基本離邊
  語意，再做 bounded top-pressure／跨層規劃修正。特殊平台需在新語意下逐一重驗。
- 本輪沒有開始 Dataset、BC、DAgger、PPO、DQN、NEAT 或任何實機操作。
- 詳細報告：`reports/SIMULATOR_V03_EDGE_FIDELITY_REPORT.md`。
- 驗證：完整 **490 tests passed in 104.51s**；compileall、4個新增JSON、4支主要
  edge MP4的codec／幀數／尺寸與`git diff --check`全部PASS。

### 前一狀態：Spring Oracle Escape／Baseline PASS；整體 Alignment 仍 BLOCKED

- Spring失敗trace證明29個top deaths全在第2～4次contact後發生，0個是first-bounce
  direct top；失敗後動作RELEASE/LEFT/RIGHT=`547/73/71`。既有真機308 records雖有
  159筆可見spring、7筆target spring，卻有0個confirmed spring event／vertical pair，
  因此沒有猜改190 px/s。
- 唯一候選`oracle-full-v2-spring-clearance`只修privileged Oracle：先離開spring
  footprint＋2 px，通過source高度後再恢復下一層target tracking。真機Teacher不變。
- Development 11000～11099：overall與spring-conditioned reach10均100%，spring 30回合，
  top／health death 0。
- Untouched holdout 12000～12099第一次執行：overall與spring-conditioned reach10均100%，
  spring 29回合，top／health death 0；Q25/CVaR25皆10。
- Holdout Baseline PASS：15.76 vs spike-only 15.55，retention 101.35%；reach3 94%、
  0 health death、無collapse、40個spring episodes的early top為0。
- Spring distribution的Simulator Gate已解除，但這不是實機physics或Teacher PASS。
  下一步先做conveyor/flipping低比例Gate與phase-aware support shadow；全部離線通過後，
  才安排一次受監督真機驗證。Dataset v2與Student長訓仍BLOCKED。
- 產物：`SPRING_FAILURE_TRACE_FIDELITY_REPORT.md`、
  `SPRING_ORACLE_ESCAPE_GATE_REPORT.md`、`spring_failure_fidelity_audit_v1.json`、
  `spring_oracle_escape_gate_v1.json`。
- 驗證：spring／Oracle相關36 tests與完整 **482 tests passed in 70.32s**；compileall、
  artifact JSON、candidate source/protocol fingerprints與`git diff --check`全部PASS。

### 前一狀態：Spring Curriculum v0 Oracle FAIL／STOP

- 依D-071先處理第一個缺失分布spring；協議在實作與執行前凍結，基於既有
  spike curriculum加入6% spring proposal、前3層normal、spring前3個normal，並保持
  spikes間5個真正normal。Conveyor／flipping沒有混入。
- Engineering、Reachability 100／1,000與spawn ratios全部PASS：1,000 seeds共9,000
  platforms，normal/spikes/spring=`8325/432/243`，比例為92.50%／4.80%／2.70%，
  0 unreachable、0 unsafe；feature-off 100 seeds序列完全相同。
- Oracle固定10000～10099只達71% reach-floor-10，低於95%；0 health death且35個回合
  有spring coverage。沒有spring的65/65全成功，有spring的35回合僅6成功、29個全為
  top death，失敗前各有2～4次spring contact。
- 狀態為`FAIL_STOP_ORACLE`。Baseline依順序未執行；Dataset v2、BC、DAgger、PPO、
  DQN、NEAT、conveyor/flipping分布與實機候選全部維持BLOCKED。6000～6099未使用。
- 下一步只准先做Spring Failure Trace／Fidelity Audit，分離190 px/s provisional physics、
  top/camera semantics與Oracle escape責任；不得事後降門檻或重用正式seeds調參。
- 產物：`reports/SPRING_CURRICULUM_V0_PROTOCOL.md`、
  `reports/SPRING_CURRICULUM_V0_REPORT.md`、
  `artifacts/spring_curriculum_v0_gate.json`。
- 驗證：相關63 tests與完整 **475 tests passed in 69.02s**；compileall、JSON／
  source／protocol fingerprint及`git diff --check`全部PASS。

### 前一狀態：Simulator／Real Alignment Audit FAIL／STOP

- 第二次受監督真機run已取得3 episodes／308 records，alignment Integrity／Coverage全部
  通過；target geometry match 96.39%，ordinary／edge／spring／spikes／wall coverage為
  225／56／7／20／12。Packet只作diagnostic，仍不可直接當Student資料。
- 已在執行前凍結Simulator/real audit，使用主要通過run、第一次低表現run與Simulator
  診斷seeds 8000～8029；fresh reliability 6000～6099未使用，沒有再開遊戲或送鍵。
- 時間與基本動作反應PASS：真機median cadence 125 ms、Simulator 100 ms；兩者LEFT
  median delta-vx<0、RIGHT>0，各action皆有至少10筆。
- 平台分布FAIL：真機重要kinds包含normal/spikes/spring/conveyor/flipping；Simulator
  mechanism雖已實作五類，一般Teacher分布實際只生成normal/spikes，缺後三類。
- Support phase FAIL：主要真機rising-support為125/308（40.58%）、最長11步；Simulator
  311/1838（16.92%）、最長2步。主要run episode 3 step47由同source 12連續8個rising
  support records觸發departure timeout，step50同source restart，確認phase alias。
- 主要run有5次同一次support departure方向反轉，Simulator為0；因此使用者看到的多餘
  左右移動會污染sequence labels，不能因最好樓層較高就pass Teacher dataset。
- 狀態為`FAIL_STOP_SIMULATOR_REAL_ALIGNMENT`。Dataset v2、BC、DAgger、PPO、DQN、
  NEAT及P4.2仍BLOCKED；下一步只准先做mixed-special低比例generator Gate，以及使用既有
  packet的phase-aware support ownership shadow replay，不直接實機試錯。
- 產物：`reports/SIMULATOR_REAL_ALIGNMENT_AUDIT_PROTOCOL.md`、
  `reports/SIMULATOR_REAL_ALIGNMENT_AUDIT.md`、
  `artifacts/simulator_real_alignment_audit_v3.json`。
- 驗證：新增6 tests、相關14 tests、完整 **468 tests passed in 63.52s**；compileall、
  artifact JSON/source fingerprint與`git diff --check` PASS。

### 前一狀態：Real Alignment Packet `PASS_REAL_ALIGNMENT_PACKET`

- `real-alignment-packet-v1`同步保存structured observation/next、pre/post memory、target
  geometry、四時間點與MP4 frame indices；raw ID只供同幀診斷。
- 第一次run 136 records因缺spring/wall coverage停止；第二次run 308 records通過全部
  Integrity/Coverage checks。Real Teacher performance Gate仍因1 timeout／1 same-support
  cycle FAIL，沒有被alignment PASS覆寫。
- Runner旁路沒有改Teacher action或安全鏈；alignment PASS只解鎖本次audit。

### 前一狀態：Observation-Schema Probe `INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE`

- 已依執行前凍結的7000～7399 splits完成400-episode bounded probe；test 7300～7399只
  評估本次一次，保留的fresh reliability seeds 6000～6099完全未使用。
- Delayed2 base／launch-handoff的reach為76.25%／69.25%、bottom為23.75%／30.75%、
  Q25為10／8、CVaR25為5.14／4.04；handoff在更大獨立樣本仍全面退化。
- 395/400有首次action divergence；終局只有1 improved、29 regressed、365 unchanged，
  另5個無分歧。補充重播確認5個的base/candidate floors完全相同。
- development沒有任何improved case，故4組schema的5-NN balanced accuracy均不可評估；
  不是0分，也不能以唯一改善seed擬合新rule。Gate因changed 30<40及improved 1<10停止。
- 384/395 rows有可見且成功配對的target geometry；資料欄位完整有限且沒有raw identity或
  privileged feature。但凍結協定將vx列入phase_basic，執行版只在causal/combined含vx；
  此偏差已公開記錄，不重用test split，也不宣稱完成schema可分性比較。
- 狀態固定為`INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE`。沒有修改controller、沒有訓練、
  沒有開啟原版遊戲，且不新增Teacher候選、不跑fresh100、不生成Dataset v2。
- 下一個唯一合理方向是由使用者監督的bounded真機alignment packet：同步保存frame／
  observation、action timing、previous action/hold、landing recency、target safe interval及
  spring/spike/edge/wall短序列。先對齊真機與模擬器語意，再凍結新Gate。
- 產物：`reports/SIMULATOR_OBSERVATION_SCHEMA_PROBE_REPORT.md`、
  `artifacts/simulator_teacher_observation_schema_probe_v1.json`。
- 驗證：schema／Teacher相關 **14 tests passed in 6.04s**；完整
  **457 tests passed in 162.51s**。Artifact JSON、凍結協定／source fingerprints、
  compileall與diff check均PASS。

### 前一狀態：Phase Observability Audit `INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL`

- 已在delayed2同一批seeds 2000～2059旁路重播decision-level觀測；base trace SHA、
  performance及60/60首次action分歧step均完整重現來源Launch-Handoff artifact。
- 首次介入終局只有2個改善、6個退化、52個不變；changed>=20、improved>=10、
  regressed>=10的固定證據量門檻皆FAIL。
- 8種可部署phase signatures中，有一個相同簽章同時包含1改善、2退化與7不變；
  `steps_since_landing_event`、privileged phase及nearest-is-last-landed也未能分開結果。
- 60回合共有936個support-heuristic rows，其中876為rising；它是bounce附近幾何重疊，
  不是可靠的stable-support phase訊號。
- 狀態固定為`INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL`。沒有改controller、沒有使用fresh
  seeds、沒有正式v2、Student訓練或真機操作。
- 下一個唯一允許工作是bounded observation-schema probe：只評估可由真機因果重建的
  landing recency、past-action commitment、來源／目標safe interval相對幾何；先過
  held-out可分性稽核，才准提出一個新Teacher候選。不得再堆heuristic。
- 產物：`reports/SIMULATOR_TEACHER_PHASE_OBSERVABILITY_AUDIT.md`、
  `artifacts/simulator_teacher_phase_observability_audit_v1.json`。
- 驗證：phase／observer targeted 6、完整 **454 tests passed in 178.57s**；compileall、
  artifact JSON/source fingerprint與diff check PASS。

### 前一狀態：Launch-Handoff Gate `FAIL_STOP_LAUNCH_HANDOFF_SAME_SEED`

- Delayed2 base的trace SHA、summary與60個per-seed floors完整重現前一artifact，確保本輪
  只有一個新變因：Simulator-only support-aware launch handoff。真機與legacy default關閉。
- Base/candidate reach=`81.67%/75%`、bottom=`18.33%/25%`、Q25=`10/9.5`、
  CVaR25=`6.27/4.2`、reversal=`9.06/10.36`。候選明確退化且Gate FAIL。
- Candidate相對base有6個success→bottom、2個bottom→success；launch rows 736→991，
  support-departure 117→0，wall guard 223→314。handoff precedence過度觸發並完全吃掉
  departure phase；branch count較接近v1不代表時序正確。
- `selected_profile=null`、fresh6000～6099未使用、正式v2未生成、Student未訓練、遊戲未開。
- 下一個唯一允許工作是decision-level phase observability audit，不改controller：記錄
  events/motion/vy/gap/geometry/target/support，privileged last-landing只作診斷label。
  若deployable features不能分離phase，應升observation/schema，禁止再堆heuristic。
- 產物：`reports/SIMULATOR_TEACHER_LAUNCH_HANDOFF_GATE_REPORT.md`、
  `artifacts/simulator_teacher_launch_handoff_gate_v1.json`。
- 驗證：handoff／profile／policy／dataset related 90、完整 **451 tests passed in
  174.77s**；compileall、artifact JSON、source fingerprint與diff check PASS。

### 前一狀態：Simulator Teacher Profile Gate `FAIL_STOP_SAME_SEED_RELIABILITY`

- 已將Real-game與Simulator Teacher分離；真機policy預設行為不變。Simulator profiles為
  `current`、`departure_delayed`（2 steps）、`departure_disabled`，各有獨立v3 version。
- 同seeds 2000～2059結果：current reach/bottom=`75%/25%`；delayed=
  `81.67%/18.33%`；disabled=`76.67%/23.33%`。三者health death皆0。
- Delayed是最佳候選，Q25/CVaR25=`10/6.27`、reversal=9.06/100，但仍未達
  reach>=91.33%、bottom<=8.67%；action TV=0.207亦超過0.10。三者Gate全FAIL。
- `selected_profile=null`，fresh 6000～6099未使用，正式Dataset v2未生成，Student未訓練，
  原版遊戲未啟動。不得以delayed的局部改善放行。
- 首次分歧median由current step1延到step6；delayed的53/60首次reason分歧是
  `escape_launch_platform -> aligned_with_safe_platform`。v1/current/delayed/disabled
  launch rows=`1692/545/736/773`，顯示離台只是一部分，下一個最小根因是假support
  contact阻擋launch handoff。
- 下一個唯一允許工作：以delayed為base，測試單一Simulator-only support-aware launch
  handoff；先unit scene後同60 seeds。禁止delay sweep、fresh100、Dataset v2或Student。
- 產物：`reports/SIMULATOR_TEACHER_PROFILE_GATE_REPORT.md`、
  `artifacts/simulator_teacher_profile_gate_v1.json`。
- 驗證：profile／policy／dataset related 88、完整 **449 tests passed in 197.56s**；100k既有
  headless smoke為主要耗時（163.06s），新增6-seed integration僅0.62s。compileall、
  artifact JSON parse與`git diff --check` PASS。

### 前一狀態：Dataset v2 Gap Audit `FAIL_STOP_BEFORE_V2_GENERATION`

- Dataset v2 Gap Audit 已完成；它是離線資料／策略稽核，沒有訓練、沒有開啟遊戲、
  沒有使用 P4.1 final seeds，也沒有產生正式 Dataset v2。
- 凍結 Dataset v1 與 current Teacher 使用完全相同 seeds 2000～2059。v1 的
  target/bottom 為 56/4（reach 93.33%、bottom 6.67%）；current diagnostic 為
  45/15（reach 75%、bottom 25%），health death 皆為 0。
- 60/60 episodes 都在 step 1 分歧；57 次首次 reason 從
  `aligned_with_safe_platform` 變成 `depart_support_platform`。14 個 v1 success
  seeds 在 current Teacher 變成 bottom，只有 3 個反向改善。這把候選問題定位到
  simulator support-departure lifecycle，但 trajectory 分岔後不能宣稱它是唯一原因。
- Current diagnostic 的 RELEASE share 由 37.63% 升到 48.42%，方向反轉由
  10.14 升到 11.06/100 steps，action distribution TV=0.10787。舊 Dataset Gate
  因沒有 reach/bottom 條件仍判定 PASS，已確認會 false positive。
- 已凍結 Dataset v2 readiness Gate：policy version/fingerprints、同種子 reach>=91.33%、
  bottom<=8.67%、health death=0、action TV<=0.10、critical branch split／episode
  coverage；全部通過後才可跑 fresh 100 seeds（reach>=90%、bottom<=10%）。
- 本輪 `v2_ready=false`。下一個唯一允許工作是分離 Simulator Teacher profile，
  依序比較 current、normal-support departure delayed、disabled 三個 bounded 候選；
  未過同種子 Gate 不得跑 fresh100，更不得啟動 BC／DAgger 或 P4.2。
- 產物：`reports/P41_DATASET_V2_GAP_AUDIT.md`、
  `artifacts/p41_dataset_v2_gap_audit.json`。
- 驗證：Dataset audit targeted 3、P4.1 related 28、完整 **441 tests passed**；
  compileall、artifact JSON parse與`git diff --check` PASS。

### 前一結果：P4.1 Colab bounded Gate `FAIL_STOP_SELECTION_CONFIRMED`；P4.2 BLOCKED

- 使用者提供的正式結果 `20260803T085551Z_p41_ablation.zip` 完整可讀，archive
  SHA-256 為 `b1fd2291d4b84bafc1a4fba0822341e56b1c075ff963d6aae2f53aeb35bc2926`；內含
  summary、manifest與S0～S3各三個selected checkpoints。資料仍是凍結的60 episodes／
  3,529 rows，SHA-256 `fa3e111a...`，沒有資料漂移。
- 正式三初始化selection結果為 **FAIL_STOP_SELECTION**；沒有enhanced architecture
  通過，故4100～4139 final seeds完全未使用。不得以本次結果調參後再碰final seeds，
  P4.2 rare-branch dataset與後續DAgger／NEAT／RL維持BLOCKED。
- 三初始化平均：S0 mean/Q25/CVaR25/reach-10/bottom=`54.83/33.58/18.27/88.3%/13.3%`；
  S1=`62.18/44.25/17.00/85.0%/18.3%`。S1改善mean與Q25，但最差尾端、reach及bottom
  退化，故不能因較高平均值放行。S2 bottom 50.0%、S3 bottom 98.3%，兩者淘汰。
- Audit另發現兩個工程問題：P4.1 checkpoint selection把reach排在bottom之前，與全域
  risk-first排序不一致；現有`direction_switches`只計相鄰LEFT↔RIGHT，忽略經RELEASE
  的反轉。S0該值僅0.005／100 steps，要求改善0.10在數學上不可能。即使移除這個錯誤
  check，S1仍因CVaR25、reach-10與bottom退化而FAIL，故本輪科學結論不變。
- 已修正selection priority與release-bridged reversal telemetry，並只用保存的S0/S1
  checkpoints在4000～4019 selection seeds重播；6/6 checkpoint provenance通過，舊
  closed-loop指標與per-episode deepest floors完全重現。沒有訓練，final seeds未使用。
- 新metric顯示S0三初始化平均10.05 reversals/100 steps，S1為10.73；S1相對退化
  0.679，三個初始化delta皆為負。修正後Gate仍為`FAIL_STOP_SELECTION_CONFIRMED`，
  failed checks另包含oscillation一致性與mean non-regression，原科學結論更強而非翻盤。
- 下一個唯一允許工作是 **P4.1 Dataset v2 Gap Audit**：先比較凍結v1與current Teacher
  的policy/version、episode長度、動作、branch、early-bottom/recovery coverage，提出
  新dataset的可靠性與coverage Gate。Audit完成前不得生成v2、重跑Colab、使用4100～4139
  或進P4.2。
- 修正後targeted 25 tests與完整 **438 tests passed**；compileall、兩個P4.1結果JSON、
  diff check均PASS。ZIP／PT／遊戲／本機設定未加入工作樹。
- 結果摘要：`artifacts/p41_colab_result_digest.json`、
  `artifacts/p41_checkpoint_reanalysis_v1.json`；完整分析已更新
  `reports/SEQUENCE_MODEL_ABLATION.md`。

### P4.1 本機 preflight／介面成果（前置工程已 PASS）

- 已凍結 `artifacts/p41_experiment_manifest.json`：唯一訓練資料為 Spike Teacher
  Dataset v1，60 episodes／3,529 rows，SHA-256
  `fa3e111a6204ac53767824e8d71d1ccf841637976427c410c1e14dff308c7a0a`；split、Teacher
  version、S0～S3架構、sequence length 24、burn-in 8、hidden 128、300 updates、
  candidate updates 100／200／300、三初始化與selection/final seeds均已凍結。
- S1／S3只使用由模型自身`action<t`重建的9維causal action state；episode第0步
  全零，reset不carry。S3為22維最新幀compact observation＋9維state。當步post-decision
  controller sidecar、未來observation、privileged simulator state與raw IDs全部拒絕。
- 已完成dataset loader、episode/seed/sequence split防洩漏、chunk、padding、loss mask、
  每row只計loss一次、GRU hidden reset、policy causal reset、checkpoint save/load與
  closed-loop reset測試。S0～S3各2-update synthetic training均PASS。
- 本機真實Dataset interface smoke已執行：S0～S3各4 updates、development seeds
  3900／3901，所有finite training、checkpoint round-trip與2回合closed-loop checks
  共12/12 PASS，狀態`INTERFACE_PASS`。兩回合結果只證明介面；四組bottom rate皆1.0，
  不構成科學Gate，S2短樣本mean deepest 9.5也不得當作優勝證據。
- 可重現性檢查發現current source重建同名Dataset v1會得到3,571 rows、SHA-256
  `04417d...`，與凍結資料不同；Teacher程式後續已變更但policy version未升版。依
  D-061禁止Colab重建，正式bundle必須攜帶凍結JSONL並核對manifest hash。
- `notebooks/ns_shaft_colab.ipynb`已新增預設停用的P4.1 cell；scientific FAIL會保存
  summary且exit 0，不再只顯示`CalledProcessError`。`scripts/package_p41_colab.py`
  會拒絕dirty工作樹、local `config.yaml`、遊戲與媒體／權重，並只加入唯一凍結JSONL。
- 完整回歸：**432 tests passed in 63.34s**；compileall、三個P4.1 JSON、notebook JSON／
  最後一格Python syntax、absolute-path manifest preflight與`git diff --check` PASS。
  Dirty development bundle另以373 entries驗證必要檔／dataset存在且config缺席，隨後刪除。
- 專用clean bundle與Colab三初始化bounded Gate均已完成；本節的本機結果只保留作
  engineering provenance，不再是目前下一步。
- 產物：`reports/SEQUENCE_MODEL_ABLATION.md`、`artifacts/p41_experiment_manifest.json`、
  `artifacts/p41_local_interface_smoke.json`、`artifacts/p41_dataset_regeneration_drift.json`。

### P4.0 State-aliasing Audit（前置 Gate 已 PASS）

- 已對 Gate v11 的 10 回合、753 筆實機 Teacher transitions 完成 P4.0；每筆皆為
  268 維，controller／transition 的 step、action 與筆數完全對齊，kNN 僅允許跨
  episode 鄰居。
- sidecar 的 `controller_memory` 是 Teacher 決定本步 action 後才寫入；同一步的
  `previous_action` 已等於 label，`controller_phase` 也由本步 reason 生成。因此正式
  Audit 僅使用 `memory[t-1] -> decision[t]`；同一步 memory 只列 leakage ceiling，
  不得成為 Student input 或 Gate 證據。raw platform/track IDs 亦全部排除。
- observation-only 的 5-NN action disagreement／entropy／accuracy 為
  `56.20% / 1.0402 bits / 48.07%`；加入完整 causal memory 後為
  `45.39% / 0.8529 bits / 61.09%`，衝突相對下降 **19.23%**、entropy 降
  0.1873 bits、accuracy 增 13.01 percentage points。
- paired episode bootstrap 的 disagreement 改善 95% CI 為
  `[0.0979, 0.1411]`，10 個 episode 的改善方向全部為正；預先固定的 10% reduction、
  CI 下界與 entropy/accuracy supporting checks 全數 PASS。P4.0 Gate 為 **PASS**。
- 最有效的單一組是 causal action history（disagreement 42.76%），比 121 維 full
  memory 更精簡也更好；P4.1 的 S1 必須以此 compact deployable state 為主要候選，
  full memory 只作公平對照，不可依 post-decision leakage ceiling 選模。
- branch 仍有風險：launch 只有 13 筆且 causal disagreement 63.08%，brake 57.00%；
  因此 P4.0 PASS 只解鎖相同 split／seed／budget 的 **bounded P4.1 S0/S1/S2/S3
  ablation**，不授權長 BC、DAgger、PPO、DQN、NEAT 或 rare-branch dataset。
- 產物：`reports/STATE_ALIASING_AUDIT.md`、`artifacts/state_aliasing_audit.json`、
  `artifacts/state_aliasing_summary.csv`、`artifacts/teacher_action_conflicts.csv`。
- 驗證：P4.0 targeted 5 passed；完整 **415 tests passed**；compileall、artifact
  JSON/CSV count validation 與 `git diff --check` PASS。
- GitHub 保存前完成保守 cleanup：引用與用途稽核後移除 237.82 MiB 舊 Colab ZIP、
  已禁止續訓的 PPO/probe/BC/DAgger weights、中間 correction/aggregate JSONL、5 個
  已有 v2 的無引用重複 JSON、舊啟動 logs 與 caches。保留 clean easy dataset、
  Spike Dataset v1、Gate v11 全部真機證據、calibration、templates、summaries 與報告。

### P4.0 的來源 Gate（已凍結）

- 完整自然 run `20260803_034023_674665` 有 10/10 episodes；原始 Gate v10 floors
  `8,11,3,2,2,5,4,4,8,2`。10 支 MP4 逐幀重播皆可讀、每幀 HUD counter
  available、初始值皆為 1，並證實 episode 3 的 terminal frame 已到第 4 層；
  證據修正後為 `8,11,4,2,2,5,4,4,8,2`。
- Gate v10 的兩個 FAIL 是監測定義問題，不是降低控制品質門檻：無限遊戲把所有
  bottom terminal 限為最多 2 次會反向獎勵 top death；特殊平台的 RELEASE brake
  則把 entry brake 加上唯一允許的 replan brake 誤判成振盪。
- Gate v11 保留至少 7/10 reach-3、4/10 reach-5、floor-1 bottom death=0、Q25／
  CVaR、安全、觀測、wall、departure 與 special lifecycle checks。Bottom 指標改為
  `floor<3` 的 early bottom failure，不得超過 reach-3 miss budget；特殊 brake 只允許
  entry 1 次加每次准許 reversal 1 次，且絕對上限 2。
- 同一批不可變 sidecars 加同 run 的可信 MP4 audit 重算，Gate v11 **全部 checks
  PASS**：reach-3 7/10、reach-5 4/10、mean/median/Q25/CVaR25=`5/4/2.5/2`；
  early bottom 3/10（budget 3）、floor-1 bottom 0、安全事件 0。
- 16 次 special contacts 覆蓋 spring 7／spike 9；contact 最長 10 steps、replan／
  reversal 最大 1、brake 最大 2 且 violation 0、restart／safety abort 0。invalid
  observation、blind action、outward wall push、wall re-entry、departure cycle／
  switch／timeout 皆為 0。
- 主要 artifact：`artifacts/p36_teacher_real_gate_v11_reclassification_20260803_034023_v2.json`；
  MP4 audit：`artifacts/teacher_real_gate_v10_10episode_floor_video_audit_v2.json`。
  原始 v10 artifact 不覆寫；reclassification 未開遊戲、未送輸入、未挑選 episode。
- 未來 runner 會同步追蹤寫入 MP4 的 terminal frame，避免同類樓層漏記。姓名輸入框
  僅有精確 same-process owned `#32770`＋標題白名單的 Enter-once code/test 支援；
  本次成功 run 未遇到該 modal，不能宣稱已 live 驗證。
- 驗證：Gate/HUD targeted 51 passed；完整 **410 tests passed**、compileall 與
  `git diff --check` PASS。
- **P3.6 stability qualification 完成，但不是 Teacher 已完美。** 到第 3 層與 early
  bottom 都剛好壓線，lower-tail 風險仍開放。現在只解鎖 P4.0 State-aliasing Audit；
  尚未授權 S0～S3、BC、DAgger、PPO、DQN、NEAT 或任何長訓練。完整報告：
  `reports/P36_GATE_V11_10EP_STABILITY_REPORT.md`。

## 前一狀態：Teacher 策略審查完成；P3.6 HOLD／STOP；禁止直接部署新 dynamics/FSM

- 已依 repository、Gate v7／v8、最近四組 MP4、694 transitions、controller
  sidecars 與既有 calibration model 完成提案審查：
  `reports/TEACHER_CONTROL_STRATEGY_REVIEW.md`。
- 決策表：action-conditioned dynamics 與 Spring lifecycle 只
  **ACCEPT_WITH_MODIFICATIONS**（離線 model audit／encounter telemetry）；
  safe interval 與 receding horizon 為 **INSUFFICIENT_EVIDENCE**；新增 Spike FSM
  與 generic active stuck watchdog 為 **REJECT**。
- 新的可重跑 audit 在 10 個 episode、337 個嚴格 continuous normal rows 上做
  leave-one-episode-out。action-conditioned form 的 one-step x MAE 為 4.049 px，
  carry-vx baseline 為 8.462 px；2～5 step actual-action rollout 也較 baseline 好。
  但 reverse-braking 僅 LEFT 7／RIGHT 8 rows，未達每側 30 的預定門檻，故
  `shadow_model_eligible=false`、`live_deployment_approved=false`。
- RELEASE 實證：100 個 non-zero strict rows，下一幀位移 median 6／max 24 px；
  舊 `vx×0.25s` MAE 25.099 px，短 `vx×0.05s` MAE 3.647 px。這支持 D-051
  的方向，但不支持把 5～8 px 當成通用常數。
- 14 份舊 calibration logs 另有 450 strict continuous rows，但反向煞車只有
  LEFT 1／RIGHT 0。後續固定平台 bounded reversal calibration 完成 3 runs／
  125 raw／84 strict，新增 LEFT 23／RIGHT 21；使用者正確指出單一平台反覆左右
  不代表自然落台分布，因此全部只列 diagnostic-only，不合併 deployment Gate。
  第 4 run 中止並明確排除，方向鍵已確認釋放。詳見
  `reports/REVERSE_BRAKING_CALIBRATION_REVIEW.md`。
- Spring encounter audit 將 Gate v7 EP2 steps 101～116 聚合為同一診斷區段：
  4 contact IDs／4 source IDs、2 bounce、7 RELEASE、3 direction reversals，之後
  成功落到 normal platform。這證明 single-contact Gate 低估 lifecycle，但尚未證明
  需要新 Spring FSM。
- Spike audit 已合併 transition terminal flags：Gate v7 早期 contact 1～3 steps
  可離開；step 139 的 terminal contact 不再誤算成功。最新樣本只足以列
  provisional local pass，不足以宣告全域可靠，也不支持立即新增 FSM。
- 分離 Gate：Normal Landing **FAIL**、Spring **INSUFFICIENT_EVIDENCE**、Spike
  **PROVISIONAL LOCAL PASS／NOT QUALIFIED**、Restart/Safety fresh real
  **PENDING**；整體 Teacher Real **FAIL／HOLD**。P4.0 正式 Student 工作仍禁止。
- 離線產物：`artifacts/teacher_control_strategy_audit_v1.json`、
  `reports/ACTION_CONDITIONED_DYNAMICS_REPORT.md`、`NORMAL_LANDING_GATE.md`、
  `SPRING_ESCAPE_GATE.md`、`SPIKE_ESCAPE_GATE.md`。本輪未送實機輸入、未改
  `SafePlatformPolicy`、未啟動任何訓練。
- 驗證：新增 audit targeted 4 tests、完整 **397 tests passed**、compileall PASS；
  artifact 明列 `sends_game_input=false` 與所有未實作 live/training 決策。

## 前一狀態：Release Projection 與 Reset Focus 已修復，Gate v8 待 fresh REAL

- Fresh Gate v7（`20260803_012857_250916`）完成 3 回合，floors
  `2,5,2`，mean 3、median/Q25/CVaR25 皆為 2；reach-floor-3 僅 1/3，
  因此 lower-tail **FAIL**。三回合皆為 bottom death。
- Repair v10 的視覺與特殊平台 lifecycle 在本次證據中通過：invalid
  observation 0、pre-special dropout 0、wall re-entry/outward 0、special contact
  8 次且最長 4 steps，restart/abort 0。
- Gate v7 原本將 spring 上方的 5-step 正常對齊自由落體也算成
  pre-special release stall。影片證實這不是發呆；Gate v8 改為只阻擋
  observation dropout 以及 dropout 導致的 RELEASE，generic release 只留 telemetry。
- 真正的 lower-tail 根因是落點模型假設 RELEASE 後仍以原 vx 滑行
  0.25～0.55 秒，但實機於一個 125 ms step 內幾乎停止。EP1 step 38
  與 EP3 step 27 因此被錯判為已對齊，實際卻停在目標前並觸底。
- 控制器現保留長 horizon 來選可達目標，但最後的
  RELEASE-vs-steer 判斷改用校正的 0.05 秒 release projection。Gate v8 並要求
  此 telemetry 必須存在，避免用舊 sidecar 假通過。
- Fresh Gate v8（`20260803_014454_612146`）只完成第 1 回合
  floor 3／57 steps，第 2 回合重開時因視窗焦點安全中止；該 run 不滿
  3 回合要求，是 **INVALID／INCOMPLETE**，不能用來判斷新策略成敗。
- 保存的 dialog frame 證實焦點在第三個 `EXIT` 按鈕；舊 guard 只認
  START／TWO_PLAYER。現已新增 EXIT 校正區、有上限的 Tab 路徑與數秒等待。
  未知焦點仍絕不送 Enter。保存畫面離線辨識為 `exit`。
- 驗證：targeted 34 tests、完整 **393 tests passed**、compileall PASS。
  詳細報告見 `reports/P36_GATE_V7_RELEASE_PROJECTION_DIAGNOSIS.md`。

## 歷史狀態：Repair v9 READY／Gate v5 REAL 待辦

- Repair v9 已完成 adaptive landing intercept：保留0.25秒最小 horizon，依垂直距離
  與速度擴張至最多0.55秒；rising 直接使用最大 horizon，讓長下降窗口提早收油。
- support-departure 不套用長 airborne horizon，改以 destination safe interval、既有
  離台動量與來源邊界決定方向，避免破壞 v8 已通過的 departure lifecycle。
- special escape 先選可達的更深安全落點；若尚不可見，但角色在平台邊緣以超過
  40 px/s 向外移動，會反向煞車。持續 contact 時可因新出現的落點有限重規劃。
- Gate v5 要求 landing-intercept 與 special-destination telemetry available；v4 的
  36 項 safety／lower-tail checks 全數保留，不降低 reach 門檻。
- Gate v4 錄影反事實重播：EP2 frame23 由舊 LEFT 改為 RELEASE，投影 x=116.6 落在
  safe interval 50～126；EP3 於右向動量後提早 brake→LEFT。outward、wall re-entry、
  same-support cycle 仍為0。凍結舊軌跡造成 EP1 一次 departure timeout，不能冒充
  新 closed-loop 結果，真機 Gate 仍要求 timeout=0。
- 驗證：targeted 107、完整379 tests PASS；compileall、Gate v5 dry-run、config parse
  與 diff check PASS。完整報告見 `reports/P36_REPAIR_V9_REPORT.md`。

## 歷史狀態：Gate v4 實機 FAIL

- 全新 Gate v4：`logs/teacher_real_micro_20260802_021704_107779`，HUD／影片重播
  floors `9,2,2`，mean 4.33、median/Q25/CVaR25 皆為 2。36 checks 中 35 PASS，
  唯一失敗為 `reach_floor_3_case`：只有 1/3 reach-3，門檻為至少 2/3。
- Repair v8 的目標問題已通過真機確認：safety event、blind action、wall re-entry、
  outward push、departure timeout、same-support cycle、unrecovered dropout 全為 0；
  player missing streak 最大 1，forensic 3/3 available。
- EP2 是長距離向左追落點後煞車太晚，保留的水平動量越過平台；EP3 是彈簧附近
  special／launch escape 向右，但後續安全落點位於左側，轉向時已不可達。新 primary
  branch 是 landing-intercept／braking 與 destination-aware special escape，不是舊的
  發呆、永久 cooldown 或漏偵測。
- 因 lower-tail Gate 未過，不進 P4.0。下一步是 bounded Repair v9：加入動量／煞車
  距離的落點攔截，以及依下一個安全落點選特殊平台離開方向；先做 recorded-scenario
  regression，再允許一次 fresh Gate v5。完整報告見
  `reports/P36_REPAIR_V8_LIVE_GATE_REPORT.md`。

## 歷史狀態：Repair v8／Gate v4 準備

Repair v8 最終離線驗證：**375 tests passed、compileall PASS、Gate v4 dry-run
PASS**。Dry-run 不等於真機 Gate 通過，P3.6 因此仍維持 HOLD。

- 最新 Gate v3 run parser floors `2,4,10`；使用者觀察第三回合約 13，影片明確
  顯示至少 floor 12。reach、wall re-entry=0、outward=0 與多數 safety checks 通過，
  但 EP2 25-step dropout＋departure timeout、EP3 16-step dropout，使整體 FAIL。
- 影片／sidecar 證實三段長 RELEASE：EP2 steps 0–24 player missing、EP2 66–82
  timeout 後 source 永久 blocked、EP3 200–215 player missing。這不是單純主觀猶豫。
- Repair v8 把 departure timeout 後的永久 block 改成 2-step cooldown 後重新規劃；
  8-step hard cap 與 timeout=0 Gate 不放寬。Gate 另要求 cooldown streak<=2。
- 新 runner 在每回合以固定 milestones 與最多 6 snapshots 保存 lossless raw frame、
  同規則 player mask、component/threshold metadata 與 recovery frame。MP4 重播
  438/439 可偵測、真機卻有 41 invalid，證明壓縮影片不能取代 raw 校正。
- Gate 升為 v4，recoverable dropout 門檻由 20 收緊為 8 steps，並要求每回合
  forensic manifest。完整報告見 `reports/P36_REPAIR_V8_REPORT.md`。

## 歷史狀態：Repair v7／Gate v3

- Gate v2 後兩次全新 3-episode runs floors 分別為 `1,4,1` 與 `7,5,2`，兩份
  artifact 都 FAIL。六回合合併 mean 3.33、median 3、reach-3 3/6、reach-5 2/6、
  bottom 4/6；第一份因 floor-1 bottom 2、reach 不足失敗，第二份只因 wall
  re-entry 3 失敗。
- 第二份 run 的 support-departure 仍正常：50 exits、median 4／max 7 steps，
  restart／target switch／timeout／actionable RELEASE 全為 0。新 primary branches
  是撤離 wall 後 cooldown RELEASE 讓舊方向回牆，以及 top-pressure observation
  dropout 期間 RELEASE 導致普通平台短暫停頓後 top death。
- Repair v7 已 test-first 完成：wall cooldown 遇 outward request 時保持向內；只有
  最近可靠 top-danger 畫面已有實際方向時，player dropout 才沿同方向最多 2 steps；
  一般 missing 仍立即 RELEASE；top-danger same-support settle 2 steps 後 edge escape。
- Gate v3 分開量測 approved top-pressure bridge 與 blind action；bridge streak 必須
  <=2，`top_pressure_dropout_exhausted` 必須為 0。未授權的 missing directional
  action 仍直接 FAIL。
- 最新 7／5／2 三支 MP4 的 current-policy counterfactual replay：351 playing
  frames、outward 0、wall re-entry 0、same-support cycle 0、target switch 0，offline
  checks PASS。完整 369 tests、compileall 與 no-input Gate v3 dry-run PASS。
- 壓縮影片不能驗證新 action 的 closed-loop 結果，因此尚未放行 P4.0。下一步唯一
  允許的是一次使用者監督、bounded 3-episode Gate v3。完整報告見
  `reports/P36_REPAIR_V7_REPORT.md`。

## 歷史狀態：Gate v2 與 Repair v6

- 已建立完整專案藍圖 `docs/PROJECT_MASTER_PLAN.md`，涵蓋 P3.6 repair、P4.0
  state-aliasing、S0～S3、rare-branch sequence dataset、conservative DAgger、
  NEAT 對照、bounded RL、特殊平台 curriculum 與最終真機 Gate。
- repair v4 後新增四組真機測試，共 18 episodes／721 control steps：floor max
  `3,1,1,2,3,3,1,1,1,1,5,2,2,2,2,4,3,4`，mean 2.28、median 2；
  13/18 bottom death、6/18 floor-1 bottom death、14/18 observation invalid，
  四份 Gate 全 FAIL。此證據推翻 v4 READY 結論。
- 新 failure branches：`escape_launch_platform` 262/721 steps，最長單次承諾 6 steps；
  最新 EP4 的單步 wall override 與 persistent launch 互搶，形成 12 次快速反轉；
  70/721 steps 為 `player_not_detected`。平台邊緣真正 stationary 尚未證實，但
  aligned RELEASE 有 3～5 steps 的可見遲疑。
- Repair v5 已 test-first 完成：暖色 sprite closing 與 14 px 校正、最多 2 幀
  bounded player extrapolation、latched wall evacuation、enter/exit hysteresis、
  velocity-lookahead wall entry、清除衝突 launch/special memory、wall cooldown、
  launch 最多 3 steps commit／2 steps replan cooldown、vx projected landing，及
  support/edge/aligned-release telemetry。
- Gate 新增 raw/tracked/missing、max missing streak、wall re-entry、global/wall
  reversal、aligned release、floor-1 bottom death；三回合須 2/3 reach-3、1/3
  reach-5，五回合另須 bottom death ≤1、reach-5 ≥2。
- 正式離線 replay r1 正確 FAIL；依證據修正 detector 高度 off-by-one 與把正常
  跨樓層換向誤列 wall oscillation 的 Gate 定義。最終 r4 對 18 MP4／729 playing
  frames：raw detected 716、13 tracked bridge、effective missing 0、max missing 2、
  outward 0、wall re-entry 0、max wall reversal burst 1、aligned release max 5，
  全部 offline checks PASS。
- Targeted 102 passed；完整 `pytest -q` 350 passed in 66.51s；compileall、Teacher
  Real Micro dry-run JSON 與 `git diff --check` 皆 PASS。壓縮 MP4 replay
  是 counterfactual proxy，不能取代 raw-frame 真機驗證；P3.6 仍 FAIL／STOP，
  但 repair v5 已達新的 bounded 3-episode real retest 門檻。
- repair v5 新真機共完成 3-episode 與 5-episode 兩次 Gate：HUD floors 分別為
  `2,3,3` 與 `2,2,5,3,3`；合計 mean 2.875、median 3、bottom 2/8、floor-1
  bottom 0。兩份 Gate 均 FAIL：第一份另有 wall re-entry 1 且無 reach-5；第二份
  reach-3 僅 3/5、reach-5 僅 1/5。
- 使用者觀察的「平台邊緣猶豫」已由 sidecar 與 MP4 證實。471 steps 中
  RELEASE 203、aligned 154、launch 175、brake 40；37 個 RELEASE 發生於仍有
  support contact 且 edge distance ≤20 px。主因是 departure 與 airborne landing
  共用 alignment 規則：仍在來源平台時 projected landing delta=0 便 RELEASE；
  3-step launch cap、event 清 cooldown、launch 清 destination target 再形成重規劃
  循環。完整診斷見 `reports/P36_REPAIR_V5_LIVE_DIAGNOSIS.md`。
- Repair v6 已 test-first 完成 explicit support-departure latch：保存 source、
  destination 與 direction，仍接觸 source 時禁止 landing alignment 提前 RELEASE；
  support-lost 後才交回 airborne landing。8-step hard cap 只作 safety abort，wall
  evacuation／special escape／F8 與所有真機防線不變。
- 新 Gate 量測 same-support departure cycles、target switches、timeout、edge RELEASE
  ratio、support-lost exit、max departure steps 與 phase-aware support aligned streak。
  舊 global aligned streak 跨 airborne/support phase，只保留 telemetry。
- 最新 8 MP4／476 playing-frame counterfactual replay r3：departure active 177
  steps、same-support cycles 0、target switches 0、outward 0、wall re-entry 0、
  max support-aligned streak 3、edge RELEASE 17/96，offline checks PASS。舊軌跡
  有 5 次達 8-step cap，因影片不能呈現新 action 的 support-lost，僅列 telemetry；
  新真機 Gate 仍要求 timeout 0。
- Repair v6 targeted 86 passed；完整 `pytest -q` 357 passed in 83.27s；compileall、
  no-input dry-run、replay JSON 與 diff check 全 PASS。完整報告見
  `reports/P36_SUPPORT_DEPARTURE_V6_REPORT.md`。
- Repair v6 已完成一次全新 3 回合實機紀錄：舊 HUD parser 記錄 floors
  `5,3,10`，3/3 reach-3、2/3 reach-5、0 safety event；第三回合持續運作到
  300-step 上限，使用者與影片尾段顯示實際約到 12～13 層，暴露 HUD parser
  lag／unstable，但不影響最低 reach Gate 已通過。
- 舊 Gate v1 把同平台 target 的正常 settle RELEASE、特殊平台脫困中的方向反轉，
  以及全程安全 RELEASE 且之後恢復的短暫 observation dropout 都當成 blocking
  failure，因此 artifact 為 FAIL。sidecar 顯示 same-support cycle 0、departure
  timeout 0、46 次 support exit、median 3 steps、max 5 steps，核心 v6 離台流程有效。
- Gate v2 已 test-first 改為語意量測：只有 `target != support` 時的 aligned RELEASE
  才算 actionable stall；wall oscillation 只量 wall guard／evacuation active 狀態，
  special／launch escape 另列；observation dropout 必須 bounded、全程 RELEASE、
  後續恢復，未恢復或 blind directional action 仍立即 FAIL。
- 同一份真機 controller sidecar 的不可覆寫 v2 重分類 PASS：29 invalid steps、
  4 次全恢復、最長 15 steps、blind action 0、unrecovered 0、active-wall reversal
  max 0、actionable support RELEASE 0；13 次同平台 settle RELEASE 只保留 telemetry。
  artifact：`artifacts/p36_teacher_real_gate_v2_reclassification_20260801_225518.json`。
- 本次只修改 Gate／runner telemetry，沒有改 v6 控制策略。Targeted 98 passed；
  完整 `pytest -q` 363 passed in 85.93s；compileall、v2 dry-run 與 diff check PASS。
  重分類不是新 runner 的獨立實機確認，因此 P3.6 仍 HOLD／STOP，尚未放行 P4.0。

- `../CODEX_SEQUENCE_CONTROL_STRATEGY_UPDATE.md` 已取代舊 Prompt 成為最高優先規格。
- 已直接核對 artifacts：Teacher holdout reach-floor-10 94%、deepest-floor Q25
  30、0 health death；Spike Dataset v1 60 episodes／3,529 rows／validator 0；
  BC0 v1 mean deepest 45.5、Q25 7.75、reach-floor-10 60%、bottom 14，baseline
  49.7／30／100%／1；舊 Spike DAgger reach 86.67%→75%、bottom 15→27、
  1 health death。最新 Prompt 數值與 artifact 一致。
- 數值語意釐清：49.7 是 BC0 final seeds 的 baseline mean deepest；Teacher
  holdout mean deepest 是 47.31。Prompt 的「Teacher／Baseline 約 49.7」不可
  當成同一 partition 指標，但不影響目前 Gate 判定。
- 已建立 Teacher Real-Game Micro Gate：預設 dry-run、明示 `--execute`、固定確認
  字串、倒數、3～5 回合及 episode/total step/time 硬上限；保存 canonical
  transition、controller-memory sidecar、MP4 與 Gate summary。
- `SafePlatformPolicy` 現可唯讀輸出 deployable memory snapshot：controller phase、
  target lock/age、active/pending direction、braking/launch/recovery、previous action
  與 streak；reset lifecycle 已測試。
- dry-run artifact 已產生，且明確證明沒有尋找遊戲、載入 input backend 或送鍵。
- 2026-08-01 已完成 3 回合／146 steps 真機 smoke：安全事件 0、三動作分布
  61/43/42、transition/controller/MP4 全部完整，無 PPO 式 action collapse。
- **Teacher Real Gate：FAIL／STOP**。三回合全部 top death；人工影片 HUD 最高
  floor 3/2/2，只有 1 回合達第 3 層、0 回合達第 5 層。不得執行
  State-aliasing、S0/S1/S2/S3、rare-branch dataset、conservative DAgger 或 NEAT。
- Spring：兩次 spring bounce 後有連續 13 步 aligned RELEASE，未維持特殊平台
  escape state，最後撞頂。Spikes：落刺後有連續 16 步 recovery-aligned RELEASE，
  雖最終落 normal 回血，仍因 hazard/top-danger escape 太晚死亡。
- Floor telemetry 與影片不一致：自動 events 為 0/2/2，但影片 HUD 最高為
  3/2/2；舊 detector 以 track-ID change 猜樓層，既漏掉 HUD 變化也把同樓層
  spring/spike cycle 當成下降，不能直接作 Gate。這是舊 run 的 failure evidence。
- 記錄的 0～1 ms latency 是 command dispatch，不是真實畫面 response latency；
  observation confidence 亦未反映 kind/track/floor-event 不穩定。
- 使用者觀察到控制像逐次點按；程式確認真機 adapter 每個 decision step 只 hold
  80 ms 就無條件放鍵，即使連續同向 action 也會在約 8 Hz 下形成 pulses。
  2026-08-01 已完成 bounded stateful hold：同向 action 跨 observation 保持，
  RELEASE／非 PLAYING／例外／reset／close 放鍵，控制迴圈停滯則 500 ms lease
  watchdog 放鍵；mock regression PASS，但尚未真機重測，不能宣稱 fidelity PASS。
- Persistent special-contact escape 已完成 mock Gate：spring／spikes 的可觀測
  event 會保存 source ID、kind、最後可見邊界、方向與 age；即使來源暫時消失或
  spring 壓縮後 kind 改變，仍持續離台。離開來源邊界、落到非特殊平台或達
  12-step hard cap 才清除。6 個 fixed scenarios 與 memory assertions PASS，
  尚待真機重測，P3.6 整體仍為 FAIL／STOP。
- HUD floor tracker 已完成：校正數字 ROI `(266,16,112,32)`，以二值 fingerprint、
  change threshold 與 2-frame stable debounce 直接追蹤畫面樓層，不再用 platform
  ID 推估。重播三支舊 MP4 自動得到最高樓層 3/2/2、變化次數 2/1/1，與人工
  逐幀結果完全一致，0 unavailable frame；offline floor telemetry Gate PASS。
- 新 sidecar 已分開 `command_dispatch_latency_ms` 與
  `physical_response_latency_ms`；後者從方向 command 起算，到畫面 `velocity_x`
  首次朝正確方向且超過 threshold 才成立。新 Gate 要求 LEFT/RIGHT 都有樣本，
  因舊影片沒有 command timestamp，必須於下一次 3 回合實機補考驗證。
- 人工感受「普通平台比舊 PPO 好」與 log 一致，但不足以通過特殊平台、reach-5
  與 observation fidelity 門檻。完整分析見 `TEACHER_REAL_GAME_MICRO_GATE.md`。
- 真機 `reach floor N` 改以視覺 HUD counter 的 episode max 判定；仍不能與
  simulator privileged `deepest_floor` 混稱。
- repair v1 當時驗證：P3.6 targeted 48 passed；完整 `pytest -q`
  324 passed in 65.15s；舊 MP4 floor audit PASS、dry-run PASS；
  三份真機 transition 亦各自通過 validator（0 error／0 warning）。
  `compileall -q src scripts tests`、dry-run JSON parse、`git diff --check` 全通過。
  本輪 repair 全程未啟動遊戲、未送真實輸入、未訓練模型。已具備受限 3 回合
  real retest 條件，但 retest 通過前仍不得進 P4.0。
- 第二次 retest run `teacher_real_micro_20260801_031907_767286` 留下 episode 1
  的 71 筆 transition/controller records 與完整 MP4；HUD 由 1 到 4，動作
  RELEASE/LEFT/RIGHT 為 38/18/15，雙方向共 10 筆 visual motion-onset sample
  均約 94 ms。使用者與影片都確認持續按鍵後的水平移動較線性。
- 此 run 仍是 **FAIL／ABORTED**：死亡後 phase probe 正確阻止下一個 action，
  runner 卻把 `action_applied=false` 誤當 exception，summary 因而沒有納入 episode。
  現已只在 non-PLAYING 且 terminated/truncated 時接受 terminal safety no-op、保存
  終止 frame，且不偽造未送出的 transition；PLAYING 下 no-op 仍立即報錯。
- 影片與 268 維 observation 解碼確認 steps 50～70 連續 21 步
  `aligned_with_recovery_platform → RELEASE_ALL`。角色實際隨尖刺平台上移，但接觸
  平台遭遮蔽／未分類，nearest 指向另一個 normal 且 gap 固定約 57 px；直到
  health 1→0 才出現無 source 的 generic damage。
- Repair v2 新增 deployable sequence fallback：同 target、aligned 且相對 gap 在
  3 px 內連續 4 steps，就建立 persistent edge escape；top danger 優先於 recovery。
  同一 MP4 離線 replay 時，新版由 frame 53 起持續 RIGHT，取代舊版 21 步 RELEASE。
  Targeted regression 75 passed；完整 regression 329 passed in 68.31s，compileall、
  dry-run、audit JSON 與 diff check 均 PASS。P4.0 仍為 STOP。
- 第三次真機 run `teacher_real_micro_20260801_034041_303682` 已正常完成 3 回合：
  HUD max 5/5/2、mean 4、median 5，2/3 達 floor 5；動作 RELEASE/LEFT/RIGHT
  105/81/82，32 筆 physical response median 94 ms，0 safety event，三組
  transition/controller/MP4 完整。相較舊 3/2/2 且全 top death 是實質改善。
- Gate 仍 **FAIL／STOP**：episode 1/3 有 player observation missing；episode 2 的
  floor unavailable 只發生在 terminal dialog，確認是 runner 把非 PLAYING 終止幀
  誤算成 HUD 必填，而非遊玩中的 floor tracker 遺失。此 accounting 已修正。
- 使用者觀察的 spring 重複彈跳集中於 episode 3。解碼顯示 nearest 已辨識 spring，
  但 gap 週期為約 18→50→84→19 px，`spring_bounce` event 為 0；landing correlation
  仍錯連前一個 spikes，故 event-only escape 沒啟動，stable-gap dwell 亦不適用。
- Repair v3 讓 close visible spring（gap ≤30 px）與 spikes 一樣直接建立 persistent
  special escape，不再依賴 bounce event。EP3 MP4 離線 replay 由 frame 14 起持續
  LEFT，而舊 run 在該區間多為 RELEASE。Targeted 74 passed；完整回歸 331 passed
  in 67.55s，compileall、dry-run、audit JSON 與 diff check 均 PASS。
- 後續 3 回合 run `teacher_real_micro_20260801_035120_340142` 為 artifact floors
  5/2/1；5 回合 run `teacher_real_micro_20260801_035223_571410` 為 2/1/3/3/7，
  使用者人工最高看到第 8 層。五回合安全事件 0、三動作 118/110/105、latency、
  artifact completeness 與 reach-floor-3/5 checks 全通過，但 observation valid
  仍 FAIL，故未准進 P4.0。
- 新阻擋 failure branch 為貼牆 special escape：五回合 EP1 spring 在 x≈54–56
  仍有兩段共 12 個 outward LEFT；EP4 spikes 由 x=326.5 推至 x≈410，連續 12
  個 special RIGHT。因來源平台貼牆，沿原方向離開 source bounds 幾何上不可能，
  12-step cap 只會延後脫困，不能視為小問題。
- 已先建立並凍結 `reports/P36_WALL_SAFETY_REPAIR_PLAN.md`，再依序 test-first
  實作共用 wall guard。Playfield 40～423 px，guard margin 32 px；左側 outward
  LEFT 改 RIGHT，右側 outward RIGHT 改 LEFT，且仍保留 direction brake。
- Guard 位於所有 policy decision 的共同出口，涵蓋 special、launch、aligned dwell、
  recovery、top-danger 與一般 target。Sidecar 新增 guard 原始動作／側邊及 applied
  outward streak；Gate 強制 wall telemetry available、outward count=0、max streak=0。
- 兩個真機 runs 共 8 支 MP4／497 frames 以修正版離線 replay，outward wall action
  為 0。Targeted 84 passed；完整 338 passed in 70.08s；compileall、修復 audit JSON、
  新路徑 dry-run 與 diff check 全部 PASS。狀態為 repair v4
  READY FOR BOUNDED 3-EPISODE RETEST；新 artifact PASS 前 P4.0 仍 STOP。
- 分支 `agent/simulator-learnability-colab`，HEAD `b73ff2b`；工作樹原本已有大量
  累積未提交修改，本輪全部保留且未還原。使用者未要求本輪 commit/push。

本節優先於下方歷史 Go/No-Go 與「下一步」敘述；下方內容保留作 provenance。

## 目前工作包（最新策略）

- 已完成最新 Prompt、AGENTS、README、長期文件、既有報告與 repository
  實況核對；初始工作樹乾淨，分支為 `agent/simulator-learnability-colab`。
- 已將長期策略更新為 Data Resource Audit → Simulator v0.2 →
  Oracle-full／Teacher-observable → frequency gate → 條件式 BC0／DAgger0。
- 初始回歸：`219 passed in 32.48s`；未啟動遊戲、未送真實輸入、未訓練。
- Data Resource Audit 已完成：37 JSONL／3,561 rows；649
  `dynamics_only`、476 `needs_relabel`、2,436 invalid；BC／replay verified
  都是 0。已產生 inventory、row-level salvage manifest 與 audit report。
- Simulator v0.2 已完成 60 Hz physics、8／10／12 Hz policy、持續生成／回收、
  easy/calibrated/hard、3 層 reachability、failure taxonomy、diagnostic overlay
  與預設關閉的特殊平台 flags。
- Reachability 100／1,000、Oracle-full、Baseline gates 全 PASS。10 Hz
  baseline mean 34.68，故 simulator teacher 選 10 Hz；真實遊戲維持 8 Hz。
- Teacher Dataset 已生成 60 episodes／3,560 rows，episode/seed split，
  validator 0 error。
- BC0 診斷完成：soft-loss 模型在 learner states 的 teacher disagreement
  41.01%，確認是 rollout covariate shift／過度平滑，不是 epoch 不足。
- Hard-label BC0 三初始化 seeds 為 29.80／30.10／25.95 floors，全部高於
  23.84 gate，平均 28.62；**BC0 PASS**。
- Naive DAgger0 的 1,634 corrections 占原 train 69.2%，LEFT 比例由 27.7%
  偏移到 45.5%，使 frozen eval 降至 23.20；correction audit 已完成。
- 預先固定唯一 balanced ablation：correction cap 25%（590 rows）、依原 action
  比例、12 clusters × failure category round-robin。結果 frozen seeds
  63.15 floors、fresh seeds 400～419 為 62.90，baseline fresh 為 31.25；
  **Balanced DAgger0 PASS**。
- 17/20 fresh episodes 達 600-step time limit，easy normal-platform curriculum
  已飽和。
- 特殊機制第 1 項「血量＋普通平台回血」已完成：feature 預設關閉、
  100/100 low-health Oracle landing、HUD、observation/event/reward、
  calibration interface 與 100-seed off/on equivalence 全 PASS。
- 特殊機制第 2 項「尖刺」已完成：100/100 non-lethal、100/100 lethal、
  100/100 normal-heal interaction、100/100 Oracle avoidance 與 100-seed
  no-spawn equivalence 全 PASS。
- 特殊機制第 3 項「輸送帶」已完成：左右方向速度與 Oracle normal preference
  各 100/100，100-seed no-spawn equivalence PASS；80 px/s 明標為 provisional。
- 特殊機制第 4 項「彈簧」已完成：stronger bounce 與 Oracle normal preference
  各 100/100，100-seed no-spawn equivalence PASS；190 px/s 明標為 provisional。
- 特殊機制第 5 項「翻板」已完成：active collision、inactive passthrough、
  Oracle normal preference 各 100/100，100-seed no-spawn equivalence PASS；
  1／1 秒週期明標為 provisional。
- 五項特殊機制目前都只通過 mechanism gate；generator 仍不生成特殊平台，
  其中只有 spike 已進入低比例 generator v0。
- Spike curriculum v0：10% proposal、前 3 層 normal、尖刺間至少 5 normal；
  1,000-seed realized 5.11%，reachability／health safe PASS。
- Oracle 100/100 到第 10 層；baseline 33.07 floors，相對 plain 34.68
  保留 95.36%，99% 到第 3 層，兩者都 0 health death。
- 新 Teacher Dataset 使用獨立 seeds 1000～1059：60 episodes／3,541 rows，
  validator 0 error；16 spike contacts、最低 health 7；spike-visible rows
  train／validation／test 為 909／123／232。
- 本機 bounded interface smoke：seed 0、5 epochs、fresh eval 1100～1119；
  BC 27.0 floors vs baseline 31.55，retention 85.58%，0 health death，
  無 collapse，**interface PASS**。
- Test overall／spike-visible accuracy 為 74.75%／75.43%；spike-target
  emergency subset 僅 10 rows／40%，列為正式 Colab 必報風險。
- Colab notebook 已加入預設停用的三-seed spike BC0 cell，會自行重跑 Gate、
  重建 ignored dataset、封裝 summary/model/gate ZIP，且不啟動 DAgger。
- 舊 Colab 正式 seed 0 在離線 validation loss 選出的 epoch 17 **FAIL**：
  test accuracy 82.06%，但 BC 12.85 floors vs baseline 31.55，retention
  40.73%，17/20 bottom death；0 health death、無 action collapse。
- 同一初始化的本機 epoch 5 為 27.0 floors，證明主要問題是以離線 loss
  選錯閉迴路 checkpoint，而非尖刺／血量機制故障。1100～1119 已用於此
  診斷，永久退出正式 final evaluation。
- 已實作 `BC0-rollout-selected-v1`：dataset 1000～1059、checkpoint selection
  1060～1079、untouched final 1200～1219，候選 epoch 固定
  3／5／8／11／14／17；選模以安全、rollout gate、mean floors、bottom
  deaths 為主，validation loss 只作 tie-break。
- 新流程本機 seed 0／最多 5 epochs bounded smoke：selection epoch 3／5
  為 19.8／24.45 floors，選 epoch 5；untouched final 為 BC 27.85 vs
  baseline 29.60，retention 94.09%，0 health death、無 collapse，pipeline PASS。
- 尚未執行新版正式三初始化 seed；舊 seed 0 結果不得與新版協議混算。
- 新版完整回歸：283 passed in 65.19s；compileall、notebook JSON 與
  `git diff --check` 全通過。
- 新版 Colab spike BC0 3/3 final Gate PASS：selected epochs 11／5／8，
  final floors 26.20／31.05／29.95，平均 retention 98.20%，0 health death、
  無 collapse；准許單一 bounded Spike DAgger0。
- Spike DAgger0 已使用三 source models、aggregation seeds 1300～1359，
  從 8,076 disagreements 依 25% cap 平衡選出 592 corrections。
- DAgger final seeds 1500～1519：mean floors 28.57→38.75，但 floor-10
  success 86.67%→75%、bottom death 15→27；seed 2 有 1 health death，
  因此僅 2/3 initialization Gate PASS，**Spike DAgger0 整輪 FAIL／STOP**。
- Health death 重播證明每層仍有平台；策略跳過 normal 回血平台，使最低
  5-normal recovery gap 在實際落台序列中不足。不得執行第二輪 DAgger。
- 本輪完整回歸：285 passed in 72.08s；compileall 與 `git diff --check` 通過。
- 已實作 Teacher-observable health recovery mode：受傷時優先最近 normal、
  覆蓋 deeper target lock，非 normal 不視為回血平台；未啟動新訓練。
- Reliability-first checkpoint ranking 已改為 safety → reach-floor-10 → bottom
  death → deepest-floor Q25 → median deepest → Gate → mean deepest → offline
  tie-break。
- 指標稽核確認舊 `floor-10 success` 是下降事件數，不是實際 deepest floor；
  Gate 已改用 `reach_rate_floor_10`，歷史事件欄位只保留相容性。
- Teacher 新增可見落點 approach 與 future-aware launch escape；development
  1600～1699 為 95%、已診斷 audit 1700～1799 為 96%，一次 untouched
  holdout 1800～1899 為 94%，皆 0 health death，absolute 90% Gate PASS。
- 1700 組已參與原因分類，不再稱為 holdout；1800 組執行一次後已凍結。
- 暫不從真實主程式廣泛重蒐資料；後續只收集 spike／受傷回血／跳過 normal
  的小型人工 verified calibration packet。
- 本階段完整回歸：296 passed in 68.51s；未啟動新訓練或真實遊戲。
- Spike Teacher Dataset v1 已以全新 seeds 2000～2059 生成：60 episodes／
  3,529 rows、validator 0 error、Dataset coverage Gate 全部 PASS；舊 v0 未覆寫。
- v1 有 36/60 spike-visible episodes、33 spike-target labels、16 damage events、
  179 recovery-related decisions、0 health death。
- 本機 BC0 v1 seed 0／5 epochs bounded smoke **FAIL／STOP**：selected epoch 5
  final mean deepest floor 45.5 vs baseline 49.7，但 reach-floor-10 60% vs
  100%、Q25 7.75 vs 30、bottom 14 vs 1；不追加 epochs、不進正式多 seed。
- 診斷顯示 learner-state disagreement 集中於 launch escape（40.2%）、move safe
  （55.4%）、recovery（53.5%）與 direction brake（71.9%）；這是閉迴路
  covariate shift／Teacher memory observability 問題，不能只靠平均樓層掩蓋。
- 本階段完整回歸：298 passed in 97.85s；compileall／JSON／diff check 通過。

## 已完成

- 完成 repository、真實控制鏈、觀測／reward、資料、baseline、PPO artifact
  與測試稽核。
- 建立永久上下文、roadmap、實驗 protocol、schema、simulator、workflow、
  decisions 與 risk register。
- 建立 `ns-shaft-transition-v1` dataclass、JSONL validator 與 CLI。
- 建立 Gymnasium/Pymunk simulator v0：
  RELEASE／LEFT／RIGHT、重力、水平加速度／限速、release drag、單向落台反彈、
  邊界、捲動、樓層下降、上下死亡、固定 seed、human／rgb_array render。
- 模擬器重用真實環境的 64 維 `FeatureEncoder` 與 4 幀／動作歷史，
  輸出相容的 268 維觀測。
- 已有 schema／validator／simulator 測試、Gymnasium `check_env`、
  baseline smoke 與 100,000-step headless smoke。
- 修完交接中已知的 `platform_target_action_reward` 半成品測試。
- 建立並實際完成 Colab pipeline validation；pytest、check_env、throughput、
  checkpoint save/load/resume 與 MP4 均通過。768-step deterministic 全 RIGHT，
  該 checkpoint 只證明 pipeline 可執行，不得續訓。
- 建立新版 `TransitionJsonlWriter`，並在一次受限實機 calibration 中完成
  43 筆 transition；validator 0 error／0 warning，資料明確標為 `invalid`。
- 第二次 RIGHT-first 校正完成 56 筆；兩批合計 99 筆、81 筆無事件 clean
  transitions。兩個檔案各自 validator-clean。
- legacy quarantine manifest 已掃描 23 個 JSONL、2,912 筆，沒有任何檔案被
  升格為 BC 或 DQN 資料。
- simulator 固定評估完成：每策略 5 seeds × 20 episodes；baseline 平均 1.46
  層、random 0.76、RELEASE 0。
- 本機 vector benchmark 完成；最高 throughput 為 16 async envs，約
  11,939 steps/s。Colab 必須另行重測。
- 完成 14 個 calibration JSONL、649 transitions；所有檔案維持
  `policy_source=invalid`，只作物理校正。R14 的 LEFT／RIGHT／RELEASE／
  free-motion／landing sample gates 全部通過。
- 一步 fitted MAE 為 x 3.99 px、y 6.83 px、vx 32.67 px/s、vy
  56.17 px/s；landing classifier precision 0.846、recall 0.957、
  death misclassification 0。
- simulator v0.1 已套用 125 ms control step、action impulse、release、
  gravity、bounce、scroll、平台尺寸／間距及水平 shift 校正值。
- v0.1 固定 benchmark 完成；baseline 100 episodes、2,490 steps、
  landing／floor rate 都是 0.0602。
- seeded distribution fidelity gate 通過：real vs simulator landing
  z = −0.569、floor z = −1.698，皆滿足雙尾 |z|≤1.96。
- simulator learnability P0 通過：PPO／SB3-DQN 各 4,096 steps，held-out
  floors 1.00／1.05，均高於 random 0.70 且未達 98% collapse。
- simulator learnability P1 通過：3 個 fresh train seeds、每演算法
  8,192 steps、20 held-out eval seeds。PPO 平均 1.45 floors，
  SB3-DQN 1.167，六個模型皆通過左右方向 coverage 與 no-collapse gate。

## 交付驗證

- P1 完成後完整回歸 `python -m pytest -q`：219 passed，33.58 秒。
- `python -m compileall -q src scripts`：通過。
- `python -m json.tool notebooks/ns_shaft_colab.ipynb`：通過。
- Colab 私人 repository 改採手動 ZIP 上傳；setup cell 的專案定位、安全
  解壓與 traversal rejection 合成測試通過。metadata 已由僅限 Python 3.11
  改為支援 3.11／3.12，並完成 wheel metadata 與隔離 target import 驗證。
- `git diff --check`：通過；只有 Windows checkout 的 LF→CRLF 提示。
- `scripts/check_simulator.py --steps 10000 --baseline-steps 1000`：
  `check_env`、10k headless、1k baseline 全通過；v0.1 本機約
  3,317 steps/s。
- 本次依使用者明確確認執行多個單回合、20 秒硬上限的 calibration；
  foreground／F8／phase／release-all 安全鏈全程保留。未開始模型訓練。

## 已知限制

- simulator v0.1 只實作 normal platform，不包含 spikes、spring、conveyor
  或 flipping；特殊平台仍是後續 fidelity 工作。
- exact 10／30-control-step screen-y 受 viewport 外隨機平台與 camera lock
  影響。held-out 樂觀下界仍約 52.3／95.4 px，因此依 D-009 改用 seeded
  distribution gate；exact pixel 值仍保留作 FAIL 診斷，不能宣稱已通過。
- 舊 JSONL 缺少新版 transition 欄位，不能直接當 BC 資料。
- 最新累積 PPO 模型在 deterministic 128-step 評估中 128 次全為
  RELEASE_ALL，視為 action collapse，不得續訓。
- action effective 至 next observation 中位約 94 ms；observation transition
  中位 125 ms。
- v0.1 歷史 learnability 數字不能作 v0.2 BC gate；v0.2 已另以 100／1,000
  reachability seeds 與 frozen evaluation 重建基準。

## Go / No-Go

- **Go**：Data Resource Audit、v0.2 simulator／reachability／teacher 工程及
  有硬上限的 gate 評估。
- **通過**：Colab runtime／throughput／checkpoint／resume／video pipeline。
- **No-Go**：自動追加本機 probe timesteps；P1 已完成，依 D-010 停止擴訓。
- **通過**：Reachability、Oracle-full、Baseline、Teacher Dataset。
- **通過**：hard-label BC0，3/3 initialization seeds PASS。
- **歷史 FAIL**：naive DAgger0 round 1。
- **通過**：單次預先固定 balanced DAgger0；fresh-seed generalization PASS。
- **停止**：easy curriculum 已飽和，不追加 corrections／epochs。
- **通過**：health＋normal heal mechanism gate；尚未加入 training distribution。
- **通過**：spike mechanism gate；尚未加入 generator／training distribution。
- **通過**：conveyor mechanism gate；尚未加入 generator／training distribution。
- **通過**：spring mechanism gate；尚未加入 generator／training distribution。
- **通過**：flipping mechanism gate；尚未加入 generator／training distribution。
- **No-Go**：直接混合特殊平台；須先凍結比例、phase、reachability 與 Oracle gate。
- **通過**：單一 spike curriculum v0 generator／Reachability／Oracle／Baseline。
- **通過**：spike Teacher Dataset v0，3,541 rows、validator 0 error。
- **通過**：spike BC0 本機 5-epoch interface smoke。
- **歷史 FAIL**：舊 Colab spike BC0 seed 0；offline-loss epoch 17 在
  1100～1119 僅保留 baseline 的 40.73%。
- **通過（限新管線 smoke）**：rollout-selected seed 0／5 epochs，
  untouched final retention 94.09%。
- **Go**：新版 Colab bounded spike BC0，3 initialization seeds；每個 seed
  只用 1060～1079 選 checkpoint，1200～1219 只作一次 final gate。
- **通過**：新版 spike BC0 3/3 initialization final Gate。
- **FAIL／停止**：balanced Spike DAgger0，2/3 final Gate；平均樓層提升但
  lower-tail、bottom death 與 health safety 退化。
- **No-Go**：第二輪 Spike DAgger、下一種特殊平台 curriculum 或實機訓練；
  須先完成 health-aware recovery Teacher 與 reliability-first Gate。
- **通過**：Teacher recovery safety／non-regression（所有固定組 0 health death）。
- **通過**：absolute reach-floor-10 reliability；development 95%、已診斷 audit
  96%、一次 untouched holdout 94%，皆高於預先固定 90%。
- **No-Go**：在 conveyor／spring／flipping 尚未進各自 curriculum gate 前混合。
- **No-Go**：長 PPO、長 DQN、DQfD、Residual、特殊平台混合訓練。
- **No-Go**：把舊 JSONL 或塌縮 PPO 當教師、初始化或續訓來源。
- **No-Go**：新增實機 rollout；本輪 calibration 已達 sample gate，不再追加。
- **通過（限 v0.1 probe）**：一步／landing 與 seeded distribution
  calibration gate。exact screen-y 多步仍是診斷 FAIL，不得另行宣稱通過。

## 歷史（Gate v8 前）的下一步

1. 新的 release projection、Gate v8 telemetry 與 EXIT-focus reset 已完成離線驗證。
   下一個允許動作只是一次使用者監督的 fresh 3-episode bounded
   Gate v8；不從上次中斷 run 接續。
2. Gate v8 同時要求 3 回合完整、safety event=0、release-projection
   telemetry available、wall re-entry=0、restart/abort=0、pre-special dropout
   與 dropout-release 均 <=2，至少 2/3 reach-floor-3 與 1/3 reach-floor-5。
3. 只有 fresh Gate v8 完整 PASS 才允許 10 回合穩定性確認。單一回合
   floor 3 不是進入 P4.0 的證據，也不得以 best case 取代 lower-tail。
4. Gate v8 未過前不進 P4.0、S0～S3、BC／DAgger／PPO／DQN／NEAT
   或任何長時間訓練。
