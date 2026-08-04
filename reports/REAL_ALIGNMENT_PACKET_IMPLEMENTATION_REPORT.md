# Real-Game Alignment Packet Implementation Report

日期：2026-08-03  
狀態：**ENGINEERING_PASS／SUPERVISED_REAL_RUN_PENDING**

## 結論

已完成下一次受限真機實驗所需的alignment packet旁路。它不改變Teacher action，
只在既有transition、controller sidecar及MP4之外，多保存decision前／後狀態與結構化
觀測。Dry-run及完整回歸已通過，目前可以進行使用者監督的3-episode真機run；尚未實際
執行，所以不能宣稱`PASS_REAL_ALIGNMENT_PACKET`，也不能進入Teacher候選或Student訓練。

## 為何舊資料不足

最新10回合真機run已保存268維transition、action timing、post-decision controller
sidecar及MP4，但：

- transition沒有保存同一步的structured `GameObservation.platforms`；
- controller sidecar是在`policy.choose()`後才snapshot，當步action已進入memory；
- MP4可做人眼覆核，但重新偵測壓縮影片不等於當時live observation；
- 因此無法在不猜值的前提下核對每一步target safe interval、target match與因果memory。

依資料規範，沒有用舊影片補造欄位，也沒有把post-decision memory當同一步Student input。

## 本輪實作

- 新增`real-alignment-packet-v1` immutable JSONL writer與strict validator。
- 每一步保存structured observation／next observation、MP4 frame index、
  pre/post-decision memory、Teacher action/reason、visible target geometry及完整timing。
- step 0必須是reset memory；step t的pre-memory必須與t-1 post-memory完全相同。
- Raw track ID只作同幀診斷；每筆固定`diagnostic_only=true`、
  `training_eligible=false`。
- Runner在action實際套用後才同步寫入transition、alignment與controller；PLAYING no-op、
  失焦、例外、F8及terminal安全語意維持不變。
- 每回合新增`episode_XX.alignment.jsonl`；run summary自動加入`alignment_packet` Gate。

## 凍結 Gate

協定：`reports/REAL_ALIGNMENT_PACKET_PROTOCOL.md`。

Integrity全部通過後才看coverage：requested episodes、schema/finite、step/frame、四時間點、
pre/post memory continuity、安全事件與三種record counts。失敗狀態為
`FAIL_STOP_ALIGNMENT_DATA_INTEGRITY`。

Coverage至少需要30 records、ordinary 20、target geometry match率90%、edge 10、
spring 3、spikes 3、wall 3。不足為
`INSUFFICIENT_EVIDENCE_STOP_ALIGNMENT_COVERAGE`；最多只可在人工監督下累積到10回合，
不得自動追加或固定平台左右震盪湊數。

全部通過才是`PASS_REAL_ALIGNMENT_PACKET`，而且只解鎖Simulator／real alignment audit。

## 驗證

- Test-first：模組不存在時測試先失敗，實作後alignment tests 5 PASS。
- Alignment／real Gate／transition targeted：50 PASS。
- 完整回歸：462 PASS in 71.03s。
- Dry-run contract PASS：不尋找視窗、不載入input backend、不送按鍵；Gate保持PENDING。
- Dry-run JSON parse、compileall與`git diff --check`：PASS。

## 下一次受監督命令

從repository根目錄執行：

```powershell
.\.venv\Scripts\python.exe scripts\run_teacher_real_game_micro_gate.py `
  --execute `
  --focus-target `
  --dismiss-name-entry `
  --episodes 3 `
  --max-steps-per-episode 300 `
  --max-seconds-per-episode 60 `
  --max-total-steps 900 `
  --max-total-seconds 180
```

執行前由使用者手動開啟遊戲。程式仍要求輸入大寫`TEACHER REAL MICRO`並倒數；F8可
隨時停止。完成後只需提供新`logs/teacher_real_micro_*`資料夾或其中Gate JSON、三組
alignment/controller/transitions與MP4；不要只提供影片。
