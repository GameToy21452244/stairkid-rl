# Spring Curriculum v0 Gate Protocol

日期：2026-08-03  
狀態：**FROZEN BEFORE EXECUTION**

## 目的與界線

本實驗只處理 D-071 的第一個分布缺口：讓既有 `normal + spikes` 一般生成器以
低比例產生 spring，確認它沒有破壞可達性、health safety、Oracle 可解性或既有
Baseline 表現。Spring v1 的 190 px/s 仍是 provisional mechanism value；本 Gate
不把它宣稱為真機物理校正完成。

本輪不加入 conveyor／flipping、不修改真機 Teacher、不開啟原版遊戲、不生成
Teacher Dataset v2，也不執行 BC、DAgger、PPO、DQN、NEAT 或其他長時間訓練。

## 凍結生成規格

- 基底：已通過 Gate 的 spike curriculum v0。
- policy rate：10 Hz；physics：60 Hz；distribution：`easy`。
- spike proposal：10%；傷害 5；normal heal 1。
- 前 3 層固定 normal。
- 兩個 spikes 之間必須實際出現至少 5 個 normal；spring 不算回血平台。
- spring proposal：6%。
- spring 只能在前面連續至少 3 個 normal 時生成，因此不會緊鄰 spike 或 spring。
- 每層仍恰有一個平台；本實驗不建立空白樓層。
- `spring_spawn_probability=0` 必須保持既有 spike curriculum 的 seeded 序列不變。

預期 1,000 seeds、每 seed 9 個初始平台的實現比例：spring 2%～5%，spikes
3.5%～7%。這些範圍在執行前固定，不得看結果後調整。

## Seeds 與 budgets

- Reachability smoke：9000～9099（100 seeds）。
- Reachability full：9000～9999（1,000 seeds；包含 smoke）。
- Oracle／candidate Baseline／spike-only reference：10000～10099（paired 100 seeds）。
- 每個 evaluation episode 最多 600 control steps。
- 保留的 Dataset v2 fresh reliability seeds 6000～6099不得使用。

## Gate 順序與門檻

1. **Engineering／generation**
   - config validation、fixed-seed reproducibility、feature-off equivalence通過；
   - 前3層normal、spring前3個normal、spikes間5個normal；
   - 每層一個平台，沒有空白樓層。
2. **Reachability 100**
   - geometric reachability、health safety與reproducibility全部PASS。
3. **Reachability 1,000＋spawn ratio**
   - 上述checks全部PASS；
   - realized spring ratio介於0.02與0.05；
   - realized spike ratio介於0.035與0.07。
4. **Oracle-full**
   - 至少95% episodes實際到達deepest floor 10；
   - health death為0；
   - 至少20個episodes出現`spring_contact`，證明mechanism被實際走到。
5. **Baseline retention**
   - candidate mean floors至少保留同seeds spike-only reference的80%；
   - candidate至少90% episodes實際到達deepest floor 3；
   - health death為0且沒有單動作collapse；
   - 至少20個episodes出現`spring_contact`。

任一階段失敗即以 `FAIL_STOP_*` 保存artifact並停止後續階段。科學Gate失敗是正常
實驗結果；不得以降低門檻、重用同一seeds調參或只報最高樓層改判。只有全部Gate通過，
才可另行凍結下一階段；本協議本身不授權生成Dataset v2。

## Artifact 與完整性

- 權威輸出：`artifacts/spring_curriculum_v0_gate.json`。
- 報告：`reports/SPRING_CURRICULUM_V0_REPORT.md`。
- artifact需保存完整config、seed ranges、每個Gate、evaluation summaries、source
  fingerprints及protocol SHA-256，且拒絕覆寫既有輸出。
