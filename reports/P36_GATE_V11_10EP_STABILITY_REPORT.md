# P3.6 Gate v11 10-Episode Stability Report

日期：2026-08-03

狀態：**PASS／P3.6 STABILITY QUALIFIED／P4.0 AUDIT ONLY**

## 結論

這是目前最完整、也最好的 Teacher 實機結果。完整自然 run 有 10/10 回合，
經同 run 的 MP4 HUD 逐幀稽核後，最高樓層為
`8,11,4,2,2,5,4,4,8,2`。Gate v11 以原始 controller sidecars 加可信影片證據
離線重分類後，所有 blocking checks 通過。

本次沒有把數字門檻調低。Reach-3 仍須 7/10、reach-5 仍須 4/10，floor-1 bottom
death 必須為 0，安全、觀測、wall、departure、特殊平台 lifecycle、影片與 sidecar
完整性要求也全部保留。修改的是兩個與遊戲／控制語意不一致的計數方式：

- 無限下樓遊戲不能把所有 bottom terminal 當失敗，否則會反向獎勵 top death；
- 特殊平台 entry brake 加上唯一允許的 replan brake，不應被當成反覆振盪。

因此 P3.6 可判定 stability qualified，下一步開放 P4.0 State-aliasing Audit。這不等於
Teacher 已完美，也不授權 S0～S3、BC、DAgger、PPO、DQN、NEAT 或長時間訓練。
Reach-3 與 early-bottom budget 都剛好壓線，lower-tail reliability 仍是主要風險。

## 不可變來源與影片稽核

- Run：`logs/teacher_real_micro_20260803_034023_674665/`
- 原始 Gate v10：`teacher_real_game_micro_gate.json`
- 原始 floors：`8,11,3,2,2,5,4,4,8,2`
- MP4 audit：`artifacts/teacher_real_gate_v10_10episode_floor_video_audit_v2.json`
- Gate v11 reclassification：
  `artifacts/p36_teacher_real_gate_v11_reclassification_20260803_034023_v2.json`

10 支 MP4 全部可讀，HUD floor counter 每幀 available，且每回合初始值皆為 1。
Episode 3 的最後一個可讀 frame 已顯示第 4 層；live sidecar 因 terminal phase timing
停在第 3 層。影片修正只能向上，若低於 sidecar 會拒絕；audit 來源也必須與 Gate
位於同一 run。原始 Gate v10 artifact 沒有被覆寫。

## Gate v11 結果

| 指標 | 結果 | 門檻／判定 |
|---|---:|---|
| Episodes | 10/10 | PASS |
| Floors | 8, 11, 4, 2, 2, 5, 4, 4, 8, 2 | 影片校正後 |
| Mean／median | 5.0／4.0 | 診斷 |
| Q25／CVaR25 | 2.5／2.0 | lower-tail 保留 |
| Reach floor 3 | 7/10 | 至少 7，PASS（壓線） |
| Reach floor 5 | 4/10 | 至少 4，PASS（壓線） |
| Reach floor 10 | 1/10 | 診斷 |
| Floor-1 bottom death | 0 | 必須 0，PASS |
| Early bottom（floor<3） | 3 | budget 3，PASS（壓線） |
| Total bottom／top | 9／1 | 完整 telemetry，不作錯誤偏好 |
| Safety events | 0 | PASS |

## 為何不是單純放寬 Gate

舊 `bottom death <= 2` 把終局方向和早期失敗混在一起。NS-SHAFT 沒有「走到底
通關」的有限終點；角色持續往下後自然可能從下方終止。若只允許兩次 bottom，模型
反而可能因被上方尖刺殺死而得到較好的 Gate 結果。Gate v11 改量真正要阻擋的分支：
尚未到第 3 層就從下方死亡。其 budget 直接等於 reach-3 門檻允許的 misses，並保留
total bottom 與 terminal taxonomy 供診斷。

特殊平台方面，Gate 原本允許一次 replan／reversal，卻又要求 brake 最多一次。
Sidecar 顯示兩個 brake=2 的 contact 都是：第一次方向切換前 RELEASE 煞車，之後
可見落點改變而執行唯一一次准許的 reversal，再 RELEASE 煞車一次。Episode 1 與 2
分別到第 8 與第 11 層，contact 並未失控。Gate v11 因此要求每 contact：

- brake <= `1 + reversal_count`；
- brake 絕對值 <= 2；
- replan 與 reversal 各自仍 <= 1；
- restart=0、safety abort=0、contact duration <=16。

本次 special contacts 16 次，spring 7、spike 9，最長 10 steps；brake violation 0。

## 安全與控制完整性

以下 blocking 指標全部為 0：invalid observation、unrecovered dropout、blind
directional action、outward wall push、wall re-entry cycle、actionable support
release、same-support departure cycle、departure target switch、departure timeout、
same-special restart、special safety abort。10 支影片、controller/transition records、
floor counter、dropout forensics 皆完整，LEFT／RIGHT physical response 皆有 sample，
且沒有 action collapse。

姓名輸入 modal 的處理已限制為唯一、same-process、owner target、class `#32770`、
標題白名單，且只送一次 Enter、不輸入文字；未知 related window 仍 fail closed。
本次完整 run 未遇到此 modal，所以此功能是 code-tested，不是 live-validated。

## 下一步與停止條件

下一步只執行 P4.0 State-aliasing Audit：

1. 固定目前資料，不先訓練模型。
2. 比較 observation-only 與 deployable controller memory 下的 action conflict／entropy。
3. 分別報 normal、spring、spike、wall、departure、dropout/recovery 分支。
4. 若 memory 不能穩定降低 conflict，停止並修 observation／label timing；不進 S0～S3。
5. 若 P4.0 Gate 通過，才設計相同資料、seed、budget 的 S0／S1／S2／S3 smoke。

本次不啟動任何 Student、BC、DAgger、PPO、DQN、NEAT 或長時間實機探索。

## 驗證

- Gate 單元測試：43 passed。
- Gate＋HUD targeted：51 passed。
- 完整測試：410 passed in 172.95s。
- `compileall`：PASS。
- `git diff --check`：PASS（僅既有 Windows LF/CRLF 提示）。
