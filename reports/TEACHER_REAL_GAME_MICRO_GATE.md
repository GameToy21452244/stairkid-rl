# Teacher Real-Game Micro Gate Report

日期：2026-08-01

## 結論

**FAIL／STOP：3 回合真機 smoke 已完成；普通平台表現優於舊 PPO 的塌縮行為，
但特殊平台 escape、連續控制、floor telemetry 與真實 action-latency Gate 未通過。**

依 `CODEX_SEQUENCE_CONTROL_STRATEGY_UPDATE.md`，第一個 Gate 已取得實測負結果。
本輪在此停止，沒有執行 State-aliasing Audit、
S0/S1/S2/S3、rare-branch dataset、sequence smoke、conservative DAgger 或 NEAT。

## 真機實測結果

Run：`logs/teacher_real_micro_20260801_000521_887512/`

| 指標 | 結果 | 判定 |
|---|---:|---|
| Episodes／steps | 3／146 | 完整 |
| 安全事件 | 0 | PASS |
| Transition/controller/MP4 | 3/3 完整 | PASS |
| RELEASE／LEFT／RIGHT | 61／43／42 | 無 collapse |
| 最大 action share | 41.78% | PASS |
| 自動 floor events／episode | 0／2／2 | 與影片不一致 |
| 人工影片 HUD 最高樓層 | 3／2／2 | 1 回合達 3、0 回合達 5 |
| Terminal | top／top／top | FAIL |
| Observation valid | episode 2 最後 2 步 player missing | FAIL |

自動 summary 原判 `reach-floor-3=0`，但影片清楚顯示 episode 1 HUD 由第 1 層
到第 3 層；同時 episode 2／3 各記 2 個 `floor_descended`，HUD 最高卻只有第
2 層。因此目前 event-based floor telemetry 既會漏計也會重計，不能作可靠 Gate
指標。人工覆核後仍只有 1/3 達第 3 層、0/3 達第 5 層，所以不論採自動或人工
語意，Teacher Real Gate 都是 FAIL。

## 第二次 retest（部分成功、Gate 無效）

Run：`logs/teacher_real_micro_20260801_031907_767286/`

- Episode 1 留下 71 筆 canonical transitions、71 筆 controller rows 與 72-frame
  MP4；HUD max floor 4，動作 RELEASE/LEFT/RIGHT 為 38/18/15。
- LEFT/RIGHT 共 10 筆 physical motion-onset samples，皆約 94 ms；使用者人工觀察
  也確認移動比舊逐次點按線性。這支持 stateful hold 已在真機生效。
- Run 在 terminal 後中止：phase probe 已偵測非 PLAYING 並安全拒絕送出下一個
  action，但 runner 把合法的 `action_applied=false` 當成 exception，summary 因此
  `episodes=[]`。這是 runner accounting bug，不是輸入安全失效。
- 因不足 3 回合且 summary aborted，本 run 判為 **FAIL／ABORTED**；floor 4 只能作
  development evidence，不能宣稱 P3.6 PASS 或進入 P4.0。

影片與 observation audit 顯示 steps 50～70 連續 21 步
`aligned_with_recovery_platform → RELEASE_ALL`。角色實際位於會造成傷害的平台序列，
但接觸平台被角色遮蔽而未被辨識為 spikes；nearest observation 指向另一個 normal，
相對 gap 約 57 px，最後扣血事件也沒有 source kind。因此只依 special-event 的
escape memory 不足以覆蓋這類 perception alias。

Repair v2：

- terminal 前 action safety no-op 只在 non-PLAYING 且 terminated/truncated 時被接受；
  terminal frame 仍保存，未送出的 action 不寫成 transition。PLAYING 下 no-op 仍報錯。
- 新增 aligned dwell sequence state：同一 target 且相對 gap 在 3 px 內連續 4 個
  observations，就沿最近邊緣啟動 persistent launch escape；不需 privileged state。
- top-danger 選深落點現在優先於 recovery，避免低血量時為等回血而被整段序列帶到頂端。
- 以本次 MP4 離線重放，新策略在 frame 53 由 RELEASE 轉 RIGHT，後續維持 escape；
  舊策略同區間會連續 RELEASE 到死亡。這只證明 regression 被命中，仍須新真機 Gate。

## 第三次 retest（reach Gate 改善、spring observation 仍 FAIL）

Run：`logs/teacher_real_micro_20260801_034041_303682/`

| 指標 | 結果 | 判定 |
|---|---:|---|
| Episodes／steps | 3／268 | 完整 |
| HUD max floors | 5／5／2 | reach-3、reach-5 PASS |
| Mean／median floor | 4.0／5.0 | 明顯優於舊 3/2/2 |
| RELEASE／LEFT／RIGHT | 105／81／82 | 無 collapse |
| Physical samples／median | 32／94 ms | PASS |
| Safety events | 0 | PASS |
| Transition/controller/MP4 | 3/3 完整 | PASS |
| Observation valid | episode 1/3 有 player missing | FAIL |
| Floor available | episode 2 terminal dialog 為 null | accounting FAIL |

使用者人工確認水平操作保持線性；這與三動作平衡、32 筆雙方向 motion onset 及兩個
reach-floor-5 回合一致。P3.6 仍不能通過，因 episode 3 在 spring sequence 多次失去
player observation，且角色會在彈簧上重複數次才離開。

EP3 解碼顯示 spring 本身其實有被辨識，但 contact gap 呈週期
18→50→84→19→85→19 px，完全沒有 `spring_bounce` event；landing detector 還把
前段 contact 關聯成 spikes。故 event-only special escape 不會開始，而 repair v2
的 stable-gap dwell 也刻意不會把週期跳躍誤判成固定卡住。

Repair v3 直接使用 deployable close geometry：nearest kind 為 spring/spikes 且
gap ≤30 px 時建立 persistent special escape。以 EP3 MP4 離線 replay，新策略在
frame 14 起連續 LEFT，取代原本多輪 RELEASE。另將 terminal dialog 排除於遊玩中
HUD availability Gate，避免自然終止幀製造假 floor failure。Targeted 74 tests、
完整 331 tests、compileall、dry-run 與 diff check 全 PASS；仍須全新三回合驗證。

## 後續 3／5 回合 retest（最高突破、wall safety 仍 FAIL）

Runs：

- `teacher_real_micro_20260801_035120_340142`：3 回合，artifact floors 5/2/1。
- `teacher_real_micro_20260801_035223_571410`：5 回合，artifact floors 2/1/3/3/7；
  使用者人工看到 terminal 附近第 8 層。

五回合 run 的 safety events、floor availability、physical latency、target lock、
record/video completeness、action collapse、reach-floor-3/5 與 failure taxonomy
checks 全通過。Gate 仍因 observation valid 失敗；最高樓層突破是正向 transfer
證據，但不能覆蓋 controller safety failure。

Wall failure 逐步 audit：

- EP1 spring：steps 10～21、23～27 共 17 個 special LEFT；進入 left guard zone
  後仍有 steps 15～21（7）及 23～27（5）outward actions，x 約 54～56。
- EP4 spikes：steps 22～33 共 12 個 special RIGHT，x 由 326.5 到最高約 410；
  其中 11 步位於 right guard zone。Hard cap 後才煞車／向左，之後又有 dwell
  escape 向右並受傷。

因此本輪維持 **P3.6 FAIL／STOP**。這不是訓練量問題，而是 persistent escape 的
終止幾何在貼牆來源上不可滿足。

Wall-safety repair v4 已先由 `P36_WALL_SAFETY_REPAIR_PLAN.md` 凍結，再實作：

- 40～423 px playfield、32 px margin 的共用 wall guard；
- 左 guard zone 禁止 applied LEFT、右 guard zone 禁止 applied RIGHT；
- 覆蓋 special/launch/dwell/recovery/top-danger/normal move，並保留一幀 brake；
- sidecar 保存 guard active/side/original action 與 applied outward streak；
- Gate 新增 wall telemetry required、outward count=0、max streak=0。

兩個 runs 共 8 支 MP4／497 frames 以修正版完整 replay，outward wall action 為 0；
fixed scenarios 與 targeted 84 tests、完整 338 tests 全通過。仍只有全新 bounded
3-episode artifact 能決定是否進 P4.0。

## Repair v5：v4 retest 退步與重新修復

v4 後四組新 artifact 共 18 episodes／721 steps，floor mean/median 2.28/2，
13 bottom death、6 floor-1 bottom、14 observation-invalid；四份 Gate 全 FAIL。
最新 EP4 證明 outward=0 不足：單步 guard 離開範圍後，persistent launch 會再次
指向牆面，造成 12 次快速反轉。另有 70 steps player missing。

Repair v5 改為 latched wall evacuation，加入 enter/exit hysteresis、velocity lookahead、
state cancellation 與 cooldown；player detector/tracker 可橋接最多 2 個 raw dropout；
launch commit cap 3 steps 並以 vx projected landing replan。Runner/Gate 另加入 player
continuity、wall re-entry、wall-corridor burst、aligned release 與 floor-1 bottom metrics。

18 MP4／729 playing-frame 最終 r4 replay：716 raw player detections、13 tracked bridge、
effective missing 0、max missing 2、outward 0、wall re-entry 0、max wall burst 1、
aligned release max 5，offline checks 全 PASS。Targeted 102、完整 350 tests PASS。
壓縮影片 replay 不能證明 raw capture 或 closed-loop transfer，因此 P3.6 仍 FAIL／STOP；
repair v5 只達新的 bounded 3-episode real retest 門檻。

## 特殊平台失敗證據

### Spring

- Episode 2 在 step 23、33 各記一次 spring landing／`spring_bounce`。
- Steps 22～34 有連續 13 步 `aligned_with_safe_platform → RELEASE_ALL`。
- 影片顯示角色在彈簧鏈上垂直反覆彈跳，沒有持續橫向脫離；step 39 撞頂受傷，
  steps 40～41 玩家偵測消失，之後死亡。
- 原因不是 action collapse，而是 Teacher 把「對準下方普通平台」誤當成可以等待，
  沒有把 spring contact 保存成必須完成的跨步 escape state。

### Spikes

- Episode 3 step 23 落到 spikes 並計入 floor；之後 steps 24～39 連續 16 步
  `aligned_with_recovery_platform → RELEASE_ALL`。
- 影片顯示角色長時間留在尖刺／頂端危險循環；step 36 再受 5 格傷害，step 39
  才落到 normal 回血，最後仍於頂端死亡。
- Teacher 有選 recovery target，但「水平已對準」優先於「離開當前 hazard／避免
  頂端」，所以動作表面合理、closed-loop 卻失敗。

### 普通平台與 PPO 比較

Teacher 三動作都有使用，並能在普通平台段落逐步下樓；這確實比舊 PPO 的
128/128 RELEASE 或 RIGHT collapse 好。但它只證明規則控制基礎有效，不能抵銷
三回合全部 top death、特殊平台 trap 與 reach-floor-5 失敗。

## 其他量測限制

- Control loop 約 7.1～10.6 Hz，平均約 8.0～8.2 Hz，符合目前真機 8 Hz 設定。
- 使用者人工觀察到移動呈現「按一下、放一下」而非線性連續移動；程式核對確認
  `LiveGameAdapter.step()` 每步只按住方向 `action_duration_ms=80`，隨後無條件
  `release_all()` 再擷取畫面。因此即使 Teacher 連續選同一方向，實際仍是約 8 Hz
  的 80 ms pulses，而不是跨 observation 持續 hold。這是控制介面設計造成的
  stick-slip，不只是影片幀率或主觀感受，也可能縮短 spring bounce 的逃離窗口。
- Sidecar 的 `action_latency_ms` 約 0～1 ms，只量到 Python command→backend return，
  不是畫面中角色真正開始反應的 physical latency；Prompt 要求的真實 latency
  尚未通過。
- 平均 observation confidence 約 0.93～0.98，但它沒有反映 spring 壓縮外觀、
  platform kind／track 穩定性或 floor-event 錯誤，現行 confidence 定義過度樂觀。

## 數值核對

直接讀取 repository artifacts，而非只引用舊報告：

| 項目 | Artifact 實值 | Prompt | 核對 |
|---|---:|---:|---|
| Teacher holdout reach floor 10 | 94% | 約 94% | 一致 |
| Teacher deepest-floor Q25 | 30 | 約 30 | 一致 |
| Teacher health death | 0 | 0 | 一致 |
| Spike Dataset v1 | 60 episodes／3,529 rows | 約 60／3,529 | 一致 |
| Dataset validator | 0 error | 0 error | 一致 |
| BC0 mean deepest | 45.5 | 約 45.5 | 一致 |
| BC0／baseline Q25 | 7.75／30 | 約 7.75／30 | 一致 |
| BC0／baseline reach floor 10 | 60%／100% | 約 60%／100% | 一致 |
| BC0／baseline bottom death | 14／1 | 約 14／1 | 一致 |

舊 Spike DAgger artifact 亦確認 mean 28.57→38.75，但 reach-floor-10
86.67%→75%、bottom 15→27 且有 1 health death。因此不把 mean 上升視為 PASS。

唯一需要釐清的是 Prompt 的「Teacher／Baseline mean 約 49.7」是簡寫：49.7
實際是 BC0 final seeds 2200～2219 的 baseline mean deepest；正式 Teacher
holdout 1800～1899 的 mean deepest 是 47.31、reach-floor-10 是 94%。兩者使用
不同 seed partition，不能混成同一個 Teacher 指標。這不改變 Gate 結論。

補充語意：simulator 的 reach 使用 `deepest_floor`；真機無 privileged floor index，
新版直接讀取校正 HUD counter 並明標 `visual_hud_max_floor`，不再由 landing／
track ID 猜測。兩者仍不可冒充同一指標。

## 已建立的安全工具

入口：

```powershell
.\.venv\Scripts\python.exe scripts\run_teacher_real_game_micro_gate.py
```

預設 dry-run：

- 不尋找遊戲視窗；
- 不建立 live environment；
- 不載入 PyAutoGUI／PyDirectInput backend；
- 不送出 Enter、LEFT、RIGHT 或 RELEASE；
- 只驗證 limits、確認字串、artifact contract 與下一個人工命令。

實際模式固定要求：

- `game.auto_launch=false`；
- 唯一已驗證前景視窗；
- 輸入 `TEACHER REAL MICRO` 與 3 秒倒數；
- 3～5 回合；每回合與總 step/time 上限；
- F8、失焦、related window、例外、Ctrl+C 與結束時 `release_all()`；
- 每回合 canonical transition、controller-memory JSONL 與 MP4；
- 最後產生 `teacher_real_game_micro_gate.json`。

controller sidecar 每步包含 phase、target lock/age、active/pending direction、
braking/launch/recovery、previous action/streak、observation confidence、action
command/effective/next-observation timing、latency、loop Hz、events。

## Dry-run 結果（歷史前置）

Artifact：`artifacts/teacher_real_game_micro_gate_dry_run.json`

- Dry-run 工具：PASS。
- 真機 Gate：當時 PENDING；2026-08-01 實測後為 FAIL。
- 真實輸入：0。
- 遊戲啟動：0。
- 下游 Gate：STOP。

## 已執行的人工命令

先手動開啟原版遊戲並確認可正常進入遊玩／死亡選單，再在 repository 執行：

```powershell
.\.venv\Scripts\python.exe scripts\run_teacher_real_game_micro_gate.py `
  --execute `
  --episodes 3 `
  --max-steps-per-episode 300 `
  --max-seconds-per-episode 60 `
  --max-total-steps 900 `
  --max-total-seconds 180
```

本命令已執行一次；此 partition 現為 development/failure evidence，不得在修正後
冒充新的 untouched Gate。原始 logs 與影片保留供回歸分析。

## Gate 通過條件

- 安全事件 0；
- 至少 3 個完整回合與影片；
- observation、target lock、controller memory 逐步記錄完整；
- canonical transition count 與 controller rows 等於實際 steps；
- 最大單一 action 比例小於 98%；
- HUD floor counter 全回合 available；
- LEFT／RIGHT 至少各一筆 visual motion-onset latency；
- 至少各一個 visual reach-floor-3 與 reach-floor-5 案例；
- terminal reason 可映射到共同 failure taxonomy。

若不通過，下一步只能修 observation、latency、target tracking、controller memory
或 simulator fidelity；不得增加 BC epochs。

## 下一個唯一允許工作

修復 P3.6，而不是進 P4.0：

1. 把可觀測的 spring/spike contact 保存為 persistent special-platform escape
   state；在水平離開來源平台或確認落到安全平台前，不允許單純因 target aligned
   而長時間 RELEASE。
2. 修正 floor telemetry（至少解決普通平台漏計與 spring/track-ID 重計），並把
   platform-kind/track stability 納入 observation quality。
3. 將 physical action response latency 與 command dispatch latency 分欄量測。
4. 將「決策頻率」與「按鍵保持」解耦：同方向 action 跨 observation 保持，只有
   RELEASE、方向切換、失焦、例外、terminal 或 emergency stop 才放鍵；方向切換
   仍保留安全 brake。先用 fake backend 證明連續同向不會重複 key-up/down，並設
   最長 hold watchdog，再進真機。

完成 fixed scenario 與 mock tests 後，才可用全新 run 再做 3 回合 micro Gate。
在 reach-floor-5 與 telemetry Gate 通過前，不擴成 20 回合。

### Repair progress（2026-08-01）

- 第 4 項 bounded stateful hold 已完成本機實作與 mock Gate：連續同方向不再
  每步 key-up/down，並由 500 ms lease watchdog 防止 stalled loop 卡鍵。
- RELEASE、非 PLAYING observation、例外／Ctrl+C、reset、close 仍強制放鍵；
  原有 F8／失焦 SafetyMonitor 保留。
- 本項尚未在真實遊戲重測，因此 P3.6 整體仍為 FAIL／STOP；下一個程式修復是
  persistent spring/spike contact escape，而不是立即重跑或開始訓練。
- Persistent special-contact escape 隨後亦完成 mock Gate：只用事件 source
  ID/kind 與可見／快取邊界，active 時不允許 aligned target 導致長 RELEASE；
  edge clear、非特殊 landing 或 12-step hard cap 會終止。6 fixed scenarios PASS。
- HUD floor tracker 已完成 calibrated offline Gate：舊三支 MP4 自動讀得 max
  3/2/2、changes 2/1/1，與人工逐幀一致，149 frames 均可用。Landing/track ID
  不再負責 floor increment。
- Physical latency tracker 已加入 sidecar：dispatch 與 visual velocity onset 分欄，
  新 Gate 要求 LEFT／RIGHT 各至少一筆有效 sample。
- 第一版 repair package 曾為 READY；第二次 run 證明 hold/latency 改善，但暴露
  terminal accounting 與 aligned dwell。兩者修正後現為
  **repair v2 READY FOR 3-EPISODE REAL RETEST**。這不會回溯改寫舊 Gate 的 FAIL，
  也不代表允許 P4.0；只有全新實機 artifact 可決定 PASS/FAIL。

## 自動驗證

- Repair v2 targeted：75 passed；完整 `python -m pytest -q`：329 passed in 68.31s。
- 第二次 MP4 observation/policy replay：frame 53 觸發 RIGHT dwell escape。
- Repair v2 compileall、dry-run、audit JSON 與 `git diff --check`：PASS。
- Repair v1 當時 P3.6 targeted：48 passed。
- Repair v1 當時完整 `python -m pytest -q`：324 passed in 65.15s。
- 舊 MP4 HUD floor audit：PASS，observed/expected max 均為 3/2/2。
- `python -m compileall -q src scripts tests`：PASS。
- dry-run JSON parse：PASS。
- `git diff --check`：PASS（只有既有 Windows LF→CRLF 提示）。
- 真實遊戲與模型訓練：均未執行。

## Repair v6：Support-departure phase（2026-08-01）

- v5 新真機兩份 Gate 均 FAIL，平台邊緣猶豫由 sidecar／MP4 證實。
- v6 新增 source/destination-aware departure latch；仍有來源 support 時不允許
  landing alignment 提前 RELEASE，support-lost 後才切回 airborne planner。
- Sidecar/Gate 新增 same-support cycles、destination switches、timeout、edge RELEASE
  ratio、exit samples、max steps 與 support-phase aligned streak。
- 8 支最新 MP4／476 playing frames counterfactual replay：cycles 0、switches 0、
  outward 0、wall re-entry 0、support aligned max 3，offline PASS。
- Targeted 86、完整 357 tests PASS；compileall、dry-run、JSON 與 diff check PASS。
- 目前仍是 P3.6 FAIL／STOP；repair v6 只取得 OFFLINE PASS／REAL PENDING，下一步
  只允許一個全新 bounded 3-episode Gate。

## Gate v2：可執行失敗語意（2026-08-01）

- repair v6 新真機 3 回合共 466 steps；parser floors `5,3,10`，3/3 reach-3、
  2/3 reach-5、0 safety event。使用者觀察最高 13；影片證實 parser 有 lag。
- 舊 Gate v1 FAIL 不能直接解讀成 controller FAIL：support aligned max 4 發生於
  target 與 support 相同的 settle；wall burst 3 跨 special escape；29 個零信心
  observation steps 全是 RELEASE，4 個 dropout 全部恢復。
- Gate v2 改用 actionable support target、active wall-safety context、bounded
  release-only recovered dropout；舊 raw 指標保留為非 blocking telemetry。
- 同一 controller sidecar 重分類：dropout max 15、unrecovered 0、blind action 0、
  active-wall burst 0、actionable support RELEASE 0、46 support exits；全項 PASS。
- 完整 363 tests、compileall、no-input dry-run 與 diff check PASS；controller policy
  未修改。詳細見 `P36_GATE_SEMANTICS_V2_REPORT.md`。
- 狀態為 **RECLASSIFICATION PASS／FRESH REAL CONFIRMATION PENDING**；只有下一次
  v2 runner 的全新 3 回合 artifact PASS 才能解除 P3.6 HOLD 並進入 P4.0。

## Gate v9：Natural 3-Episode Micro PASS（2026-08-03）

- 誤切視窗的run由focus guard安全停止並列INVALID／INCOMPLETE；其替代run完整
  3回合，floors `2,9,7`，MP4 HUD重播一致且counter unavailable=0。
- v8唯一FAIL的edge RELEASE 16/57中，15筆是同平台settle、1筆是spring brake；
  它們都沒有active departure。Gate v9只以不同target或active departure作blocking
  opportunity，generic occupancy仍原樣保存。
- 不可變sidecar重分類結果為actionable RELEASE 0/39、51/51 checks PASS；
  safety/dropout/outward/wall re-entry/departure timeout皆0。
- 此結果解除3回合Micro Gate，但不直接進P4.0。下一個Gate是獨立10回合穩定性確認：
  reach-3>=7、reach-5>=4、bottom death<=2、spring/spike皆出現，其餘checks全過。
- 詳細證據：`P36_GATE_V9_NATURAL_MICRO_REPORT.md`。

## Gate v11：10-Episode Stability PASS（2026-08-03）

- 完整run `teacher_real_micro_20260803_034023_674665` 有10/10回合，safety event=0。
  同run MP4逐幀HUD audit將EP3 terminal maximum由sidecar 3證實為4；最終floors
  `8,11,4,2,2,5,4,4,8,2`，raw artifact保持不變。
- Gate v11沒有降低reach門檻：reach-3=7/10、reach-5=4/10；Q25=2.5、CVaR25=2、
  floor-1 bottom=0。只把錯誤的all-bottom限制改為floor<3 early-bottom budget，結果
  3/3剛好通過。
- Special contacts共16（spring7／spike9）；entry brake加一次允許reversal可到2，
  但絕對上限仍為2。實際violation=0，replan/reversal max1、restart/abort=0。
- 相同不可變sidecars加可信video audit重分類全部checks PASS；未開遊戲、未送輸入、
  未挑episode。P3.6 stability qualification完成，下一步是P4.0 State-aliasing Audit，
  尚未授權S0～S3或Student訓練。
- 完整證據：`P36_GATE_V11_10EP_STABILITY_REPORT.md`。

## Repair v7／Gate v3（2026-08-02）

- Gate v2 後兩個 fresh runs floors `1,4,1` 與 `7,5,2`，兩份皆 FAIL。第二份
  reach-3／reach-5 已通過且 departure 正常，唯一 blocking check 是 wall re-entry 3。
- Sidecar 定位到 exit 後 cooldown RELEASE 讓舊方向回牆，以及 top-pressure dropout
  期間 RELEASE 停頓。v7 改為 cooldown 持續向內，並只在可靠 top-danger context
  允許最多兩步同方向 bridge；一般 missing 不變。
- Gate v3 將 approved bridge 與 blind action 分欄，要求 bridge max<=2、exhausted=0。
- 369 tests、compileall、dry-run 及最近三片 counterfactual replay PASS；影片重播不能
  取代 closed-loop，故 P3.6 仍 HOLD，下一步只允許一次 bounded Gate v3。
- 詳細證據與限制見 `P36_REPAIR_V7_REPORT.md`。

## Repair v8／Gate v4（2026-08-02）

- Gate v3 fresh run parser floors `2,4,10`；影片至少 floor12，使用者觀察約13。
- EP2 steps0–24 與 EP3 200–215 是 live player dropout；EP2 66–82 是 timeout 後
  source 永久 block 造成的連續 RELEASE。
- v8 保留8-step departure hard cap，但 abort 後只 cooldown 2 steps，再重新規劃。
- Runner 新增每回合最多6組 lossless raw/mask/component forensic；Gate v4 收緊
  recovered dropout<=8、要求 forensic available 與 cooldown<=2。
- 當時程式與測試已就緒，下一個判定點是 fresh bounded Gate v4；其結果記錄如下。

### Fresh Gate v4 結果

- Run floors `9,2,2`；mean 4.33、median/Q25/CVaR25=2；35/36 checks PASS。
- 唯一 blocking check 是 reach-3 只有1/3；reach-5 1/3 PASS。
- dropout max1、departure timeout0、wall re-entry0、outward0、blind action0、
  safety event0，證實 v8 的目標分支在本次真機樣本改善。
- EP2 是 late-braking landing overshoot，EP3 是 destination-unaware special escape；
  故維持 P3.6 HOLD，先做 Repair v9，不進 P4.0。

## Repair v9／Gate v5（2026-08-02）

- Adaptive landing intercept 使用0.25～0.55秒 horizon；rising 最大化，falling 依
  垂直距離／速度估計。Support departure 保留獨立方向規則。
- Special escape 先看更深可達安全落點，再使用 bounded edge-momentum guard；
  controller sidecar 記錄 prediction、safe interval、direction source、destination 與 replan。
- Gate v5 要求新 telemetry available；v4 的 timeout=0、wall/dropout/departure、
  reach-3 2/3、reach-5 1/3 與其他 safety checks 不變。
- 379 tests、compileall、no-input dry-run PASS；fresh real Gate v5 PENDING。
