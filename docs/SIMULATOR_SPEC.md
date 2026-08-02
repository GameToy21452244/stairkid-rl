# Simulator Specification

## Sequence-control 對齊限制

Simulator v0.2 已足以作 sequence representation 實驗，但尚未證明 Teacher 能轉移
到原版遊戲。P3.6 必須先比較真實畫面的 observation confidence、target tracking、
action latency、loop frequency 與 failure taxonomy。輸送帶 ±80 px/s、彈簧
190 px/s、翻板 1/1 秒仍是 provisional；Teacher Real Gate 未通過時，優先修正
視覺／延遲／tracking／controller memory 或 fidelity，不得靠 Student 長訓補償。

## v0.2 已實作

- fixed 60 Hz physics substeps，policy 可選 8／10／12 Hz；
- 平台持續生成與回收，序列由 seed 完全重現；
- `easy`／`calibrated`／可選 `hard` 分布；
- easy 每個生成點至少一個具安全 margin 的可達候選，並檢查未來 2～3 層；
- Reachability、Oracle-full、Baseline 使用分離 gate；
- failure taxonomy、diagnostic overlay 及特殊平台 feature flags（預設全關）。

Oracle-full 可使用完整 state 與短 rollout，只驗證可解性。Teacher-observable
只能使用與學生相同的 structured observation／允許歷史，並在動作近似等價時
輸出 soft target 與 confidence；兩者不可共用特權輸入。

2026-07-30 gates：100／1,000 easy seeds reachability、Oracle-full 與 Baseline
皆通過。10 Hz baseline 在相同 seeds 平均 34.68 層，優於 8 Hz 的 29.75 與
12 Hz 的 33.48；因此 simulator teacher 使用 10 Hz，真實遊戲仍維持約 8 Hz。

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

## 特殊平台 curriculum

- spikes、spring、conveyor、flipping；
- damage／health dynamics；
- domain randomization、像素 observation、視覺噪聲；
- curriculum、多人、真實畫面重建；
- BC、DAgger、DQfD 或任何訓練器。

先建立關閉狀態的 feature flags。基本 BC0／DAgger0 通過後才依序啟用：
血量＋普通平台回血、尖刺、輸送帶、彈簧、翻板。每一項需 fixed-seed、
unit/render/oracle 與 calibration-interface tests，不得一次混入訓練分布。

### Health＋normal heal v1

- `enable_health=false` 預設關閉；
- max／initial／normal heal 預設 12／12／1 segments；
- normal landing 只在未滿血時發出 `health_gained` 與正 delta；
- reward component 預設 0，不改變既有 easy reward；
- feature-on version：`ns-shaft-sim-v0.2+health-v1`；
- 100 fixed Oracle landing 與 100-seed feature equivalence gates 通過。

Health-v1 目前只是機制 gate，尚未混入 teacher dataset 或模型訓練。

### Spikes v1

- `enable_spikes=false` 預設關閉，且必須搭配 health；
- 每次有效 landing 預設 damage 5 segments；
- health 歸零以 `health_depleted` 終止；
- spikes 不觸發 normal heal；
- damage／death events 與 reward components 可重算；
- 同層 normal alternative 存在時 Oracle 優先避開 spikes；
- feature-on version：`ns-shaft-sim-v0.2+health-v1+spikes-v1`；
- non-lethal／lethal／normal-heal／Oracle 各 100 fixed seeds 及
  100-seed no-spawn equivalence 全通過。

Spikes-v1 尚未加入一般 generator、teacher dataset 或模型訓練。

### Conveyor v1

- `enable_conveyor=false` 預設關閉；
- platform kind 分為 `conveyor_left`／`conveyor_right`；
- 有效 landing 依方向施加暫定 ±80 px/s 水平速度增量，並受既有
  `max_horizontal_speed` 限制；
- 發出 `conveyor_contact` 與方向事件，`info` 保存實際速度增量；
- 左右方向以不同顏色 renderer 呈現；
- 同層 normal alternative 存在時 Oracle 優先普通平台；
- feature-on version：`ns-shaft-sim-v0.2+conveyor-v1`；
- 左／右速度與 Oracle 各 100 fixed seeds，以及 100-seed no-spawn
  equivalence 全通過。

80 px/s 是未經真實輸送帶 telemetry 校正的 provisional mechanism value。
Conveyor-v1 尚未加入一般 generator、teacher dataset 或模型訓練。

### Spring v1

- `enable_spring=false` 預設關閉；
- platform kind 為 `spring`；
- 有效 landing 將垂直速度設為暫定 190 px/s，一般平台為 95 px/s；
- 發出 `spring_contact`、`spring_bounce`，`info` 保存實際速度增量；
- spring renderer 使用獨立橘色；
- 同層 normal alternative 存在時 Oracle 優先普通平台；
- feature-on version：`ns-shaft-sim-v0.2+spring-v1`；
- stronger-bounce 與 Oracle 各 100 fixed seeds，以及 100-seed no-spawn
  equivalence 全通過。

190 px/s 是未經真實 spring telemetry 校正的 provisional mechanism value。
Spring-v1 尚未加入一般 generator、teacher dataset 或模型訓練。

### Flipping v1

- `enable_flipping=false` 預設關閉；
- platform kind 為 `flipping`；
- 暫定同步週期為 active 1.0 秒／inactive 1.0 秒；
- active 時可碰撞，inactive 時 player 直接穿過；
- observation/info 暴露當下 `active`，renderer 以青色／灰色區分；
- Oracle 不把 inactive 翻板列為候選，同層 normal alternative 優先；
- feature-on version：`ns-shaft-sim-v0.2+flipping-v1`；
- active collision、inactive passthrough、Oracle 各 100 fixed seeds，以及
  100-seed no-spawn equivalence 全通過。

1／1 秒同步週期是未經真實 flipping telemetry 校正的 provisional mechanism。
Flipping-v1 尚未加入一般 generator、teacher dataset 或模型訓練。

### Spike curriculum generator v0

- 首個進入一般 generator 的特殊平台只有 spikes；
- proposal probability 10%，前 3 層固定 normal；
- 任兩個 spikes 之間至少 5 個 normal，對應 damage 5／heal 1 的完整恢復；
- feature/version：`health-v1+spikes-v1+spike-curriculum-v0`；
- 1,000 initial seeds 實現 spike ratio 5.11%，幾何與 health reachability
  皆 100%；
- Oracle 100/100 到第 10 層且 0 health death；
- baseline 平均 33.07 floors，保留 plain easy 34.68 的 95.36%，
  99% 到第 3 層且 0 health death。

只有 spike curriculum v0 通過 mixed-distribution 前置 gate；conveyor、
spring、flipping 仍未加入 generator。
