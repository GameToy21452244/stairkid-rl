# P3.6 Repair v5 Report

日期：2026-08-01

結論：OFFLINE PASS／REAL PENDING

專案 Gate：P3.6 FAIL／STOP

## 問題證據

repair v4 後四組真機測試共 18 回合、721 steps。13 回合 bottom death，6 回合
第一層即 bottom death，14 回合 observation invalid；mean floor 2.28、median 2。
`escape_launch_platform` 占 262 steps。最新 EP4 在單步 guard 與 persistent launch
之間反覆切換，形成 12 次快速反轉。Live sidecar 有 70 steps player missing。

## 實作

- Player detector：3×3 warm-mask close、min component height 14、min coloured pixels 12。
- Player tracker：只用最近 raw detection/velocity 做最多 2 幀 extrapolation；輸出
  `detection_source` 與 `missing_streak`，超限立即 missing，不生成無先驗 ghost。
- Wall evacuation：32 px enter、64 px exit hysteresis、0.2 s velocity lookahead、
  觸發時清除 launch/special/dwell、退出 cooldown、方向切換仍有 brake。
- Landing：launch commit cap 3、replan cooldown 2、vx projected landing safe interior。
- Edge：新增 support contact、platform ID、edge distance、aligned release streak；因舊片
  沒有連續 stationary 證據，本輪未加入風險較高的強制 edge tap。
- Runner/Gate：新增 player、wall re-entry、global/wall reversal、aligned release、
  floor-1 bottom 與 reliability metrics。

## Replay provenance

- r1：FAIL；vision max missing 3、過寬 global oscillation Gate FAIL。
- r2/r3：vision 修正後 effective missing 0；剩餘 wall-corridor burst 3。
- 稽核顯示跨樓層正常換向不應等同牆邊震盪；保留 global telemetry，以 wall-corridor
  burst、wall re-entry 與 outward action 作 blocking checks。
- r4：18 MP4、747 total frames、729 playing frames；raw player 716、tracked bridge
  13、effective missing 0、max missing 2、outward 0、wall re-entry 0、global reversals
  64、max global burst 8、max wall burst 1、aligned release max 5；全部 checks PASS。

Artifact：`artifacts/p36_repair_v5_offline_replay_r4.json`。

## 自動驗證

- Targeted：102 passed。
- 完整：350 passed in 66.51s。
- `python -m compileall -q src scripts tests`：PASS。
- Teacher Real Micro dry-run JSON：PASS，且未建立遊戲輸入 backend。
- `git diff --check`：PASS（僅有既存 LF/CRLF 提示，無 whitespace error）。

## 限制與下一步

MP4 經過壓縮，且 policy replay 使用舊軌跡，因此能拒絕明顯控制錯誤，但不能證明
raw capture detector 或新 action 的 closed-loop 結果。下一步只允許一次全新 bounded
3-episode Teacher Real Gate。新 artifact PASS 前不得進 P4.0、資料生成或訓練。
