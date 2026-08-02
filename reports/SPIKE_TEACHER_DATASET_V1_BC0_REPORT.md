# Spike Teacher Dataset v1 and BC0 Smoke Report

日期：2026-07-31

## 結論

- Spike Teacher Dataset v1：**PASS**。
- 本機 seed 0／5-epoch bounded BC0：**FAIL／STOP**。
- 未追加 epochs、未執行多初始化、DAgger、長 RL 或真實遊戲。

## 固定分區

- Dataset：2000～2059。
- Checkpoint selection：2060～2079。
- Final evaluation：2200～2219。
- 以上 partitions 執行後均視為已消耗，不得供下一模型重用。

## Dataset v1

| 指標 | 結果 |
|---|---:|
| Episodes／rows | 60／3,529 |
| Train／validation／test | 2,327／605／597 |
| RELEASE／LEFT／RIGHT | 1,328／1,092／1,109 |
| Spike-visible episodes | 36／60 |
| Spike-visible train／validation／test rows | 863／309／241 |
| Spike-target labels | 33 |
| Damage／health-gained events | 16／48 |
| Recovery-related decisions | 179 |
| Health deaths | 0 |
| Validator errors | 0 |

所有預先固定的 coverage checks 通過；每列保留
`teacher-observable-safe-platform-v2` 與 `teacher_reason` provenance，並引用
通過的 spike curriculum 與 Teacher holdout artifacts。

## BC0 smoke

候選 epochs 預先限制為 3／5，選出 epoch 5。兩個 selection candidates 都未
通過 lower-tail Gate，因此本輪只完成介面與負結果診斷。

| Final 指標 | BC0 | Baseline |
|---|---:|---:|
| Mean deepest floor | 45.50 | 49.70 |
| Deepest-floor Q25 | 7.75 | 30.00 |
| Reach floor 10 | 60% | 100% |
| Bottom deaths | 14 | 1 |
| Health deaths | 0 | 0 |

BC0 test accuracy 77.22%；spike-visible 241 rows accuracy 73.44%。Spike-target
test 只有 6 rows且 accuracy 16.67%，不足以宣稱學會緊急尖刺策略。

## 原因診斷

Final learner states 上，Teacher／BC disagreement 主要為：

- `escape_launch_platform`：40.2%；
- `move_toward_safe_platform`：55.4%；
- `move_toward_recovery_platform`：53.5%；
- `direction_change_brake`：71.9%。

結果呈雙峰：8/20 episodes 在第 10 層前落底，另有 4 episodes 達 116～118
層。平均值因少數長回合看似良好，但 Q25、reach-floor-10 與 bottom death 明確
失敗。Teacher 規則含 target lock、launch direction、direction braking 等跨步
記憶；雖然學生有四幀與 action history，現有單步 BC 與隨機 Teacher trajectory
仍不足以穩定重建這些狀態，並出現閉迴路 covariate shift。

## 下一步限制

不得用增加 epochs 掩蓋此負結果。下一個 protocol 應先：

1. 對 launch／brake／recovery／emergency branches 設 split-level 最低配額；
2. 比較明示可部署 controller-memory features、sequence BC 或 recurrent policy；
3. 以全新 seeds 重新做 selection／final；
4. 若加入 NEAT，只能作相同 simulator、相同 lower-tail Gate 的 bounded
   compact-observation baseline，不得用單次最高樓層取代成功率與死亡率。

## 驗證

- `python -m pytest -q`：298 passed in 97.85s。
- Dataset／BC0 summary JSON：可解析。
- `compileall`、notebook JSON 與 `git diff --check`：通過。
- 未開啟遊戲、未送真實輸入、未執行長訓練。
