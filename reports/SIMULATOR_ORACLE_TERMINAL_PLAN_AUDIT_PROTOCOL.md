# Simulator Oracle Terminal-Plan Incidence Audit Protocol

日期：2026-08-04
狀態：`FROZEN_BEFORE_EXECUTION`

## 問題

全域receding v7在development造成21 regressions；首次分歧類型未形成單一dominant
mechanism。此補充audit不掃commit length或score，只檢查既有planner輸出的
`predicted_terminal`能否作為窄化receding適用範圍的事件型條件。

## 固定資料與執行

- 重播已曝光16000～16099的v6 cached Oracle，保存所有route plans；
- 以formal artifact既有終局分成v6 success／top failure／bottom failure；
- 同時讀取retired 14000～14099 taxonomy中3個`search_found_no_survival`案例；
- Simulator v0.3 edge config、10 Hz、最多600 steps、目標第10層；
- 不執行v7、不讀17000～17099、不改任何程式參數。

每個episode統計是否曾有`predicted_terminal`、首次發生step／floor、terminal kind及總數。

## 預先門檻

只有以下全部成立才准提出terminal-risk-only v8：

1. v6 successful development中，terminal-plan exposure不超過5%；
2. v6 development的top failures全部有terminal-plan exposure；
3. retired taxonomy的3個`search_found_no_survival`全部有terminal-plan exposure；
4. 所有planner calls保持snapshot restoration與固定12／24 search bounds；
5. source formal artifact與seed分類完整一致。

若通過，唯一候選只能是：正常plan完全沿用v6 cache；只有新plan已預測terminal時，
暫時逐decision重規劃，直到找到non-terminal plan、離開trigger、跨層或終局。不得加入
seed特例、commit length、score margin、always-plan或擴大搜尋。

若未通過，狀態`INSUFFICIENT_EVIDENCE_STOP`，不得實作v8。所有結果只作development
diagnostic，不生成Dataset、不訓練、不操作遊戲。

