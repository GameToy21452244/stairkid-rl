# Branch-Preservation Test-First Implementation Plan

日期：2026-08-04  
狀態：`READY_FOR_TEST_FIRST_IMPLEMENTATION`

## Scope

只在`BoundedRoutePlanner`加入固定首動作lane search與三lane existing-score selection，並在
`OracleFull`加入明確opt-in的`branch_preserved` execution mode。v6、v7、v8 modes保持可重現；
normal/non-terminal path不得分歧。

## Test-first順序

1. 先新增lane isolation、first-action preservation、existing selector、14 rescue triggers、
   suffix cache/execute、all-terminal fallback、restore、determinism與node cap單測，確認因API
   尚不存在而FAIL。
2. 新增runner/Gate tests：seed範圍、18000 primary／18100 conditional、19000 holdout、
   17000永遠拒絕、development FAIL阻擋holdout、interrupted artifact與telemetry。
3. 最小重構planner共用原score/signature/search；不得改任何score常數、horizon或beam。
4. 最小加入Oracle opt-in mode；terminal plan才呼叫branch-preserved search並cache完整suffix。
5. 完整pytest、compileall、diff check全PASS後，才從頭執行18000 development。

## Formal artifacts

- Development：`artifacts/simulator_oracle_branch_preservation_development_v1.json`
- Combined holdout（只有development PASS）：
  `artifacts/simulator_oracle_branch_preservation_gate_v1.json`
- Report：`reports/SIMULATOR_ORACLE_BRANCH_PRESERVATION_REPORT.md`

任何第二個production變因、test無法維持v6 normal identity或selector需要修改，立即標記
`PROTOCOL_CONFLICT`並停止。
