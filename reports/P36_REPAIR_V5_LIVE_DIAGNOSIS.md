# P3.6 Repair v5 Live Diagnosis

日期：2026-08-01

結論：REAL GATE FAIL／STOP

診斷範圍：只分析新 artifact；本輪未修改 policy、未啟動遊戲、未訓練

## 1. 新真機結果

使用者完成兩次有界測試：

| Run | Episodes | HUD floor max | Gate 主要失敗 |
|---|---:|---|---|
| `teacher_real_micro_20260801_050522_790876` | 3 | 2／3／3 | wall re-entry 1；reach-5 0 |
| `teacher_real_micro_20260801_050608_675616` | 5 | 2／2／5／3／3 | reach-3 3/5；reach-5 1/5 |

合計 8 episodes／471 control steps，mean floor 2.875、median 3、reach-3 5/8、
reach-5 1/8、bottom death 2/8、floor-1 bottom death 0。安全面相較 repair v4
的 13/18 bottom death、6/18 floor-1 death 有明顯改善，但可靠下降深度仍未達 Gate。

新測試 observation 全部 valid，player missing 合計 12 steps，最長 streak 2；
outward wall push 0、wall-direction burst 0、physical-response timeout 0。因此本次
「不敢下平台」不能主要歸因於角色消失、撞牆保護或輸入沒有送達。

## 2. 可重現的猶豫型態

471 steps 中：

- `RELEASE_ALL` 203 steps（43.1%）。
- `aligned_*` 154 steps（32.7%）。
- `escape_launch_platform` 175 steps（37.2%）。
- `direction_change_brake` 40 steps（8.5%）。
- 37 個 RELEASE step 同時仍有 support contact，且離平台邊緣不超過 20 px。

這些類別不是互斥的 episode 統計，但逐步序列顯示固定循環：

1. 角色仍接觸來源平台。
2. `escape_launch_platform` 往邊緣移動最多 3 steps。
3. policy 重新規劃下方目標，projected x 落在目標 safe interval，得到
   `horizontal_delta=0`。
4. `aligned_with_*` 因而輸出 `RELEASE_ALL`，即使角色尚未離開來源平台。
5. 下一次 rising/falling 或落台事件重新啟動 launch；若方向改變，再插入一個
   `direction_change_brake` RELEASE。

Run 2 Episode 1 的 source platform 7 是清楚案例：step 13 aligned RELEASE；
step 14～16 LEFT launch；step 17～19 aligned RELEASE；step 20～21 RIGHT launch；
step 22 brake；step 23～24 LEFT launch；step 25 再 brake。畫面也顯示角色在同一
支撐平台上反覆靠近／離開邊緣，而不是一次完成離台。

Run 2 Episode 3 的 source platform 22：step 61～64 LEFT，step 65～67 在 edge
distance 12.5→4→4 px 時連續 aligned RELEASE，step 68 才再次 LEFT。這與使用者
所述「平台邊界特別明顯」一致。

對照圖：

- `artifacts/p36_v5_live_edge_episode01_contact_sheet.jpg`
- `artifacts/p36_v5_live_edge_episode03_contact_sheet.jpg`

## 3. 根因判定

### Primary：departure phase 與 landing phase 混用

`SafePlatformPolicy._landing()` 的 vx lookahead 是空中落點控制；只要 projected x
已在下方平台 safe interval，horizontal delta 就會變成 0。`choose()` 接著把 0
解讀為「已對準，可 RELEASE」。但 observation 同時明確顯示 support contact，代表
角色仍需先離開來源平台。相同 observation 被兩個不同控制階段以同一條規則解釋，
屬於 phase/state aliasing，不是參數單獨過大或過小。

### Secondary：launch cap 變成頻繁重規劃，而非完整離台承諾

v5 將 launch commit 限為 3 steps，成功降低長時間過衝，但 generic landed／
floor-descended event 會清除 launch 與 cooldown；真機 sidecar 中 cooldown 幾乎始終
為 0。角色仍在來源平台附近時，3-step cap 會頻繁回到 landing planner，因此安全
修正轉化為猶豫，而沒有真正的「已離台」完成條件。

### Secondary：launch 時清除 destination target

launch branch 會 `_clear_target()`，所以來源平台、下一落點與 recovery/deeper target
可在數個 step 間切換。Run 2 EP1 的 target 7／9／11／13 交替即是例子。方向切換
保護本身合理，但 target 反覆改變會讓 brake 更常出現，放大肉眼看到的停頓。

## 4. 為何舊 Gate 沒抓到

`max_aligned_release_streak` 只量「連續」aligned RELEASE；本次最大值只有 4，符合
既有 ≤5 門檻。然而真正問題是 aligned RELEASE 被 launch／brake 穿插後，在同一
support platform 上重複發生。下一版 Gate 必須增加：

- same-support departure cycle count；
- support-contact exit latency；
- 同一 support 上的 destination target switch count；
- edge-zone RELEASE ratio；
- launch 是否以 `support_lost`／明確離台事件結束，而非只因 step cap 結束。

## 5. 明日修復順序（尚未實作）

1. 先用現有 sidecar 建立 failure replay tests，固定上述兩段 step sequence。
2. 將 controller 明確分成 `ON_SUPPORT_DEPARTURE` 與 `AIRBORNE_LANDING`；有 support
   contact 時禁止單純以 landing alignment 產生 RELEASE。
3. departure latch 保存 source platform、destination target 與 direction，直到
   `support_lost` 且保持 1～2 frames，或觸發 wall/safety abort。
4. 3-step cap 改為安全重新評估點，不清除 destination intent；不得重新選回來源
   platform。
5. 保留方向 brake、wall evacuation 與 F8，不以取消安全機制換取速度。
6. 新增上述 Gate metrics；離線 replay 通過後才允許一次新的 3-episode 真機測試。

P3.6 通過前仍禁止 P4.0、dataset generation、BC、DAgger、PPO、DQN 與 NEAT。

## 6. 後續處理結果

上述明日工作已於 repair v6 完成：failure sequence regression、source/destination-
aware support-departure latch、support-lost handoff 與新 Gate 均已實作。8 支最新
MP4 的可判定 offline checks PASS，完整 357 tests PASS。狀態為 OFFLINE PASS／
REAL PENDING；詳見 `reports/P36_SUPPORT_DEPARTURE_V6_REPORT.md`。
