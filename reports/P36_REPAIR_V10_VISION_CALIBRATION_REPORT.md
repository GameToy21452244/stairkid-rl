# P3.6 Repair v10 實機與視覺校正報告

日期：2026-08-03

## 結論

P3.6 仍為 **HOLD／STOP**。Repair v10 已將特殊平台內的長時間反轉、重啟與
煞車問題從第一組實機最長 14 steps／一次 replan／reversal／brake，降到第二組
最長 5 steps／全部為 0。但第二組仍因尖刺接觸前 10-step 角色偵測失聯、一次
wall re-entry 與 0/3 reach-floor-5 失敗。

使用者觀察到的「尖刺上左右為難」是真實問題，不是視覺錯覺。根因不是尖刺 escape
方向反覆，而是角色與普通平台暖色紋理合併後，detector 因 component 過寬而連續丟失
角色，controller 因安全規則連續送出 `RELEASE_ALL`。

## 實機 Gate 證據

| Run | Floors | 特殊接觸 | 最長 contact | lifecycle | Gate |
|---|---:|---:|---:|---|---|
| `20260803_010405_293428` | 3, 3, 4 | 2 spikes | 14 | restart 0、replan/reversal/brake 1、forced 1、abort 0 | FAIL：reach-5 0/3 |
| `20260803_011114_410228` | 2, 4, 4 | 1 spring＋2 spikes | 5 | restart/replan/reversal/brake/forced/abort 全 0 | FAIL：dropout、wall re-entry、reach-5 |

第二組 EP2 的 sidecar：

- steps 63～72：`observation_confidence=0`、`player_not_detected`、`RELEASE_ALL`。
- step 73：角色恢復，啟動 spikes contact 2，steps 73～77 連續 RIGHT 並離開。
- 因此真正的停滯在 contact 前；Gate v6 只統計 contact 內反轉，並未捕捉它。

Gate v7 重分類 artifact：
`artifacts/p36_repair_v10_vision_gate_v7_reclassified.json`。它測得 EP2 spikes contact 前
dropout/release 皆為 10 steps，其他 spring/spikes 只有 0～1 step。

## 根因與修復

Lossless forensic raw frames 中，角色本身仍肉眼可見，但暖色 HSV mask 連到普通平台的
水平紋理：

| Frame | 舊 component | 新角色框 | 新彩色 pixels |
|---|---|---|---:|
| step 61 | 111×34，過寬 | 24×33 | 139 |
| step 63 | 95×25，過寬 | 20×19 | 97 |
| step 68 | 95×34，過寬 | 26×27 | 148 |
| step 73 | 32×32，原可偵測 | 32×32 | 469 |

新 detector 在 HSV close 後、component dilation 前，以 1×(`player_max_width + 1`) 的
horizontal opening 取出不可能屬於角色的過長水平 run，再從 mask 扣除。它不會
放寬角色寬高或彩色 pixel 門檻，也不改變真實輸入安全鏈。

## Gate v7 語意

Gate v7 保留 v6 所有安全、lifecycle 與 lower-tail checks，另增：

- `max_pre_special_observation_dropout_streak <= 2`
- `max_pre_special_release_streak <= 2`

每個新 semantic special contact 啟動時，記錄它前一段連續 invalid observation 與
`RELEASE_ALL` 長度。這使「進入特殊接觸前已經卡住」不再被 in-contact 指標漏掉。

## 離線驗證

- 精確 4 張 EP2 forensic frames：4/4 皆可偵測角色。
- 54 張歷史 raw-dropout frames：19/19 原 recovered 幀仍可偵測；另救回
  20 張尺寸與彩色 pixels 均合法的舊 missing 幀。
- Targeted：62 passed。
- Full suite：389 passed in 61.86s。
- 未開啟遊戲、未送出按鍵、未啟動訓練。

## Go／No-Go

- **No-Go P4.0**：當前只有舊 closed-loop 軌跡與新 detector 的離線重偵測，還沒有
  fresh Gate v7。
- **Go（有界）**：使用者重新開啟遊戲並置頂後，只執行一次 3-episode Gate v7。
- **10 回合尚未放行**：3 回合全數 PASS 後才擴大到 10 回合穩定性確認。
- 任一 Gate 未過時仍禁止長 BC、DAgger、PPO、DQN、NEAT 或長時間實機訓練。

## 2026-08-03 後續勘誤

本報告上述「Gate v7 待 fresh REAL」為當時狀態。後續 fresh Gate v7
已完成，floors `2,5,2`，視覺 dropout 分支通過，但 lower-tail 未通過。
另外，generic `max_pre_special_release_streak<=2` 會把 spring 上方對齊後的
正常自由落體當成停滯，已由 Gate v8 的 dropout-specific 語意取代。

後續根因、release projection 修復、Gate v8 與 reset-focus 診斷請以
`reports/P36_GATE_V7_RELEASE_PROJECTION_DIAGNOSIS.md` 為準。P3.6 仍為 HOLD／STOP。
