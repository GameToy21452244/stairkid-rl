# Real-game Calibration Report v0

日期：2026-07-30

## 執行界線

- 唯一目標視窗 `NS-SHAFT`，client 634×431，開始前為前景。
- 只執行一回合；固定序列上限 56 steps／20 seconds。
- 使用既有 single-Enter reset、foreground／related-window、F8 與
  `release_all()` 安全鏈。
- 實際在死亡前完成 43 transitions，沒有開始第二回合。
- 原始檔：`logs/calibration_v1_20260730_180831_356152.jsonl`。
- `policy_source=invalid`：這是校正 telemetry，不是 expert demo。

## Validator

- records：43
- errors：0
- warnings：0
- action counts：RELEASE 28、LEFT 9、RIGHT 6
- terminated：true（最後一筆）

## 初步量測

268 維觀測中最新單幀的 velocity feature 以既有 scale 500 反正規化：

- LEFT 單步水平速度變化中位數：約 −60 px/s。
- RIGHT 單步水平速度變化中位數：約 +42.2 px/s。
- RELEASE 單步水平速度變化中位數：0 px/s；需要依「動作前速度不為零」子集
  再估 release drag，不能把大量靜止 RELEASE 混入。
- command → backend apply 完成的中位數低於目前 monotonic clock 可辨識尺度。
- backend apply → next observation 的中位數：約 94 ms。
- 事件：damage 2、health_gained 3、landed 1。

左右量測不對稱可能來自當時的角色慣性、落台、牆面、平台捲動或小樣本，不應
直接把 simulator acceleration 設成兩個不同值。下一輪應依動作前速度、motion、
牆距與 landing event 分層，再做 10–30 step rollout fit。

## 結論

這次證明新版 writer 與 timing schema 能在真實安全鏈中產生 validator-clean
transition，但樣本不足以宣稱 simulator 已校正。資料維持 quarantine；目前只可
用於估計 latency 與設計下一輪受控實驗。
