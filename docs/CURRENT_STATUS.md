# Current Status

最後更新：2026-07-30

## 已完成

- 完成 repository、真實控制鏈、觀測／reward、資料、baseline、PPO artifact
  與測試稽核。
- 建立永久上下文、roadmap、實驗 protocol、schema、simulator、workflow、
  decisions 與 risk register。
- 建立 `ns-shaft-transition-v1` dataclass、JSONL validator 與 CLI。
- 建立 Gymnasium/Pymunk simulator v0：
  RELEASE／LEFT／RIGHT、重力、水平加速度／限速、release drag、單向落台反彈、
  邊界、捲動、樓層下降、上下死亡、固定 seed、human／rgb_array render。
- 模擬器重用真實環境的 64 維 `FeatureEncoder` 與 4 幀／動作歷史，
  輸出相容的 268 維觀測。
- 已有 schema／validator／simulator 測試、Gymnasium `check_env`、
  baseline smoke 與 100,000-step headless smoke。
- 修完交接中已知的 `platform_target_action_reward` 半成品測試。
- 建立 Colab pipeline validation notebook；包含預設停用的 768-step
  checkpoint save/load/resume 與 MP4 驗證，尚未在 Colab runtime 執行。
- 建立新版 `TransitionJsonlWriter`，並在一次受限實機 calibration 中完成
  43 筆 transition；validator 0 error／0 warning，資料明確標為 `invalid`。
- 第二次 RIGHT-first 校正完成 56 筆；兩批合計 99 筆、81 筆無事件 clean
  transitions。兩個檔案各自 validator-clean。
- legacy quarantine manifest 已掃描 23 個 JSONL、2,912 筆，沒有任何檔案被
  升格為 BC 或 DQN 資料。
- simulator 固定評估完成：每策略 5 seeds × 20 episodes；baseline 平均 1.46
  層、random 0.76、RELEASE 0。
- 本機 vector benchmark 完成；最高 throughput 為 16 async envs，約
  11,939 steps/s。Colab 必須另行重測。
- 完成 14 個 calibration JSONL、649 transitions；所有檔案維持
  `policy_source=invalid`，只作物理校正。R14 的 LEFT／RIGHT／RELEASE／
  free-motion／landing sample gates 全部通過。
- 一步 fitted MAE 為 x 3.99 px、y 6.83 px、vx 32.67 px/s、vy
  56.17 px/s；landing classifier precision 0.846、recall 0.957、
  death misclassification 0。
- simulator v0.1 已套用 125 ms control step、action impulse、release、
  gravity、bounce、scroll、平台尺寸／間距及水平 shift 校正值。
- v0.1 固定 benchmark 完成；baseline 100 episodes、2,490 steps、
  landing／floor rate 都是 0.0602。
- seeded distribution fidelity gate 通過：real vs simulator landing
  z = −0.569、floor z = −1.698，皆滿足雙尾 |z|≤1.96。
- simulator learnability P0 通過：PPO／SB3-DQN 各 4,096 steps，held-out
  floors 1.00／1.05，均高於 random 0.70 且未達 98% collapse。
- simulator learnability P1 通過：3 個 fresh train seeds、每演算法
  8,192 steps、20 held-out eval seeds。PPO 平均 1.45 floors，
  SB3-DQN 1.167，六個模型皆通過左右方向 coverage 與 no-collapse gate。

## 交付驗證

- P1 完成後完整回歸 `python -m pytest -q`：219 passed，33.58 秒。
- `python -m compileall -q src scripts`：通過。
- `python -m json.tool notebooks/ns_shaft_colab.ipynb`：通過。
- Colab 私人 repository 改採手動 ZIP 上傳；setup cell 的專案定位、安全
  解壓與 traversal rejection 合成測試通過。metadata 已由僅限 Python 3.11
  改為支援 3.11／3.12，並完成 wheel metadata 與隔離 target import 驗證。
- `git diff --check`：通過；只有 Windows checkout 的 LF→CRLF 提示。
- `scripts/check_simulator.py --steps 10000 --baseline-steps 1000`：
  `check_env`、10k headless、1k baseline 全通過；v0.1 本機約
  3,317 steps/s。
- 本次依使用者明確確認執行多個單回合、20 秒硬上限的 calibration；
  foreground／F8／phase／release-all 安全鏈全程保留。未開始模型訓練。

## 已知限制

- simulator v0.1 只實作 normal platform，不包含 spikes、spring、conveyor
  或 flipping；特殊平台仍是後續 fidelity 工作。
- exact 10／30-control-step screen-y 受 viewport 外隨機平台與 camera lock
  影響。held-out 樂觀下界仍約 52.3／95.4 px，因此依 D-009 改用 seeded
  distribution gate；exact pixel 值仍保留作 FAIL 診斷，不能宣稱已通過。
- 舊 JSONL 缺少新版 transition 欄位，不能直接當 BC 資料。
- 最新累積 PPO 模型在 deterministic 128-step 評估中 128 次全為
  RELEASE_ALL，視為 action collapse，不得續訓。
- action effective 至 next observation 中位約 94 ms；observation transition
  中位 125 ms。
- Colab notebook 尚未完整跑完 runtime gate；已確認最初安裝失敗來自舊
  `requires-python <3.12` 與目前 Colab Python 3.12 不相容，修正版仍需在
  Colab 重新執行安裝後 import checks。第二次執行確認 editable install
  已完成但目前 kernel 未重新載入 `.pth`；setup 已改為一般 wheel install。

## Go / No-Go

- **Go**：離線 validator、v0.1 模擬器開發、固定 seed smoke、Colab
  短 benchmark。
- **Go（嚴格限縮）**：固定 seed、固定步數、無實機 I/O 的短 simulator
  learnability probe 已完成；現在 **Go** 為 Colab runtime／throughput／
  checkpoint／resume／video pipeline validation。
- **No-Go**：自動追加本機 probe timesteps；P1 已完成，依 D-010 停止擴訓。
- **No-Go**：長時間 PPO、BC、DAgger、DQfD、Residual 訓練。
- **No-Go**：把舊 JSONL 或塌縮 PPO 當教師、初始化或續訓來源。
- **No-Go**：新增實機 rollout；本輪 calibration 已達 sample gate，不再追加。
- **通過（限 v0.1 probe）**：一步／landing 與 seeded distribution
  calibration gate。exact screen-y 多步仍是診斷 FAIL，不得另行宣稱通過。

## 下一步

1. 在 Colab 重跑 pytest／check_env、1／4／8／16 vector benchmark、
   checkpoint save/load/resume 與 MP4 `rgb_array` 驗證。
2. 凍結 Colab P2 訓練規格；Colab pipeline gate 通過前不跑較大預算。
3. 規劃 v1 特殊平台與 camera／partial-observability model；不得用未來平台
   teacher forcing。
4. Colab P2 與 simulator v1 gate 通過後才提乾淨
   human／baseline_verified 資料收集；BC／DAgger
   仍屬後續里程碑。
