# Training Roadmap

## 原則

每一階段都必須保留固定評估集、版本化 observation/reward、seed、設定、checkpoint
與結果摘要。前一 gate 未通過，不得以「再多訓練」取代診斷。

## 2026-07-31 最高優先 Gate 順序

| 階段 | 工作 | Gate／停止條件 |
|---|---|---|
| P3.6 | Teacher Real-Game Micro Gate，先 3～5 回合 | 安全事件 0；memory/target/observation 可用；實際 reach 3/5；未通過即停止 |
| P4.0 | State-aliasing Audit | deployable memory 能否顯著降低 conflict/entropy；若不能先修 observation/label timing |
| P4.1 | S0/S1/S2/S3 公平消融 | 相同資料、seeds、更新預算；sequence student 必須穩定優於 S0 |
| P4.2 | Rare-branch sequence dataset | branch 最低 coverage、episode/seed 隔離、controller timeline 完整 |
| P4.3 | Conservative sequence DAgger | 初始 80/20；health/reach 不退化且 Q25/CVaR25 改善 |
| P4.4 | Compact NEAT 公平對照 | common seeds/fixed env steps；不以單次最高樓層選模 |
| P5+ | 選 closed-loop 策略後才准 bounded RL／curriculum／擴大實機 | 仍禁止長 BC/DAgger/PPO/DQN/NEAT |

P4.0 State-aliasing Audit 已 **PASS**。完整 10 回合 natural run 經可信 MP4
terminal-frame audit 後 floors 為 `8,11,4,2,2,5,4,4,8,2`。Gate v11 保留既定
reach-3 7/10、reach-5 4/10、floor-1 death=0 與所有安全／觀測／控制 checks；只把
「所有 bottom 終局」修正為「floor<3 early bottom failure」，並把特殊平台 brake
定義為 entry brake＋唯一允許 reversal 的 brake、絕對最多2次。相同不可變資料重算
全部 checks PASS；沒有重跑、挑 episode 或降低 reach/tail 門檻。

P4.0 使用 753 筆實機 rows 與 cross-episode 5-NN；observation-only disagreement
56.20%，加入前一步 causal memory 後 45.39%，相對下降19.23%。entropy 降0.1873
bits、accuracy 增13.01 points，episode bootstrap 95% CI `[0.0979,0.1411]`，全部
預定 checks PASS。當步 post-decision sidecar 會洩漏 action label，只作 ceiling；raw
track IDs 不可用。causal action history 單組 disagreement 42.76%，優於 full memory，
是 P4.1 S1 的主要 compact 候選。

目前進入 **P4.1 bounded S0/S1/S2/S3 ablation 設計與 smoke**。只可凍結 episode
split、seeds、update budget 與 Student 可用的 causal schema，再做短消融；不可用本次
P4.0 PASS 直接啟動長 BC/DAgger/PPO/DQN/NEAT，也不可跳到 rare-branch dataset。

Action-conditioned dynamics 雖在475 strict rows／15 held-out episodes優於 carry-vx，
但自然 reverse-braking LEFT／RIGHT僅11/15，仍不得進 shadow/live。固定平台23/21
資料維持 diagnostic-only，與 P3.6 通過無關。

最新證據與逐項決策以 `reports/TEACHER_CONTROL_STRATEGY_REVIEW.md`、
`reports/ACTION_CONDITIONED_DYNAMICS_REPORT.md` 及分離的 Normal／Spring／Spike
Gate 報告為準。

以下保留 Repair v9 以前的證據鏈：Gate v4 floors `9,2,2` 的 late-braking 與
destination-unaware special escape 已轉成 regression；adaptive airborne horizon、
departure phase isolation、visible-destination／edge-momentum escape 與 v5 telemetry
已完成。只有後續 Gate 證據可以覆蓋舊的 CODE／TEST READY 結論。
以下保留此前證據鏈：repair v4 後 18 回合有 13 bottom death、6 floor-1 death、
14 observation-invalid，且 wall override 與 persistent launch 形成左右震盪；v4
READY 結論已被新 artifact 推翻。Repair v5 已完成 player continuity、latched
wall evacuation、velocity-lookahead、bounded launch commit、projected landing 與
新 telemetry/Gate。18 MP4／729 playing-frame replay 最終 PASS：effective missing 0、
outward 0、wall re-entry 0、max wall reversal burst 1。狀態為
repair v5 雖 OFFLINE PASS，但兩次新真機 Gate（3＋5 episodes）均 FAIL。安全面已改善
至 floor-1 bottom death 0、outward 0；然而 landing alignment 在仍有 support contact
時過早 RELEASE，與 3-step launch replan／target reset 組成 same-platform hesitation
cycle。Repair v6 已以真機失敗序列建立 tests，加入 source/destination-aware
support-departure latch 與新 Gate；8 支最新 MP4 的可判定 offline checks PASS。
隨後新真機 3 回合 parser floors `5,3,10`、3/3 reach-3、2/3 reach-5、0 safety
event，核心 departure telemetry 全部通過。舊 Gate 的 FAIL 經 sidecar 證實混入
同平台 settle、special escape reversal 與 release-only recovered dropout；Gate v2
已改量 actionable target、active wall-safety 與 bounded safe recovery，同一紀錄重分類
PASS，完整 363 tests PASS；這是 Gate v2 當時的歷史狀態。其後兩組 fresh runs
觸發 Repair v7，最新允許工作與門檻以本段開頭的 Gate v3 狀態為準。

| 階段 | 工作 | 進入下一階段的 gate |
|---|---|---|
| 0. 稽核與安全 | 模組、資料、checkpoint、控制鏈、測試盤點 | 全部風險與未知量有文件；測試綠燈 |
| 1. 資料基礎 | transition writer、validator、quarantine、時間校正 | 無 schema error；episode/action/time continuity 可證明 |
| 2. Data Resource Audit | 逐檔／episode／row 分類 demo、replay、dynamics、relabel、invalid | inventory／salvage manifest 完整；不可猜補 provenance |
| 3. Simulator v0.2 | 持續生成／回收、easy／calibrated／hard、2～3 層 reachability | 100→1,000 easy seeds 可重現且無已知不可達序列 |
| 4. 教師分離 | Oracle-full 驗可解；Teacher-observable 產標籤 | Oracle 95% 達 10 層；教師不含特權資訊 |
| 5. Baseline／頻率 | baseline gate；60 Hz physics 下比較 8／10／12 Hz | baseline mean≥5、90% 達3層；凍結控制率 |
| 6. Teacher Dataset | easy、小型、episode/seed 隔離 split | schema／validator 0 error；分布與 confidence 已報告 |
| 7. BC0 | 268→256→128→3，小型 smoke | 不塌縮、優於 random/release、至少接近 baseline |
| 8. DAgger0 | 一輪 failure-state relabel 與重訓 | frozen seeds 上改善，否則停止 |
| 9. 特殊平台 | 回血→尖刺→輸送帶→彈簧→翻板，逐項 feature flag | 每項 unit/render/oracle/calibration gate |
| 10. Residual／Double DQN／DQfD-lite | 依序消融，不一次實作 | 多 seed 穩定、ablation 支持收益 |
| 11. Domain randomization／實機驗證 | sim-to-real 後少量真實回合 | 確認／倒數／硬上限；只報告不自動擴大 |

## PPO 的位置

PPO 只允許：

- simulator v0 是否可學的短 probe；
- BC 初始化與隨機初始化的小型對照；
- 與離散 value-based 方法的固定預算比較。

PPO 不允許：

- 在真實遊戲逐步長訓；
- 續訓 action-collapsed checkpoint；
- 以不增加觀測／動作多樣性的方式反覆追加 timesteps。

## 目前停點

舊階段 0／1、v0.1 骨架與校正已完成；Colab runtime／pytest／check_env／
throughput／checkpoint／resume／MP4 pipeline 已通過，但 768-step PPO
deterministic 全 RIGHT，只證明 pipeline 可執行，不證明策略成功。
依最新策略重新停在階段 2：先完成 Data Resource Audit，再升級 Simulator v0.2。
舊 PPO checkpoint 不續訓；BC0／DAgger0 必須等新 gates。

2026-07-31 更新：hard-label BC0 3/3 seeds 通過；naive DAgger0 失敗後，
唯一 balanced correction ablation 在 frozen／fresh seeds 達 63.15／62.90
floors，easy normal-platform curriculum 已飽和。依 Phase F 停止；下一階段只可
從「血量＋普通平台回血」開始逐項特殊平台 gate，不得直接混合 hazards。

Health＋normal heal mechanism gate 已通過：100 fixed Oracle landings 與
100-seed feature equivalence 都 PASS，尚未進入訓練分布。下一個獨立 gate
是尖刺；不得同時實作輸送帶、彈簧或翻板。

2026-07-31 尖刺 mechanism gate 已通過：固定傷害、致死、普通平台回血互斥、
Oracle 避讓與 renderer 均通過；在一般生成器尚不產生尖刺時，開關前後
100 seeds 的 trajectory 完全一致。本階段沒有新增訓練資料，也沒有把尖刺
混入 easy curriculum。下一個獨立 gate 是輸送帶，仍須預設關閉並先通過
fixed scenario、Oracle、render、calibration 與 feature-equivalence 測試。

輸送帶 mechanism gate 亦已通過：左右速度與 Oracle 各 100 seeds，
no-spawn feature equivalence 100 seeds 完全相同。±80 px/s 仍是 provisional，
不能視為真實 fidelity。一般 generator 與 training distribution 不變；
下一個獨立 gate 是彈簧，不得同時加入翻板。

彈簧 mechanism gate 已通過：stronger bounce 與 Oracle 各 100 seeds，
no-spawn feature equivalence 100 seeds 完全相同。190 px/s 仍是 provisional，
一般 generator 與 training distribution 不變。下一個獨立 gate 是翻板。

翻板 mechanism gate 已通過：active collision、inactive passthrough 與 Oracle
各 100 seeds，no-spawn feature equivalence 100 seeds 完全相同。五項特殊
機制均完成工程 gate，但所有特殊參數仍缺真實 fidelity。下一階段不是立即
重訓，而是先設計低比例、單一機制 generator，重新通過 reachability／Oracle／
baseline，再建立新的 Teacher Dataset。

首個單一機制 generator 已選 spike：10% proposal、前 3 層 normal、尖刺間
至少 5 normal。Reachability 100／1,000、Oracle 與 Baseline gates 全 PASS；
baseline 保留 plain 的 95.36%。使用獨立 seeds 生成 3,541-row Teacher
Dataset 且 validator 0 error。下一步是 dataset audit 與 bounded spike BC0；
正式多-seed 重訓才進 Colab。

Dataset coverage audit 顯示 test 有 232 spike-visible rows；本機 seed 0、
5-epoch interface smoke 在該 subset accuracy 75.43%，rollout 27.0 floors，
保留 baseline 85.58%，0 health death，已准許進 Colab。Spike-target emergency
subset 仍只有 10 rows／40%，正式三-seed BC0 必須保留此指標且不得直接進 DAgger。

2026-07-31 spike BC0 舊 Colab seed 0 顯示 offline validation loss 與
closed-loop rollout 反向：epoch 17 accuracy 82.06%，但 retention 僅 40.73%；
epoch 5 離線 accuracy 較低，rollout retention 卻為 85.58%。因此 BC0 改為
預先固定候選 epoch，以獨立 seeds 1060～1079 做 rollout checkpoint
selection，並只在完全未使用的 1200～1219 做 final gate。1100～1119
永久列為診斷集，不得再當 final evaluation。新管線 5-epoch smoke 已通過，
正式三初始化 seed 仍須在 Colab 執行。

2026-07-31 後續更新：新版 spike BC0 三初始化 final Gate 已通過；單輪 balanced
Spike DAgger0 雖提高 mean floors，卻使 early failure／bottom／health safety
退化，依協議停止。Teacher recovery 與 floor-10 reliability 修正後，正式一次
untouched seeds 1800～1899 的 reach-floor-10 為 94%、0 health death，通過
90% Gate。下一階段是凍結全新 seed partitions、重新產生新版 Spike Teacher
Dataset 並做 bounded BC0；不續跑舊 DAgger、不啟動長訓或實機 rollout。

Spike Teacher Dataset v1 已使用 2000～2059 生成並通過 coverage Gate；但 seed 0、
5-epoch BC0 smoke 在 final 2200～2219 的 mean deepest floor 雖保留 91.5%，
reach-floor-10 只有 60%、Q25 7.75、bottom 14，正式 Gate FAIL。依協議停止追加
epochs。下一設計需先處理 launch escape／direction brake 等具有 controller
memory 的 rare branches，再決定 branch-balanced sequence BC 或 bounded NEAT
compact-feature baseline；所有已使用 seeds 均不得再當 final。
