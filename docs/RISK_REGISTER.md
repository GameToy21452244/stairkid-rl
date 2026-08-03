# Risk Register

| ID | 風險 | 嚴重度 | 證據／觸發 | 緩解與狀態 |
|---|---|---:|---|---|
| R-01 | 真實輸入送錯視窗或按鍵未釋放 | 極高 | Windows 自動輸入 | 保留 foreground／related-window／F8／release_all；自動測試禁實機。持續 |
| R-02 | 舊資料 transition 錯位或跨 episode | 高 | legacy JSONL 缺 episode、next obs、時間戳 | quarantine + 新 validator；writer 尚未接入。開放 |
| R-03 | 動作 label 與實際生效時間錯位 | 高 | capture/action latency 未量測 | 四個時間戳、held/action duration schema；待 calibration。開放 |
| R-04 | PPO action collapse | 高 | 128/128 RELEASE，其他 checkpoint 也曾 128/128 RIGHT | 禁止續訓；固定 action metrics gate。已控制 |
| R-05 | simulator reality gap | 高 | v0 參數為工程初值 | 有限 telemetry 校正、固定 baseline、逐參數 ablation。開放 |
| R-06 | simulator reward exploitation | 高 | floor／landing shaping 可能可刷 | component audit、終止原因、影片、跨 seed、真實 replay comparison。開放 |
| R-07 | observation schema drift | 中高 | 歷史已有 16／64／268 維格式 | version + strict dimension validator + shared encoder tests。已控制 |
| R-08 | reward drift | 中高 | 真實 reward 已多次加入 shaping | reward_version、component totals；真實／sim 統一決策待做。開放 |
| R-09 | episode reset 污染 rollout | 高 | menu/dialog/focus correction 跨 episode | terminal/truncated continuity checks；真實 writer 尚待接入。開放 |
| R-10 | 多 env 非獨立或 seed 洩漏 | 中 | Colab vector env | 每 env 獨立 Pymunk Space/RNG、fixed-seed tests；vector benchmark 待跑。部分控制 |
| R-11 | 長訓消耗資源但無資訊增益 | 中高 | 真實環境約 6–7 steps/s | Go/No-Go、短 probe、early stop、固定評估。已控制 |
| R-12 | artifact／密鑰誤提交 | 高 | models/logs/captures/Drive | `.gitignore`、只提交 summary、config 不含 secret。持續 |
| R-13 | human render 在 headless 環境開窗 | 中 | Pygame display | Colab 設 dummy driver，只用 None/rgb_array；human 僅本機手動。已控制 |
| R-14 | v0 platform crossing 容差產生穿透／假落台 | 中 | 明確 crossing test 尚未真實校正 | landing/edge tests，待 telemetry 與高速度案例。開放 |
| R-15 | v0.1 平台序列不可達或後續必死 | 極高 | fixed generator shift 可達 180 px，無 look-ahead | v0.2 reachability checker、100→1,000 seeds gate。進行中 |
| R-16 | Oracle 特權資訊污染 BC teacher | 極高 | full state／未來平台可使標籤不可能被學生重現 | Oracle-full／Teacher-observable 分離 API 與 anti-leak tests。待實作 |
| R-17 | 8 Hz 粗步進造成一幀碰撞／煞車假象 | 高 | v0.1 physics dt=125 ms | 固定 60 Hz physics substeps，比較 8／10／12 Hz policy。待實作 |
| R-18 | teacher dataset split 洩漏平台序列 | 高 | 相同 seed/sequence 跨 train/val/test 會高估 BC | 按 episode＋seed split，validator 檢查 sequence id。待實作 |
| R-19 | repository cleanup 誤刪校正 provenance | 高 | 多輪 calibration report 看似重複 | 2026-08-03清理前先做引用／用途／路徑稽核；只刪舊封存weights、中間aggregate、舊ZIP與v2重複JSON，保留Gate v11、calibration、templates、clean/v1 datasets與reports。已控制 |
| R-20 | soft teacher confidence 過度平滑關鍵控制邊界 | 高 | soft BC 20.95 floors、learner-state disagreement 41.01% | BC0 改 hard CE；soft targets 只作 audit，待校正。已控制 |
| R-21 | DAgger corrections 淹沒原 teacher distribution | 高 | 1,634 corrections 使 29.80 降至 23.20 floors | 25% cap＋action ratio＋cluster/category sampling 後 63.15；easy 階段凍結。已控制 |
| R-22 | Health feature 在關閉／滿血時改變既有物理或 reward | 高 | 特殊機制可能造成 hidden drift | 預設關閉、heal reward=0、100-seed episode equivalence。已控制 |
| R-23 | 滿血落台重複產生假回血事件 | 中高 | normal landing 會反覆發生 | 只在實際 delta>0 發事件；cap 與 fixed-scene tests。已控制 |
| R-24 | 尖刺同時觸發回血或傷害重複計算 | 高 | landing 共用 normal collision path | platform kind 分支互斥；100-seed damage/heal interaction gate。已控制 |
| R-25 | 致死傷害未正確終止或被 top/bottom 覆蓋 | 高 | 同一步可能同時有多種 terminal | health_depleted 優先，100 lethal seeds 與 failure mapping。已控制 |
| R-26 | 輸送帶方向或速度符號錯誤 | 高 | Pymunk y 向上且左右事件需與畫面一致 | 左右 fixed landing 各 100 seeds、方向事件與實際 velocity delta 同步。已控制 |
| R-27 | 暫定輸送帶速度被誤當真實校正值 | 高 | 尚無真實 conveyor telemetry | 文件與 artifact 明標 provisional；進 mixed curriculum 前必須另做有限 calibration。開放 |
| R-28 | 彈簧彈力不足、過強或誤用一般 bounce | 高 | 強彈跳會改變可達平台集合 | fixed landing 100 seeds、獨立事件與 velocity delta；190 px/s 明標 provisional。部分控制 |
| R-29 | 翻板 phase 不可觀測造成無法學習 | 極高 | inactive 時直接穿透 | observation 暴露 active；Oracle 排除 inactive；混合前仍需歷史／phase observability gate。部分控制 |
| R-30 | 所有翻板同步造成不真實且可能整層不可達 | 高 | v1 使用全域 1／1 秒週期 | 尚不進 generator；混合前加入 seeded phase offset 與 3-floor reachability gate。開放 |
| R-31 | 隨機尖刺序列累積傷害造成必死課程 | 極高 | damage 5、heal 1 | 前 3 層 normal、尖刺間至少 5 normal；1,000 seeds health-safe、rollout 0 health death。已控制 |
| R-32 | 提案機率與實際尖刺比例不同 | 中高 | recovery gap 會抑制 10% proposal | artifact 同時報 proposal 與 realized；1,000 initial seeds realized 5.11%。已控制 |
| R-33 | 新 dataset 與 Gate seeds 洩漏 | 高 | 相同 platform sequence 會高估後續評估 | Gate 0～999；dataset 1000～1059；後續 BC eval 使用另一組 fresh seeds。已控制 |
| R-34 | Overall accuracy 掩蓋尖刺情境資料不足 | 高 | spike-target test 僅 10 rows／40% accuracy | 記錄 visible kinds；spike-visible 232 rows／75.43%，正式 BC 同時報兩種 subset。部分控制 |
| R-35 | Offline loss 選出閉迴路退化 checkpoint | 極高 | epoch 17 accuracy 82.06% 但 retention 40.73%；epoch 5 accuracy 74.75% 但 retention 85.58% | 預先固定候選 epoch；獨立 rollout-selection／final seeds；final 不回饋選模。已控制，待 3-seed 驗證 |
| R-36 | Mean floors 掩蓋 early failure 與 health death | 極高 | Spike DAgger mean 28.57→38.75，但 floor-10 success 86.67%→75%、bottom 15→27、1 health death | selection 改 safety／lower-tail 優先；health-aware recovery Teacher；本輪 FAIL 並停止。開放 |
| R-37 | Recovery 修正安全但基本 baseline floor-10 未達門檻 | 高 | 初始事件計數 88%；語意修正後 initial reach 92%，但 1700 audit 仍只有 87% | 可見落點 approach＋future-aware launch escape 後，untouched 1800 holdout 94%、0 health death。已控制 |
| R-38 | `floor_descended` 事件數低估跳層策略的實際進度 | 高 | 同一 dev rollout 事件成功率 88%，實際 reach-floor-10 92% | 歷史欄位保留；Gate 改用 simulator `deepest_floor`／`reach_rate_floor_*`，並以測試鎖定語意。已控制 |
| R-39 | Teacher 的跨步 target／launch／brake memory 無法由單步 BC 穩定重建 | 極高 | BC0 v1 offline 77.2% 但 final reach-floor-10 60%；direction-brake disagreement 71.9% | 停止加 epochs；下一版先做 branch quotas 與 explicit deployable memory／sequence model ablation。開放 |
| R-40 | NEAT 以單次 lucky seed／fitness exploit 取得高分 | 高 | 外部專案報告高隨機性、模型難重現與 healing exploit | 每 genome common multi-seed、holdout、Q25／death Gate；只准 bounded baseline。待設計 |
| R-41 | Simulator Teacher 尚未轉移至原版遊戲 | 極高 | 真機 3 回合 HUD 最高 3/2/2、全 top death、0 回合達5；spring/spike trap | Gate FAIL；先修 special-contact escape、telemetry、physical latency，再重跑 3 回合。開放 |
| R-42 | Teacher 私有 controller memory 造成 action label state aliasing | 極高 | P4.0實機753 rows：observation-only conflict 56.20%；causal full 45.39%；post-decision leakage ceiling僅11.42% | 僅准 `memory[t-1]`；raw IDs排除。causal改善19.23%、bootstrap下界0.0979，P4.0 PASS；launch/brake conflict仍63.08/57.00%，須以P4.1公平消融確認。部分控制 |
| R-43 | 單步 row DAgger 破壞 sequence 與 tail safety | 極高 | 舊 DAgger mean 上升但 reach 降、bottom 增且有 health death | correction 改 sequence、初始 20%、safety replay；Q25/CVaR/health Gate。開放 |
| R-44 | 真機 floor 指標與 simulator deepest-floor 語意混用 | 高 | 真機只能由視覺 floor events 推估 | artifact 明標 event-based reach，不宣稱 privileged deepest floor；影片人工覆核。開放 |
| R-45 | 真機 floor event 漏計與重計 | 極高 | 舊 run events 0/2/2；HUD max 3/2/2 | HUD counter 取代 track-ID 推估；149-frame MP4 replay 得 3/2/2、0 unavailable。待新真機確認。部分控制 |
| R-46 | 特殊平台 contact 未成為持久控制狀態 | 極高 | spring 13 步 aligned RELEASE；spikes 後 16 步 recovery-aligned RELEASE | 可觀測 persistent escape、kind-aware bounds cache、safe landing/edge/12-step exits 與 6 fixed tests 已完成；待真機。部分控制 |
| R-47 | `action_latency_ms` 只量 command dispatch | 高 | 真機 sidecar 約 0～1 ms，但 control loop 約 8 Hz | 已分欄並實作 velocity motion-onset tracker；新 Gate 要求 LEFT/RIGHT 樣本。待新真機。部分控制 |
| R-48 | 真機 adapter 把連續方向切成 80 ms 脈衝 | 極高 | 使用者觀察 stick-slip；程式每 step 無條件 `release_all()` | bounded stateful hold、500 ms watchdog 與 fake-backend tests 已完成；待全新真機 micro run 驗證視覺連續性。部分控制 |
| R-49 | 被角色遮蔽的特殊平台退化成普通／缺失觀測 | 極高 | 第二次 retest 影片為尖刺接觸，但 nearest 指向 normal 且 generic damage 無 source，造成 21 步 aligned RELEASE | 以同 target＋stable relative gap 的 deployable dwell state 啟動 persistent edge escape；MP4 replay 命中，待真機。部分控制 |
| R-50 | terminal 前安全 no-op 被誤列為 Gate exception | 高 | phase probe 正確不送鍵，runner 卻因 `action_applied=false` 中止且 summary 丟失 episode | 僅接受 non-PLAYING terminated/truncated no-op；不偽造 transition並保存 terminal frame；PLAYING no-op 保持 fail-fast。已修，待真機。 |
| R-51 | Spring bounce event 漏失，週期反彈不符合 stable-gap dwell | 極高 | 第三次 EP3 nearest=spring，但 gap 18→50→84→19 循環且 bounce event=0 | close visible spring（≤30 px）直接啟動 persistent escape；同片 replay frame 14 起 LEFT，待真機。部分控制 |
| R-52 | 貼牆 special escape 沿不可行方向持續撞牆 | 極高 | 5 回合 EP1 left spring 在 x≈54 仍 outward LEFT；EP4 right spikes 12 步 RIGHT 到 x≈410 | 共用 inward wall guard、方向 brake、逐步 telemetry、outward count/streak=0 Gate；8 MP4 replay 0 outward，待真機。部分控制 |
| R-53 | 單步 wall guard 與 persistent launch 互搶造成牆邊左右震盪 | 極高 | v4 後最新 EP4 有 12 次快速反轉，即使 outward=0 | latched evacuation、hysteresis、velocity lookahead、清衝突 state、cooldown；18 MP4 replay wall re-entry 0、burst max 1。待真機，部分控制 |
| R-54 | 角色肉眼可見但 warm-colour component 低於 detector 高度門檻 | 極高 | 18 回合 70/721 live steps player missing；影片 frame component 高度 14、舊門檻 15 | 14 px 校正、morphological closing、最多 2 幀 bounded extrapolation；compressed replay effective missing 0。raw-frame 真機待驗，部分控制 |
| R-55 | launch direction 承諾過久造成第一層過衝觸底 | 極高 | 13/18 bottom death、6/18 floor-1 death；launch 262/721 steps，單次最長 6 steps | commit cap 3、replan cooldown、vx projected landing、floor-1 bottom Gate；counterfactual replay不能驗證死亡改善，待真機。開放 |
| R-56 | support departure 與 airborne landing phase aliasing 造成平台邊緣猶豫 | 極高 | v5 真機 471 steps：203 RELEASE、175 launch；37 個 edge≤20 px RELEASE 仍有 support，兩份 Gate 均 FAIL | v6 真機 3 回合有 46 次 support exit、median 3／max 5 steps、restart／timeout 0、actionable support RELEASE 0；核心 lifecycle 已控制，仍待全新 Gate v2 獨立確認。部分控制 |
| R-57 | Gate 把正常 settle、特殊脫困或可恢復視覺失聯誤判為控制失敗 | 高 | v6 實機達 parser 5/3/10、0 safety event，舊 Gate 卻因 support aligned 4、wall burst 3、missing 17、任一零 confidence 而 FAIL | Gate v2 改量 actionable target、active wall-safety context、release-only bounded recovered dropout；raw 指標仍保留。sidecar 重分類 PASS，須以全新 3 回合確認後才關閉。部分控制 |
| R-58 | Wall exit 後 RELEASE 讓舊 special／launch 動量回到同一牆 | 極高 | 最新 7/5/2 run 有 3 次 re-entry；sidecar 顯示 exit→cooldown RELEASE→舊方向→re-entry | v7 cooldown outward request 改為持續向內；同片 replay re-entry 0、outward 0。closed-loop 待 Gate v3，部分控制。 |
| R-59 | 頂部壓力下 player dropout 的 RELEASE 停頓造成 top death | 極高 | 最新 EP2 尾段連續 missing RELEASE，使用者觀察普通平台短暫發呆後被上方尖刺夾死 | 只在可靠 top-danger context 延續最後安全方向最多 2 steps；一般 missing RELEASE；exhausted=0 為 blocking Gate。待 fresh real，部分控制。 |
| R-60 | Departure timeout 將同 source 永久 block，造成長時間 RELEASE | 極高 | Gate v3 EP2 steps 66–82 連續 17 個 safety-abort RELEASE | v8 改為 safety abort＋2-step cooldown 後 retry；Gate 要求 timeout=0、cooldown streak<=2。待 fresh real，部分控制。 |
| R-61 | MP4 壓縮掩蓋 raw player detector 失敗 | 極高 | live sidecar 41 invalid，但相同影片解碼重播 438/439 raw detected | 每回合 bounded lossless raw/mask/component forensic；dropout Gate 收緊至8。待下一次 raw evidence，部分控制。 |
| R-62 | 單次高樓層掩蓋 landing lower-tail 早死 | 極高 | Gate v4 floors 9/2/2，35/36 checks PASS，但 reach-3 只有1/3；EP2晚煞車過衝，EP3向無後續落點方向離開彈簧 | 保留2/3 reach-3 Gate；v9 adaptive intercept、destination／edge-momentum escape 與 recorded regression 已完成，379 tests PASS；closed-loop Gate v5 待確認。部分控制。 |
| R-63 | 特殊平台 tracker ID churn 與逐幀重規劃造成假 hard cap／方向性失能 | 極高 | Gate v5 影片有 spring 25-step、spikes 12-step 滯留；152 special-active steps 中50次 brake RELEASE、50次方向變更；同 spring ID 27→30→34→38→41並反覆重設計數 | Repair v10 已改 semantic identity、direction latch／單次 replan、forced-exit／abort。第二組 REAL 最長 contact 5、restart/replan/reversal/brake/abort 皆 0；核心 lifecycle 明顯改善，仍待 Gate v7 lower-tail 確認。部分控制。 |
| R-64 | 角色與暖色平台紋理合併，在特殊接觸前造成長時間 RELEASE | 極高 | Gate v6 EP2 spikes 前 10 steps `player_not_detected`／`RELEASE_ALL`；raw component 寬 95～111 px，肉眼角色仍可見 | Detector 移除寬於 player max 的水平 color run。Fresh Gate v7 的 invalid observation 與 pre-special dropout 均為 0，點式根因已有 closed-loop 正向證據；整體 P3.6 仍因 lower-tail HOLD。部分控制。 |
| R-65 | RELEASE 後水平動量被高估，導致角色在目標前停止並觸底 | 極高 | Gate v7 floors 2/5/2；EP1 step38 與 EP3 step27 都以 0.25～0.55 s constant-vx 預測誤判已對齊，實機 RELEASE 下一 step 只移 5～8 px | 目標選擇保留長 horizon；RELEASE 決策改用 0.05 s projection，加入兩個精確回歸與 Gate v8 telemetry。待 fresh 3-episode closed-loop。部分控制。 |
| R-66 | 死亡對話框焦點落在 EXIT 導致重開等待過長或 Gate 中斷 | 高 | Gate v8 只完成 1/3；保存 screenshot 為 EXIT focus，舊 guard 未建模，舊觀測上限每段約 56 s | 新增 EXIT rect 與有界 Tab correction；只在連續確認 START 後 Enter，UNKNOWN fail closed；等待降為 24/12 frames。離線 frame／393 tests PASS，待 fresh real reset。部分控制。 |
| R-67 | Action-conditioned dynamics 在常見 action 上過度樂觀，反向煞車自然情境 coverage 不足 | 極高 | natural 337 strict rows 的 held-out x MAE 4.049 px，但 reverse LEFT／RIGHT 只有 7／8；固定平台另有23／21但分布過窄、無 sidecar | 固定平台資料降級 diagnostic-only；shadow/live 仍阻擋，不接入 SafePlatformPolicy。下一證據限一次 bounded natural Teacher run，無資訊增益即停止。開放。 |
| R-68 | 以單一 special contact ID 評估 lifecycle 會漏掉跨 bounce 滯留，反之 generic gap 聚合也可能合併不同實體 | 高 | Gate v7 spring steps 101～116 跨 contact 3→6、source 38/39/41/44；影片顯示多個堆疊 spring 且最後成功 normal landing | encounter 聚合只作離線診斷，明標不代表同一物理平台；同時報 contact/source IDs、bounce、normal landing、terminal outcome，不驅動 live controller。部分控制。 |
| R-69 | 為達樣本數門檻而重複固定平台左右震盪，造成 distributionally narrow 假覆蓋 | 高 | 3 runs／84 strict rows 很快累積23／21 reversal，但沒有自然 target/safe interval/support context；第4 run 因使用者疑慮中止 | 不以固定平台30/30解鎖任何 Gate；manifest 標 diagnostic-only、interrupted run 排除。代表性資料只取 natural Teacher full sidecar。已控制。 |
| R-70 | Generic edge RELEASE 被誤當 actionable departure stall，造成 false Gate FAIL | 高 | 最新完整 run floors 2/9/7，舊 metric 16/57；15筆為 target==support settle，1筆為spring brake，departure cycle/switch/timeout皆0 | Gate v9 分離 actionable 0/39 與 generic 16/57；舊門檻不放寬、policy不變，以不可變 sidecar重算51/51 PASS。10回合穩定性 Gate仍待確認。部分控制。 |
| R-71 | 無限遊戲的 terminal 類型與早期失敗混用，造成 Gate 反向獎勵 top death | 高 | 完整10回合有9 bottom、1 top，但 reach-3=7、reach-5=4、floor-1 bottom=0；舊 bottom<=2 與遊戲目標及 reach Gate 衝突 | Gate v11 保留 total bottom telemetry，blocking 改為 floor<3 early bottom 且不得超過 reach-3 miss budget。本次early-bottom 3／budget 3剛好壓線，lower-tail仍開放監控。部分控制。 |
| R-72 | Terminal frame HUD 已進樓但 live sidecar 因 phase timing 漏記 | 中高 | 10回合 EP3 sidecar=3，MP4逐幀=4；所有影片可讀、counter每幀available、初始值1 | 同 run可信video audit只允許向上修正且不覆寫raw；runner新增寫入影格同步HUD tracker。離線修正已控制，未來live路徑待下一次自然run驗證。部分控制。 |
| R-73 | 姓名輸入 modal 中斷多回合 Gate，或過寬自動 Enter 誤操作未知視窗 | 高 | 前一個10回合attempt於5/10被owned dialog中斷；使用者確認姓名框可Enter略過 | 僅唯一same-process owned #32770＋title白名單可明示啟用Enter-once；其餘fail closed。77 related tests通過，但成功10回合未觸發，live仍待觀察。部分控制。 |
| R-74 | Teacher程式演進但policy/dataset version未升，Colab重建同名資料造成實驗漂移 | 極高 | 凍結Dataset v1為3,529 rows/hash `fa3e...`；current source同seeds重建為3,571 rows/hash `04417...`，action counts亦顯著改變 | P4.1 manifest鎖exact hash；專用bundle攜帶原JSONL，notebook禁止重建。新Teacher資料必須升版並重跑reliability/coverage Gate。部分控制；version discipline仍待修。 |
| R-75 | Sequence模型介面成功或兩個短回合高樓層被誤當P4.1科學PASS | 極高 | 4-update smoke中S2兩回合mean deepest 9.5，但四組bottom rate皆1.0，S2 max action share 97.96%接近collapse門檻 | Artifact明標`scientific_gate_evaluated=false`；3900/3901永久只作development。只有3 initialization、selection/final隔離且tail/bottom/oscillation Gate通過才准P4.2。已控制。 |
