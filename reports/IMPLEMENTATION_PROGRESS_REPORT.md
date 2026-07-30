# Implementation Progress Report

日期：2026-07-30

## 本次規格範圍

依 `CODEX_NS_SHAFT_PROJECT_REFACTOR_PROMPT.md`，本次只做 audit、永久上下文、
資料 schema／validator、simulator v0、Gymnasium/Pymunk 基礎環境、測試與 Colab
骨架。未開始長時間訓練，也未實作 BC、DAgger、Residual 或 DQfD trainer。

## 完成項目

### 1. Repository audit

- 讀完長期規格、AGENTS、README、handoff 與現有 training strategy。
- 檢查 git status/diff，保留原有 18 個 tracked dirty files 與 2 個 untracked
  handoff/report。
- 盤點真實 control flow、observation dimension、action、reward、
  terminal/truncated、legacy data、baseline、PPO artifact 與測試。
- 產出 `reports/PROJECT_AUDIT_REPORT.md`。

### 2. 永久上下文

新增：

- `docs/PROJECT_CONTEXT.md`
- `docs/CURRENT_STATUS.md`
- `docs/TRAINING_ROADMAP.md`
- `docs/EXPERIMENT_PROTOCOL.md`
- `docs/DATASET_SCHEMA.md`
- `docs/SIMULATOR_SPEC.md`
- `docs/LOCAL_COLAB_WORKFLOW.md`
- `docs/DECISIONS.md`
- `docs/RISK_REGISTER.md`

並擴充 `AGENTS.md`，加入每次 context 恢復順序、Go/No-Go、PPO／legacy data
禁用條件與完成後更新規則。

### 3. Dataset schema / validator

新增：

- `src/stair_agent/data/schema.py`
- `src/stair_agent/data/validator.py`
- `scripts/validate_dataset.py`
- `tests/test_data_schema.py`
- `tests/test_dataset_validator.py`

實作 strict required/unknown fields、版本、NaN/Inf、268 維、action、timestamp、
terminal continuity、episode crossing、step gap、observation jump、action collapse
與 duplicate checks。CLI 拒絕覆寫既有 output。

### 4. Simulator v0 / Gymnasium

新增：

- `src/stair_agent/simulator/{state,player,platform,generator,physics,renderer}.py`
- `src/stair_agent/envs/{shaft_env,reward}.py`
- `scripts/check_simulator.py`
- `tests/test_simulator_env.py`

特性：

- Pymunk player/platform；
- RELEASE/LEFT/RIGHT、重力、acceleration、max speed、release drag；
- normal one-way landing、bounce、bounds、scroll、floor progress、top/bottom death；
- fixed seed、None/human/rgb_array；
- 重用真實 `FeatureEncoder`／`TemporalObservationStack`，輸出 268 維；
- `check_env`、existing baseline smoke、100k headless smoke。

依賴已加入 `pyproject.toml` 與 `requirements.txt`：
`pymunk>=6.8,<8`、`pygame-ce>=2.5,<3`。

### 5. 既有半成品修復

接完 `platform_target_action_reward` constructor、component 與
`StairAgentEnv` config wiring，使開始時已存在的 5 個 failing tests 通過。
未還原或重寫其他 dirty worktree 修改。

### 6. Colab

新增 `notebooks/ns_shaft_colab.ipynb` 骨架，涵蓋 clone/install、Drive、
dummy video driver、pytest/check_env、headless smoke、1/4/8/16 sync/async
benchmark、推薦 env count、TensorBoard、checkpoint/video 與 resume。沒有任何
real executable 或 input backend 操作。

### 7. 報告

- `reports/PROJECT_AUDIT_REPORT.md`
- `reports/TRAINING_STRATEGY_REPORT_V2.md`
- `reports/IMPLEMENTATION_PROGRESS_REPORT.md`

## 驗證結果

- 初始基線：169 passed、5 failed；5 個皆為已知 target-action reward 半成品。
- 新 schema／validator tests：通過。
- simulator `check_env` 與行為 tests：通過。
- 100,000-step headless smoke：通過，約 24.4 秒（單次本機測量）。
- 最終 `python -m pytest -q`：204 passed，26.93 秒。
- `python -m compileall -q src scripts`：通過。
- notebook JSON parse：通過。
- `git diff --check`：通過；只有 Windows LF→CRLF 提示。
- `scripts/check_simulator.py --steps 10000 --baseline-steps 1000`：
  約 4,519 steps/s，check_env 與 baseline smoke 通過。

所有驗證都在 mock／headless simulator 執行，沒有尋找或操作真實遊戲。

## 尚未完成（刻意留待後續 gate）

- 新 transition writer 接到真實與 simulator step；
- legacy migration/quarantine manifest；
- 真實 physics/action/observation latency 校正；
- 正式 random／release／baseline benchmark artifact；
- Colab 實際 runtime benchmark；
- BC、DAgger、Residual、Double DQN／DQfD-lite；
- 長時間訓練或新增實機 rollout。

## 下一個建議工作包

先做「transition writer + quarantine + calibration telemetry」：

1. 讓每一 action 可靠產生符合 v1 schema 的 transition。
2. 逐檔掃描 legacy data，產出可追溯 quarantine manifest，不猜補欄位。
3. 用有限且安全的人工 telemetry 擬合 simulator v0。
4. 建立固定 seeds 的 random／release／baseline benchmark。

完成上述 gate 後，再決定是否准許短 learnability probe。

## 2026-07-30 後續進度

- 新增 `data/writer.py` 與測試；writer 拒絕覆寫、錯誤 reward 加總及 terminal
  後續寫。
- 新增 `data/migration.py`／`quarantine_legacy_data.py`；實際掃描 23 files、
  2,912 rows，全數 quarantine。
- `LiveGameAdapter` 新增 command/effective/next-observation timing，不改變既有
  foreground、F8 或 release 行為。
- 一次實機 calibration 在 56 steps／20 seconds 上限內於死亡前完成 43 步，
  validator 0 error／0 warning，未重開第二回合。
- 新增 `CALIBRATION_REPORT_V0.md`、`SIMULATOR_BENCHMARK_V0.json` 與
  `VECTOR_ENV_BENCHMARK_V0.json`。
- simulator benchmark：baseline 1.46 floors、random 0.76、RELEASE 0；
  每組 5 seeds × 20 episodes。
- 本機 vector benchmark：16 async 約 11,939 steps/s 為最高值；此建議不可
  直接外推至 Colab。
- 沒有開始 BC、DAgger、Residual、DQfD、PPO 或其他模型訓練。
- 後續完整回歸：`python -m pytest -q` 為 209 passed，27.28 秒。
- 第二次 RIGHT-first 實機校正完成 56 筆；總計 99 records，沒有開始訓練。
- 新增自動 calibration gate analyzer 與
  `CALIBRATION_PROFILE_V1.json`／`CALIBRATION_GATE_REPORT_V1.md`。
- 目前 fidelity gate 為 FAIL：clean LEFT/RIGHT 只有 15/11、非零 RELEASE 6、
  landing 2；單步 y/vy 與 10-step x/y error 也超標，30-step 尚無可用 window。
- 因最新唯讀檢查找不到可見遊戲視窗，passive calibration 安全停止於未執行；
  沒有自動啟動遊戲。

## 2026-07-30 Calibration v0.1 完成

- 累積 14 個 calibration JSONL、649 transitions；sample、一步與 landing
  classifier gates 通過，所有 calibration labels 仍為 invalid/quarantine。
- 最終一步 fitted MAE：x 3.99、y 6.83 px、vx 32.67、vy 56.17 px/s。
- landing classifier：23 events、precision 0.846、recall 0.957、
  death misclassification 0。
- 校正 simulator control dt、action impulse、release drag、screen-space
  gravity／bounce／scroll、平台尺寸／間距與水平 shift。
- 發現 exact 30-control-step pixel replay 的 partial-observability blocker；
  未使用未來平台 teacher forcing 或放寬碰撞框過關。
- v0.1 baseline fixed benchmark：100 episodes、2,490 steps、150 landings／
  floors；landing/floor rate 0.0602。
- real landing-focused：325 steps、17 landings、12 floors；
  two-proportion z 分別 −0.569／−1.698，seeded distribution gate 通過。
- Gate 僅開放短 simulator learnability probe；沒有開始 BC、DAgger、
  Residual、DQfD、PPO 或其他訓練。
- v0.1 最終完整回歸：217 passed；`check_env`、10k headless 與 1k
  baseline smoke 通過，約 3,317 headless steps/s。

## 2026-07-30 Simulator learnability P0／P1

- 新增 simulator-only 評估器，保存 floors、return、episode length、
  landing、terminal reason、action distribution 與 collapse 指標。
- P0：PPO／SB3-DQN 各 4,096 steps；held-out floors 1.00／1.05，
  random 0.70、baseline 1.65；兩者均未 collapse。
- P1：3 個 fresh train seeds，每演算法／seed 8,192 steps，20 個 held-out
  eval seeds。PPO floors 1.50／1.95／0.90，平均 1.45；SB3-DQN
  1.00／1.20／1.30，平均 1.167。
- 六個 P1 模型皆未達 98% action collapse；LEFT／RIGHT 各至少 2%。
- P1 gate 通過，但 PPO seed variance 仍大，兩者平均仍未超過 baseline。
- 依 D-010 停止本機擴訓；下一步是 Colab pipeline validation。
- P1 後完整回歸：219 passed；六個 checkpoint 已保存，抽樣 PPO／DQN
  checkpoint 可重新載入並產生合法動作。
- Colab notebook 已由註解 skeleton 升級為預設停用的 bounded pipeline
  validation：512-step PPO、checkpoint load、256-step resume、MP4 與
  `colab_pipeline_gate.json`；仍需在實際 Colab runtime 執行。
