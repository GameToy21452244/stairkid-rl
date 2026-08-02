# P3.6 Gate v9 Natural Teacher Micro Report

日期：2026-08-03

狀態：**3-EPISODE MICRO GATE PASS／10-EPISODE STABILITY GATE PENDING**

## 結論

最新完整自然 Teacher run 在目前 Gate v9 語意下為 **PASS**。三回合 HUD
最高樓層為 `2,9,7`，51/51 checks 通過，且 safety event、無效 observation、
blind directional action、wall re-entry、outward wall push、departure timeout
皆為 0。

這只解除 3 回合 Micro Gate，不等於 P4.0 已開始。仍有一回合只到第 2 層，
所以依既定計畫先跑獨立 10 回合穩定性 Gate；通過後才進 State-aliasing Audit，
本輪沒有啟動 BC、DAgger、PPO、DQN、NEAT 或長時間訓練。

## Focus 與資料完整性

- 使用者誤切視窗的 run：`teacher_real_micro_20260803_025855_425666`。
  Runner 正確觸發 `focus_lost_or_related_window`、立即 release all，該 run 只有
  2 回合且標記 INVALID／INCOMPLETE，不列入 Gate 通過判定。
- 替代的完整 run：`teacher_real_micro_20260803_030549_704516`。
  3/3 回合完成，沒有 focus-loss、安全事件或 observation dropout。
- MP4 HUD 重播 artifact：
  `artifacts/natural_teacher_gate_20260803_030549_floor_video_audit.json`，逐幀重播
  `2,9,7`，counter unavailable frame 為 0，狀態 PASS。

## Gate v8 唯一假失敗

原始 v8 artifact 只有 `support_edge_release_bounded` 失敗：

- generic edge RELEASE：16/57，28.07%，超過舊門檻 25%；
- same-support departure cycle：0；
- target switch：0；
- departure timeout：0；
- actionable support-aligned RELEASE：0；
- support exit：33，median 3 steps，max departure 7 steps。

逐筆 controller sidecar 顯示，16 個 RELEASE 中 15 個是
`target_platform_id == support_platform_id` 的同平台 settle；另 1 個是 spring
bounce 中的 `direction_change_brake`。它們都不是「正在嘗試離開支撐平台卻放開方向」。
因此不能用這 16 步阻擋 departure Gate，也不能直接把門檻從 25% 放寬。

## Gate v9 語意

Gate-facing edge opportunity 只有在下列任一條件成立時才計數：

- `target_platform_id != support_platform_id`；或
- `support_departure_active == true`。

所有 edge occupancy 仍以 `generic_support_edge_*` 完整保存，供診斷與回歸使用。
同一份不可變 sidecar 依 v9 重算後：

- actionable edge RELEASE：0/39，0%；
- generic edge RELEASE：16/57，28.07%；
- 51/51 checks PASS。

主要 artifact：
`artifacts/p36_teacher_real_gate_v9_reclassification_20260803_030549_v2.json`。
此修改只修 Gate 的監測語意，沒有改 `SafePlatformPolicy`、action arbitration、
輸入時序或安全機制。

## 最新 3 回合結果

| Episode | Steps | HUD max floor | Terminal | Spring contacts | Spike contacts |
|---:|---:|---:|---|---:|---:|
| 1 | 18 | 2 | bottom | 0 | 0 |
| 2 | 144 | 9 | bottom | 0 | 1 |
| 3 | 111 | 7 | top | 4 | 2 |

- mean／median／Q25／CVaR25：`6 / 7 / 4.5 / 2`；
- reach floor 3：2/3；reach floor 5：2/3；
- actions：LEFT 76、RIGHT 90、RELEASE 107，max share 39.19%；
- special contacts：7，max 9 steps，restart／safety-abort 0；
- pre-special observation dropout：0；
- floor-1 bottom death：0。

## 離線 dynamics 資訊增益

納入這次自然 run 後，strict normal rows 由 357 增至 475、held-out episodes
增至 15；自然 reverse-braking 由 LEFT/RIGHT `7/9` 增至 `11/15`。模型 one-step
x MAE 4.442 px，仍優於 carry-vx 9.110 px，2～5 step rollout 也全部較佳。

但 reverse-braking 尚未達預先固定的每側 30，因此
`shadow_model_eligible=false`、`live_deployment_approved=false`。不會用固定平台
震盪資料補門檻，也不會把候選 dynamics 接入真機 Teacher。

## 驗證與下一 Gate

- Gate targeted tests：39 passed；相關 targeted suite：61 passed；
- 完整測試：402 passed；
- `compileall`：PASS；
- 10 回合 no-input dry-run：PASS，artifact：
  `artifacts/teacher_real_game_micro_gate_v9_10episode_dry_run.json`。

下一步只允許一次受監督、硬上限的 10 回合 Gate v9。門檻不因本次 PASS 放寬：
至少 7/10 reach floor 3、至少 4/10 reach floor 5、bottom death 最多 2/10、
spring 與 spike 都需出現，且其餘 51 項安全、觀測、departure、special lifecycle
與記錄完整性 checks 全部通過。任一 blocking check 失敗即停止並回到證據分析。
