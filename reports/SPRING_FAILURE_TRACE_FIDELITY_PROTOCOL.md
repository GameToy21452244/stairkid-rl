# Spring Failure Trace / Fidelity Audit Protocol

日期：2026-08-03  
狀態：**FROZEN BEFORE DIAGNOSTIC EXECUTION**

## 目的

Spring curriculum v0在Engineering、Reachability與spawn ratio通過後，Oracle只有
71%到第10層；29個失敗全為spring-conditioned top death。本稽核先分離三個假說：

1. provisional `spring_jump_velocity=190`與真機vertical response不一致；
2. Simulator的camera scroll／top termination語意使正常spring bounce被判死；
3. Oracle知道下一層位置，但缺少離開當前spring footprint的控制目標。

本階段只產生trace與診斷，不修改真機Teacher、不操作原版遊戲、不訓練模型。

## 資料與seed隔離

- 正式失敗10000～10099：只重播並產生逐step trace，不用來選參數或重新判Gate。
- 既有real alignment packet：
  `teacher_real_micro_20260803_205952_924961`，只讀取已保存structured observation；
  不把可見spring誤當已確認spring contact。
- Candidate development：11000～11099；最多比較3個單一假說候選。
- Untouched holdout：12000～12099；候選與參數凍結後只執行一次。
- Dataset v2 fresh reliability 6000～6099保持未使用。

## Trace欄位

每個Simulator step至少記錄seed、step、action、target floor/kind/x、player x/y/vx/vy、
top margin、deepest floor、visible platform floor/kind/bounds、events、terminal reason。
每個spring encounter另摘要首次contact、contact次數、離開spring水平footprint所需steps、
最低top margin、下一層是否到達與終局。

Real packet只量測可證明的screen-space player y/vy、spring bounds/gap、motion、action與
時間間隔；沒有`spring_contact`／`spring_bounce`事件或接觸幾何時必須標
`INSUFFICIENT_EVIDENCE`，不可用「畫面有spring」推定彈力。

## 候選規則

- Audit先於candidate實作完成。
- 每個候選只能改一個責任層：physics/top semantics或Oracle escape；不得同時改兩者。
- 優先接受不更動未校正物理、只補Oracle privileged solvability能力的最小候選；但若
  trace證明即使水平離開spring仍因單次bounce直接top death，才允許physics候選。
- 所有候選先寫失敗測試；development比較最多3個，不做無限參數搜尋。

## Candidate與holdout Gate

Development與untouched holdout都必須：

- overall reach-floor-10 >= 95%；
- 至少20個episodes出現spring contact；
- spring-contact episodes reach-floor-10 >= 90%；
- health deaths = 0；top death rate <= 5%；
- no-spring episodes不得比對應reference退化；
- action max share < 98%。

只有holdout Oracle全部PASS才准執行同一12000～12099的Baseline比較：mean floors相對
spike-only reference保留>=80%、reach-floor-3>=90%、health death=0、無collapse，且
spring-conditioned early top不得超過10%。Baseline FAIL仍會阻擋Dataset v2。

## 停止條件

- real packet不足以校正物理時，不猜值；可以先修明確的Oracle solvability缺口，但仍標
  spring physics未校正，最終實機前需最小補充證據。
- development沒有候選通過時停止並報告，不碰holdout。
- holdout或Baseline任一FAIL即停止；不得重用12000～12099調參。
- 本協議不授權Dataset、BC、DAgger、PPO、DQN、NEAT或長時間實機探索。
