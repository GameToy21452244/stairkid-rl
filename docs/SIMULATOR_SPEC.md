# Simulator Specification

## v0 已實作範圍

- Pymunk 動態矩形 player 與 sensor platform shapes；
- 離散動作 RELEASE、LEFT、RIGHT；
- 水平加速度、速度上限、release drag；
- 重力與自動 bounce；
- 從上往下 crossing 才成立的 one-way normal-platform landing；
- 左右邊界、平台向上捲動、floor index／floor_descended；
- player 離開底部或頂部時 terminated，step limit 為 truncated；
- Gymnasium fixed seed、`render_mode=None|human|rgb_array`；
- 共用 64 維 encoder + 4 幀／action history，總觀測 268 維；
- headless `check_env`、獨立 env instance、baseline smoke、100k smoke。

## 座標與步進

- Pymunk world 採 y 向上；`GameObservation`／render 轉為畫面 y 向下。
- 預設畫面 634×431；一個 simulator action 對應一個實機 control
  transition。目前由 649 筆校正資料量得中位數 125 ms，因此 v0.1 使用 8 Hz。
- 平台 collision shape 是 sensor；v0 在每步以 previous/current player bottom
  crossing、下降速度及水平 overlap 做單向 landing，避免從下方碰撞。
- landing 將垂直速度設為 bounce velocity；首次落到更深 floor 才發出
  `floor_descended`。

## Reward v0

component 為 step penalty、landing reward、floor reward、death penalty。
每步 `info.reward_components` 可重算總 reward。這是 simulator v0 專用的清楚基線；
和真實環境 reward 統一前必須先完成 calibration 與版本決策。

## 校正參數

v0.1 provisional screen-space 對應值：

- horizontal impulse acceleration：1048 px/s²（由靜止到左右第一步中位數
  −134／+128 px/s，取共用近似）；
- max horizontal speed：230 px/s；
- release drag：0.035 / control step；
- gravity：−192 px/s²（Pymunk y 軸向上；由畫面 y 二階差分估計）；
- bounce velocity：+95 px/s；
- platform scroll：+96 px/s（Pymunk 座標；畫面為 −96 px/s）；
- platform width／height／spacing：96／16／48 px。
- 相鄰平台水平 shift 上限：180 px；真實可見樣本的絕對 shift
  中位數 80.5 px、平均 90.3 px，原本由 spacing 推導的 74.4 px 上限
  會使平台明顯過度容易。

這些參數已通過 sample、one-step 與 landing gate，但不能宣稱 30-control-step
exact-pixel fidelity。該 horizon 會依賴 viewport 外的隨機平台；後續必須使用
seeded distribution fidelity gate，不得偷看未來平台來宣稱通過。

## 明確不在 v0

- spikes、spring、conveyor、flipping；
- damage／health dynamics；
- domain randomization、像素 observation、視覺噪聲；
- curriculum、多人、真實畫面重建；
- BC、DAgger、DQfD 或任何訓練器。

這些屬 v1/v2 候選，除非 `CURRENT_STATUS` 與決策記錄明確開 gate，不得提前加入。
