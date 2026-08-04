# Simulator Teacher Launch-Handoff Gate Report

日期：2026-08-03  
狀態：**FAIL_STOP_LAUNCH_HANDOFF_SAME_SEED**

## 結論

Delayed2 base 已從前一個artifact完整重現：trace SHA-256、所有summary metrics與60個
per-seed floors完全一致。唯一新候選只在Simulator profile啟用support-aware launch
handoff；真機與legacy default均未改變。

候選明顯退化，因此同種子Gate FAIL，fresh6000～6099沒有使用。這否定了「只要在
contact＋rising/falling時優先launch escape」這個過度簡化假說。下一步不再修改控制器，
先做decision-level phase observability audit。

## 2000～2059 結果

| 指標 | delayed2 base | launch-handoff candidate | 變化 |
|---|---:|---:|---:|
| reach floor 10 | 81.67% | 75.00% | -6.67 pp |
| bottom death | 18.33% | 25.00% | +6.67 pp |
| mean deepest | 9.22 | 8.95 | -0.27 |
| Q25 | 10.00 | 9.50 | -0.50 |
| CVaR25 | 6.27 | 4.20 | -2.07 |
| reversal / 100 | 9.06 | 10.36 | +1.30 |
| action TV vs frozen v1 | 0.2070 | 0.1231 | 改善但仍FAIL |

候選相對base有43次success→success、6次success→bottom、2次bottom→success、9次
bottom→bottom。退化seeds為`2014, 2016, 2031, 2035, 2045, 2053`；改善seeds只有
`2044, 2047`。這不是小幅隨機差異，而是lower-tail、bottom與oscillation同方向惡化。

## 為何原假說不成立

Base到候選的首次action分歧median為step6，符合前一輪定位；但候選將：

- launch escape rows由736增至991；
- support departure rows由117降為0；
- wall guard inward＋cooldown由223增至314；
- special escape rows由99降至49；
- no-reachable rows由36降至26，bottom卻由11增至15。

60回合首次reason分歧主要是38次`aligned -> launch`與18次aligned後直接進wall guard。
因handoff位於support-departure之前，它實際上完全吃掉了離台phase，並把更多軌跡推向
牆邊。即使action TV與launch row count更接近frozen v1，closed-loop可靠度反而更差。
因此「branch數量相似」不能當作時序或因果對齊證據。

Candidate相對frozen v1的首次reason仍有25次`escape_launch -> aligned`與25次
`escape_launch -> direction brake`；它沒有重建舊Teacher的phase timing，只是把另一批
aligned狀態改成edge escape。

## 下一個允許工作

下一步只做觀測／phase audit，不新增控制heuristic：在delayed2 base的同60 seeds記錄
decision前的landed/floor-descended events、motion、vy、nearest gap、player/platform
geometry、target與support判定；privileged simulator的last landed floor只作診斷標籤，
不得進Teacher input。

Audit需區分post-bounce launch、airborne near-platform overlap與真正新landing，並比較
成功／bottom episodes。只有deployable observable features能穩定分離phase，才允許再
提出一個單一候選；若不能分離，應升級observation/schema，而不是繼續堆規則。

本輪沒有訓練、沒有正式Dataset v2、沒有真機操作。機器可讀證據：
`artifacts/simulator_teacher_launch_handoff_gate_v1.json`。

## 驗證

- handoff／profile／policy／dataset related：90 passed；
- 完整 repository：451 passed in 174.77s；
- `compileall`、artifact JSON parse、source fingerprint、`git diff --check`：PASS。
