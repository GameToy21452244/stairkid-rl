# Simulator / Real-Game Alignment Audit Protocol

日期：2026-08-03  
狀態：**FROZEN_BEFORE_EXECUTION**

## 目的

`PASS_REAL_ALIGNMENT_PACKET` 只代表真機診斷資料完整，不代表 Simulator 已與真機對齊。
本稽核比較控制時間、動作反應、平台種類分布、support-contact phase 與短期反向操作，
判斷目前 Simulator 是否足以產生正式 Student 訓練資料。

本稽核不修改 Teacher action、不把真機 packet 轉成訓練資料，也不啟動 BC、DAgger、
PPO、DQN、NEAT 或其他長時間訓練。

## 凍結輸入

- 主要真機證據：`logs/teacher_real_micro_20260803_205952_924961/`
  - 3 episodes、308 alignment records。
  - `alignment_packet.status=PASS_REAL_ALIGNMENT_PACKET`。
- 次要低表現對照：`logs/teacher_real_micro_20260803_205750_137469/`。
  - 不因表現較差而刪除或排除；只用來檢查方向反轉是否為單次 run 特例。
- Simulator policy：`departure_delayed`（目前 bounded experiments 的基準 profile）。
- Simulator 診斷 seeds：`8000..8029`，共 30 episodes、每回合最多 300 steps；
  不使用已保留的 fresh reliability seeds `6000..6099`。
- Simulator 診斷環境：目前 `spike_teacher_environment_config()`，10 Hz policy、
  60 Hz physics；不在執行後調 Gate 門檻。

## 指標定義

### 1. 資料與時間完整性

- 主要 packet 必須是 `PASS_REAL_ALIGNMENT_PACKET`。
- 主要 packet 至少 3 episodes／30 records。
- 真機相鄰 observation 的 median cadence 必須落在 70–140 ms。
- Simulator policy cadence 必須落在真機 median cadence 的 ±25%。

### 2. Action-conditioned response（診斷，不單獨解鎖）

以 `observation -> next_observation` 計算 `delta_x` 與 `delta_vx`，依 LEFT、RELEASE、
RIGHT 分組。至少各 10 筆有限樣本，並報告 median／p25／p75。方向鍵的 median
`delta_vx` 必須 LEFT < 0、RIGHT > 0；Simulator 與真機方向一致。因視覺 velocity
含追蹤雜訊，數值尺度只報 ratio，不以單一尺度門檻決定通過。

### 3. 平台機制與分布

- 真機主要 packet 中，被 Teacher 選為 target 或成為 special-contact source 的平台
  kind 視為「觀測到的重要種類」。
- Simulator 必須先區分：程式是否實作該 mechanism，以及本次 Teacher 診斷分布是否
  真正啟用該 kind。
- 真機已觀測的重要 kind 若未在 Simulator 診斷分布啟用，mechanism-distribution Gate
  失敗。不可用「程式碼已經有 feature flag」視為對齊。

### 4. Support phase / aliasing

- 比較 `support_contact_active` 在 stable／rising／falling 的分布。
- `support_contact_active=true` 且 player motion=`rising`、nearest platform仍是同一
  support ID，定義為 rising-support persistence；報告筆數、連續 streak 與比例。
- 任一 support-departure timeout 或 same-support restart 必須列出 episode/step context。
- 若 rising-support persistence 直接跨越 departure max steps並導致 timeout，判為
  `SUPPORT_PHASE_ALIAS_CONFIRMED`；否則只能標記 risk，不可猜測因果。

### 5. 多餘反向操作

- directional reversal：忽略 RELEASE，LEFT/RIGHT 在不超過 3 個 raw steps內反向。
- target-conflicting directional step：target safe interval完全位於 player左／右側，
  action卻向反方向。
- support-departure overshoot：departure active時 action已把 player推離 target safe
  interval，或在同一 departure內方向反轉。
- 主要與次要 run皆報告，不因單一漂亮回合而放寬。

## Gate 與停止條件

只有以下全部成立才為 `PASS_SIMULATOR_REAL_ALIGNMENT_AUDIT`：

1. packet／時間完整性通過；
2. action response樣本充分且方向正確；
3. 真機重要平台 kinds全都在 Simulator診斷分布啟用；
4. 無 confirmed support-phase alias；
5. 主要 run無 support-departure timeout／same-support restart。

任一完整性問題：`FAIL_STOP_ALIGNMENT_AUDIT_INTEGRITY`。  
資料不足：`INSUFFICIENT_EVIDENCE_STOP_ALIGNMENT_AUDIT`。  
其他不對齊：`FAIL_STOP_SIMULATOR_REAL_ALIGNMENT`。

Gate 未通過即停止正式 Dataset v2／BC／DAgger／RL；輸出最小修正方向，但本輪不得
事後改門檻或用額外實機回合覆蓋失敗證據。
