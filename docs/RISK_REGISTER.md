# Risk Register

| ID | 風險 | 嚴重度 | 證據／觸發 | 緩解與狀態 |
|---|---|---:|---|---|
| R-01 | 真實輸入送錯視窗或按鍵未釋放 | 極高 | Windows 自動輸入 | 保留 foreground／related-window／F8／release_all；自動測試禁實機。持續 |
| R-02 | 舊資料 transition 錯位或跨 episode | 高 | legacy JSONL 缺 episode、next obs、時間戳 | quarantine + 新 validator；writer 尚未接入。開放 |
| R-03 | 動作 label 與實際生效時間錯位 | 高 | capture/action latency 未量測 | 四個時間戳、held/action duration schema；待 calibration。開放 |
| R-04 | PPO action collapse | 高 | 128/128 RELEASE，其他 checkpoint 也曾 128/128 RIGHT | 禁止續訓；固定 action metrics gate。已控制 |
| R-05 | simulator reality gap | 高 | v0 參數為工程初值 | 有限 telemetry 校正、固定 baseline、逐參數 ablation。開放 |
| R-06 | simulator reward exploitation | 高 | floor／landing shaping 可能可刷 | component audit、終止原因、影片、跨 seed、真實 replay comparison。開放 |
| R-07 | observation schema drift | 中高 | 歷史已有 16／64／268 維格式 | version + strict dimension validator + shared encoder tests。已控制 |
| R-08 | reward drift | 中高 | 真實 reward 已多次加入 shaping | reward_version、component totals；真實／sim 統一決策待做。開放 |
| R-09 | episode reset 污染 rollout | 高 | menu/dialog/focus correction 跨 episode | terminal/truncated continuity checks；真實 writer 尚待接入。開放 |
| R-10 | 多 env 非獨立或 seed 洩漏 | 中 | Colab vector env | 每 env 獨立 Pymunk Space/RNG、fixed-seed tests；vector benchmark 待跑。部分控制 |
| R-11 | 長訓消耗資源但無資訊增益 | 中高 | 真實環境約 6–7 steps/s | Go/No-Go、短 probe、early stop、固定評估。已控制 |
| R-12 | artifact／密鑰誤提交 | 高 | models/logs/captures/Drive | `.gitignore`、只提交 summary、config 不含 secret。持續 |
| R-13 | human render 在 headless 環境開窗 | 中 | Pygame display | Colab 設 dummy driver，只用 None/rgb_array；human 僅本機手動。已控制 |
| R-14 | v0 platform crossing 容差產生穿透／假落台 | 中 | 明確 crossing test 尚未真實校正 | landing/edge tests，待 telemetry 與高速度案例。開放 |
