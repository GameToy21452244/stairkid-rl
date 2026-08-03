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

## D-011：最新策略優先，先證明 v0.2 可解再產生教師資料

- 日期：2026-07-30
- 決策：`CODEX_UPDATE_TRAINING_STRATEGY_AND_CONTINUE.md` 優先於 D-010 的
  舊停點；先做 Data Resource Audit、Simulator v0.2 與三個獨立 gate。
- 理由：Colab pipeline 雖通過，768-step PPO deterministic 全 RIGHT，
  v0.1 baseline 平均僅約 1.65～1.8 層，環境可解性與教師品質尚未證明。
- 影響：禁止續訓 512／768-step checkpoint；gate 前不生成 teacher dataset。

## D-012：Oracle-full 與 Teacher-observable 永久分離

- 日期：2026-07-30
- 決策：Oracle-full 可用完整 simulator state 與短 rollout，只驗證環境可解；
  Teacher-observable 只能使用 268 維學生觀測或明確允許的短歷史。
- 理由：避免把畫面外平台、未來生成或精確碰撞 state 洩漏到 BC 標籤。
- 影響：兩者使用獨立 API、測試、指標及 dataset provenance。

## D-013：物理更新率與 policy 控制率分離

- 日期：2026-07-30
- 決策：Simulator v0.2 使用固定 60 Hz physics substeps，比較 8／10／12 Hz
  policy 決策率；真實遊戲仍維持已量測約 8 Hz，除非新證據支持變更。
- 理由：降低低頻積分造成的一幀精準操作與碰撞偏差，同時保留控制延遲可比性。

## D-014：不採 Windows VM，真實遊戲只作最後受限可視驗證

- 日期：2026-07-30
- 決策：訓練使用 headless simulator／Colab；不以 Windows VM 複製真實遊戲。
- 理由：部署成本高、無法安全有效平行前景鍵盤輸入，且不解決資料可解性問題。

## D-015：BC0 使用 hard label，soft target 保留作 audit

- 日期：2026-07-31
- 決策：BC0 預設使用 hard-label cross-entropy；dataset 仍保存 soft target
  與 confidence，不刪除 ambiguity provenance。
- 證據：soft loss 20.95 floors；hard loss 三 seeds 為
  29.80／30.10／25.95，全部通過 23.84 gate。soft BC 在 learner states
  與 teacher disagreement 為 41.01%。
- 可逆：未來 soft probabilities 經校正後可重新比較，但不得假設現有 confidence
  已是正確 training target。

## D-016：DAgger0 第一輪負結果後停止

- 日期：2026-07-31
- 決策：不自動執行第二輪 DAgger。
- 證據：1,634 corrections 合併後，frozen eval 從 29.80 降至 23.20 floors，
  跌破 23.84 gate。
- 理由：corrections 相對原 train set 比例過高且高度相關；繼續 aggregation
  會違反 bounded smoke 與「負結果應停」原則。

## D-017：只批准一次預先固定的 balanced correction ablation

- 日期：2026-07-31
- 決策：audit 後以 25% correction cap、原 train action ratio、12 state
  clusters × failure category round-robin 執行唯一一次新訓練。
- 證據：naive corrections/train 比 69.2%，LEFT 由 27.7% 偏至 45.5%。
- 結果：frozen 63.15 floors；fresh seeds 62.90，fresh baseline 31.25；
  action max share 36.9%，17/20 fresh episodes 達 time limit。
- 影響：basic easy curriculum 判定飽和並凍結；不再追加 DAgger rounds。

## D-018：特殊平台逐項開放，先完成 health＋normal heal

- 日期：2026-07-31
- 決策：第一項只加入可校正 health state 與普通平台 +1 heal；
  `enable_health=false` 保持預設，reward 預設不因回血增加。
- 證據：100/100 low-health Oracle landing 及 100-seed feature off/on
  episode equivalence 通過。
- 影響：health-v1 可供下一項尖刺使用，但尚不加入 training distribution；
  尖刺必須另開獨立 gate。

## D-019：尖刺先完成機制 gate，不進 generator

- 日期：2026-07-31
- 決策：spikes-v1 固定 damage 5、health 歸零終止；一般 generator 不生成
  spikes，reward penalty 預設 0。
- 證據：non-lethal、lethal、normal-heal interaction、Oracle avoidance
  各 100 seeds 全通過；no-spawn feature equivalence 100 seeds 完全相同。
- 影響：可開始下一個輸送帶 mechanism gate，但不得建立 mixed curriculum。

## D-020：輸送帶先驗證方向性速度，不宣稱真實 fidelity

- 日期：2026-07-31
- 決策：conveyor-v1 在落地時施加方向性水平速度增量，暫定值為
  ±80 px/s；feature 預設關閉，一般 generator 不產生 conveyor。
- 證據：left／right velocity 與 Oracle normal preference 各 100 seeds
  全通過；100-seed no-spawn feature equivalence 完全相同。
- 限制：尚無真實輸送帶 telemetry，80 px/s 只供 mechanism gate，不得標為
  calibrated fidelity。
- 影響：下一個獨立機制可規格化彈簧；不得建立 mixed curriculum 或啟動長訓。

## D-021：彈簧先驗證強彈跳，不宣稱真實 fidelity

- 日期：2026-07-31
- 決策：spring-v1 落地垂直速度暫定 190 px/s，普通 bounce 為 95 px/s；
  feature 預設關閉，一般 generator 不產生 spring。
- 證據：stronger-bounce 與 Oracle normal preference 各 100 seeds 全通過；
  100-seed no-spawn feature equivalence 完全相同。
- 限制：尚無真實 spring telemetry，190 px/s 只供 mechanism gate。
- 影響：下一個獨立機制可規格化翻板；不得建立 mixed curriculum 或啟動長訓。

## D-022：翻板先採可觀測的同步 active/inactive 週期

- 日期：2026-07-31
- 決策：flipping-v1 暫定 active／inactive 各 1 秒；inactive 不碰撞，
  observation 明確暴露 active state，Oracle 排除 inactive 候選。
- 證據：active collision、inactive passthrough、Oracle normal preference
  各 100 seeds 全通過；100-seed no-spawn equivalence 完全相同。
- 限制：尚無真實週期與相位 telemetry，同步 1／1 秒只供 mechanism gate。
- 影響：五項特殊機制工程 gate 完成；不得直接混合訓練，下一階段先凍結
  generator 分布、可達性與特殊平台 curriculum gates。

## D-023：首個特殊平台課程只加入低比例尖刺

- 日期：2026-07-31
- 決策：spike curriculum v0 proposal 10%，前 3 層 normal，尖刺間至少
  5 個 normal；不加入 conveyor／spring／flipping。
- 理由：damage 5、normal heal 1，五個 normal 可保證下一次尖刺前完整恢復；
  避免 generator 製造必死 health sequence。
- 證據：1,000-seed spike ratio 5.11%，reachability／health safe PASS；
  Oracle 100% 到 10 層；baseline 33.07 floors，保留 plain 95.36%，0 health death。
- 影響：准許使用獨立 seeds 1000～1059 生成 spike Teacher Dataset；
  是否重訓 BC 仍須先通過 dataset audit 與 bounded smoke protocol。

## D-024：Spike BC0 本機只跑 5-epoch 介面 smoke

- 日期：2026-07-31
- 決策：本機只允許 seed 0／5 epochs／fresh eval 1100～1119；正式 BC0
  使用 Colab 三初始化 seeds 與相同凍結 protocol。
- 證據：介面 smoke 27.0 floors、baseline 31.55、retention 85.58%；
  0 health death、無 collapse。Spike-visible test 232 rows、accuracy 75.43%。
- 限制：spike-target emergency rows 只有 10，accuracy 40%；正式報告必須保留。
- 影響：准許 bounded Colab BC0，不准本機自動追加 epochs 或直接 DAgger。

## D-025：BC checkpoint 必須用獨立閉迴路 rollout 選擇

- 日期：2026-07-31
- 決策：spike BC0 預先固定 epoch 3／5／8／11／14／17；dataset seeds
  1000～1059、selection 1060～1079、final 1200～1219 完全隔離。
- 證據：舊 Colab seed 0 的 offline-loss best epoch 17 accuracy 82.06%，
  rollout 12.85 floors／17 bottom deaths；epoch 5 accuracy 74.75%，卻有
  27.0 floors／4 bottom deaths。
- 選模：先確保無 collapse／health death，再比較 selection rollout gate、
  mean floors、bottom deaths；validation loss 只作 tie-break。
- 防洩漏：1100～1119 已用於 epoch 5／17 診斷，永久退休；final seeds
  checkpoint 凍結後只評估一次。
- 驗證：新管線 seed 0／5-epoch smoke 選 epoch 5，untouched final
  27.85 vs baseline 29.60，retention 94.09%，pipeline PASS。
- 影響：舊 seed 0 正式 FAIL 不與新版結果混算；新版 3-seed Colab 通過前
  不執行 spike DAgger0。

## D-026：Spike DAgger0 平均樓層提升但安全 Gate 失敗後停止

- 日期：2026-07-31
- 決策：balanced Spike DAgger0 只執行一輪；2/3 initialization final Gate
  後停止，不准追加 corrections、epochs 或第二輪。
- 證據：mean floors 28.57→38.75，但 floor-10 success 86.67%→75%、
  bottom death 15→27，且 seed 2 有 1 health death。
- 診斷：策略會跳過 normal platforms；generator 的 5-normal health-safe
  invariant 假設逐層落台，不能保證 learner rollout 的實際回血序列。
- 影響：下一步先改 reliability-first checkpoint gate 與 Teacher-observable
  recovery mode。1500～1519 已成為 final evidence，不得重用。

## D-027：Recovery safety 通過但 preliminary reliability 未過前不重訓

- 日期：2026-07-31
- 決策：Teacher 受傷時優先最近 normal recovery platform；checkpoint selection
  改為 safety／floor-10／bottom／Q25／median 優先。
- 證據：初始 evaluation 把 10 次 `floor_descended` events 當成到達第 10 層，
  得到 88%；後續語意稽核確認實際 `deepest_floor>=10` 為 92%。
- 判定：recovery safety/non-regression PASS，absolute reliability FAIL；不得
  事後把門檻降為 88%。
- 資料決策：暫不廣泛重蒐真實遊戲資料；未來只收集 spike、回血、跳過 normal
  與延遲的 targeted verified packet。

## D-028：Floor Gate 使用實際 deepest floor，可靠度 holdout 通過

- 日期：2026-07-31
- 決策：保留歷史 `success_rate_floor_*` 作事件計數，但所有 reachability／
  reliability／checkpoint Gate 改用 `reach_rate_floor_*` 與 deepest-floor Q25。
- 修正：Teacher 對可見但暫判不可達的平台持續靠近；反彈離台方向優先對準
  畫面內下一個 recovery／safe／可承受 spike 落點。
- 證據：1600～1699 development 95%、1700～1799 diagnosis 96%；正式一次
  untouched 1800～1899 holdout 94%，三組皆 0 health death 且高於 90%。
- 防洩漏：1700～1799 已用於失敗診斷，不列為 holdout；1800～1899 執行後
  即凍結，不得再用於調參或選模。
- 影響：准許凍結新 Spike Teacher Dataset 與 bounded BC0 protocol；不自動
  恢復第二輪 Spike DAgger、長訓練或實機 rollout。

## D-029：Spike Teacher Dataset v1 使用全新分區與固定 coverage Gate

- 日期：2026-07-31
- 決策：v1 dataset seeds 固定為 2000～2059；bounded BC0 checkpoint
  selection 固定 2060～2079；final evaluation 固定 2200～2219。
- 隔離：1500～1899 已作 DAgger／Teacher reliability evidence 或診斷，永久
  不得重用；v0 的 1000～1219 artifact 不覆寫。
- 前置：生成 v1 必須同時讀取通過的 spike curriculum Gate 與一次 untouched
  Teacher holdout Gate，並寫入 `teacher-observable-safe-platform-v2` provenance。
- Dataset Gate：60 episodes、validator 0 error、三 splits／三 actions 非空且每個
  action 至少 60 rows、至少 30 episodes 可見 spike、各 split 均有 spike、
  至少 5 spike targets／5 damage events／1 recovery decision、0 health death、
  全部 Teacher labels verified。
- 影響：只有 Dataset Gate PASS 才准執行 seed 0、最多 5 epochs 的本機 BC0
  interface smoke；正式多初始化仍須另行批准，不自動接 DAgger。

## D-030：BC0 v1 lower-tail Gate 失敗後停止，NEAT 僅列 bounded 對照

- 日期：2026-07-31
- 證據：5-epoch seed 0 final mean deepest 45.5 vs baseline 49.7，但
  reach-floor-10 60% vs 100%、Q25 7.75 vs 30、bottom 14 vs 1。
- 決策：不追加 epochs、不進多初始化／DAgger；先修正 launch／brake／recovery
  rare-branch coverage 與 Teacher controller-memory observability。
- 外部比較：NS-Shaft NEAT 專案使用自行實作的遊戲內部狀態與 fitness，並非
  直接控制封閉 Windows 原版。其單次最高樓層不可代替 mean／Q25／death Gate。
- 影響：NEAT 只可在另行凍結 protocol 後作 compact-observation、common-seed、
  bounded baseline；不能因此跳過 simulator fidelity 或最終實機驗證。

## D-031：Teacher 真機 Micro Gate 前置於所有 sequence Student 工作

- 日期：2026-07-31
- 決策：`CODEX_SEQUENCE_CONTROL_STRATEGY_UPDATE.md` 成為最高優先規格；先用
  3～5 個受限真機回合驗證 Teacher-observable 的視覺、target lock、controller
  memory 與 latency。只有 dry-run 或缺少真機 artifact 時狀態是 PENDING，不得
  進入 state-aliasing、S0/S1/S2/S3 或 rare-branch 正式資料生成。
- 理由：目前只證明 Teacher 在 simulator holdout reach-floor-10 94%、Q25 30、
  0 health death；尚未證明原版遊戲轉移。
- 影響：禁止長 BC/DAgger/PPO/DQN/NEAT，並保留全部實機安全鏈。

## D-032：單步 BC 問題改為可部署 memory／sequence 公平比較

- 日期：2026-07-31
- 決策：單步 MLP 降為 S0 對照；S1 加 explicit deployable state，S2/S3 使用
  full/compact sequence GRU。模型排序以安全、death、Q25/CVaR25、reach 為先。
- 證據：BC0 v1 mean deepest 45.5 接近 baseline 49.7，但 Q25 7.75 vs 30、
  reach-floor-10 60% vs 100%、bottom 14 vs 1；brake disagreement 71.9%。
- 影響：DAgger correction 必須是 sequence、初始最多 20%，不得恢復舊等權 row
  aggregation；NEAT 只作 fixed-budget common-seed 對照。

## D-033：Teacher Real Micro Gate 失敗，先修特殊平台 escape 與 telemetry

- 日期：2026-08-01
- 證據：3 回合／146 steps、0 safety event、動作 61/43/42，卻全部 top death；
  人工影片 HUD 最高 3/2/2，0 回合達第 5 層。Spring 有 13 步 aligned RELEASE，
  spikes 後有 16 步 recovery-aligned RELEASE。
- 決策：Gate 判定 FAIL；普通平台優於 PPO collapse 只算正面局部證據。不得進
  P4.0 或擴成 20 回合。
- 修正順序：bounded stateful key hold → persistent special-contact escape state →
  floor/event/track telemetry → physical response latency。真機 adapter 不再於每個
  同向 decision tick 強制 key-up；RELEASE、換向、失焦、錯誤與停止仍必須釋放。
  修正後以全新 run 重跑 3 回合。
- 影響：本次真機 run 轉為 development/failure evidence，不得重用為 untouched
  Gate；禁止增加 BC epochs、恢復 DAgger 或啟動其他長訓。

## D-034：真機方向輸入改為 bounded stateful hold

- 日期：2026-08-01
- 證據：舊 adapter 每個 8 Hz decision step 只 hold 80 ms，隨後無條件放鍵；
  使用者在影片觀察到逐次點按，快速 spring escape 也缺少連續橫移窗口。
- 決策：連續 LEFT／RIGHT 跨 observation 保持；每步更新 500 ms lease。
  RELEASE、換向、非 PLAYING、失焦／安全監控、例外、Ctrl+C、reset 與 close
  仍會放鍵；若 capture／decision loop 卡住，daemon watchdog 自動釋放。
- 驗證：fake controller/backend 證明同方向不重送 key-down、RELEASE 與 terminal
  會清鍵、watchdog 可獨立到期；完整 311 tests PASS。
- 影響：只完成 P3.6 repair 的本機控制介面子 Gate，尚未真機驗證；下一步是
  persistent spring/spike contact escape，不得因此進 P4.0 或開始訓練。

## D-035：特殊平台事件建立可部署的 persistent escape memory

- 日期：2026-08-01
- 證據：真機 spring event 後 13 步 aligned RELEASE、spike landing 後 16 步
  recovery-aligned RELEASE；舊 launch state 在任何 landing/floor event 立即清除。
- 決策：只用視覺 observation/event 建立 special-contact state，保存 source
  ID/kind、最後可見左右邊界、方向與 age。Spring 壓縮造成 kind 不穩時，以
  `(track_id, kind)` 快取取回事件來源邊界；不使用 simulator privileged state。
- 終止：玩家水平離開來源邊界＋clearance、確認落到非 spring/spikes 平台，或
  達 12 decision-step hard cap。普通 aligned target 不得覆蓋 active escape。
- 驗證：spring、spikes、edge clear、safe landing、hard cap、kind-change cache
  六個 fixed scenarios 全通過；完整 317 tests PASS。
- 影響：P3.6 special-controller mock Gate PASS／real pending。下一步修 floor
  telemetry 與 observation quality，不能直接重跑訓練或進 P4.0。

## D-036：真機樓層以 HUD counter 為 source of truth

- 日期：2026-08-01
- 證據：舊事件數 0/2/2，人工 HUD max 3/2/2；逐幀核對顯示 platform track-ID
  change 會漏掉真正 HUD increment，也會在同樓層 spring/spike cycle 產生假事件。
- 決策：landing 只代表接觸；`floor_descended` 改由校正 HUD 數字 ROI 的穩定影像
  change 產生。真機 reach 指標採 episode HUD max，不與 simulator deepest floor
  混稱。
- 實作：reference 634x431 下 ROI `(266,16,112,32)`、binary threshold 120、
  change 0.04、stability 0.02、連續 2 stable frames 才確認 +1。
- 驗證：重播舊 MP4 得 3/2/2，人工也是 3/2/2；三片 149 frames 全部 available，
  floor changes 2/1/1。Artifact：`p36_floor_counter_video_audit.json`。
- 影響：floor telemetry offline Gate PASS；新真機 sidecar 必須保存 floor payload。

## D-037：physical latency 以畫面 motion onset 量測

- 日期：2026-08-01
- 證據：舊 `action_latency_ms` 0～1 ms 只量 command→backend return，無法代表
  角色開始移動時間。
- 決策：保留舊欄位作相容性，新增 `command_dispatch_latency_ms`；方向切換／起按
  後，直到 observation `velocity_x` 首次朝正確方向且達 10 px/s，記為
  `physical_response_latency_ms`。500 ms 未反應則記 timeout。
- Gate：新 3 回合 run 至少各有一個 LEFT／RIGHT physical sample；否則 observation/
  latency Gate FAIL。
- 驗證：pending、motion onset、反向速度拒絕、既有同向慣性排除與 RELEASE
  清除測試通過；完整 324 tests PASS。舊影片無 command timestamp，狀態為
  real pending。
- 影響：P3.6 repair package 已 READY FOR RETEST；仍禁止自動開始或進 P4.0。

## D-038：terminal safety no-op 與 aligned dwell 使用不同處置

- 日期：2026-08-01
- 證據：第二次 retest episode 1 到 HUD floor 4 且控制線性，但 terminal 後
  `action_applied=false` 被 runner 當 exception；同一影片另有 21 步 aligned
  RELEASE，接觸尖刺遭遮蔽且 generic damage 沒有 source kind。
- 決策：non-PLAYING 且 terminated/truncated 的未套用 action 是預期安全 no-op，
  不寫 transition、不中斷 Gate runner；PLAYING 下 no-op 仍是錯誤。Teacher 另以
  deployable target ID/kind、relative gap 與連續步數建立 4-step dwell escape，並讓
  top-danger 優先於 recovery。
- 驗證：同一 MP4 離線 replay 在 frame 53 開始持續 RIGHT，取代直到死亡的 21 步
  RELEASE；targeted 75 tests PASS。必須再以全新 3 回合 artifact 決定 Gate。
- 影響：第二次 run 是 development/aborted evidence；P3.6 仍 FAIL／STOP，禁止 P4.0
  與任何新訓練。

## D-039：Spring 以近距離視覺幾何補足漏失的 bounce event

- 日期：2026-08-01
- 證據：第三次 run 完整達 HUD 5/5/2，但 EP3 spring gap 週期約
  18→50→84→19 px，`spring_bounce` event 為 0；使用者觀察角色反覆彈數次。
- 決策：nearest kind 為 spring/spikes 且 gap ≤30 px 時，直接啟動原有 persistent
  special escape。這只使用部署時可見 observation，不使用 simulator privileged state。
  Terminal dialog 不再列為遊玩中 HUD telemetry 必填幀。
- 驗證：EP3 MP4 離線 replay 由 frame 14 起連續 LEFT；targeted 74 tests、完整
  331 tests、compileall、dry-run、audit JSON 與 diff check 全 PASS。
- 影響：repair v3 可進下一次 bounded 3-episode retest；P3.6 仍 FAIL／STOP，禁止
  state-aliasing、S0–S3、資料生成或訓練。

## D-040：貼牆 special escape 必須由共用 wall guard 硬性覆蓋

- 日期：2026-08-01
- 證據：5 回合 EP1 spring 在 left guard zone 仍有 12 個 outward LEFT；EP4
  spikes 有 12 個連續 special RIGHT，x 由 326.5 推到約 410。最高人工 floor 8
  不能抵銷可重現的方向鎖死。
- 決策：playfield 40～423 px、margin 32 px。所有 policy output 在共同出口接受
  inward override；左側 LEFT→RIGHT、右側 RIGHT→LEFT，換向仍保留 brake。
- Telemetry/Gate：逐步記錄 wall guard 與 applied outward streak；新 Gate 要求
  telemetry available、outward count=0、max streak=0。
- 驗證：special/launch/dwell/brake fixed tests PASS；8 MP4／497 frames replay
  0 outward；targeted 84、完整 338 tests PASS。
- 影響：repair v4 可重跑唯一 bounded 3-episode Gate；新 artifact 未 PASS 前
  P4.0、資料生成與任何訓練維持 STOP。

## D-041：Wall safety 必須是可完成的撤離狀態，不能只計 outward action

- 日期：2026-08-01
- 證據：repair v4 後 18 回合中 13 bottom death；最新 EP4 雖 outward count=0，
  但單步 guard 離開 32 px 區後，persistent launch 又把角色拉回，形成 12 次快速
  反轉。另有 70/721 steps player missing。
- 決策：guard 改成 enter/exit hysteresis 的 latched evacuation，觸發時清除 launch、
  special 與 dwell 衝突狀態；以 0.2 s velocity lookahead 提前攔截高速撞牆，安全
  退出後有 cooldown。Player detector 接受 14 px 暖色 component，tracker 最多橋接
  2 幀。Launch 單次方向承諾最多 3 steps，之後強制 replan，landing action 使用 vx
  projected position。
- Gate：保留 global reversal telemetry，但只以 wall-corridor burst 阻擋，因跨樓層
  正常落台本來就可能快速換向；另要求 missing streak≤2、wall re-entry=0、floor-1
  bottom=0、outward=0 與 aligned-release bounded。
- 驗證：18 MP4／729 playing frames 最終 replay effective missing 0、outward 0、
  wall re-entry 0、wall burst max 1；targeted 102、完整 350 tests PASS。
- 影響：repair v5 只取得 OFFLINE PASS；壓縮 MP4 無法證明 raw capture 與真實
  closed-loop 成功。P3.6 維持 FAIL，下一步唯一允許的是 bounded 3-episode retest。

## D-042：平台離台與空中落點必須是不同控制 phase

- 日期：2026-08-01
- 證據：repair v5 兩次真機 Gate floors 為 `2,3,3` 與 `2,2,5,3,3`，均 FAIL。
  471 steps 有 203 RELEASE、154 aligned、175 launch；37 個 RELEASE 發生於仍接觸
  support 且 edge distance ≤20 px。影片與 sidecar 顯示同一平台上 launch→aligned
  RELEASE→re-launch 的循環。
- 決策：不得只調大 launch steps 或取消 brake。下一版要加入明確
  `ON_SUPPORT_DEPARTURE` latch，保存 source／destination／direction；只有穩定
  support-lost 或 safety abort 才交給 `AIRBORNE_LANDING`。landing alignment 不得在
  support contact 時單獨觸發 RELEASE。
- Gate：新增 same-support departure cycles、support exit latency、destination target
  switches 與 edge RELEASE ratio。既有 aligned streak ≤5 不足以捕捉交錯循環。
- 影響：repair v5 REAL FAIL；完成 replay tests 與 departure repair 前不再真機重跑，
  P4.0 與所有訓練維持 STOP。

## D-043：Support departure 使用 source/destination-aware latch

- 日期：2026-08-01
- 決策：有 support contact 且目標不是來源平台時，進入獨立 departure phase；保存
  source bounds、destination target 與 direction。直到 source support-lost 才交回
  airborne landing，不讓 projected alignment 提前 RELEASE。
- 安全：wall evacuation 可改為向內但不拆掉 lifecycle；special-contact 優先；
  8 steps 未離台則 safety abort。F8、失焦、related-window 與 release_all 不變。
- Gate：same-support restart=0、departure target switch=0、timeout=0、edge RELEASE
  ratio≤25%、至少一筆 exit、max steps≤8、support aligned streak≤3。
- 證據：8 MP4 replay 有 177 departure-active steps，restart 0、target switch 0、
  edge RELEASE 17/96、support aligned max 3；357 tests PASS。MP4 無法驗證新 action
  是否真的造成 support-lost，因此狀態只升為 OFFLINE PASS／REAL PENDING。

## D-044：P3.6 Gate 必須量測可執行失敗，不以動畫／正常 settle 代替

- 日期：2026-08-01
- 證據：repair v6 三回合實機已達 HUD parser `5,3,10`，0 safety event、46 次
  support exit、departure median 3／max 5 steps、restart／timeout 皆 0；舊 Gate
  仍因 support-aligned 4、wall-corridor reversal 3、missing streak 17 與任一零信心
  observation 而 FAIL。逐步 sidecar 證明 aligned 4 發生於 `target == support` 的
  settle；wall reversal 跨 special escape；29 個零信心 steps 全是 RELEASE 且
  4 個 dropout 全部恢復。
- 決策：Gate v2 只把 `target != support` 時的 aligned RELEASE 視為 actionable
  support stall；wall oscillation 只在 wall guard／evacuation active 時計數，
  special／launch escape 會切斷 burst；observation dropout 須在 20 steps 內恢復、
  期間 directional action=0，且非 terminal 時不得未恢復。
- 安全：舊 raw missing、global reversal、support settle 與 aligned streak 全數保留為
  telemetry，沒有刪除證據；outward push、wall re-entry、departure timeout、F8、
  foreground 與 release-all Gate 未放寬。本決策不改任何 controller action。
- 驗證：同一份 3 回合 sidecar v2 重分類 29 invalid／4 recovered／max 15、blind 0、
  unresolved 0、active-wall burst 0、actionable support RELEASE 0，全部 checks PASS；
  完整 363 tests PASS。
- 影響：此為 post-hoc 語意修正，不得冒充獨立新實驗。P3.6 維持 HOLD／STOP；
  下一步只允許一次全新 v2 runner 3 回合確認，PASS 後才進 State-aliasing Audit。

## D-045：頂部漏偵測只允許有限方向橋接；wall cooldown 必須完成撤離

- 日期：2026-08-02
- 證據：Gate v2 後兩組 floors `1,4,1` 與 `7,5,2` 均 FAIL；第二組唯一 blocking
  check 是 3 次 wall re-entry。其 EP2 sidecar 顯示 wall exit 後 cooldown RELEASE，
  舊 special／launch 方向隨後回牆；另有 top-pressure player dropout 期間長 RELEASE，
  使用者看到普通平台停頓後 top death。
- 決策：wall cooldown 遇原牆方向要求時持續向內，不等待回撞。只有最近可靠畫面
  確認 top danger 且 controller 已有實際方向時，允許最多 2-step 同方向 bridge；
  一般 missing 仍 RELEASE，第 3 step 記為 exhausted 並 RELEASE。top-danger
  same-support settle 2 steps 後啟動 edge escape。
- Gate：升為 v3，approved bridge 與 blind action 分欄；bridge max<=2、exhausted=0。
  其餘 observation、wall、departure、lower-tail 與 safety checks 不放寬。
- 驗證：369 tests、compileall、no-input dry-run PASS；最新三支 MP4 counterfactual
  replay wall re-entry 3→0、outward 0。影片不能模擬新 action 後的畫面，因此只列
  OFFLINE PASS／REAL PENDING。
- 影響：P3.6 保持 HOLD／STOP；下一步只允許一次 supervised bounded Gate v3。

## D-046：Departure timeout 不得永久 block；raw dropout 必須無損留證

- 日期：2026-08-02
- 證據：Gate v3 EP2 timeout 後 `support_departure_safety_abort` 連續 RELEASE 17
  steps；EP2／EP3 另有 25／16-step player missing。角色在 MP4 肉眼可見，且壓縮片
  重播 438/439 raw detected，與 live 41 invalid 不一致。
- 決策：8-step departure hard cap 保留，但 source block 只維持 2-step cooldown，
  之後依最新 target retry。每回合以 milestones 1/3/8/16/24/recovery、最多 6 組
  lossless raw＋mask＋component metadata 保存真機失敗證據。
- Gate：升為 v4；recovered dropout<=8、abort cooldown<=2、forensic manifest
  available。Timeout 仍須 0，blind control、wall、reach 與 safety 門檻不變。
- 影響：v8 只達 CODE／TEST READY；舊 MP4 無法模擬 retry 後的 closed-loop 畫面，
  必須一次 fresh bounded Gate v4，未通過不得進 P4.0。

## D-047：單一高樓層 best case 不得覆蓋 lower-tail 早死

- 日期：2026-08-02
- 證據：fresh Gate v4 HUD floors `9,2,2`；35/36 checks PASS，但只有 1/3
  reach floor 3，median、Q25 與 CVaR25 都是 2。EP2／EP3 都是 bottom death。
- 決策：不以 EP1 floor 9 或主觀「整體順暢」覆蓋預先固定的 2/3 reach-3 門檻；
  P3.6 維持 HOLD，不進 State-aliasing Audit／P4.0。
- 下一修復：只處理兩個由影片及 sidecar 證實的分支：momentum-aware landing
  braking，以及 destination-aware special／launch escape。不得放寬 Gate 或展開長訓練。

## D-048：Airborne intercept 與 support departure 必須使用不同時間尺度

- 日期：2026-08-02
- 證據：Gate v4 EP2 在 rising／長下降窗口仍用固定0.25秒投影，直到接近落點才停止
  LEFT；EP3 在 spring 右緣沿用先前 RIGHT。初版長 horizon 若直接套在 support
  departure，會把已在離台的方向反轉，破壞 v8 lifecycle tests。
- 決策：airborne landing 依垂直距離／速度使用0.25～0.55秒 horizon；rising 使用
  0.55秒。仍有 support 時改用 destination safe interval＋既有動量，不用長 horizon。
  special escape 優先更深可達落點；無落點時只在12 px edge 且 outward velocity
  >40 px/s 才強制反向。
- Gate：升為 v5，要求兩組新 controller telemetry available；v4 全部 safety、timeout、
  wall、dropout、departure 與 lower-tail checks 保留。
- 影響：Repair v9 僅為 CODE／TEST READY。舊 MP4 不會回應新 action，必須 fresh
  bounded Gate v5 才能判斷 closed-loop lower-tail。

## D-049：特殊平台 contact 必須採語意 identity 與有界方向承諾

- 日期：2026-08-03
- 證據：三組 Gate v5 共11回合只有中間一組 PASS，後續5回合仍因 bottom death
  2/5 FAIL。影片／sidecar 有152個 special-active steps，其中50個是方向切換前的
  `RELEASE_ALL`；最長同一 spring 區段25 steps。該區段 tracker ID
  27→30→34→38→41，每次都把 escape steps 重設；spikes 即使 ID 穩定，也因
  `visible_landing` 與 `edge_momentum_guard` 交替而反覆換向。
- 決策：special-contact lifecycle 不再以 raw track ID 作唯一 source identity。
  同 kind、水平幾何連續且 player-relative contact 相符時須保留同一 semantic
  episode、elapsed steps、方向與 replan budget。初始方向需短期 latch；只有穩定且
  顯著較佳的 destination 可觸發至多一次 replan，wall safety 仍有最高優先權。
- Hard cap：達一般 escape cap 後不得 clear 再由同 source 立即啟動；進入有界
  forced-exit，仍未脫離則標記 safety abort、停止後續 Gate。不得用無限重啟換取
  偶然成功。
- Gate：v6 新增 semantic contact duration、track reacquisition、same-source restart、
  reversal/replan 與 safety-abort 指標；現有 Gate v5 checks 全數保留。
- 影響：Gate v5 的單組 PASS 不足以進 P4.0。Repair v10 recorded regression 與完整
  測試通過前，不再執行真機 Gate；之後只允許一次 fresh bounded Gate v6。

## D-050：特殊平台前的視覺失聯屬於 special-context Gate

- 日期：2026-08-03
- 證據：Repair v10 第二組 Gate v6 的 special lifecycle 最長只有 5 steps、無反轉，
  但使用者仍看到尖刺前猶豫。Sidecar 證實 EP2 steps 63～72 為連續 10 個
  `player_not_detected`／`RELEASE_ALL`，step 73 才啟動 spikes contact。Lossless mask 顯示
  角色與普通平台暖色紋理合併成 95～111 px 寬 component。
- 決策：不再增加尖刺移動 heuristic；改在 player mask 內移除寬於有效角色的水平
  color run，保留原寬高與彩色 pixel 門檻。Gate v7 在每個 semantic special contact 前
  額外量測 dropout 與 release streak，兩者必須 <=2 steps。
- 影響：舊 Gate v6 的 in-contact PASS 指標不能單獨證明肉眼無停滯。新 detector 離線證據
  與 389 tests 已通過，但只能在 fresh 3-episode Gate v7 後判斷 closed-loop 成效；
  此前 P3.6 仍 HOLD。

## D-051：目標可達性與 RELEASE 後落點使用不同時間尺度

- 日期：2026-08-03
- 證據：Fresh Gate v7 floors `2,5,2`。EP3 step 27 舊模型以
  vx 約 144 px/s 外推 0.25 秒，誤以為 x 將到 238.5 並對齊 spring；
  實際 RELEASE 後下一幀只移動約 5.5 px。EP1 step 38 也因同一假設
  在目標前停下。
- 決策：保留 0.25～0.55 秒 controlled-motion horizon 選擇可達目標；
  最後 RELEASE-vs-steer 判斷改用 0.05 秒 release projection。離線回歸
  要求上述兩幀分別持續 LEFT 與 RIGHT，而不是 RELEASE。
- Gate：v8 必須有 release-projection seconds/projected-x/delta telemetry。
  舊 sidecar 缺欄位時只能診斷，不得重分類成 PASS。
- 語意修正：generic pre-special RELEASE 可能是正常自由落體，只留
  telemetry；只阻擋 pre-special observation dropout 與 dropout-caused RELEASE。

## D-052：回合重開必須辨識 EXIT 焦點並使用有界修正

- 日期：2026-08-03
- 證據：Fresh Gate v8 第 1 回合後只完成 1/3 episodes；保存的
  `captures/diagnostic_menu_current.png` 顯示焦點在最左側 EXIT，舊 guard 只辨識
  START 與 TWO_PLAYER，焦點觀測上限 450 frames 在 8 Hz 約為 56 秒。
- 決策：校正 EXIT rect `(172,297,70,21)`；已知 EXIT 以最多 3 次
  Tab 進行修正，每次後都必須重新證實 START 才能送 Enter。未知焦點
  繼續 fail closed，不嘗試修正或 Enter。
- 時限：passive wait 由 450 降為 24 frames，correction wait 由 450 降為
  12 frames；在 8 Hz 分別約 3 秒與 1.5 秒。安全守衛、F8、foreground
  與 release-all 不變。
- 狀態：保存實機 frame 離線辨識為 EXIT；34 targeted 與 393 full tests
  PASS。待下一次 fresh Gate v8 驗證 closed loop reset。

## D-053：Teacher 控制策略提案必須逐項以最新真機證據審查

- 日期：2026-08-03
- 證據：Gate v7 floors `2,5,2` 的兩個 early bottom deaths 均從普通平台
  RELEASE 落點誤判開始；v7 spring steps 101～116 雖跨 4 個 contact/source IDs，
  但之後落到 normal platform；v7 spike contact 多數 1～3 steps 離開，terminal
  contact 可由 transition flag 分辨。Gate v8 只有 1/3 episodes，不能定案。
- 決策：action-conditioned dynamics 與 Spring lifecycle 僅接受離線、修改後的
  audit/telemetry 範圍；safe interval、receding horizon 證據不足；新增 Spike FSM
  與 generic active stuck watchdog 拒絕。不得因提案命名就預設機制正確。
- Gate：Normal Landing、Spring Escape、Spike Escape、Restart/Safety 分開報告；
  任一 blocking Gate 未過，整體 P3.6 維持 HOLD。完整決策表見
  `reports/TEACHER_CONTROL_STRATEGY_REVIEW.md`。

## D-054：Action-conditioned 模型須以 episode-held-out regime coverage 阻擋部署

- 日期：2026-08-03
- 證據：最近四組 run 共 694 transitions；嚴格排除 event、wall、special、recovery、
  dropout、edge 與 motion-boundary 後有 337 rows／10 episodes。既有模型形式的
  leave-one-episode-out x MAE 4.049 px，優於 carry-vx 8.462 px；2～5 step
  actual-action rollout 也較佳。但 LEFT-while-moving-right 只有 7 rows，
  RIGHT-while-moving-left 只有 8 rows。
- 決策：不新增重複 dynamics subsystem，也不把目前 fit 接進 `SafePlatformPolicy`。
  reverse-braking 每側至少 30 個嚴格樣本、各 action 與 bounded rollout 的 held-out
  Gate 全過前，`shadow_model_eligible=false`；live deployment 永遠需要另一次明確決策。
- 舊資料核對：14 份 calibration logs／450 strict continuous rows 僅含 LEFT 1／
  RIGHT 0 個 reverse-braking rows，且無 controller sidecar，不能與 primary Gate
  合併。固定平台 reversal 後續結論由 D-055 覆蓋。
- 特殊平台：只以短 same-kind gap 聚合 encounter 作診斷，不把 unstable track ID
  當物理真值，也不讓該聚合影響 live action arbitration。

## D-055：固定平台反覆左右只能作 system identification，不得解鎖落台控制

- 日期：2026-08-03
- 證據：3 個 completed bounded runs 有125 raw／84 strict rows、LEFT 23／RIGHT 21
  reverse-braking；使用者觀察角色只在同一平台反覆左右。第4 run 在提出分布疑慮後
  立即停止，57 raw／40 strict rows 保留但排除；方向鍵確認未卡住。
- 決策：不再為湊30/30重複固定平台校正。已完成資料只證明短期 action response，
  一律 `diagnostic-only`，不得合併 natural Teacher Gate、不得部署 dynamics、不得
  開啟 receding horizon 或 P4.0。
- 下一證據：最多一次 bounded 3-episode natural Teacher run，現行 controller 不變，
  candidate model 不參與 action；只在事後以完整 controller sidecar 分析自然 landing、
  support、special、recovery 與 terminal context。若沒有資訊增益即停止。

## D-056：Support-edge Gate 必須分離 actionable departure 與 generic settle

- 日期：2026-08-03
- 證據：完整 natural run floors `2,9,7`；原 Gate v8 唯一 FAIL 為 edge RELEASE
  16/57。逐筆 sidecar 顯示其中15筆 `target_platform_id == support_platform_id`，
  另1筆是 spring bounce 的 direction-change brake；departure cycle／target switch／
  timeout／actionable support RELEASE 全為0。
- 決策：blocking edge opportunity 只在 `target != support` 或
  `support_departure_active` 時計數；所有 edge occupancy 另以 generic counters 保存。
  不降低25%門檻、不修改 Teacher policy、不重跑已完整的3回合。
- 結果：相同 sidecars 的 Gate v9 actionable RELEASE 0/39，51/51 checks PASS；
  generic 16/57 仍可追蹤。3回合 Micro Gate 通過，但一個floor-2 tail case仍存在。
- 下一步：只允許一次10回合 stability Gate；至少7/10 reach-3、4/10 reach-5、
  bottom death<=2、spring/spike皆有 coverage，且所有 safety／telemetry checks PASS。
  未過即停止，不開始 P4.0 Student 正式訓練。

## D-057：10 回合 Gate 修正終局與特殊 brake 語意，不降低表現門檻

- 日期：2026-08-03
- 證據：完整 run `20260803_034023_674665` 的原始 Gate v10 為 10/10 回合、
  safety event 0、reach-3 7/10、reach-5 4/10；兩個 FAIL 分別是 bottom terminal
  9/10 與 special direction-change brake 最大2。逐筆 sidecar 顯示 brake=2 的
  contact 都是 entry brake 加上唯一一次 replan/reversal brake，不是反覆振盪。
- 終局語意：NS-SHAFT 是持續下樓的無限遊戲；要求所有 bottom terminal<=2 會反向
  偏好 top death，且與 reach-3 Gate 衝突。Gate v11 保留完整 bottom telemetry，
  blocking 指標改為 `terminal=bottom and floor<3`，budget 等於既定 reach-3 允許的
  miss 數；floor-1 bottom death=0、reach、Q25/CVaR 與全部 safety checks 不變。
- Brake 語意：每個 special contact 最多 entry brake 1 次，加每次准許 reversal
  1 次；因 reversal 本來最多1次，絕對 brake 上限仍為2。Replan、reversal、contact
  duration、restart 與 safety-abort checks 全數保留。
- HUD 證據：10 支 MP4 逐幀 audit 全部可讀、counter 每幀 available、初始 floor=1；
  episode 3 的 terminal frame 為 floor4，而 live sidecar 為3。可信 video correction
  只能向上、不得覆寫 raw artifact，且來源 run 必須完全相同。
- 結果：修正 floors `8,11,4,2,2,5,4,4,8,2`；Gate v11 reclassification 全部
  checks PASS。這不是降低 reach 或 lower-tail 門檻，也沒有重跑／挑 episode。
- 影響：P3.6 stability qualification 完成，只解鎖 P4.0 State-aliasing Audit。
  由於 reach-3 與 early-bottom budget 都剛好壓線，S0～S3 與正式 Student 訓練仍須
  等 P4.0 Gate，不得直接開始 BC、DAgger、PPO、DQN 或 NEAT。

## D-058：姓名輸入 modal 只能精確識別後 Enter-once，未知視窗維持 fail closed

- 日期：2026-08-03
- 證據：前一個 10 回合 attempt 在 5/10 後遇到遊戲 owned 的姓名輸入對話框；
  使用者確認可直接 Enter 跳過。若把所有同程序 related window 都自動 Enter，可能
  對未知對話框產生不可逆操作。
- 決策：只有唯一、same-process、owner=target、class=`#32770` 且 title 符合姓名
  白名單的 modal 才可送一次 Enter；不輸入文字。其他 related window 一律停止並
  release all。功能還需明示 `--dismiss-name-entry`。
- 證據限制：程式與測試已通過，但成功的完整 10 回合 run 沒有再遇到 modal，故只算
  code-tested，不能宣稱 live-validated。

## D-059：P4.0 只用 lagged causal memory；通過後優先 compact S1

- 日期：2026-08-03
- 證據：Gate v11 的10回合共753筆，transition/controller在筆數、step、action完全
  對齊。runner 在 `policy.choose` 後才取 `memory_snapshot`，因此同一步
  `previous_action` 已等於 action label，`controller_phase` 亦由本步 reason 決定。
- 決策：P4.0 正式 representation 使用 episode 內 `memory[t-1] -> decision[t]`；
  第0步用reset/empty state。當步 memory僅列 leakage ceiling，不參與Gate；所有 raw
  platform/track IDs 排除。k=5 且鄰居只能跨episode，observation/memory block固定各0.5。
- 結果：observation-only disagreement/entropy/accuracy為
  `56.20%/1.0402/48.07%`，causal full為`45.39%/0.8529/61.09%`；衝突相對下降
  19.23%，paired episode bootstrap CI `[0.0979,0.1411]`，P4.0全部checks PASS。
- 影響：只解鎖 P4.1 bounded公平消融。causal action-history單組42.76%優於121維
  full memory，故S1優先compact schema；launch/brake仍高衝突，不能跳過P4.1或直接
  啟動rare-branch dataset、長BC/DAgger/PPO/DQN/NEAT。

## D-060：發布前只刪除已封存／可再生資料，保留 P4.1 與真機 provenance

- 日期：2026-08-03
- 稽核：本機忽略資料中 `.venv` 約3.5 GB、logs 352 MB、artifacts 228 MB、captures
  71 MB、models 70 MB。真機 sidecar/MP4、校正、templates 與最新dataset不能因容量
  大就視為垃圾；舊action-collapsed權重與中間aggregate則已明確禁止續用。
- 決策：移除三個舊Colab ZIP、全部舊PPO/probe weights、34個BC/DAgger `.pt`、六個
  已被clean easy／Spike v1取代的correction/aggregate JSONL、五個無引用且已有v2的
  重複JSON、舊PPO/pip啟動log與cache，共237.82 MiB。
- 保留：`teacher_dataset_v0.jsonl`、`spike_teacher_dataset_v1.jsonl`、Gate v11
  十回合完整資料、calibration、vision templates、summary JSON/CSV與所有失敗報告。
- 影響：舊模型的bit-exact重播不再保證，但它們原已禁止續訓；結論與設定仍由summary、
  reports、版本化script與seed保存。P4.1不得依賴已刪除checkpoint。

## D-061：P4.1 固定舊 Dataset v1，不用新版 Teacher 靜默重建

- 日期：2026-08-03
- 證據：保留的 Spike Teacher Dataset v1 是3,529 rows，SHA-256
  `fa3e111a6204ac53767824e8d71d1ccf841637976427c410c1e14dff308c7a0a`；以current
  source、相同seeds 2000～2059與相同CLI重建得到3,571 rows、SHA-256
  `04417d1de89535b16f9ee65a3f5910a476437a3ecb28cb4e4acae9a289975205`，動作分布
  也由1328/1092/1109變為1729/975/867。Teacher控制已演進，但兩者仍標成同一
  `teacher-observable-safe-platform-v2`，故名稱/version不足以證明等價。
- 決策：P4.1是representation公平消融，固定使用曾產生S0 lower-tail失敗證據的原
  3,529-row資料；manifest以hash拒絕替換。Colab專用bundle明確攜帶此ignored JSONL，
  notebook缺檔即停止，不呼叫generator。
- 替代方案：以current Teacher建立Dataset v2；拒絕在本Gate採用，因需先升policy／
  dataset version、重跑Teacher reliability與dataset coverage，否則同時改資料和模型
  表示會混淆因果。未來可作獨立實驗，不能覆寫P4.1 v1。
- 影響：一般GitHub source ZIP不足以跑P4.1；須用`package_p41_colab.py`。大型JSONL
  仍不commit，bundle manifest保存commit、dirty flag、dataset/archive hash。

## D-062：P4.1 明確 causal state 只由 Student 過去動作重建

- 日期：2026-08-03
- 證據：P4.0中action-history group的disagreement 42.76%，優於121維full memory
  45.39%；同一步post-decision sidecar則低至11.42%，但已確認含本步label leakage。
- 決策：S1/S3採固定9維state：previous action、presence、last non-release direction、
  same/release streak與recent switch rate。它在decision前snapshot，action選出後才更新；
  reset全零。Teacher phase、target、platform ID及任何當步sidecar都不進第一版。
- Sequence：S2/S3固定24-step、burn-in 8、GRU-128；每row label只計一次。四組300
  updates、三初始化、相同selection/final env seeds；offline accuracy不選模。
- Gate：候選必須對S0的Q25、CVaR25、reach-10、bottom及oscillation跨初始化一致改善，
  維持health safety且不collapse。selection FAIL不碰final；final FAIL停止P4.2。
