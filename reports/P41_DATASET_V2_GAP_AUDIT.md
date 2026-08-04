# P4.1 Dataset v2 Gap Audit

日期：2026-08-03  
狀態：**FAIL_STOP_BEFORE_V2_GENERATION**

## 結論

P4.1 的 S0／S1 checkpoint 重播證實：加入 causal action state 並沒有改善可靠度，
反而增加方向反轉並惡化 lower tail。依既定順序，本輪只進行 Dataset v2 Gap Audit，
沒有產生正式 Dataset v2、沒有訓練 Student，也沒有使用 final seeds 4100～4139。

更重要的是，用目前 repository 中的 Teacher 在完全相同的 seeds 2000～2059 重建
診斷資料時，成功率由凍結 Dataset v1 的 56/60（93.33%）降至 45/60（75%），
bottom death 由 4/60（6.67%）升至 15/60（25%）。舊 Dataset Gate 仍會判定兩者
PASS，因此它對可靠度漂移會產生 false positive。正式 Dataset v2 在 Teacher 分離或
修復、同種子 Gate 與 fresh-seed Gate 通過前一律禁止生成。

機器可讀結果：`artifacts/p41_dataset_v2_gap_audit.json`。

## 比較基準

| 項目 | Frozen Dataset v1 | Current Teacher diagnostic |
|---|---:|---:|
| seeds | 2000～2059 | 2000～2059 |
| rows | 3,529 | 3,571 |
| target reached | 56 | 45 |
| bottom death | 4 | 15 |
| health death | 0 | 0 |
| reach rate | 93.33% | 75.00% |
| bottom rate | 6.67% | 25.00% |
| RELEASE share | 37.63% | 48.42% |
| release-bridged reversals / 100 steps | 10.14 | 11.06 |

兩份資料的 action-distribution total variation distance 為 `0.10787`，高於本輪預先
提出的 `0.10` 上限。Current diagnostic JSONL 的 SHA-256 為
`98934cbd847175f1d0e1ce3eb044a259a85699b876caddf5ec3470907ed56dd0`；產生當下
Teacher source fingerprint 為
`56360c2fb30e4fa3779d57d8e9de5400c0bb0af312478ebfed3b054f4a8f177b`。

## 同種子 outcome 與首次分歧

| Frozen → Current | episodes |
|---|---:|
| target → target | 42 |
| target → bottom | 14 |
| bottom → target | 3 |
| bottom → bottom | 1 |

退化 seeds：`2002, 2007, 2008, 2016, 2020, 2021, 2025, 2026, 2035, 2037,
2044, 2045, 2051, 2053`。改善 seeds：`2017, 2028, 2033`。

60/60 episodes 都在 step 1 出現首次 action 分歧；主要 transition 是：

- `RELEASE -> LEFT`：32 episodes；
- `RELEASE -> RIGHT`：25 episodes；
- 其餘 3 episodes 是方向鍵與 RELEASE 的互換；
- 57/60 的首次 reason 由 `aligned_with_safe_platform` 變成
  `depart_support_platform`。

這把候選根因定位到新版 support-departure lifecycle，但不能只靠相關性宣稱它是所有
terminal 退化的唯一原因；step 1 分歧之後，兩條 trajectory 已不再是逐步反事實比較。
所以下一步是 bounded causal micro-ablation，而不是直接回退整個已通過實機 Gate 的
Teacher。

## Branch coverage

| branch | v1 rows / episodes | current rows / episodes |
|---|---:|---:|
| direction brake | 199 / 59 | 263 / 60 |
| launch escape | 1,692 / 60 | 545 / 60 |
| recovery | 179 / 13 | 201 / 14 |
| support departure | 0 / 0 | 567 / 60 |
| wall guard | 0 / 0 | 305 / 46 |
| special escape | 0 / 0 | 75 / 17 |
| no reachable target | 23 / 4 | 52 / 15 |
| spike target | 33 / 17 | 105 / 19 |
| damage | 16 / 14 | 16 / 15 |
| bottom context | 32 / 4 | 120 / 15 |

Current diagnostic 的 critical branches 均有 train／validation／test coverage，
但 coverage 不等於 policy reliability。舊 Gate 只檢查 validator、split 與 recovery
是否非零，沒有 reach 或 bottom 門檻，因此 current Teacher 即使 bottom rate 25%
仍會 PASS。

## Dataset v2 readiness Gate

下列條件在正式生成前固定，不用結果反向調整：

1. `teacher_policy_version` 必須升版，summary 必須嵌入 Teacher source 與 config
   fingerprints。
2. 相同 seeds 2000～2059：reach rate 至少 91.33%、bottom rate 至多 8.67%、
   health death 必須為 0、action TV 至多 0.10。
3. direction brake、recovery、spike target 必須跨 train／validation／test；episode
   coverage 下限分別為 20、10、10。
4. 同種子 Gate 全通過後，才能在 100 個 fresh seeds 評估；fresh reach 至少 90%、
   bottom 至多 10%、health death 為 0，並必須報告 Q25 與 CVaR25。
5. Real-game Teacher 與 Simulator Teacher 必須有不同 profile/version；不得為改善
   simulator dataset 而回退已通過 P3.6 真機穩定性 Gate 的控制器。

本輪失敗項目：policy version 未升、fingerprints 尚未嵌入原 summary、同種子 reach、
同種子 bottom、action TV、fresh reliability 未執行／未通過。因此 `v2_ready=false`。

## 下一個允許的實驗

只允許建立獨立 Simulator Teacher profile，並在相同 60 seeds 做三個有界候選：

1. current behavior；
2. normal-support departure 延後；
3. normal-support departure 關閉。

先比較 outcome、Q25/CVaR25、bottom、reversal 與 branch coverage。沒有候選通過
同種子 Gate 就立即停止，不跑 fresh 100；通過後才准 fresh reliability Gate，最後才
升版並生成正式 Dataset v2。此流程不包含 BC、DAgger 或任何長時間訓練。

## 驗證

- Dataset audit targeted tests：3 passed；
- P4.1 related tests：28 passed；
- 完整 repository：441 passed；
- `compileall`、artifact JSON parse、`git diff --check`：PASS；
- diagnostic-only 26.3 MB JSONL及暫存summary已在確認未受Git追蹤後刪除；正式audit
  artifact保留統計、hash與provenance。
