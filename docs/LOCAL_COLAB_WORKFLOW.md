# Local / Colab Workflow

## 本機

本機是唯一可接觸真實遊戲的環境，負責：

- 視窗、capture、辨識、校正與安全輸入工具；
- 有明確確認與硬上限的有限資料收集／實機評估；
- schema validator、單元測試、simulator 開發與短 smoke；
- 將不含執行檔／密鑰／大量 artifact 的原始碼推送到 Git。

## Colab

Colab 只負責 headless simulator：

- clone、安裝依賴、執行 pytest／check_env；
- 1／4／8／16 個同步與非同步 env benchmark；
- 後續短訓練、TensorBoard、checkpoint、video、Drive resume。

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
BC／DAgger／DQfD 或長訓。
