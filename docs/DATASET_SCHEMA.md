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
