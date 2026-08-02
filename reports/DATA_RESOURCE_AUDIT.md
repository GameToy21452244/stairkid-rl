# Data Resource Audit

日期：2026-07-30

## 結論

本次掃描 `logs/` 下全部 37 個 JSONL、3,561 rows，逐檔、逐 synthetic/explicit
episode 並逐 row 產生 hash 與分類。結果是：

| 分類 | files／episodes | rows | 可用範圍 |
|---|---:|---:|---|
| `dynamics_only` | 14 | 649 | 普通平台動力／landing fidelity |
| `needs_relabel` | 8 | 476 | 舊 baseline decision states，可重新標記 |
| `invalid` | 15 | 2,436 | 不進訓練 |
| `demo_verified` | 0 | 0 | 無 |
| `replay_valid` | 0 | 0 | 無 |

因此目前**沒有足夠且合格的真實示範可直接進入 BC**，也沒有可作 replay 的完整
真實 transition。下一步應由通過 gate 的 Simulator v0.2
Teacher-observable 產生小型初始 teacher dataset；476 筆舊 baseline 狀態只能
作 relabel 候選，不能保留原 action 當 expert。

## Prompt 指定問題

1. 649 筆 calibration 中，649 筆都符合 v1 transition schema 並可作
   `dynamics_only`；0 筆可作 BC／replay，因它們是固定校正動作且
   `policy_source=invalid`。
2. 2,912 筆 legacy rows 中，476 筆可救回為 `needs_relabel` 狀態；
   其餘 2,436 筆為 invalid training input。
3. 可用於 BC：0 rows、0 episodes。
4. 可用於 replay：0 rows、0 episodes。
5. 可用於 DAgger/offline relabel：476 rows、8 synthetic file-episodes。
6. 649 筆 calibration action：RELEASE 353（54.39%）、LEFT 150（23.11%）、
   RIGHT 146（22.50%）。476 筆 relabel 候選的舊 action 僅供稽核：
   RELEASE 256、LEFT 108、RIGHT 112，不得作教師 label。
7. legacy structured observation 中平台 occurrence（不是 verified transition
   coverage）：normal 12,211、spikes 2,698、flipping 1,652、conveyor 1,521、
   spring 1,517。649 筆 calibration 是普通平台動力校正，特殊平台沒有可信
   action/outcome coverage。
8. 主要拒絕原因：缺 episode id、`next_observation`、四段 action timing、
   schema／observation／reward version、reward components；早期資料另有
   16／64 維格式、manual action 字串及未驗證 baseline policy。
9. 不存在足夠資料直接進 BC。
10. 尚缺：easy normal-platform 的 RELEASE／LEFT／RIGHT 可觀測教師資料、
    煞車／慣性與左右牆 recovery、錯失平台前狀態、低 confidence soft targets，
    以及未來逐項加入特殊平台後的 validated demonstrations。

## Legacy 2,912-row 明細

| family | rows | 判定 |
|---|---:|---|
| baseline | 574 | 476 有 `decision_observation`，只作 relabel；98 更舊資料 invalid |
| observations | 1,331 | 無 action／next state／episode，invalid |
| reward audit | 1,007 | 16 維、manual action、無完整 timing／next state，invalid |

## 完整性與污染檢查

- Canonical schema-valid：649 rows；legacy schema-valid：0。
- NaN／Inf：0。
- Canonical observation jump warnings：0。
- BC／replay eligibility：均為 0。
- observation-only 檔案的 raw-frame 重複率只作診斷，不可解讀為 transition
  duplicate ratio。
- 每個 salvage row 都保留來源檔、line、step 與 canonical JSON SHA-256；
  沒有改寫原始 ignored logs。

## 產物

- `artifacts/dataset_inventory.csv`：每檔／episode 的要求欄位與分類。
- `artifacts/dataset_salvage_manifest.csv`：3,561 個 row-level provenance。
- 產生器：`scripts/audit_data_resources.py`。

## Gate

- Data Resource Audit 完整性：**PASS**。
- 既有真實 demo gate：**FAIL（0 verified rows）**。
- 既有真實 replay gate：**FAIL（0 valid rows）**。
- Dynamics resource gate：**PASS（649 rows，僅限普通平台校正）**。
- 准許下一階段：**GO Simulator v0.2＋Teacher-observable 工程**。
