# Simulator Teacher Profile Gate Report

日期：2026-08-03  
狀態：**FAIL_STOP_SAME_SEED_RELIABILITY**

## 結論

Real-game Teacher 與 Simulator Teacher 已分離。真機仍使用
`SafePlatformPolicy(BaselineConfig())` 的既有預設；三個模擬器候選各自有明確且不同的
policy version。本輪只跑 simulator，沒有啟動遊戲、沒有訓練、沒有生成正式 Dataset v2。

延後普通平台離台 2 個 decision steps 明顯優於 current，但仍未達預先固定 Gate；完全
停用離台又比延後版本差。因此 support-departure 是退化來源之一，卻不是唯一根因。
依協議沒有選出候選，fresh seeds 6000～6099 完全未使用。

## 同種子 2000～2059 結果

| profile | reach floor 10 | bottom | Q25 | CVaR25 | reversal / 100 | action TV | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| current | 75.00% | 25.00% | 9.75 | 4.73 | 11.06 | 0.1079 | FAIL |
| departure delayed 2 | **81.67%** | **18.33%** | 10.00 | **6.27** | 9.06 | 0.2070 | FAIL |
| departure disabled | 76.67% | 23.33% | 10.00 | 5.73 | **8.45** | 0.2183 | FAIL |
| Frozen Dataset v1 reference | 93.33% | 6.67% | — | — | 10.14 | 0 | reference |

Gate 要求 reach >= 91.33%、bottom <= 8.67%、health death=0、action TV <= 0.10，
以及版本、source/config fingerprints與critical branch coverage。三個profile都通過
provenance、health與branch checks，但都同時失敗 reach、bottom、action TV。

延後版本相對 frozen v1 有46次success→success、10次success→bottom、3次
bottom→success、1次bottom→bottom。它比current少4個bottom，證明延後離台有實際
資訊增益，但離門檻仍有顯著差距。

## 根因定位

離台延後後，和 frozen v1 的首次 action 分歧由current的median step 1移到step 6；
這表示第一個根因已被延後。但60回合中有53回合的首次reason分歧變成：

`escape_launch_platform -> aligned_with_safe_platform`

Frozen v1共有1,692列launch escape；current、delayed、disabled分別只有545、736、
773列。延後版本的11個bottom回合尾端全部進入`no_reachable_landing`，且多數前面伴隨
direction brake、wall cooldown或visible-safe approach。這支持下一個候選根因是：
simulator中角色已開始rising/falling，但近平台contact heuristic仍把它視為supported，
因而阻止既有launch escape handoff。這是從相同seed trace做出的推論，尚不是因果證明。

Action TV在延後／停用版本反而升至0.207／0.218，主要因RELEASE增加。即使closed-loop
表現局部改善，也不能事後移除這個預先固定的資料漂移門檻；它表示新label distribution
仍和frozen v1差異過大。

## 下一個最小實驗

不再掃描更多delay數值。只以最佳的`departure_delayed`作base，加入一個Simulator-only
的support-aware launch handoff候選：角色為rising/falling、近平台仍被判contact、且存在
較深可達落點時，允許既有bounded launch escape先於generic aligned release。真機Teacher
不變。

先以單元場景證明它只處理contact／launch overlap，再用同一2000～2059 seeds比較base與
單一候選。仍沿用相同Gate；未通過就停止，不跑fresh100，不改門檻，不產生Dataset v2。

機器可讀證據：`artifacts/simulator_teacher_profile_gate_v1.json`。

## 驗證

- profile／policy／dataset related：88 passed；
- 完整 repository：449 passed in 197.56s；
- 最慢項目為既有100k headless smoke（163.06s），新增6-seed profile integration
  只占0.62s；
- `compileall`、artifact JSON parse、`git diff --check`：PASS。
