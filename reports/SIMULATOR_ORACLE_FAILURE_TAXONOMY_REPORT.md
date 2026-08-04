# Simulator Oracle Failure Taxonomy Report

日期：2026-08-04
狀態：`EVIDENCE_OPEN_LOOP_PRIMARY`

> 後續正式結果：v7在全新16000～16099 development只有76% reach-floor-10，低於
> v6的96%，已於`SIMULATOR_ORACLE_ROBUSTNESS_REPORT.md`正式REJECT。本報告只保留為
> retired failures的mechanism diagnostic，不再構成候選批准。

## 結論

Oracle-full v6 的第一次正式 holdout 失敗可以完整重現，且現有 generator checker
認定 14000～14099 全部可達、health-safe、seed-reproducible。7 個失敗不是「每層沒有
平台」或靜態 generator 已知不可達造成。

在執行前凍結的四個反事實中，唯一改善的是：保留原本的 route trigger 與
12-step／24-beam 搜尋，但每一步只執行 plan 第一個 action，下一 decision 重新依新狀態
規劃。它救回 4/7 個已退休失敗案例。每一步都規劃反而 0/7；把搜尋放大到
24-step／96-beam 也為 0/7。因此主要證據支持 **open-loop cached plan execution**，
不支持「越早規劃越好」或「只要加大 beam/horizon」。

仍有 3/7 未被最小候選救回，不能宣稱 Oracle 已修好。它們必須保留為 retired
diagnostic evidence；正式泛化只能由全新 development／holdout seeds 判定。

## 固定結果

| Mode | Reach floor 10 | Mean deepest | Terminal | Plan calls | Expanded nodes |
|---|---:|---:|---|---:|---:|
| current v6 | 0/7 | 6.86 | bottom 4／top 3 | 17 | 4,956 |
| receding＋current trigger | 4/7 | 8.71 | target 4／bottom 2／top 1 | 109 | 26,457 |
| always receding | 0/7 | 7.71 | bottom 7 | 288 | 61,473 |
| extended always receding | 0/7 | 7.29 | bottom 7 | 240 | 157,092 |

所有 planner 呼叫均完整 restore simulator snapshot；最大單次 expanded nodes 分別為
672、645、687、3,069，皆在預先固定的上限內。

## 逐案例分類

| Seed | Current phenotype | Current | Receding current-trigger | Attribution |
|---:|---|---|---|---|
| 14005 | post-plan bottom | floor 7 bottom | floor 12 target | open-loop execution |
| 14013 | search found no survival | floor 6 top | floor 12 target | open-loop execution |
| 14025 | search found no survival | floor 9 top | floor 10 target | open-loop execution |
| 14057 | pre-trigger bottom | floor 3 bottom | floor 3 bottom | unresolved |
| 14060 | search found no survival | floor 7 top | floor 7 top | unresolved |
| 14061 | post-plan bottom | floor 9 bottom | floor 13 target | open-loop execution |
| 14065 | post-plan bottom | floor 7 bottom | floor 4 bottom | unresolved |

Phenotype 總數為 post-plan bottom 3、search-found-no-survival 3、pre-trigger bottom 1；
counterfactual attribution 為 open-loop 4、unresolved 3。

## 解讀限制

- 這 7 個案例是看過正式結果後建立的診斷集，只能找機制，不能估計泛化成功率。
- `always_receding` 的退化表示「每一步都規劃」會在安全 headroom 下干擾原本 Oracle；
  production 候選不得採此模式。
- extended 模式運算量約為 current v6 的 31.7 倍，仍未救回任何案例；不批准擴大搜尋。
- 靜態 reachability 只證 generator 的幾何／health checker PASS，不證某個 controller
  一定能在動態 top/bottom hazard 下通關。
- 3 個 unresolved 案例不能用事後 score tuning 消除；必須由新 Gate 的 lower-tail
  結果判斷候選是否足夠穩健。

## 決策

批准唯一 production 候選：`oracle-full-v7-receding-route-planner`。它只把 v6 的
route-plan 執行從整段快取改為「原 trigger 觸發時，每個 control decision 重新規劃並
只執行第一個 action」；不改 trigger、horizon、beam、score、physics、generator、
Simulator observation 或門檻。

本報告不批准直接修改後重跑 14000～14099，也不解鎖 Dataset、Student 或實機。
下一步必須先依 `SIMULATOR_ORACLE_ROBUSTNESS_PROTOCOL.md` test-first 實作，再用
16000～16099 development；只有 development PASS 才能首次使用 17000～17099 holdout。

## Artifact

- `artifacts/simulator_oracle_failure_taxonomy_v1.json`
- `reports/SIMULATOR_ORACLE_FAILURE_TAXONOMY_PROTOCOL.md`
