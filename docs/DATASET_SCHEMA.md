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
| `held_action` | boolean | 是否延續前步按住狀態 |
| `action_duration_ms` | float | 該動作有效持續時間 |
| `observation_schema_version` | string | 特徵意義與維度版本 |
| `reward_version` | string | reward 定義版本 |
| `timestamp` | ISO-8601 string | record 寫入的 wall-clock time |

`policy_source` 只允許 `human`、`baseline`、`baseline_verified`、`old_ppo`、
`model`、`corrected`、`invalid`。其中 `baseline` 不等於可作教師；
人工通過品質 gate 後才可升格 `baseline_verified`。

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
