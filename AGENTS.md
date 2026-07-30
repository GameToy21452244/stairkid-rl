# Codex 工作規範

## 每次工作階段的強制恢復順序

1. 完整閱讀父目錄的 `../CODEX_NS_SHAFT_PROJECT_REFACTOR_PROMPT.md`。該文件是長期規格；context 壓縮、重新開啟工作階段或交接後都不得略過。
2. 閱讀本文件、`README.md`、`docs/PROJECT_CONTEXT.md`、`docs/CURRENT_STATUS.md`、`docs/DECISIONS.md` 與 `docs/RISK_REGISTER.md`。
3. 閱讀與任務相關的 roadmap、protocol、schema、simulator spec、workflow、報告與測試。
4. 執行 `git status` 與 `git diff`；現有修改一律視為使用者工作，不得還原或覆寫。
5. 確認 `docs/CURRENT_STATUS.md` 的完成項目、Go/No-Go 與下一步後才修改。

## 不可偏離的技術方向

- 主路線為：資料清理／校正 → 結構化模擬器 → BC → DAgger → baseline + residual → Double DQN／DQfD-lite → 少量實機驗證。
- PPO 僅可作模擬器可學性與小型對照。不得續訓或長訓已塌縮的 PPO checkpoint。
- 舊 baseline／reward-audit JSONL 未通過新版 validator 前不得作 BC 標籤。
- 未通過 `docs/EXPERIMENT_PROTOCOL.md` 的 Go gate，不得開始長時間訓練或大量實機 rollout。
- 完成工作後更新 `docs/CURRENT_STATUS.md` 與 `reports/IMPLEMENTATION_PROGRESS_REPORT.md`，避免 context 壓縮後方向漂移。

## 實機安全

- 不可直接執行未知 `.exe`，除非使用者明確允許。
- 不可注入、修改、掛鉤、反編譯遊戲程序或讀取程序記憶體；不可使用 Cheat Engine 或繞過反作弊。
- 僅允許螢幕擷取與一般鍵盤輸入；`auto_launch` 保持 false。
- 不可關閉 F8 緊急停止或 PyAutoGUI fail-safe。
- 所有輸入自動化必須具有 `release_all()`，並在例外、失焦、未知狀態、回合結束、Ctrl+C 與正常結束時呼叫。
- 自動輸入只能在已驗證唯一目標遊戲視窗位於前景時執行。
- 實機實驗必須有明確確認、倒數、步數／回合／時間上限，且不得默默開始下一回合。
- 不得猜測 UI 位置；只能使用校正工具、已標記樣本或集中設定。

## 開發與驗證

- 先寫或更新測試，再修改關鍵控制、資料或物理邏輯。
- 自動測試、模擬器、Colab notebook 不得載入真實輸入後端，也不得操作真實鍵盤、滑鼠或遊戲。
- 本機負責實機介面、校正、資料收集、開發與 smoke test；Colab 僅負責 headless 模擬器實驗。
- 每次完成工作至少執行：
  - `python -m pytest -q`
  - `python -m compileall -q src scripts`
  - `git diff --check`
- 不要提交遊戲執行檔、模型、錄影、大量截圖、密鑰或本機 `config.yaml`。
- 遊戲路徑、視窗標題與按鍵必須集中在設定檔。
- 所有使用者可見文字優先使用繁體中文。
