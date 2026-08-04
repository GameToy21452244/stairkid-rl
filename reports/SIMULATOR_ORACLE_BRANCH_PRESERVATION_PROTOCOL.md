# Simulator Oracle Branch-Preservation Frozen Protocol

版本：v1  
凍結日期：2026-08-04  
狀態：`READY_FOR_TEST_FIRST_IMPLEMENTATION`  
候選：`oracle-full-v9-terminal-branch-preserving`

## 1. 科學問題與唯一production變因

Phase 2F證明v8的成功RIGHT prefix在shared beam depth 4被剪除。此protocol只允許一個
production變因：當v6既有12-step／24-beam plan預測terminal時，分別以固定首動作
`RELEASE_ALL`、`LEFT`、`RIGHT`建立三個獨立lane；每個lane各自擁有完整beam 24。

明確凍結、不修改：Simulator physics、generator、observation、platform semantics、
`BoundedRoutePlanner._score`、completed-node selector、horizon 12、每lane beam 24、
`should_plan` trigger、normal-path planning及v6正常cache語意。

所有v6 plan未預測terminal的paths必須action-for-action與v6相同。候選不得用privileged
Oracle actions作Teacher或Dataset labels。

## 2. Cross-lane selector

每個lane winner仍由既有規則產生：在該lane的completed nodes中以
`max(node.score)`選擇。三個lane winner依`RELEASE_ALL`、`LEFT`、`RIGHT`固定順序交給
同一個既有`max(score)` selector；Python stable-first行為是唯一tie-break，不新增
survivor bonus、terminal override或新score。

在看18000 development結果前凍結的selector audit Gate：

1. 使用Phase 2F既有14個rescue trigger snapshots，不取得任何新formal evidence。
2. 三個lane皆為12-step／24-beam且從相同root snapshot開始。
3. 14/14都必須由既有selector選到RIGHT、selected winner為nonterminal／floor progress，
   且既有committed counterfactual為reach10。
4. selector與score source hash不得改變。

Audit已得到14/14 PASS；完整rows寫入protocol artifact。若後續實作需要更改selector或
score，狀態立即改為`PROTOCOL_CONFLICT`並停止。

## 3. Lane bounds與資源上限

- 每lane：horizon=12、beam_width=24。
- 不得改為共享總beam 24或8／8／8。
- 每lane theoretical expanded-node cap：`1 + 11 × 24 × 3 = 793`。
- 三lane總expanded-node cap：2,379。
- 實作必須依固定action順序逐lane執行並在lane間restore相同root。
- 結構性peak memory cap：單lane最多288個completed/beam nodes＋72個當層candidate
  nodes＋root＋3個lane winners，即不超過364個node snapshots；不得同時保留三棵tree。
- 每次branch-preserved search的wall-clock watchdog為5.0秒。超時不是fallback PASS，runner
  必須保存`INCOMPLETE`並停止formal stage。
- 每個lane都必須記錄expanded nodes、runtime、winner score、terminal reason與首動作。

Snapshot、RNG與platform object identity在每個lane後及整體search後都必須完全restore。

## 4. Empty lane、all-terminal與determinism

- Empty lane：因每個forced first action至少產生一個child，empty lane屬工程不變量違反；
  不得靜默忽略或改selector，必須`INCOMPLETE`停止。
- All-terminal：仍將三個terminal lane winners交給既有`max(score)` selector，依固定lane
  順序tie-break；選定後cache完整suffix。不得臨時加survival bonus或擴大搜尋。
- Duplicate replay：相同seed的v6與candidate各重播一次，per-seed terminal、deepest floor、
  action sequence、planning telemetry與lane selection必須完全一致。

## 5. Commit semantics

1. 仍先用v6 normal planner；只有該plan預測terminal才啟動三lane search。
2. 現有plan為nonterminal時直接cache原suffix，與v6完全一致。
3. 選定lane winner後立即cache並依序執行完整suffix，不做v7式每decision任意切lane。
4. 只有suffix執行完、Simulator instance或deepest floor改變所觸發的v6既有清除條件，
   或日後以相同凍結search證明suffix terminal時才可replan；本v1在deterministic Simulator
   不新增逐步suffix probe。
5. 不新增cooldown、hysteresis或minimum-commitment數字。
6. All-terminal也cache既有selector選出的完整suffix，不進v8逐步terminal replan。

## 6. Seed ledger與污染防護

正式分區：

- Primary development：18000～18099。
- Conditional development extension：18100～18199。
- One-time holdout：19000～19099。

Repository-wide text audit確認三組均無實際使用。17000～17099保持unused但永久禁止轉作
本候選holdout。14000、16000及所有retired／diagnostic seeds不得作本protocol正式證據。

若primary development的paired v6有至少一個top failure，只使用18000～18099完成正式
Gate。若v6 top failure為0，必須依已先凍結的條件加入18100～18199，並對完整
18000～18199共200 seeds重新計算所有aggregate與paired Gate，不得只挑extension。
若200 seeds仍無v6 top failure，判`INSUFFICIENT_EVIDENCE`並停止，不得使用holdout。

任何development FAIL、INCOMPLETE、source/protocol/ledger hash mismatch都禁止19000～19099。
Holdout只能在development全部PASS後使用一次；中止後整批退休，不得重跑。

## 7. Development Gate

Paired v6 reference與candidate都必須報reach3／5／10、mean／median／Q25／CVaR25、
bottom／top／health、safety、action distribution、switches/100 steps、direct reversals、
RELEASE-bridged reversals、branch-search count、lane distribution、compute、reproducibility及
per-seed結果。

全部必須成立：

- reach10 ≥95%。
- reach10不低於paired v6。
- v6-success regressions=0。
- bottom death不高於v6；health death=0；safety violations=0。
- 所有未暴露terminal plan的paths與v6 action-for-action相同。
- action-switches/100 steps不高於v6的1.05倍。
- duplicate replay、snapshot restore與planner bounds PASS。
- 至少一個本protocol新development中的v6 top failure被candidate修復。

任一FAIL即`FAIL_STOP_BRANCH_PRESERVATION_DEVELOPMENT`，保存artifact且禁止holdout。

## 8. Holdout Gate

Development PASS後才可將19000～19099標`used=true`並執行唯一一次paired v6/candidate：

- candidate reach10 ≥95%且不低於v6。
- bottom不高於v6、health=0、safety=0、no collapse。
- Q25與CVaR25均不低於v6。
- action-switches/100 steps≤v6×1.05。
- deterministic replay與bounds PASS。

Holdout不要求事後新增repair條件，也不得用於選版本。FAIL立即停止所有Alignment、Dataset、
Student與Colab工作。

## 9. Runner與中止語意

- Formal runner開始前寫入stage journal：started、partition、protocol/source/ledger hashes。
- Artifact採write-once；既有正式路徑存在即拒絕覆寫。
- KeyboardInterrupt、timeout、例外或不完整seed count一律寫`INCOMPLETE`與stop reason；
  不得判PASS/FAIL，且holdout維持unused。
- Development FAIL必須由runner硬性阻擋holdout。
- 不啟動遊戲、真實輸入、Dataset或training。

## 10. Protocol Review判定

Cross-lane selector 14/14 PASS、三lane可在單一變因下實作、seed ledger clean，故本protocol
判定：`READY_FOR_TEST_FIRST_IMPLEMENTATION`。

這不是candidate PASS；只有完整Engineering與新development Gate通過後才可執行holdout。
