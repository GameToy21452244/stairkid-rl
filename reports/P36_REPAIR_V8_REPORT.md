# P3.6 Repair v8 Report

日期：2026-08-02

狀態：**Gate v4 FRESH REAL FAIL；P3.6 HOLD／STOP**

## 1. Gate v3 實機證據

來源：`logs/teacher_real_micro_20260802_004816_756981`。

- 三回合 Gate parser floors：`2,4,10`；使用者觀察第三回合約 13，影片至少明確
  顯示 HUD floor 12，確認 parser 仍漏計。
- reach-floor-3／5、wall re-entry=0、outward=0、departure target stability 與 safety
  checks 通過；上一版 wall repair 有效。
- Gate v3 整體 FAIL：EP2 有 25-step recovered dropout 與一次 departure timeout；
  EP3 另有 16-step dropout。第一回合仍為 floor-2 bottom death。

影片與 sidecar 對齊後，長時間 RELEASE 有三個主要區間：

| episode | steps | 約秒數（9 Hz） | 原因 |
|---|---:|---:|---|
| 2 | 0–24 | 2.7 s | 即時 player detector missing 25 steps |
| 2 | 66–82 | 1.9 s | timeout 後同 source 被永久 blocked |
| 3 | 200–215 | 1.7 s | 即時 player detector missing 16 steps |

EP2 timeout 時，舊 controller 在 step 66 清除 departure 後把 source 19 永久 blocked；
只要 support track ID 仍為 19，任何新 destination 都輸出
`support_departure_safety_abort -> RELEASE_ALL`。因此一次 timeout 被擴大為 17-step
停頓，這是可重現的 controller bug。

另外，MP4 解碼後以相同 detector 重播可在 438/439 playing frames 找到 raw player，
但真機 sidecar 有 41 個 invalid steps。H.264/MPEG-4 壓縮改變顏色後反而跨過 HSV／
component 門檻，所以壓縮影片不能用來校正真機 raw detector。

## 2. Repair v8 實作

### 2.1 Bounded departure retry

- 保留 `support_departure_max_steps=8` hard cap；timeout 仍記錄
  `support_departure_safety_abort` 且 Gate 仍要求 timeout=0。
- timeout 後只 cooldown 2 steps，reason 為
  `support_departure_abort_cooldown`；之後解除 source block，以最新可見 target
  重新建立 departure。
- controller memory 新增 abort source 與剩餘 cooldown；Gate 要求最大 cooldown
  streak `<=2`，防止再次退化成永久 RELEASE。

### 2.2 Lossless dropout forensics

每回合固定建立 `episode_XX.dropout/manifest.json`。只在 missing streak
1／3／8／16／24 與 recovery 採樣，每回合最多 6 個 snapshot；每個 snapshot 包含：

- action 前的 lossless raw PNG；
- 使用與 live detector 完全相同規則產生的 player HSV mask PNG；
- playfield、HSV thresholds、component box／area／colored pixels、size/eligibility；
- step、source、streak、teacher reason、action、phase、confidence 與 floor。

Forensic 診斷錯誤不會中斷輸入安全；raw frame 仍會保存。固定上限避免磁碟無限制
成長，也不改 policy action。

### 2.3 Gate v4

- recovered observation dropout 門檻由 20 收緊為 8 steps；在目前約 9 Hz 下，
  20 steps 約 2.2 秒，已被使用者明顯感知為停住。
- 每回合必須有 dropout forensic manifest。
- departure abort cooldown 最大 2 steps。
- 原有 blind action、top-pressure bridge、wall、departure、lower-tail、影片與安全
  checks 全部保留。

## 3. 驗證

- Targeted tests：112 passed；Gate-only 更新後 31 passed。
- 最終完整回歸：375 passed in 58.36s。
- compileall：PASS。
- Gate v4 Repair-v8 dry-run：PASS；artifact：
  `artifacts/teacher_real_game_micro_gate_v4_repair_v8_dry_run.json`，且確認不尋找
  遊戲、不載入 input backend、不送出按鍵。
- 最新三支舊 MP4 的 v8 counterfactual replay：outward 0、wall re-entry 0，但因舊
  影片軌跡不會回應 retry action，產生重複 timeout／same-support cycles，故合理 FAIL。
  此結果不能證明 v8 closed-loop 成功或退化，只證明 safety checks 沒被繞過。

## 4. 下一步

Fresh Gate v4 已完成，floors `9,2,2`，35/36 checks PASS；v8 相關 dropout、
departure timeout、wall 與 safety checks 均通過，但 reach-3 只有1/3，未達2/3。
P3.6 因此仍 HOLD。下一步改為 Repair v9 的 momentum/braking-aware landing 與
destination-aware special escape；詳見 `P36_REPAIR_V8_LIVE_GATE_REPORT.md`。
