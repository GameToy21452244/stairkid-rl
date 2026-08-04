# Simulator v0.3 Observable Route Intent Protocol

日期：2026-08-04  
狀態：已執行；candidate development PASS、`FAIL_STOP_ORACLE_HOLDOUT`

## 問題與 development 證據

`simulator_v03_edge_fidelity_gate_v5.json` 的 observable Baseline 在
13000～13099 只有 73% 到第 3 層；27 個 early failures 全為 top death。

使用完全相同 seeds 重播 decision trace 後發現：

- Simulator 還持有來源平台 support，但 policy 已判定沒有 support：926 steps；
- 100／100 episodes 都至少發生一次；
- 27／27 個第 3 層前死亡回合都至少發生一次；
- 這些步驟主要被改判為 aligned RELEASE（420）、launch escape（277）或
  direction-change brake（88）。

真實 `PlayerTracker._nearest_platform()` 與 Simulator observation 都只會把
player AABB 與 platform AABB 仍有水平 overlap 的平台列為 nearest。現行
`SafePlatformPolicy` 又額外要求 player center 位於平台左右界內，導致角色中心剛離邊、
但身體仍重疊時，過早把 `ON_SUPPORT_DEPARTURE` 交回 airborne controller。

## 唯一候選

`teacher-observable-v5-support-extent-route-intent`：

1. `nearest_platform` 的 `vertical_gap` 在既有 contact window `0～12 px` 時，直接沿用
   tracker 已證明的 AABB overlap，視為 observable support contact；
2. 不再以 player center 是否仍落在 platform bounds 內重複縮窄 overlap；
3. 既有 source／destination／direction departure latch 必須維持到 nearest support
   穩定消失，才交回 airborne landing；
4. 不新增 Simulator state、floor index、future platform、RNG、snapshot、rollout 或
   Oracle action；輸入只限 `GameObservation` 與既有 causal controller memory；
5. 不改 physics、playfield、top hazard、generator、target score、wall guard、special
   lifecycle、控制頻率與 Gate 門檻。

本候選名稱中的 route intent 指可部署的 source→destination→exit-direction 承諾，
不是 privileged route search。

## Test-first Engineering Gate

1. 固定 regression：player center 已越過來源平台左界、AABB仍 overlap／nearest gap=0，
   support 必須保持 active；
2. 相同狀態不得切換成 aligned、launch 或一般 landing decision；
3. 真實 tracker 與 Simulator 的 nearest-platform overlap 語意各有測試；
4. 既有 support departure、wall、special、safety tests 不退化；
5. 完整 pytest、compileall、diff check 通過。

## Gate 順序與不可變門檻

1. development 仍使用已公開的 13000～13099；只允許此單一候選，不掃 margin／delay；
2. development 必須：mean deepest floor >=5、reach-floor-3 >=90%、edge violations=0、
   無 action collapse；
3. development PASS 後才首次使用 14000～14099 holdout；先跑 privileged Oracle，
   Oracle reach-floor-10 >=95%、reach-floor-3 >=99%、0 violations、三動作有使用、
   無 collapse；
4. Oracle holdout PASS 後才跑 observable candidate holdout，沿用相同 Baseline 門檻；
5. 任一 Gate FAIL 立即停止；不重跑 holdout、不放寬門檻、不追加第二個 heuristic。

本階段不生成 Dataset、不啟動 BC／DAgger／PPO／DQN／NEAT，也不操作原版遊戲。
