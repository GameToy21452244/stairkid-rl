# Spike DAgger0 Report

日期：2026-07-31

## 結論

單一 bounded balanced Spike DAgger0 已完成，但正式 Gate **FAIL**：

- 三初始化 mean floors 由 28.57 提高到 38.75（+10.18）；
- floor-10 success 卻由 86.67% 降到 75%；
- bottom death 由 15/60 增到 27/60；
- initialization seed 2 在 final seed 1500 發生 1 次 `health_depleted`；
- 因此只有 2/3 initialization seeds 通過 final Gate。

平均樓層上升是正面證據，但來自部分超長回合，不能掩蓋低樓層可靠度與安全
退化。本輪不得宣稱 PASS，不執行第二輪 DAgger，也不進入下一種特殊平台。

## 凍結協議

- Source BC0：Colab 通過的 initialization seeds 0／1／2，epoch 11／5／8。
- Aggregation seeds：1300～1359，每個來源模型 20 episodes。
- Checkpoint-selection seeds：1400～1419。
- Final comparison seeds：1500～1519。
- 候選 epochs：3／5／8／11／14／17。
- Final seeds 已使用，後續實驗不得再次把 1500～1519 當 untouched final。

## Corrections

60 episodes 共收集 8,076 disagreements：

- spike visible：3,555；
- high-confidence disagreement：1,394；
- missed-platform risk：1,424；
- top／bottom terminal risk：467／100；
- 其餘為 brake-too-late、wrong-target、wall collision。

依凍結設計只選 592 rows（base train 的 25%）：

- action quota：RELEASE 265、LEFT 161、RIGHT 166；
- source models：186／207／199；
- 60/60 aggregation episodes 有覆蓋；
- 最大單 episode share 3.04%；
- spike-visible 181；terminal-near 75；
- 12 clusters × failure category × source model round-robin。

## Final results

| init seed | epoch | 原 BC0 | DAgger0 | delta | final gate |
|---:|---:|---:|---:|---:|---|
| 0 | 5 | 27.75 | 43.95 | +16.20 | PASS |
| 1 | 3 | 29.00 | 32.20 | +3.20 | PASS |
| 2 | 11 | 28.95 | 40.10 | +11.15 | FAIL：1 health death |

三模型都沒有 action collapse。可是 seed 1 的 paired episodes 為 9 wins／
11 losses，中位 delta −4；整體 floor-10 success 降低，表示 mean floors 不是
充分的 checkpoint-selection 與 final Gate 指標。

## Health death 診斷

固定重播 DAgger seed 2／environment seed 1500：

- 終止於 step 297，`health_depleted`；
- 共接觸 5 次 spikes、13 次 health gain；
- 最後三次 spike landing 發生於 deepest floor 46／52／58；
- 角色會跳過部分 normal floors，所以雖然 generator 保證尖刺間至少 5 個
  normal platforms，實際策略沒有逐一踩到所有回血平台。

這不是空白樓層或 generator 漏建平台；每層仍有一個平台。問題是 Teacher／
policy 在受傷後沒有足夠強制地優先踩最近 normal recovery platforms。

## 下一個允許的工作

先修改協議與 Teacher，不直接重訓：

1. checkpoint selection 先依 health death、floor-10 success、bottom death、
   lower-tail floors 排序，再看 median／mean；
2. Teacher-observable 進入受傷 recovery mode，優先最近 normal platform，
   禁止為追求 deeper floor 跳過回血平台；
3. 新增 recovery-mode fixed scenarios、單元測試與 Oracle／Baseline gates；
4. 通過後才能另行凍結全新 aggregation／selection／final seeds。

目前 Spike DAgger0：**FAIL／STOP**。長 PPO、DQN、混合特殊平台與真實遊戲
長訓維持 No-Go。
