# Simulator Oracle Receding Failure Audit Protocol

日期：2026-08-04
狀態：`FROZEN_BEFORE_EXECUTION`

## 目的

正式 v7 development 在 16000～16099 只有 76% reach-floor-10，對 v6 的 96%；
配對結果為 21 regressions、1 rescue、3 both-failure、75 both-success。本 audit 只使用
已曝光 development 找 v7 退化機制，不產生新的 Gate 成功宣告，也不讀取17000～17099。

## 固定樣本

- Regression 21：16011、16012、16013、16019、16022、16028、16029、16033、16034、
  16036、16045、16054、16065、16067、16078、16079、16081、16089、16091、16093、16099。
- Rescue 1：16086。
- Both-failure 3：16002、16009、16030。
- Control 10：依seed排序取最前10個both-success，固定為16000、16001、16003、16004、
  16005、16006、16007、16008、16010、16014。

共35 seeds；每個只重播v6 cached與v7 receding，Simulator v0.3 edge config、10 Hz、
最多600 steps、目標第10層。不改controller、planner、physics或generator。

## 逐步欄位

- decision前player x/y/vx/vy、deepest／supported floor；
- action、是否當步新規劃、planning count；
- v6 decision前／後cached action count；
- 新plan的actions、predicted floor／terminal、score、expanded nodes；
- step events、step後deepest floor與terminal；
- paired first-action divergence及該步兩者decision前state是否一致；
- episode action horizontal switches與plan-first-action horizontal switches。

## 預先分類

- `cached_vs_replan_opposite`：首次分歧時v6正在執行cache、v7當步重規劃，且LEFT／RIGHT相反。
- `cached_vs_replan_release`：相同條件，但一邊為RELEASE。
- `cached_vs_replan_other`：相同條件的其他分歧。
- `fallback_or_trigger_divergence`：不是cache對replan。
- `no_divergence_before_terminal`：終局前無action分歧。

比較 regression 與 control 的首次分歧類型、v7-v6 action switch差、plan-first switch差及
bottom outcome。任何關於根因的判斷都必須由逐步artifact支持，不能只看平均。

## 決策規則

- 若至少16/21 regressions屬同一首次分歧機制，且同類在controls不超過5/10，才准提出
  一個直接處理該機制的v8。
- 若證據分裂，標記`INSUFFICIENT_EVIDENCE_STOP`，不得掃commit length／score weight。
- v8必須先另凍結protocol、test-first且只用16000 development；development PASS前
  17000 holdout保持未使用。
- 不生成Dataset、不訓練、不操作原版遊戲。
