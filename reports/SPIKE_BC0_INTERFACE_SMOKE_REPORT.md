# Spike BC0 Interface Smoke Report

日期：2026-07-31

## 結論

**PASS（只代表本機介面與短預算可執行）**。

這不是正式多-seed BC0。只執行 seed 0、hard-label、最多 5 epochs，使用
fresh evaluation seeds 1100～1119；沒有啟動遊戲或長時間訓練。

## 結果

| 指標 | 結果 |
|---|---:|
| Test overall accuracy | 74.75% |
| Spike-visible test rows | 232 |
| Spike-visible accuracy | 75.43% |
| Spike-target emergency rows | 10 |
| Spike-target accuracy | 40.00% |
| BC mean floors | 27.00 |
| Baseline mean floors | 31.55 |
| Baseline retention | 85.58% |
| Random mean floors | 3.05 |
| RELEASE mean floors | 7.55 |
| BC health deaths | 0 |
| Max action share | 45.97% |

Gate 為不 collapse、優於 random／RELEASE、至少保留 baseline 80%，以及
spike-v0 0 health death；全部通過。

## 判讀

Spike-visible accuracy 與 overall 接近，表示模型不是完全忽略含尖刺畫面。
但教師真正以 spike 作緊急目標的 test rows 只有 10，40% accuracy 不足以宣稱
已精確學會低血量緊急踩刺。正式實驗不可只報 rollout floors。

## 下一步

Colab 執行 seeds 0／1／2、hard-label、每 seed 最多 30 epochs且 early stop，
使用凍結 fresh eval。三個 seeds 都必須：

- 無 action collapse；
- 0 health death；
- 優於 random／RELEASE；
- 至少保留同 seed baseline 80%。

任一 seed 失敗即停止，不直接開始 DAgger 或追加長訓。
