# BC0 / DAgger0 Smoke Report

日期：2026-07-31

## 結論

- BC0 原始 soft-target loss：**FAIL**，20.95 floors。
- BC0 hard-label cross-entropy：3/3 initialization seeds **PASS**。
- DAgger0 round 1：**FAIL**，23.20 floors；不執行第二輪。

本輪沒有增加原始 teacher dataset、沒有放寬 80% baseline gate，也沒有長訓。

## BC0 failure diagnosis

原始 BC0 在 held-out teacher dataset 的 accuracy 為 88.79%，但在 frozen
rollout seeds 100～119 上：

- learner-state teacher disagreement rate：41.01%；
- 每回合平均 disagreement：66.95；
- 每回合最後 20 steps 平均 disagreement：11.20；
- motion 分布：rising 726、falling 511、stable 102。

因此離線 accuracy 高估 rollout 品質。問題不是 epoch 不足，而是 soft target
在序列控制中把 RELEASE／方向修正邊界過度平滑，造成 learner-state covariate
shift。

## Bounded BC0 ablation

資料、架構、frozen eval seeds 與最大 epochs 都不變，只比較 loss：

| loss／seed | test accuracy | mean floors | baseline | baseline ratio | gate |
|---|---:|---:|---:|---:|---|
| soft／0 | 88.79% | 20.95 | 29.80 | 70.3% | FAIL |
| hard／0 | 87.44% | 29.80 | 29.80 | 100.0% | PASS |
| hard／1 | 88.62% | 30.10 | 29.80 | 101.0% | PASS |
| hard／2 | 87.78% | 25.95 | 29.80 | 87.1% | PASS |

Hard-label 三 seeds 平均 28.62 floors，全部高於固定門檻
`0.8 × 29.80 = 23.84`。離線 accuracy 沒有提高，但 rollout 大幅改善，證明
決策邊界比 soft-label calibration 更重要。

Teacher dataset 仍保存 soft target／confidence 作 ambiguity audit；BC0 預設
loss 改為 hard cross-entropy。這不代表未來永久禁止 soft target，而是目前
soft probabilities 尚未校正到可直接當訓練目標。

## DAgger0 round 1

來源模型：hard-label seed 0。Aggregation 使用獨立 seeds 300～319，不與
train／validation／test 或 frozen eval seeds 重疊。

收集 1,634 corrections：

| failure category | records |
|---|---:|
| missed-platform risk | 867 |
| wrong target | 371 |
| brake too late | 276 |
| wall collision | 120 |

每 episode 平均 81.7 corrections。合併後以相同 hard-label設定重訓，在相同
frozen seeds 上：

- DAgger0：23.20 floors；
- source BC0：29.80 floors；
- 差異：−6.60 floors（−22.1%）；
- baseline：29.80 floors；
- 80% gate：23.84 floors。

DAgger0 跌破 gate。最可能原因是把所有 disagreement 等權加入，使 1,634 筆
高度相關 learner-state corrections 相對原 train 2,362 筆占比過高，並改變
RELEASE／LEFT／RIGHT 決策邊界；這一輪沒有證據支持繼續 aggregation。

## Go / No-Go

- BC0 hard-label：**PASS**。
- DAgger0 round 1：**FAIL**。
- 第二輪 DAgger、長 BC、長 PPO／DQN、特殊平台 curriculum：**NO-GO**。
- 下一步只應做 correction weighting／subsampling 的離線設計與 failure-cluster
  audit；需新的人工確認工作包，不能自動追加訓練。

## 後續單次 balanced ablation

使用者確認下一步後，完成離線 audit 並預先固定 25% cap、原 action ratio 與
12-cluster/category round-robin。唯一一次重訓在 frozen／fresh seeds 得到
63.15／62.90 floors，通過 gate。詳見
`DAGGER0_BALANCED_ABLATION_REPORT.md`；easy curriculum 隨即凍結。
