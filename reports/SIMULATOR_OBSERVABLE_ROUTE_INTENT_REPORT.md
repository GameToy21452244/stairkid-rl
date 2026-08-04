# Simulator v0.3 Observable Route Intent Report

日期：2026-08-04  
狀態：`FAIL_STOP_ORACLE_HOLDOUT`

## 結論

observable route-intent 候選在 development 明顯改善：reach-floor-3 由舊 Baseline
73% 提升為 97%，mean deepest floor 由 5.03 提升為 8.26，reach-floor-10 由 12%
提升為 55%，且 0 edge invariant violations、無 action collapse。這支持原先的
support phase 根因，也通過預先固定的 development Baseline Gate。

依協議首次使用 14000～14099 holdout 時，privileged route Oracle 只有 93% 到第10層，
低於 95% 門檻。程序因此在 Oracle holdout 立即停止，沒有執行 observable candidate
holdout。不能宣稱 candidate 已通過、不能解鎖 Dataset 或 Student。

## 根因稽核

相同 development seeds 的舊 controller trace 顯示：

- Simulator 仍持有 support、policy 卻判為 airborne：926 steps；
- 100／100 episodes 受影響；
- 27／27 個第3層前 top deaths 受影響；
- 誤交接後主要決策為 aligned RELEASE 420、launch escape 277、brake 88 steps。

真實 `PlayerTracker` 與 `ShaftEnv` 的 `nearest_platform` 都已要求 player AABB 和平台
AABB 有水平 overlap。舊 policy 再要求 player center 位於平台內，會比物理 support
提早一至數步解除 source→destination→direction 承諾。

## 唯一修改

- 新增獨立 `ObservableRouteIntentPolicy`，版本
  `teacher-observable-v5-support-extent-route-intent`；
- 只有此候選沿用 tracker 的 AABB-overlap support 語意；
- 舊 `SafePlatformPolicy` 預設行為與真實遊戲 Teacher 不變，避免未過 Gate 的候選
  靜默進入實機；
- 不使用 Simulator state、future RNG、snapshot、rollout 或 Oracle actions；
- physics、target score、wall/special lifecycle、控制頻率及 Gate 門檻均未改。

## Development Candidate Gate

| 指標 | 舊 Baseline v5 artifact | Observable candidate | 門檻／結果 |
|---|---:|---:|---|
| Mean deepest floor | 5.03 | 8.26 | >=5，PASS |
| Reach floor 3 | 73% | 97% | >=90%，PASS |
| Reach floor 10 | 12% | 55% | 診斷指標 |
| Top terminal | 88 | 45 | 診斷改善 |
| Edge violations | 0 | 0 | 必須0，PASS |
| Max action share | — | 35.82% | 無collapse，PASS |

Candidate development action counts為RELEASE 2,188、LEFT 1,986、RIGHT 1,935。

## 首次 Holdout Oracle Gate

| 指標 | Oracle holdout | 門檻／結果 |
|---|---:|---|
| Mean deepest floor | 10.21 | 診斷指標 |
| Reach floor 3 | 100% | >=99%，PASS |
| Reach floor 10 | 93% | >=95%，**FAIL** |
| Terminal | target 93／bottom 4／top 3 | 診斷 |
| Edge violations | 0 | PASS |
| 三動作／collapse | 皆有使用／否 | PASS |

失敗 seeds 已退休為診斷證據：14005 floor7 bottom、14013 floor6 top、
14025 floor9 top、14057 floor3 bottom、14060 floor7 top、14061 floor9 bottom、
14065 floor7 bottom。

其中 seed14057 在 route trigger 前即 bottom；其餘失敗有些 plan 可預測跨層，最後仍
bottom，有些最後 beam 只留下 predicted top terminal。這證明目前 12-step／24-beam
Oracle 的 lower-tail 仍不足，但尚不能區分 generator 真不可達、horizon 不足或 score／
open-loop execution 問題。不可把 93% 事後四捨五入或降低門檻。

## Gate 停止

- 14000～14099 已使用並永久退出未見 holdout 身分；不得調整後重用作 final Gate。
- Observable candidate holdout **未執行**，因此 candidate 只保留為 development evidence。
- 未產生 Dataset，未啟動 BC、DAgger、PPO、DQN、NEAT，未操作原版遊戲。
- 下一個工作只能先對上述7個 retired seeds做 bounded failure taxonomy，之後另凍結
  全新 Oracle robustness protocol 與全新 seed partitions；不能直接再調 Baseline。

## Artifact 與驗證

- Formal artifact：`artifacts/simulator_observable_route_intent_gate_v1.json`
- Targeted route-intent tests：81 passed（含完整 baseline policy tests）。
- 完整 pytest：498 passed（132.51 秒）。
- `compileall`、artifact assertion、`git diff --check`：全部通過。
