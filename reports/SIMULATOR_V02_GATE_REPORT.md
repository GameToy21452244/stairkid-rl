# Simulator v0.2 Gate Report

日期：2026-07-30

環境：`ns-shaft-sim-v0.2`，easy distribution，fixed physics 60 Hz。
所有評估均為 headless simulator，未接觸真實遊戲。

## Gate 總表

| Gate | 門檻 | 結果 | 狀態 |
|---|---|---|---|
| Reachability 100 | 0 known unreachable、3-floor look-ahead、reproducible | 0 unreachable，完全重現 | **PASS** |
| Reachability 1,000 | 通過 100 後擴大 | 0 unreachable，完全重現 | **PASS** |
| Oracle-full | easy ≥95% 到 10 層 | 100/100 到 10 層 | **PASS** |
| Baseline | mean≥5、≥90% 到3層、>random/release | mean 29.75、99% 到3層 | **PASS** |
| Teacher-observable | 無 privileged state、soft target、schema valid | API anti-leak tests 與 dataset validator 通過 | **PASS** |
| Teacher Dataset | 前置 gates 全通過、episode split | 60 episodes／3,560 rows、0 errors | **PASS** |
| BC0 | 不塌縮、>random/release、≥80% baseline | hard-label 3/3 seeds PASS，mean 28.62 | **PASS** |
| DAgger0 | 僅 BC0 PASS 才可執行 | round 1 降至 23.20、低於 23.84 gate | **FAIL** |

## 8 Hz 固定 gate

100 seeds、每回合最多 600 policy steps：

| 策略 | mean floors | median | 到3層 | 到10層 |
|---|---:|---:|---:|---:|
| Oracle-full（到10層即停） | 10.00 | 10 | 100% | 100% |
| Baseline | 29.75 | 30 | 99% | 82% |
| Random | 2.98 | 1 | 47% | 4% |
| RELEASE | 8.58 | 5 | 86% | 33% |

Paired seed 差：baseline − random 平均 +26.77 層、95% seeds 為正；
baseline − RELEASE 平均 +21.17 層、87% seeds 為正。

## Control frequency

| Hz | Oracle mean | Baseline mean | Baseline 到3層 | Baseline 到10層 |
|---:|---:|---:|---:|---:|
| 8 | 10.00 | 29.75 | 99% | 82% |
| 10 | 10.00 | 34.68 | 100% | 93% |
| 12 | 10.00 | 33.48 | 100% | 93% |

選擇 Simulator teacher／BC0 使用 10 Hz：它在相同 seeds 的 baseline mean
最高，100 ms action duration 也接近量測的約 94 ms effective→next observation。
這不是提高真實遊戲頻率的授權；真實控制仍保持約 8 Hz。

`missed_platform` 目前只能以 bottom death 作 proxy，`brake_too_late` 無可靠直接
觀測，CSV 明確標為 `not_observable`，不以假 0 通過。

## Teacher Dataset

- split：train 2,362、validation 609、test 589 records；
- episodes／seeds：40／10／10，同一 sequence 不跨 split；
- action：RELEASE 1,573、LEFT 983、RIGHT 1,004；
- 每筆含 observation、next observation、hard/soft action、confidence、
  candidate values、target、events、environment/schema version；
- `teacher_type=teacher_observable`；Oracle-full 沒有寫入資料集。

## BC0 Smoke（更新）

模型：`268 → 256 → 128 → 3`，seed 0，episode-separated dataset。

- test accuracy 88.79%；
- precision：RELEASE 0.831、LEFT 0.957、RIGHT 0.944；
- recall：RELEASE 0.948、LEFT 0.810、RIGHT 0.865；
- rollout mean floors：BC0 20.95、baseline 29.80、random 4.75、
  RELEASE 9.55；
- soft-target BC0 未 action collapse且優於 random／RELEASE，但只有 baseline
  的 70.3%，因此 FAIL。
- 診斷發現 learner-state teacher disagreement 41.01%；改用 hard-label
  cross-entropy 後，三 seeds 為 29.80／30.10／25.95，全部 PASS。
- 依條件執行一輪 DAgger0，結果降至 23.20，低於 23.84 gate，故 DAgger0
  FAIL 並停止。詳見 `BC0_DAGGER0_REPORT.md`。
