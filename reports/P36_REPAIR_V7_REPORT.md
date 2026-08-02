# P3.6 Repair v7 Report

日期：2026-08-02

狀態：**OFFLINE PASS／FRESH REAL PENDING；P3.6 HOLD／STOP**

## 1. 觸發證據

Gate v2 之後的兩次全新三回合實機結果都沒有通過：

| run | floors | mean／median | terminal | blocking checks |
|---|---:|---:|---|---|
| `teacher_real_micro_20260801_235528_366116` | 1／4／1 | 2.0／1.0 | bottom 3 | floor-1 bottom、reach-3、reach-5 |
| `teacher_real_micro_20260801_235558_287295` | 7／5／2 | 4.67／5.0 | top 2、bottom 1 | wall re-entry 3 |

六回合合併 floors 為 `1,4,1,7,5,2`，mean 3.33、median 3，reach-3 為
3/6、reach-5 為 2/6、bottom 4/6。第二個 run 的 departure lifecycle 仍健康：
50 次 support exit、median 4 steps、max 7，restart／target switch／timeout／
actionable support RELEASE 全為 0。

使用者另觀察到普通平台短暫停頓後被上方尖刺夾死。Sidecar 對應序列顯示：頂部
壓力期間 player observation 連續失效時，v6 會持續輸出 RELEASE。這不屬於
support-departure 失效，而是「危險狀態下的 perception dropout」分支。

牆邊 sidecar 則顯示撤離成功後，cooldown 把舊目標要求的 outward action 改成
RELEASE；舊 special／launch 方向接著恢復，角色又回到同一側牆，形成 3 次 re-entry。

## 2. Repair v7

### 2.1 Wall cooldown 保持向內撤離

- wall evacuation 安全離開後，若 planner 在 4-step cooldown 內再次要求向原牆移動，
  controller 改為持續短暫向內，而不是 RELEASE 等待舊動量回牆。
- 仍保留 playfield guard、hysteresis、velocity lookahead、brake 與所有輸入安全機制。

### 2.2 Top-pressure bounded dropout bridge

- 新增可部署記憶：top-pressure active、最後實際安全方向、剩餘記憶、dropout steps、
  exhausted 與 same-support settle steps。
- 只有最後一個可靠 player observation 位於 `y <= 140` 的頂部危險區，且 policy
  已實際輸出 LEFT／RIGHT 時，後續漏偵測才可延續相同方向。
- 延續硬上限為 2 control steps；第 3 step 立即 RELEASE，reason 為
  `top_pressure_dropout_exhausted`。一般區域的 player missing 仍立即 RELEASE。
- 頂部危險且 target 等於目前 support 時，same-support settle 最多 2 steps，之後
  啟動可觀測的 edge escape，避免使用一般 4-step dwell 門檻等待過久。

### 2.3 Gate v3

Gate 不把經批准的兩步橋接混入 blind action，而是分別記錄：

- `top_pressure_dropout_continue_count`；
- `max_top_pressure_dropout_continue_streak`，必須 `<= 2`；
- `top_pressure_dropout_exhausted_count`，必須為 0；
- `top_pressure_support_escape_count`。

任何其他零 confidence 下的方向鍵仍算 blind directional action 並阻擋 Gate。這不是
放寬視覺安全，而是把一個明確、有限且可稽核的 emergency action 與任意盲走分離。

## 3. 驗證

- test-first regression：牆邊 cooldown、頂部兩步 bridge、一般 missing RELEASE、
  top-pressure same-support escape 全部 PASS。
- Gate tracker tests：approved bridge 與 blind action 分類、bridge 超限／耗盡 Gate
  均已覆蓋。
- 完整 `pytest -q`：**369 passed in 57.61s**。
- `python -m compileall -q src scripts tests`：PASS。
- Gate v3 no-input dry-run：PASS；沒有尋找遊戲、載入 input backend 或送鍵。
- 最近 7／5／2 三支 MP4 的 current-policy counterfactual replay：351 playing
  frames、outward 0、wall re-entry 0、same-support cycle 0、target switch 0；offline
  checks PASS。Artifact：`artifacts/p36_repair_v7_offline_replay_r1.json`。

壓縮 MP4 重播無法把新 action 寫回遊戲物理，因此不能證明 closed-loop 死亡率改善；
尤其 top-pressure bridge 必須由 fresh raw sidecar 才能驗證。離線 PASS 不等於 REAL PASS。

## 4. Gate 與下一步

P3.6 目前仍 **HOLD／STOP**，不得進入 P4.0、S0～S3、資料生成或長訓練。下一個
唯一允許的實驗是使用者監督的一次 bounded 3-episode Gate v3。除了既有安全、
reach、lower-tail、departure 與 wall checks，還必須同時符合：

- wall re-entry cycle = 0；
- top-pressure continuation streak <= 2；
- top-pressure dropout exhausted = 0；
- floor-1 bottom death = 0；
- 至少 2/3 reach floor 3，至少 1/3 reach floor 5。

若 Gate v3 未通過，立即停在 P3.6，依新 sidecar／MP4 分支診斷，不連續重跑直到
碰巧取得好成績。
