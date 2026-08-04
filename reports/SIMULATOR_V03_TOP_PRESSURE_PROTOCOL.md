# Simulator v0.3 Top-Pressure Departure-Commit Protocol

日期：2026-08-03  
狀態：已執行；`FAIL_STOP_ORACLE_DEVELOPMENT`

## 前置條件

- 使用者已人工確認 `real_vs_simulator_v03_edge_departure.mp4` 的基本左右離台語意
  看起來正常，可進入下一個 bounded 階段。
- v3 formal development：mean 8.72、reach-3 100%、reach-10 48%、52 top deaths、
  edge invariant violations 0。
- holdout 14000～14099 尚未使用。

## 失敗假說

失敗 seed 13009 在 support floor 5 的 step 45～46 向右離台；step 47 因 player
進入 top-pressure，target 從 floor 6 改為 floor 8，stateless Oracle 重新計算出口並
改成 LEFT。角色在 step 50 仍與來源平台重疊，遭 top hazard 終止。

這是「離台期間重規劃造成方向反轉」問題。候選只允許：

1. 第一次取得某來源 support 時，鎖定該來源的 LEFT／RIGHT 出口方向；
2. 同一 support tenure 內，即使 top-pressure target 改變，也保持出口方向；
3. 仍保留最後一步反向煞車，但只有在煞車後預測位置仍能完整清除原邊緣時才允許；
4. `support_departed` 後立即解除鎖定，空中與下一次 landing 可重新規劃；
5. 不改 gravity、scroll、速度、playfield、top hazard、生成分布或 Gate 門檻。

## Gate 順序

1. 單元測試重現 seed 13009 的中途 target switch，候選不得反向走回來源平台。
2. 既有 support／edge invariant tests 全過。
3. development 13000～13099：reach-floor-10 >=95%、reach-floor-3 >=99%、
   invariant violations=0、三動作皆使用、無 collapse。
4. development Oracle 全過才執行 Baseline；Baseline 門檻沿用 v3 協議。
5. development 全過才首次使用 holdout 14000～14099；任一 Gate FAIL 立即停止。

本 Gate 不產生 Dataset、不訓練 Student，也不操作原版遊戲。
