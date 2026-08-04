# Spring Failure Trace / Fidelity Audit Report

日期：2026-08-03  
狀態：**PASS_DIAGNOSIS_ORACLE_ESCAPE_CANDIDATE_ALLOWED**

## 結論

正式失敗seeds 10000～10099的逐step重播證明：29個spring-conditioned top deaths
全部在第二至第四次spring contact後發生，沒有任何回合在第一次spring bounce後直接
top death。Spring失敗後動作合計RELEASE 547、LEFT 73、RIGHT 71；問題是Oracle對齊
下一層中心後留在當前spring footprint，反覆被同一spring彈起，而不是單次190 px/s
bounce本身不可存活。

既有real alignment packet共有308 records；159筆畫面可見spring、7筆Teacher target
為spring，但0筆有可確認的spring event，0筆可建立contact→vertical-response pair。
因此真機資料不足以校正190 px/s，本輪明確拒絕physics改值，只批准一個Oracle-full
spring-clearance候選。

## 證據

| 指標 | 結果 |
|---|---:|
| Simulator episodes | 100 |
| Spring episodes | 35 |
| Spring reach floor 10 | 6 |
| Spring top deaths | 29 |
| No-spring reach floor 10 | 65/65 |
| Top death最少／最多spring contacts | 2／4 |
| First-bounce direct top death | 0 |
| Real confirmed spring event pairs | 0 |

Artifact：`artifacts/spring_failure_fidelity_audit_v1.json`。本稽核未改physics、未開啟
遊戲、未生成Dataset或訓練模型。

## 決策

唯一允許候選是privileged Oracle先離開當前spring水平範圍，通過spring高度後再回到
下一層target。真機Teacher與Student不能直接複製這個privileged判斷；它們仍需各自的
observable sequence Gate。
