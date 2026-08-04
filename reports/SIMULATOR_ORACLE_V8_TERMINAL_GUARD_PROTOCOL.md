# Simulator Oracle v8 Terminal-Risk Guard Protocol

日期：2026-08-04
狀態：`FROZEN_BEFORE_IMPLEMENTATION_AND_EXECUTION`

## 唯一候選

`oracle-full-v8-terminal-risk-guard`：

1. 正常route plan完整沿用v6 cached execution；
2. 只有新plan的`predicted_terminal`非null時，不快取其剩餘actions，進入terminal-risk；
3. terminal-risk期間，若原`should_plan`仍成立，每decision以原12-step／24-beam重規劃；
4. 一旦找到`predicted_terminal is None`的plan，立即恢復v6 cache；
5. 若trigger消失、跨層、simulator改變或終局，清除terminal-risk並交回原v5/v6流程；
6. 不改trigger、planner score、signature、horizon、beam、physics、generator或門檻；
7. 不加入commit length、score margin、seed特例、always-plan或extended search。

此模式只供privileged Oracle，不得進Teacher-observable、BC labels或實機控制。

## 證據來源

- v7 formal Gate：16000～16099，v6/v7 reach10為96%／76%，v7正式REJECT；
- terminal-plan audit：v6成功96回合exposure 0/96；top failures 2/2；bottom failures0/2；
  retired search-found-no-survival 3/3；所有source／bounds checks PASS；
- 17000～17099從未使用。

## Test-first Engineering Gate

- 新mode有獨立policy version，v6 cached與v7 receding不變；
- non-terminal plan的action/cache與v6完全一致；
- terminal plan只執行第一個action且不保存suffix，terminal-risk=true；
- 下一decision在trigger成立時重規劃；non-terminal plan出現後恢復cache；
- trigger消失／跨層時清除risk；snapshot/RNG/platform identity完整還原；
- 12／24 bounds、edge、support與special tests不退化；完整pytest／compileall／diff PASS。

## Gate順序

1. source artifact與terminal audit SHA／status／exposure checks全部PASS；
2. 重用已曝光development 16000～16099，不再稱未見資料；reachability必須PASS；
3. v8 development必須：reach10>=95%、reach3>=99%、0 edge violations、三動作皆使用、
   無collapse、reach10不低於v6的96%、v6成功→v8失敗為0、bottom不高於v6的2；
4. v8另須救回至少1/2個v6 top failures，否則即使數值不退化也不構成有效新版本；
5. 任一development check FAIL立即`FAIL_STOP_V8_DEVELOPMENT`，holdout保持未使用；
6. 全部PASS後才首次執行17000～17099 reachability與v8 Oracle；Oracle門檻仍為
   reach10>=95%、reach3>=99%、0 violations、全動作、無collapse；
7. Oracle holdout PASS後才執行既有observable route-intent candidate，門檻mean>=5、
   reach3>=90%、0 violations、無collapse；
8. 最終狀態只有`PASS_V8_ORACLE_AND_ROUTE_INTENT`才算本版本成功。

PASS只解鎖Simulator v0.3特殊平台逐項重驗，不直接生成Dataset或啟動Student／實機。

