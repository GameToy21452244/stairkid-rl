# Local / Colab Workflow

## 本機

本機是唯一可接觸真實遊戲的環境，負責：

- 視窗、capture、辨識、校正與安全輸入工具；
- 有明確確認與硬上限的有限資料收集／實機評估；
- schema validator、單元測試、simulator 開發與短 smoke；
- 將不含執行檔／密鑰／大量 artifact 的原始碼推送到 Git。

## Colab

Colab 只負責 headless simulator：

- 以手動上傳的 repository ZIP 安裝依賴、執行 pytest／check_env；
- 1／4／8／16 個同步與非同步 env benchmark；
- 後續短訓練、TensorBoard、checkpoint、video、Drive resume。
- v0.2 gates 通過後的小型 Teacher Dataset、BC0 與條件式一輪 DAgger0 smoke。

本專案 repository 為私人存取時，不要求在 Colab 儲存 GitHub token。
`notebooks/ns_shaft_colab.ipynb` 預設提示上傳完整 repository ZIP，自動解壓縮
並尋找同時包含 `pyproject.toml` 與 `src/stair_agent/` 的專案根目錄。如果已經
用 Colab Files 面板解壓縮，也可在設定 cell 指定 `MANUAL_PROJECT_PATH`。
安裝或定位失敗會立即中止，不會退回 `/content` 繼續執行。
目前 Colab runtime 使用 Python 3.12；專案 metadata 同時支援本機 Python 3.11
與 Colab Python 3.12。Notebook 安裝時不隱藏 pip 輸出，並在安裝後實際 import
Gymnasium、Pymunk、Stable-Baselines3 與 `stair_agent`，避免只憑 pip
return code 誤判成功。安裝前也會確認 Colab 既有的 setuptools 至少為 65，
並以該 backend 建立一般 wheel，避免隔離建置環境重複下載。Notebook 不使用
editable install，因為新建立的 `.pth` 不會由已經運行中的 Colab kernel
自動重新載入；一般 wheel 安裝則可在同一個 cell 立即執行 import checks。

Colab 不得：

- 上傳或執行遊戲 `.exe`；
- import 或初始化 Windows input backend；
- 嘗試操作本機視窗／鍵盤；
- 把 Drive checkpoint 當作通過資料／模型 gate 的證明。

## Artifact 慣例

建議每次實驗放在：

`runs/<experiment_id>/{config.json,summary.json,tensorboard/,checkpoints/,videos/}`

大型 artifact 保持 git ignored；只提交小型 summary／report。Drive 同步時保留
experiment id 與版本，不以 `latest` 覆蓋唯一副本。

## Notebook

`notebooks/ns_shaft_colab.ipynb` 是 pipeline validation notebook，含 dummy
video driver、安裝、
Drive、pytest、check_env、headless smoke、vector env benchmark、TensorBoard、
checkpoint save/load、256-step resume 與實際 MP4 產生。validation cell 預設
停用，需在前置 gate 通過後手動設
`RUN_COLAB_PIPELINE_VALIDATION=True`；總訓練上限 768 steps。它不包含
自動長訓；後方另有歷史Spike BC0與目前P4.1的預設停用bounded cells。

2026-07-30 實際 Colab gate 已通過 pytest（219 tests）、check_env、
1／4／8／16 env throughput、checkpoint save/load/resume 與 MP4。768-step
deterministic 評估全 RIGHT，故 checkpoint 不得續訓。v0.2 teacher／BC0
工具完成後需另加預設停用、硬預算的 cells；不得把 pipeline PASS 當策略 PASS。

### Spike BC0 bounded experiment

Notebook 最後的 `RUN_SPIKE_BC0=False` 預設不執行。前置 pytest／check_env
通過後才改為 `True`。該 cell 會重跑 spike curriculum Gate、重建 git-ignored
Teacher JSONL，接著執行 hard-label seeds 0／1／2；每 seed 最多 30 epochs、
early stopping，eval seeds 固定為 1100～1119。

Cell 最後會封裝三個 summary／model 與 `spike_bc0_colab_gate.json`。任一 seed
失敗便停止，不會接著執行 DAgger。下載 cell 顯示的 ZIP 交回分析即可。

### P4.1 bounded S0／S1／S2／S3

P4.1不能使用一般GitHub source ZIP，因為凍結的25 MiB JSONL依repository政策被
git-ignore，而current source重新生成同名資料又與原資料不同。正式流程是：

1. 先完成本機程式、測試、文件並commit，使工作樹clean。
2. 執行：

   ```powershell
   .\.venv\Scripts\python.exe scripts\package_p41_colab.py
   ```

3. 上傳父目錄的`ai-stair-agent-p41-colab.zip`；setup cell會安全解壓並定位專案。
4. 依序執行安裝、pytest、check_env與benchmark；歷史
   `RUN_COLAB_PIPELINE_VALIDATION`、`RUN_SPIKE_BC0`保持`False`。
5. 只把最後一格`RUN_P41_ABLATION=False`改為`True`並執行一次。
6. 下載cell輸出的`*_p41_ablation.zip`；無論status是PASS或FAIL_STOP都交回分析。

Bundle會拒絕dirty工作樹、local `config.yaml`、遊戲EXE、影片、舊weights與其他JSONL；
唯一例外是manifest hash完全相符的`spike_teacher_dataset_v1.jsonl`。Bundle內另有
`p41_bundle_manifest.json`保存commit、dataset與archive provenance。

P4.1 cell固定3 initialization、300 optimizer updates、selection seeds
4000～4019與single-use final seeds 4100～4139。若selection沒有任一S1/S2/S3穩定
超過S0，runner不碰final seeds；科學FAIL仍正常回傳0並保存summary，只有schema、hash、
依賴或runtime錯誤才會拋出`CalledProcessError`。Colab不會啟動P4.2、DAgger或任何RL。
