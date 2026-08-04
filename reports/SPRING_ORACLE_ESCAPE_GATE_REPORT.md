# Spring Oracle Escape and Baseline Gate Report

日期：2026-08-03  
最終狀態：**PASS_SPRING_ORACLE_ESCAPE_AND_BASELINE**

## 結論

`oracle-full-v2-spring-clearance`已一次通過development、untouched holdout與Baseline
三層Gate。候選只修改Oracle-full在spring上方的離台策略；spring仍為190 px/s，
Simulator physics、Teacher-observable、真機controller與安全鏈都沒有改動。

Development 11000～11099及第一次、唯一一次holdout 12000～12099均為100/100到第10層；
兩組spring-conditioned成功率也是100%，top與health death皆0。Holdout Baseline平均
15.76 floors，相對同seeds spike-only reference 15.55保留101.35%，94%到第3層，
0 health death、無collapse，spring-conditioned early top為0。

這代表spring distribution的Simulator可解性與Baseline retention已達門檻，不代表
190 px/s完成真機物理校正，也不代表真機Teacher已改良。使用者目前不需要盯畫面；
等conveyor/flipping分布與support-phase shadow Gate也完成後，再安排一次真正有資訊量的
受監督實機驗證，避免用相同畫面反覆試錯。

## 唯一候選

- policy version：`oracle-full-v2-spring-clearance`。
- 仍在last-landed spring上方時，先依下一層target選擇可行離台側。
- player body未完全離開spring bounds＋2 px前持續向外。
- 已clear但仍在spring上方時RELEASE；通過spring高度後恢復原target tracking。
- 偏好側受牆限制時改走另一個可完成clearance的方向。
- feature可關閉以bit-exact重播legacy failure；spike-only 40-seed trajectories新舊完全相同。

## Gate結果

| Gate | 結果 | 關鍵數值 |
|---|---:|---|
| Regression tests | PASS | 10007舊版floor4 top；新版floor10 target reached |
| Development Oracle | PASS | reach10 100%；spring 30/30；top 0 |
| Untouched holdout Oracle | PASS | reach10 100%；spring 29/29；top 0 |
| No-spring non-regression | PASS | development/holdout皆100% |
| Holdout Baseline retention | PASS | 15.76 vs 15.55 = 101.35% |
| Holdout Baseline reach3 | PASS | 94%，門檻90% |
| Holdout Baseline spring early top | PASS | 0/40 |
| Health／collapse | PASS | 0 health death；max action share 46.56% |

Oracle holdout mean／Q25／CVaR25 deepest floor全為10。Baseline holdout deepest-floor
Q25為8、CVaR25為3.96；完整終局top 57／bottom 43是600-step持續下樓評估的終局分布，
沒有floor<3 spring-conditioned top failure。

## Artifact與界線

- Protocol：`reports/SPRING_ORACLE_ESCAPE_CANDIDATE_PROTOCOL.md`。
- Artifact：`artifacts/spring_oracle_escape_gate_v1.json`。
- Holdout 12000～12099已使用並永久凍結，不得拿來調參。
- Dataset v2、Student、BC、DAgger、PPO、DQN、NEAT均未執行。
- 原版遊戲未開啟、未送鍵；此次PASS不授權直接開始實機或長訓。
- 驗證：spring／Oracle相關36 tests與完整 **482 tests passed in 70.32s**。

## 下一步

依D-071繼續處理尚未進一般分布的conveyor、flipping，並用既有alignment packet完成
phase-aware support ownership shadow replay。這些離線Gate都通過後，才請使用者監看
一次bounded真機驗證。
