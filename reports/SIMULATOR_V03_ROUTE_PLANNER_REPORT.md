# Simulator v0.3 Action-Conditioned Route Planner Report

日期：2026-08-03  
狀態：`FAIL_STOP_BASELINE_DEVELOPMENT`

## 結論

bounded route planner 讓 privileged Oracle 首次在實機 playfield、頂刺與完整左右離台
語意下通過 development：100 seeds 中96%到第10層、100%到第3層，0 edge invariant
violations。這證明修正後的 normal-platform Simulator 在短序列規劃下具有足夠可解性。

但 observable Baseline 只有73%到第3層，低於90%門檻，因此整體仍FAIL／STOP。
holdout未使用，不能宣稱 v0.3 已通過或開始 Teacher Dataset／Student 訓練。

## 實作

- `ShaftSimulator.capture_snapshot()`／`restore_snapshot()`保存player、platform、support、
  floor、physics accumulator、health、elapsed time與RNG。
- restore同時恢復原platform object identity；即使規劃分支發生recycle，也不污染live state。
- `BoundedRoutePlanner`固定 horizon=12、beam width=24、三個離散動作；直接重播相同
  Pymunk `step()`，沒有另造簡化物理。
- trigger由頂刺headroom與12步內平台scroll距離計算，不掃人工y門檻。
- planner只屬Oracle-full；`choose()`後live Simulator與RNG完全還原。
- `support_departures`新增ordered event-time records，保存source floor與當下clearance；
  解決同一0.1秒step內landing後再次離邊時，舊字串事件無法表達順序的問題。

## 工程與 micro-check

- snapshot→step→restore→same step的狀態與結果完全一致。
- 含platform recycle的planner `choose()`後，value state、RNG與platform object IDs不變。
- seed13009：v5在floor6 top death；v6到floor10。
- 20-seed micro-check：v5 reach10 60%，v6 95%；v6 top death 0、edge violations 0，
  唯一失敗為seed13015 floor7 bottom。
- 每次規劃固定不超過 `3 × 12 × 24 = 864` expanded-node上界。

## Formal Gate v5

Artifact：`artifacts/simulator_v03_edge_fidelity_gate_v5.json`

| Gate | 結果 | 數值 |
|---|---|---|
| Engineering／Reachability | PASS | RELEASE與100／1,000 geometry checks通過 |
| Oracle development | **PASS** | mean 10.20；reach3 100%；reach10 96%；top 3、bottom 1；0 violations |
| Baseline development | **FAIL** | mean 5.03；reach3 73%；reach10 12%；top 88；0 violations |
| Holdout 14000～14099 | UNUSED | Baseline development未過，依序停止 |

Oracle的四個未成功回合仍保留為lower-tail證據；96%只比95%門檻高1 percentage point，
不得解讀成已具充分安全餘裕。

## 停止與下一步

- 不執行holdout，不產生Dataset，不啟動BC、DAgger、PPO、DQN或NEAT。
- 不把privileged snapshot search移植成Student input或Teacher label。
- 下一個 bounded 實驗應只處理 observable Baseline：使用學生可得的player運動、
  platform safe intervals、top headroom與causal action history，建立deployable route intent；
  必須先證明不需要full state／future RNG，且先凍結同種子reliability Gate。
- 在 observable Baseline development reach3>=90%前，不得首次使用holdout。

## 驗證

- Route planner targeted tests：4 passed。
- 完整測試套件：495 passed（83.13 秒）。
- `compileall`、Gate artifact assertion 與 `git diff --check`：全部通過。
