# Simulator v0.3 Edge／Playfield Fidelity Report

日期：2026-08-03  
狀態：`FAIL_STOP_ORACLE_DEVELOPMENT`  
訓練：未開始  
原版遊戲：未啟動、未送出任何按鍵

## 結論

先前影片中的「角色不離開平台左右邊緣，平台卻直接穿過角色並計算下一層」
是 Simulator v0.2 的真實物理錯誤，不是單純 renderer 問題。修正後的 v0.3
已做到普通平台接觸、隨平台上捲、完整離開水平 footprint 後才自由落下，且
formal development 的 edge invariant 為 0 次違規。

同時，實機影片比對揭露舊 Simulator 還把整張 634 px 擷取畫面當成可玩區。
v0.3 現在使用實機量測的左側遊戲框，並呈現頂部尖刺與右側非遊戲區。新的
影片已產生供人工驗收，但本報告**不宣稱 pixel-perfect 1:1**：長期頂部壓力、
特殊平台、精確 collision mask 與偵測雜訊仍未完成校正。

## 實機證據與對齊值

來源為既有 diagnostic-only alignment packet
`logs/teacher_real_micro_20260803_205952_924961`，共 3 episodes／308 records；
沒有把影片轉成訓練資料。

| 項目 | 實機證據 | Simulator v0.3 | 結果 |
|---|---:|---:|---|
| 擷取／畫布 | 634×430 | 634×431 | 1 px 高度差，保留既有 observation schema |
| 平台水平邊界 | 2,083 detections 的 min left=40、max right=423 | 40～423 | 對齊 |
| 可見平台 top | 68～400 | playfield 60～416、頂刺下緣 88 | 幾何框已顯式建模 |
| 初始角色中心 | episode 3: (232, 337.5) | (231.5, 338.5) | x/y 誤差 0.5／1.0 px |
| 平台寬高 | 常見 95～96×16，特殊圖樣可到 18 | 96×16 | 普通平台對齊；特殊待驗 |
| 平台捲動 | 主要觀測約 96 px/s | 96 px/s | 對齊 |
| 實機控制 cadence | 8 Hz（125 ms median） | formal Gate 10 Hz | 尚非時間 1:1 |

實機 episode 3 frames 33～40 顯示角色在 platform 11 接觸區向右移，清除右緣後
自由落下並在 platform 12 取得下一次接觸。新 Simulator seed 10007 以相同語意
產生 `support_departed`，而後才有 `landed`／`floor_descended`。

## 修正內容

- `ns-shaft-sim-v0.3` 預設啟用 support ownership；原地 RELEASE 不再穿越平台。
- 支撐期間角色 y displacement 與平台捲動一致。
- 只有完整 player AABB 清除來源平台左右邊緣才發出 `support_departed`。
- landing detection 使用相對於移動平台的前後 top，保留 one-way underside pass。
- 普通、尖刺、輸送帶與 active flipping 取得 support；spring bounce 與 inactive
  flipping 保持明確例外。
- playfield 改為 x=40～423、y=60～416；platform generator、player clamp、Oracle
  exit 與 renderer 使用同一組邊界。
- 初始平台 center-y=71，使畫面 top 約 352、角色中心約 338.5，貼近實機首幀。
- 頂刺碰撞下緣設 y=88；舊版把角色完全離開整張畫布才算 top death 的寬鬆語意
  不再用於 v0.3。
- Oracle 新增離邊前煞車及 top-pressure 深層目標；只屬 privileged solvability
  檢查，不可直接成為 BC labels。

## Gate 結果

### v1／v2（歷史診斷，不可當 fidelity PASS）

- v1 建立 support invariant，但仍使用全畫布；Oracle reach-3／10 為 91%／84%。
- v2 在錯誤場寬下 Oracle reach-3／10 為 100%／98%；Baseline reach-3 63%，Gate
  停在 Baseline。
- 兩者均未使用實機 x=40～423 與頂刺 y=88，因此正式結論被 v3 supersede；artifact
  保留，不覆寫。

### v3（實機 playfield 校正）

Artifact：`artifacts/simulator_v03_edge_fidelity_gate_v3.json`

| Gate | 結果 | 證據 |
|---|---|---|
| E1 Engineering | PASS | 20 RELEASE episodes 全為 floor 0；0 invariant violations |
| E2 Reachability 100／1,000 | PASS | 生成幾何通過，版本為 v0.3 |
| E3 Oracle development | **FAIL** | mean 8.72；reach-3 100%；reach-10 48%；52 top deaths；0 invariant violations |
| E4 Baseline development | NOT RUN | E3 未通過，依序停止 |
| E5 Holdout 14000～14099 | UNUSED | development 未全過，不得偷看 |
| E6 視覺輸出 | PRODUCED／待使用者驗收 | 見下一節 |

E3 的失敗不否定 edge physics 修正；它表示在較真實的頂刺範圍內，現有 Oracle
長期離台／跨層規劃仍不足。不得用 v2 的 98% 或舊 Spring 100% 宣稱新版可長訓。

## 視覺輸出

- `artifacts/simulator_visuals/simulator_v03_seed_10007_edge_departure.mp4`：
  新版單獨影片。
- `artifacts/simulator_visuals/real_vs_simulator_v03_edge_departure.mp4`：
  實機 episode 3 frames 33～40 與新版語意並排；明確為 semantic comparison，
  非時間同步。
- `artifacts/simulator_visuals/simulator_v02_vs_v03_edge_comparison.mp4`：
  舊穿透版與新版並排。
- `artifacts/simulator_visuals/real_episode3_frames33_40_edge_departure.mp4`：
  實機參考片段。
- `artifacts/simulator_visuals/real_vs_simulator_v03_edge_montage.png`：
  四個關鍵畫面的上下對照。
- `artifacts/simulator_visuals/real_vs_simulator_v03_edge_manifest.json`：
  machine-readable 邊界、來源與限制。

## 停止與下一步

目前停止在 Simulator v0.3 Oracle development，不生成新 Teacher Dataset、不啟動
BC／DAgger／PPO／DQN／NEAT，也不重驗 special curriculum 的舊 PASS。

下一步應先由使用者人工確認新版影片是否符合「從左右邊緣離台」的基本視覺語意。
若通過，只能進行 bounded top-pressure／跨層 reachability 修正，仍只用 development
seeds；達到凍結門檻後才首次使用 holdout。Spring／spikes／conveyor／flipping 必須在
新 playfield 與 support semantics 下逐一重驗，不能沿用 v0.2 結果。

## 驗證

- 完整 pytest：490 passed in 104.51s。
- `python -m compileall -q src scripts tests`：PASS。
- v1／v2／v3 Gate與visual manifest JSON：全部可解析。
- 4支主要edge MP4：8～16 frames、634／1268×504、8 fps，OpenCV可重新開啟。
- `git diff --check`：PASS（只有Windows工作樹既有LF→CRLF提示）。
