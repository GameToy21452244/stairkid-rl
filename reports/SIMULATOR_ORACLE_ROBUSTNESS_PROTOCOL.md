# Simulator v0.3 Oracle Robustness Protocol

日期：2026-08-04
狀態：`FROZEN_BEFORE_IMPLEMENTATION_AND_EXECUTION`

## 問題與唯一候選

第一次 Oracle v6 holdout（14000～14099）只有 93% 到第 10 層。失敗 taxonomy 在
預先固定的反事實中發現，保留原 trigger 但每 decision 重算 plan 可救回 4/7；
always-plan 與放大搜尋皆 0/7。14000～14099 已永久退休，不得再作 Gate。

唯一允許候選為 `oracle-full-v7-receding-route-planner`：

1. 保留 v6 的 `BoundedRoutePlanner`、`should_plan`、12-step horizon、24 beam、score、
   signature 與三動作空間；
2. trigger 未成立時仍由原 Oracle v5 邏輯決策；
3. trigger 成立時建立 plan，只執行第一個 action；下一個 control decision 不沿用快取，
   重新看當下 simulator state；
4. 不加入 always-plan、extended search、事後 seed 特例或 score tuning；
5. 只屬 privileged solvability Oracle，不得成為 BC label、Teacher input 或實機策略。

## Test-first Gate

實作前／後必須有以下固定測試：

- planner plan 完整 restore state、RNG 與 platform object identity；
- trigger 未成立時 v7 與 v5 fallback action 完全一致；
- trigger 成立時 v7 action 等於當下 plan 第一個 action，且不保存其餘 actions；
- 下一 decision 會重算 plan，而不是消耗舊快取；
- horizon=12、beam=24、單次 expanded nodes <=864；
- 既有 support departure／edge invariant／special platform tests 不退化；
- 完整 pytest、compileall、artifact JSON 與 `git diff --check` 通過。

## 全新 seed partitions

Repository 及文件稽核未發現以下範圍曾用於實驗。它們在本 protocol 凍結後才取得
正式身分：

- Development：16000～16099，可重播作工程診斷，但不可改門檻或新增候選。
- One-time holdout：17000～17099；development 全部 PASS 前不得執行。

13000～14099 為舊 development／holdout／diagnostic 範圍；不得混入新結論。

## Gate 順序與固定門檻

1. **Source integrity**：taxonomy artifact 必須為 `EVIDENCE_OPEN_LOOP_PRIMARY`、7/7
   v6 failures 重現、snapshot restoration 與 search bounds 全 PASS。
2. **Development reachability**：16000～16099 的 generator reachability、health safety、
   reproducibility 必須全部 PASS。
3. **Development reference**：同一批 seeds 跑 v6，只作同批非劣性參考，不用它調參。
4. **Development v7 Oracle**：reach-floor-10 >=95%、reach-floor-3 >=99%、edge
   violations=0、三動作皆使用、無 collapse，且 reach-floor-10 不低於 v6 reference。
5. 任一 development check FAIL，立即標記 `FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT`；
   17000～17099 必須保持未使用。
6. **One-time holdout integrity**：只在前項全部 PASS 後，執行 17000～17099 靜態
   reachability；必須全部 PASS。
7. **One-time holdout v7 Oracle**：相同 Oracle 絕對門檻；不在 holdout 跑 v6 對照。
8. Oracle holdout FAIL 即 `FAIL_STOP_ORACLE_ROBUSTNESS_HOLDOUT`，停止且永久退休 seeds。
9. Oracle holdout PASS 後，才可在相同 holdout 首次評估已凍結的
   `teacher-observable-v5-support-extent-route-intent`：mean deepest >=5、
   reach-floor-3 >=90%、edge violations=0、無 collapse。
10. Observable candidate 未通過即 `FAIL_STOP_ROUTE_INTENT_HOLDOUT`；通過才是
    `PASS_ORACLE_ROBUSTNESS_AND_ROUTE_INTENT`。

任何 PASS 都只解鎖 Simulator v0.3 特殊平台逐項重驗，不直接解鎖 Dataset 或 Student。

## 明確禁止

- 不重跑、重命名或挑選 14000～14099；
- 不降低 95%／99%／90% 門檻；
- 不掃 trigger、horizon、beam、score 或 seed；
- 不把 taxonomy 4/7 當成正式成功率；
- 不執行 BC、DAgger、PPO、DQN、NEAT、Dataset generation 或真實遊戲。
