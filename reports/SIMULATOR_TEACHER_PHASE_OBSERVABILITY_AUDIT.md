# Simulator Teacher Phase Observability Audit

日期：2026-08-03  
狀態：**INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL**

## 結論

本輪完整重現 `departure_delayed` 在 seeds 2000～2059 的 base trace、performance 與
前一個 Launch-Handoff artifact 的 60 個首次 action 分歧位置。稽核只在 decision 前
旁路記錄觀測，沒有修改 controller、沒有訓練、沒有啟動原版遊戲，也沒有使用 fresh
6000～6099 seeds。

Launch-handoff 的首次介入只改變 8/60 個終局：2 個由 bottom 改善為 target reached，
6 個由 target reached 退化為 bottom，其餘 52 個不變。預先固定的 changed>=20、
improved>=10、regressed>=10 三項證據量門檻皆未通過，所以目前不能根據這批資料設計
或選擇新的 phase rule。

更重要的是，完全相同的可部署簽章
`rising|strong_upward_screen|6_12|True|False|False|1_2|0_12|normal`
同時包含 1 次改善、2 次退化與 7 次不變。這是已觀察到的 state alias；但因改變終局
的樣本只有 8 個，尚不足以估計一個可靠的分類邊界。這裡的 alias 限定在目前分箱後的
phase signature，不宣稱原始連續觀測逐值相同。Gate 因此停止在 observation schema
review，而不是再加一條 heuristic。

## 稽核設計與 provenance

- Base：`departure_delayed`；shadow intervention：已失敗的
  `departure_delayed_launch_handoff`。
- Seeds：2000～2059；每回合只取 base 與 shadow 首次 action 不同的 decision。
- Base trace SHA-256、summary performance及 60/60 首次分歧 step 均與來源 artifact
  完全一致。
- 可部署欄位：motion、畫面座標 `velocity_y`、nearest gap、support heuristic、
  landed/floor-descended event、edge distance、visible platform count、health segments、
  steps since landing event及nearest platform kind。
- `last_landed_floor`、physical velocity及simulator phase只作 privileged diagnostic label，
  沒有進入 Teacher input或可部署簽章。
- `velocity_y` 明確依畫面座標命名：負值是向上、正值是向下，避免把物理方向倒置。

## Gate 結果

| Check | 要求 | 結果 | 判定 |
|---|---:|---:|---|
| 每回合都有首次分歧 | 60 | 60 | PASS |
| 可部署欄位完整且有限 | 全部 | 全部 | PASS |
| 介入改變終局 | >=20 episodes | 8 | FAIL |
| 改善樣本 | >=10 episodes | 2 | FAIL |
| 退化樣本 | >=10 episodes | 6 | FAIL |
| 同簽章不得同時改善與退化 | 0 conflicts | 1 | FAIL |

共有 8 種可部署 phase signatures。Privileged label也沒有把結果乾淨分開：2 個改善
全是 `post_bounce_launch`，6 個退化中有 5 個也是 `post_bounce_launch`；
`nearest_is_last_landed=True` 同時出現在 2 個改善與 5 個退化案例。因此不能把
privileged phase或last-landed identity直接移入 Student／Teacher input來製造假分離。

## Support heuristic 的語意問題

Base 60 回合共有 936 個 `support_heuristic=True` decision，涵蓋全部回合；其中 876
個 motion 是 rising、60 個是 falling。這顯示目前 heuristic 實際代表「bounce 後仍靠近
某平台的幾何重疊」，不等同穩定站在平台上。這能解釋為何廣義 handoff 容易過度觸發，
但不能單獨告訴 controller 應該向左、向右或繼續 release。

## 現在不能做的事

- 不得用這 8 個 changed outcomes 擬合另一條 launch／support heuristic。
- 不得把 raw platform ID、`last_landed_floor` 或完整 simulator phase 當成可部署特徵。
- 不跑 fresh100、不生成正式 Dataset v2、不重開 P4.1/P4.2，也不啟動 BC、DAgger、
  PPO、DQN、NEAT 或真機探索。

## 下一個最小允許工作

下一步是 **bounded observation-schema probe**，不是訓練：先提出一組因果、可由真機
逐步重建且不含 raw identity 的 pre-decision 候選，例如 landing/floor-descended recency、
前一動作與 commitment、最近一次落台來源的相對幾何、以及目標落點／safe interval的
相對幾何。`steps_since_landing_event` 已在本輪簽章中仍發生衝突，不能單獨重做一次。

候選 schema 必須先以保存的 trace 做反事實／可分性稽核，並預先凍結 held-out 判定；
只有在改善與退化案例能穩定分離、且來源欄位能在原版遊戲因果取得時，才允許建立一個
新的 simulator Teacher 候選。否則應回到感知／事件定義，而非 controller 調參。

機器可讀證據：`artifacts/simulator_teacher_phase_observability_audit_v1.json`。

## 驗證

- phase／decision-observer targeted：6 passed；
- 完整 repository：454 passed in 178.57s；
- `compileall`、artifact JSON/source fingerprint與`git diff --check`：PASS。
