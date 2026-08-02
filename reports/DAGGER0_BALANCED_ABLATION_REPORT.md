# DAgger0 Balanced Ablation Report

日期：2026-07-31

## 結論

Correction audit 後預先固定的單次 balanced ablation 通過：

- frozen seeds 100～119：63.15 floors；
- fresh audit seeds 400～419：62.90 floors；
- fresh baseline：31.25 floors；
- 無 action collapse；
- easy curriculum 已接近 600-step episode ceiling。

依 Phase F 停止，不自動執行第二次訓練、特殊平台混合 curriculum 或長 RL。

## 為何 naive DAgger0 失敗

1,634 corrections 相當於原 train set 2,362 rows 的 69.18%。雖然 exact／
rounded duplicate 都是 0，但 action distribution 明顯偏移：

| dataset | RELEASE | LEFT | RIGHT |
|---|---:|---:|---:|
| 原 train | 1,045（44.2%） | 655（27.7%） | 662（28.0%） |
| 全 corrections | 396（24.2%） | 744（45.5%） | 494（30.2%） |

這使 naive round 1 從 29.80 降至 23.20 floors。問題是相關狀態量與 action
distribution，不是相同 row 重複。

## 預先固定的唯一方案

- correction cap：原 train records 的 25%，即 590 rows；
- action quota 依原 train distribution：RELEASE 261、LEFT 164、RIGHT 165；
- observation 以 deterministic k-means 分成 12 clusters；
- 每個 action 內，以 `(cluster, failure_category)` round-robin；
- aggregation 20 episodes 全部有覆蓋；
- 最大單 episode 占 7.63%；
- random seed 固定為 20260731；
- 設計先寫入 artifact，之後才執行唯一一次訓練。

Selected failure categories：

- missed-platform risk 248；
- brake too late 157；
- wrong target 123；
- wall collision 62。

## Frozen evaluation

相同 seeds 100～119、600-step hard limit：

| candidate | mean floors | median | std | terminal |
|---|---:|---:|---:|---|
| 原 hard BC0 seed 0 | 29.80 | 30.5 | 14.27 | bottom/top/time |
| naive DAgger0 | 23.20 | — | — | — |
| balanced DAgger0 | 63.15 | 65 | 6.23 | 18 time-limit、2 top |

Balanced action counts：RELEASE 4,291、LEFT 3,880、RIGHT 3,455；
最大 action share 36.9%，不是 collapse。20/20 都達 10 層，最低 37、最高 66。

## Fresh-seed anti-overfit evaluation

完全未參與 train、validation、test、aggregation 或 frozen selection 的
seeds 400～419：

- balanced DAgger0：62.90 floors；
- baseline：31.25 floors；
- 17/20 達 600-step time limit；
- terminal：17 time-limit、2 bottom、1 top；
- floors：最低 42（另有一回合 44），多數 64～66。

另外新增 invariant test：`floor_descended` 只可在 `deepest_floor` 嚴格增加時
出現，未出現時 floor index 不得改變，且 event count 不得超過 deepest floor。
這同時允許合法跳過一個平台，並防止同平台重複刷 floor reward。

## Gate 與限制

- Balanced DAgger0：**PASS**。
- Fresh-seed generalization：**PASS**。
- Action diversity：**PASS**。
- Floor-event anti-exploit invariant：**PASS**。
- Easy curriculum：**SATURATED**；繼續在 easy normal platforms 增加 epochs
  或 corrections 幾乎沒有資訊價值。
- 特殊平台 curriculum、長 PPO／DQN、真實遊戲 rollout：**NO-GO，等待人工確認**。
