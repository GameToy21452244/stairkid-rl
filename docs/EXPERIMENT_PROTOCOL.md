# Experiment Protocol

## 每個實驗必填

- experiment id、git commit／dirty diff fingerprint、日期與執行平台；
- observation schema、reward version、environment config；
- policy source／初始化 checkpoint 及其 validation 狀態；
- seed 清單、train/eval 分離方式、步數／回合／時間硬上限；
- action counts、longest same-action streak、direction switches；
- floors descended、episode return、episode length、death reason、health loss；
- checkpoint、TensorBoard、影片與 summary 的保存路徑。

## 固定評估

- 開發 smoke 可用單 seed；決策比較至少 5 個固定 seeds。
- 每個候選策略至少 20 個 simulator evaluation episodes；訓練 seeds 與評估
  seeds 不重疊。
- 評估採 deterministic policy 時必須同時報 action distribution；單一動作
  比例 ≥ 98% 視為 collapse，除非環境 oracle 明確證明該策略合理。
- random、RELEASE-only、既有 `SafePlatformPolicy` 是最低比較基準。
- 報平均值、中位數、標準差、最差 seed，不只報最佳 checkpoint。

## Simulator Go gate

開始任何 learnability probe 前必須全部通過：

1. `pytest`、`check_env`、fixed-seed、rgb_array 與 100k headless smoke。
2. 1／4／8／16 env benchmark 已記錄，能選出不過度消耗 CPU／RAM 的 env count。
3. baseline 與 random benchmark 有固定 artifact。
4. reward component 總和可重算，terminated 與 truncated 分開。
5. 物理與真實 telemetry 的差異已列入 calibration report。

## Calibration fidelity gate

- LEFT／RIGHT 各至少 30 筆不靠牆、無事件干擾的 transition。
- 非零水平速度下的 RELEASE 至少 20 筆；自由落下至少 30 筆；normal landing
  至少 20 次。
- action effective → next observation latency 的 simulated error 不超過一個
  control step。
- 單步 MAE：x ≤ 6 px、y ≤ 8 px、vx ≤ 50 px/s、vy ≤ 60 px/s。
- 可觀測水平 rollout：10-step x ≤ 25 px、30-step x ≤ 60 px。
- exact screen-y 診斷仍報 10-step 30 px／30-step 70 px；若 horizon 依賴
  初始 viewport 外的隨機平台，依 D-009 不得 teacher-force 未來平台來過關，
  改用下列 seeded distribution gate。
- distribution gate 至少使用 300 real steps、1,000 simulator steps與
  100 個固定 simulator episodes；baseline landing／floor rate 各自的
  two-proportion test 必須 |z| ≤ 1.96。
- normal landing precision 與 recall 均 ≥ 0.80；top/bottom death 不得誤判。
- 未量測的項目一律算 FAIL，不可用工程 smoke 代替 fidelity gate。

## 資料 Go gate

- validator error 必須為 0；warning 必須逐項人工接受或 quarantine。
- 不允許 terminal 後 transition、episode 跨界、時間倒退、NaN／Inf 或無效動作。
- `policy_source=baseline_verified` 必須有對應人工／規則驗證紀錄。
- old PPO、legacy baseline 與 manual audit 預設為 quarantine，不能只補預設值就升格。

## 實機 protocol

- 需使用者明確輸入確認並顯示倒數。
- 開始前驗證唯一目標視窗、foreground 與遊戲 phase。
- 設定 step／episode／seconds 三種硬上限；達任一上限即停止。
- 失焦、額外相關視窗、F8、Ctrl+C、unknown phase 或例外立刻
  `release_all()`。
- 不得在自動測試或 Colab 中執行；不得自動增加回合數。

## 當前結論

工程 smoke、正式 benchmark、一步／landing calibration、v0.1 seeded
distribution gate 與 P0／P1 learnability probes 已完成。**Go**：Colab
runtime／throughput／checkpoint／resume／video pipeline validation。
本機追加 timesteps、長訓、BC、DAgger、Residual、DQfD 與新增實機 rollout
仍為 No-Go。
