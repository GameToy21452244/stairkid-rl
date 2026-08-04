# Project Cleanup Manifest — 2026-08-04

狀態：`CONSERVATIVE_CLEANUP_COMPLETE`  
原則：無法證明安全刪除者一律保留。

## Snapshot before cleanup

- Branch：`agent/simulator-learnability-colab`
- HEAD：`745dc70b2bf07044ca16a4b280a7ea2106f6f248`
- Working tree：32 modified、149 untracked、0 staged。
- Root Markdown：2 files。
- `docs/` Markdown：10 files。
- `reports/` Markdown：105 files。
- `artifacts/`：205 files（包含formal與diagnostic evidence）。

## Classification

### KEEP_ACTIVE

- `AGENTS.md`
- `README.md`
- `docs/CODEX_START_HERE.md`
- `docs/CURRENT_STATUS.md`
- `reports/NEXT_WORK_DELTA_2026-08-04.md`
- `reports/COLAB_READINESS_MASTER_REPORT.md`
- `docs/DECISIONS.md`
- `docs/RISK_REGISTER.md`
- Simulator production source、manual tool、tests與calibration report。

### KEEP_FORMAL_EVIDENCE

- 所有`SIMULATOR_*_PROTOCOL.md`及其他明示frozen protocol。
- `artifacts/*seed_ledger*.json`。
- Oracle v8／Phase 2F／branch-preservation formal artifacts與reports。
- Stage journal、Gate artifacts、per-seed／per-trigger evidence。
- Formal artifact直接引用的CSV、SVG、PNG及diagnostic reports。
- 目前3.57 MB receding-failure audit JSON因屬正式診斷證據而保留。

### ARCHIVE

- 本輪沒有移動檔案。歷史reports仍可能被formal evidence、decision或risk條目引用；未建立
  重複archive副本，以免破壞相對路徑或增加噪音。

### DELETE_REDUNDANT

- 0 files。沒有檔案同時滿足「可證明完全重複／可重建」及「未被任何正式證據引用」。

### UNKNOWN_DO_NOT_TOUCH

- 父目錄的歷史Codex prompts與handoffs。
- 未逐一建立引用圖的舊P3／P4／Teacher／Simulator reports。
- `artifacts/simulator_visuals/`中的非MP4比較圖。
- 所有用途未完全確定的JSON／CSV／SVG／PNG。

上述檔案均保留原位。

## Ignore policy change

新增：

```text
artifacts/manual_simulator_test/
```

理由：manual session JSON／CSV／rating與recording可由工具重建，固定標記
`formal_evidence=false`，不應誤加入Git。現有本機session沒有刪除。

既有`.gitignore`已排除：

- `.venv/`、cache與build output。
- `logs/`、captures、models、runs、checkpoints。
- MP4／AVI與可執行檔。
- private config、key、credential與secret patterns。

## Moves and deletions

- Moved：0。
- Deleted：0。
- Formal evidence deleted：0。
- Unknown files touched：0。

## Formal evidence preservation

清理採零刪除，因此formal artifacts、protocols、seed ledgers、Phase 2F與Phase C evidence
全部保留。Commit前仍須重新核對關鍵SHA-256與artifact JSON可解析性。

## Snapshot after cleanup

- Commit前snapshot：33 modified、154 untracked、0 staged（包含先前Phase 2F／Phase C與
  本輪需一併保存的source、tests、formal／diagnostic evidence）。
- `docs/` Markdown：11 files；`reports/` Markdown：106 files；`artifacts/`：229 files。
- Moved 0、deleted 0、formal evidence deleted 0；所有不確定用途項目保持原位。
- Commit後預期working tree為clean；`.gitignore`排除的manual sessions與logs不計入status。
