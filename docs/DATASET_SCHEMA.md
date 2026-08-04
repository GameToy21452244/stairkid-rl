# Dataset Schema

## 版本

- record schema：`ns-shaft-transition-v1`
- observation：`stair-observation-v3-268`
- reward：`stair-reward-v2`
- 實作：`src/stair_agent/data/schema.py`
- validator：`src/stair_agent/data/validator.py`
- writer：`src/stair_agent/data/writer.py`

## 一筆 transition

| 欄位 | 型別 | 說明 |
|---|---|---|
| `schema_version` | string | record schema |
| `episode_id` | string | 不可跨界重用的回合 id |
| `step` | integer | 同回合連續遞增 |
| `observation` | float[268] | 動作決策前的 stacked observation |
| `action` | 0/1/2 | RELEASE／LEFT／RIGHT |
| `reward` | finite float | 這次 transition 的 reward |
| `reward_components` | object | 可加總、可稽核的 component |
| `next_observation` | float[268] | 動作生效後的下一觀測 |
| `terminated` | boolean | MDP 終止，如死亡 |
| `truncated` | boolean | 時間／步數等外部截斷 |
| `events` | object[] | landed、floor_descended、damage 等 |
| `policy_source` | enum | 標籤／動作來源 |
| `target_platform_id` | integer/null | 決策時目標 |
| `target_platform_kind` | string/null | 目標種類 |
| `target_signed_offset` | float/null | 玩家到安全落點的 signed offset |
| `observation_timestamp` | float | 決策觀測完成時間 |
| `action_command_timestamp` | float | 輸入命令時間 |
| `action_effective_timestamp` | float | 估計遊戲開始反應時間 |
| `next_observation_timestamp` | float | 下一觀測完成時間 |
| `held_action` | boolean | 下一觀測完成後是否仍延續按住狀態 |
| `action_duration_ms` | float | 命令生效至下一觀測的已知最短有效時間；held 時不代表最終總 hold 時間 |
| `observation_schema_version` | string | 特徵意義與維度版本 |
| `reward_version` | string | reward 定義版本 |
| `timestamp` | ISO-8601 string | record 寫入的 wall-clock time |

`policy_source` 只允許 `human`、`baseline`、`baseline_verified`、`old_ppo`、
`model`、`corrected`、`invalid`。其中 `baseline` 不等於可作教師；
人工通過品質 gate 後才可升格 `baseline_verified`。

## Resource audit 與教師擴充

既有資料先以 `artifacts/dataset_inventory.csv` 及
`artifacts/dataset_salvage_manifest.csv` 分類為 `demo_verified`、
`replay_valid`、`needs_relabel`、`dynamics_only` 或 `invalid`。schema-valid
不等於 expert-valid；固定校正序列只能是 `dynamics_only`。

Simulator teacher dataset 在 gate 通過後另存下列 provenance：

- `teacher_type=teacher_observable`；
- `teacher_confidence`；
- `candidate_action_values`（三動作 soft target／distribution）；
- `verified`；
- `environment_version`；
- `observation_schema_version`；
- `platform_sequence_id` 與 split。

同一 `platform_sequence_id` 不得跨 train／validation／test。Oracle-full
輸出不得寫成 teacher dataset；若未來正式升級 transition schema，必須升版，
不可把上述欄位靜默塞入 v1。

Spike curriculum 的 TeacherRecord 使用四個向後相容 audit 欄位：

- `visible_platform_kinds`：decision 前可觀測的平台 kinds；
- `health_segments`：decision 前的可觀測血量。
- `teacher_policy_version`：產生標籤的規則 policy 版本；舊資料預設
  `legacy-unspecified`，新版不得為空。
- `teacher_reason`：可解釋決策分支，例如 recovery／launch escape。

它們只供 coverage／subset metrics，沒有加入 268 維 observation 以外的模型
輸入，也不得用來重建 privileged simulator state。

目前 `ns-shaft-teacher-v1` 已由獨立 validator 實作：60 episodes／3,560 rows，
train／validation／test 為 2,362／609／589，validator 0 error。這是 simulator
teacher smoke dataset，不會升格或改寫任何 legacy real-game JSONL。

Spike Teacher Dataset v1 使用 seeds 2000～2059、3,529 rows，並以通過的
Teacher recovery holdout 作前置 provenance。其 train／validation／test 為
2,327／605／597，validator 0 error；所有列標記
`teacher-observable-safe-platform-v2`。

## Dataset v2 產生前 Gate

凍結 Dataset v1 與 current Teacher 在相同 seeds 2000～2059 的診斷比較發現，
current Teacher 的 target-reached 由 56/60 降到 45/60、bottom death 由 4/60
升到 15/60；舊 coverage Gate 仍會誤判 PASS。因此任何正式 Dataset v2 必須在寫檔前：

- 升級 `teacher_policy_version`，並把 Teacher source 與 config fingerprints 寫入
  summary／manifest；Real-game 與 Simulator Teacher 使用不同 profile/version；
- 在相同 60 seeds 達 reach rate >= 91.33%、bottom rate <= 8.67%、health death=0、
  action-distribution total variation <= 0.10；
- direction brake、recovery、spike target 都跨 train／validation／test，且 episode
  coverage 分別至少 20／10／10；
- 上述全通過後才可在 100 fresh seeds 評估，要求 reach >= 90%、bottom <= 10%、
  health death=0，並報告 Q25／CVaR25；
- 任一條件失敗時不得產生或訓練正式 v2，診斷 JSONL 不得改名冒充正式資料。

完整證據見 `reports/P41_DATASET_V2_GAP_AUDIT.md` 與
`artifacts/p41_dataset_v2_gap_audit.json`。

第一次Simulator profile修復Gate已執行：current／departure delayed2／disabled的
reach為75%／81.67%／76.67%，bottom為25%／18.33%／23.33%，三者皆未達同種子
門檻，且action TV亦失敗。因此selected profile為null、fresh100未執行，schema與
正式Dataset v2均未建立。下一個診斷只允許處理support/contact與launch handoff重疊；
詳見`reports/SIMULATOR_TEACHER_PROFILE_GATE_REPORT.md`。

其後唯一support-aware launch候選亦FAIL：reach 75%、bottom 25%，且support-departure
rows被完全取代。Fresh100仍未使用。當時下一步降級為phase observability audit；在可部署
特徵無法分離phase前，不新增資料schema、不生成Dataset v2。詳見
`reports/SIMULATOR_TEACHER_LAUNCH_HANDOFF_GATE_REPORT.md`。

Phase observability audit已完成：60個首次分歧只有2改善、6退化、52不變，且一個相同
deployable signature同時包含改善與退化。現有event/motion/vy/gap/support/edge/landing
recency view不能解鎖Dataset v2。下一步只允許設計與離線評估候選schema；任何正式欄位
都必須pre-decision、真機可重建、不含raw platform identity或privileged simulator phase，
並另升schema/version。詳見
`reports/SIMULATOR_TEACHER_PHASE_OBSERVABILITY_AUDIT.md`。

## P4.1 causal／sequence view（不修改原 JSONL）

P4.1不另造或改寫Teacher rows，而是以manifest鎖定上述3,529-row JSONL及SHA-256。
Loader重新驗證episode連續、step、verified Teacher、268維、有限值、soft-target、
split/seed/platform-sequence隔離與terminal continuity，再建立下列唯讀view：

- S0：原268維row；
- S1：原268維＋decision前9維causal action state；
- S2：不跨episode的268維24-step chunks；
- S3：每step的22維compact observation＋9維causal action state之24-step chunks。

9維state包含前一action one-hot、previous-present、last non-release direction one-hot、
same-action streak、release streak與最近direction switch rate。建立row t特徵後才以
label `action_t`更新state，因此沒有同一步答案；episode第0步及deployment reset全零。
Compact observation只取268維stack最新一個67維frame中的前22維（16 core＋最近平台
6維），明確排除該frame內3維action one-hot，避免和causal state重複。

Chunk固定length 24、burn-in 8；`valid_mask`標實際row，`loss_mask`只標本chunk首次
負責的target rows，padding step為-1。所有episode的loss steps合併後必須恰為
`0..N-1`且各一次。這只是訓練view schema `p41-causal-sequence-v1`，不是P4.2正式
rare-branch sequence dataset。

## Validator

`python scripts/validate_dataset.py path/to/data.jsonl`

會檢查：

- 必填／未知欄位、版本、268 維 observation；
- NaN／Inf、無效動作、單筆及跨 transition 時間倒退；
- terminal／truncated 後仍有資料、step 不連續、episode 跨界重現；
- observation continuity 跳變；
- action collapse 與高度重複 transition。

error 代表不可訓練；warning 需人工審核，不能靜默忽略。

`TransitionJsonlWriter` 一次只寫一個 episode、拒絕覆寫、逐筆核對 reward
component 加總，且 terminal/truncated 後拒絕續寫。真實 action timing 由
`LiveGameAdapter` 在 command、backend apply 完成與 next observation 三個位置
量測；未實際送出的動作不寫入 calibration dataset。

## 舊資料政策

現有 observations、reward-audit、baseline JSONL 缺少 episode id、next observation、
獨立 action timestamps、reward components 或版本，且存在 16／64 維歷史格式。
它們一律是 legacy quarantine。未來 migration 應產生新檔與逐筆 provenance，
不可原地改寫；無法可靠重建的欄位必須標 `policy_source=invalid`，不能填假時間。

## Sequence dataset（規格已凍結，尚未生成）

下一版 rare-branch 資料以完整 episode 或不跨 episode 的連續 chunk 為單位，另行
升版，不把欄位靜默塞入 `ns-shaft-transition-v1`。每個 chunk 至少保存：

- observation/action sequence、padding mask、burn-in length；
- Teacher action distribution/confidence；
- deployable target representation、target lock age、controller phase；
- previous action/held duration、time since landing、braking/recovery flag；
- reward components、events、perturbation type/strength、success/failure；
- environment/observation/schema version、seed、episode、platform sequence、split。

同一 episode、seed 或 platform sequence 不得跨 split。branch coverage 以 sequence
數而非 row 數計算；在 Teacher Real Gate 通過前不得產生正式 sequence dataset。

### 2026-08-03 observation-schema probe停止結論

`simulator_teacher_observation_schema_probe_v1.json`是診斷artifact，不是Teacher
Dataset v2，也不得併入Student訓練。400回合的launch-handoff counterfactual只有1個
improved與29個regressed，development沒有正向class，故schema classifier不可評估。
正式v2仍未生成；下一個資料候選只能是另行定義、同步frame／action timing／causal
history／target geometry的bounded真機alignment packet，且必須使用新schema/version與
執行前凍結的split/Gate。

### Real alignment packet v1（診斷專用）

`real-alignment-packet-v1`不取代`ns-shaft-transition-v1`，也不是Student dataset。它在
受限真機run中額外保存structured observation/next observation、decision前後memory、
Teacher action/reason、visible target safe geometry、四時間點與MP4 frame index。每筆
必須`diagnostic_only=true`及`training_eligible=false`；raw track ID只供同幀對齊。

step 0 pre-memory必須是reset；後續pre-memory必須等於前一步post-memory。Integrity或
coverage Gate未過時不得抽取正式sequence dataset；即使packet PASS，也只能先進行
Simulator／real target與timing alignment audit。

### Controller memory 的因果時間序

目前實機 `*.controller.jsonl` 是在 `policy.choose(observation_t)` 後才寫入，因此
`controller_memory_t.previous_action` 已是 `action_t`，phase亦可能由本步reason產生。
它是 post-decision audit sidecar，不是同一步Student input。P4.1與後續sequence資料
必須遵守：

- 輸入 decision `t` 的 explicit memory 只能由 sidecar `t-1` 重建；
- 每個episode第0步使用明確reset/default，絕不可跨episode carry；
- 當步sidecar只可作label provenance、branch audit或leakage ceiling；
- `*_platform_id`、contact episode ID等tracker identity不可作模型特徵；
- 如果未來要記錄真正pre-decision snapshot，必須新增具明確時序名稱的schema版本，
  不得靜默改變現有欄位語意。
