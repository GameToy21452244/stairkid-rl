# Simulator Observation-Schema Probe Protocol

日期：2026-08-03  
狀態：**FROZEN_BEFORE_EXECUTION**

## 目的

上一輪只有2個改善、6個退化，不能用來追加phase heuristic。本輪只檢查一組
pre-decision、因果且真機可重建的schema，是否能在未參與設計的seeds分離
launch-handoff的改善與退化案例；不修改action，不訓練Student。

## 凍結資料分區

- development：7000～7199，共200 episodes；只供特徵標準化與最近鄰reference。
- validation：7200～7299，共100 episodes。
- test：7300～7399，共100 episodes，只評估一次。
- 6000～6099仍保留給未來Teacher reliability fresh Gate，本輪不得使用。
- Base固定為`departure_delayed`；counterfactual固定為已失敗的
  `departure_delayed_launch_handoff`，不搜尋delay或其他controller參數。

## 凍結特徵組

所有組別都只用decision當下可得資訊，且包含待評估的shadow action：

1. `phase_basic`：motion、screen-coordinate vx/vy、nearest gap/kind、support、
   landed/floor events、landing recency、edge、visible count與health。
2. `causal_action`：basic加上只由`action<t`重建的9維P4.1 causal action state。
3. `target_relative`：basic加上已選目標的signed offset、中心／高度／safe interval
   相對幾何與kind。
4. `combined`：basic＋causal action＋target relative。

Raw platform/track ID只可在同一decision內暫時用來把已選目標對回可見平台，輸出artifact
不得保存identity。Simulator deepest floor或physical state不得作特徵。

## 凍結分析

- Label只取counterfactual改變終局的episodes：`improved`對`regressed`；unchanged只報數量。
- development作reference；validation/test都只查development的5-NN。
- development本身使用leave-one-seed-out。
- 連續特徵的mean/std只由development changed rows估計。
- 主要指標為balanced accuracy與nearest-neighbor opposite-outcome rate。

## Gate

下列全部通過才是`PASS_OBSERVATION_SCHEMA_PROBE`：

- 400/400 episodes都有首次action divergence，且所有deployable欄位完整有限；
- changed outcomes至少40，其中improved與regressed各至少10；
- validation/test各至少8個changed outcomes且兩類各至少2個；
- combined在validation及test的balanced accuracy都至少0.65；
- combined相對phase_basic在validation及test都至少改善0.10；
- test的opposite-neighbor rate相對phase_basic至少下降0.10；
- artifact不含raw identity或privileged feature。

任一證據量條件失敗：`INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE`。證據量足夠但
held-out分離失敗：`FAIL_STOP_SCHEMA_NOT_SEPARABLE`。兩者都禁止新增Teacher rule、
fresh100、Dataset v2或Student訓練。
