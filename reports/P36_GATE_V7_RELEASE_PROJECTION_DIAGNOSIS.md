# P3.6 Gate v7 與 Release Projection 診斷報告

日期：2026-08-03

## 結論

P3.6 仍為 **HOLD／STOP**。Fresh Gate v7 證明 Repair v10 的視覺失聯與
特殊平台 lifecycle 已明顯改善，但 floors `2,5,2` 未通過 lower-tail
門檻。逐幀分析發現主要問題不再是尖刺上猶豫，而是控制器過度
高估 RELEASE 後的水平滑行。

已將落點模型分成「可達目標的長 horizon」與「RELEASE 後的短 horizon」，
並把 Gate 升為 v8。第一次 v8 實機嘗試只完成 1/3 回合，之後在安全
重開過程中中止，所以屬於 **INVALID／INCOMPLETE**，不是新策略的有效
PASS 或 FAIL。重開焦點根因也已以保存畫面修復並完成離線驗證。

## Fresh Gate v7

Artifact：
`logs/teacher_real_micro_20260803_012857_250916/teacher_real_game_micro_gate.json`

| 指標 | 結果 |
|---|---:|
| Episodes | 3/3 |
| Floors | 2, 5, 2 |
| Mean | 3.0 |
| Median / Q25 / CVaR25 | 2 / 2 / 2 |
| Reach floor 3 | 1/3（FAIL） |
| Reach floor 5 | 1/3（PASS） |
| Terminal | bottom 3/3 |
| Invalid observation | 0 |
| Pre-special dropout max | 0 |
| Wall re-entry / outward push | 0 / 0 |
| Special contacts | 8（spring 5, spikes 3） |
| Max special contact | 4 steps |
| Same-source restart / safety abort | 0 / 0 |

保存的 lossless 視覺證據顯示 player detector 修復確實在 closed loop 生效。
Gate v7 另因 `max_pre_special_release_streak=5` 失敗，但對應畫面為角色已在
spring 上方對齊並自由落體，不是視覺失聯或無法決策。因此 v8 不再將
generic pre-special RELEASE 當作 blocking Gate，但仍保留數值供診斷。

## Release Projection 根因

舊控制器使用 0.25～0.55 秒 constant-vx 投影同時進行：

1. 目標平台是否可達。
2. 現在是否已對齊、可以 RELEASE。

這對持續按住方向鍵的第一個問題合理，但不適用於第二個問題。實機
RELEASE 有強水平阻尼，通常在下一個約 125 ms decision step 只再移 5～8 px。

- EP3 step 27：`x≈202.5`、`vx≈144`，spring safe interval `242～318`。
  舊投影 `x≈238.5` 判為已對齊而 RELEASE；實際下一幀只到約 208，錯過
  spring 左邊。新 0.05 s 投影 `x≈209.7`，正確繼續 RIGHT。
- EP1 step 38：`x≈247`、`vx≈-166.7`，target safe interval `98～173`。
  舊投影 `x≈157.4` 判為已對齊；實際只向左約 6.5 px便停止。新投影
  `x≈238.7`，正確繼續 LEFT。

修復後目標選擇仍使用長 horizon，只有最後的 RELEASE-vs-steer 判斷改用
`landing_release_projection_seconds=0.05`。凍結舊軌跡重播的 rapid reversals 由
20 降為 14、最大 burst 由 5 降為 3，wall/departure safety 仍通過。重播不能
取代 fresh closed-loop Gate。

## Gate v8 語意

- 保留 `max_pre_special_release_streak` 作 telemetry。
- Blocking 改為 `pre_special_observation_dropout_bounded` 與
  `pre_special_dropout_release_bounded`，上限都是 2 steps。
- 必須有 `landing_release_projection_seconds`、`projected_x` 與
  `horizontal_delta` telemetry。
- 舊 Gate v7 sidecar 在 v8 重分類時會因 telemetry 不存在而 FAIL，不會被
  錯認為新控制器證據。

## Fresh Gate v8 中斷與 Reset Focus 修復

Artifact：
`logs/teacher_real_micro_20260803_014454_612146/teacher_real_game_micro_gate.json`

- 只完成 EP1：floor 3、57 steps、bottom terminal。
- Invalid observation 0、pre-special dropout 0、wall/outward/restart/abort 0。
- Release projection telemetry available，38 個 decisions。
- EP2 開始前焦點安全中止，因此 1/3 episodes 不能用來估計穩定性。

保存的 `captures/diagnostic_menu_current.png` 顯示焦點在 EXIT。已新增
EXIT rect `(172,297,70,21)`，並將安全路徑固定為最多 3 次 Tab；每次都要
重新觀測，只有連續確認 START 才送 Enter。UNKNOWN 仍立即 fail closed。
觀測上限由 450/450 frames 降為 24/12 frames，避免每個焦點狀態卡約 56 秒。

## 驗證與 Gate 判定

- Targeted dialog/live/config：34 passed。
- Full suite：393 passed in 63.09s。
- `compileall` PASS。
- 保存的實機 dialog frame 離線辨識：`EXIT`。
- **No-Go P4.0**：尚無完整 fresh Gate v8。
- **Go（有界）**：下一步只執行一次新的 3-episode Gate v8。
- **10 回合尚未放行**：Gate v8 必須完整 PASS 才能擴大樣本。
- 不執行長 BC、DAgger、PPO、DQN、NEAT 或長時間真機訓練。
