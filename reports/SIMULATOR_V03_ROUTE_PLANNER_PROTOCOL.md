# Simulator v0.3 Action-Conditioned Route Planner Protocol

日期：2026-08-03  
狀態：已執行；Oracle PASS、`FAIL_STOP_BASELINE_DEVELOPMENT`

## 問題

v5 departure commitment 將 mean deepest floor 從 8.72 提升至 8.93，並把top death
向較深樓層移動，但reach-floor-10仍48%。這表示單一步離台承諾不足以解決長期
top-pressure；下一候選必須直接比較 action sequence 的物理結果。

## 唯一候選

`oracle-full-v6-bounded-route-planner`：

- 僅供 privileged Oracle solvability Gate，不得成為 Teacher/BC label來源；
- 使用Simulator snapshot/restore，在同一套Pymunk `step()`上重播候選；
- actions固定為RELEASE／LEFT／RIGHT；
- horizon固定12 policy steps，beam width固定24；
- 觸發條件不是人工y sweep：當player top到頂刺下緣的headroom，小於
  `scroll_speed * horizon * dt`時啟用；已有plan則執行到landing、terminal或12步結束；
- 每個新support／landing重新規劃，不沿用跨landing的open-loop plan；
- 排序固定依序使用：terminal survival、相對floor progress、畫面headroom、
  deeper-platform horizontal alignment、較少action reversal；
- 不改physics、playfield、top hazard、速度、生成器、Gate seeds或門檻。

## 工程 Gate

1. snapshot→step→restore→same step的player、platform、events、floor、terminal完全相同；
2. Oracle `choose()`執行規劃後不可改動正式Simulator state或RNG；
3. 固定seed至少一個v5 top failure由planner改善，且edge invariant仍為0；
4. bounded counters證明每次規劃不超過12 depth／24 beam／3 actions。

## Formal Gate

- development：13000～13099，可作候選開發；
- Oracle reach-floor-10 >=95%、reach-floor-3 >=99%、edge violations=0、三動作有使用、
  無collapse；
- Oracle development全過才執行Baseline development；
- development全過才首次使用holdout 14000～14099；門檻沿用edge fidelity protocol；
- 任一Gate FAIL立即停止，不追加第二組horizon／beam／score、不降低門檻。

本階段不產生Dataset、不訓練模型、不啟動原版遊戲。
