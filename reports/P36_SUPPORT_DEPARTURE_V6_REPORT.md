# P3.6 Support-Departure Repair v6 Report

日期：2026-08-01

結論：OFFLINE PASS／REAL PENDING

專案 Gate：P3.6 FAIL／STOP

## 問題與證據

Repair v5 的兩次新真機 Gate 共 8 episodes／471 steps，floors 為
`2,3,3,2,2,5,3,3`，兩份 Gate 都 FAIL。使用者觀察角色在平台邊緣猶豫；sidecar
確認 203 RELEASE、154 aligned、175 launch，且有 37 個 edge≤20 px RELEASE
仍接觸原平台。

根因不是 vision、wall guard 或 input timeout，而是 support departure 與 airborne
landing 共用 alignment 規則。角色仍在來源平台時，projected landing delta=0
會過早 RELEASE；3-step launch cap、event 清 cooldown 與 target reset 再形成
launch→aligned→re-launch 循環。

## Test-first 修復

- 以真機 run `050608` EP1 source 7→destination 9 與 EP3 source 22→destination 25
  的幾何／狀態建立 regression tests。
- 新增 `support_departure_max_steps=8`、`support_departure_lost_frames=1`。
- 新增 `ON_SUPPORT_DEPARTURE` latch：保存 source ID/kind/bounds、destination
  ID/kind 與 direction。
- 仍接觸相同 source 時持續離台，不再因 landing alignment 輸出 RELEASE。
- destination 在 latch 期間保持不變；新出現的較近平台不會搶走意圖。
- 觀察到 source support-lost 後才交回 airborne landing，並啟動 generic launch
  cooldown，避免立即重新抓回來源平台。
- 8-step hard cap 是 safety abort；wall evacuation 可覆蓋方向但不拆掉 departure
  lifecycle，special-contact escape 仍有更高優先權。

## 新 telemetry 與 Gate

真機 runner／sidecar 新增：

- departure active/source/destination/direction/steps；
- same-support departure cycle count；
- departure target switch count；
- departure timeout count；
- support edge RELEASE count／opportunity／ratio；
- support-lost exit samples；
- phase-aware support aligned RELEASE streak。

新 blocking checks：

- same-support departure cycle = 0；
- departure target switch = 0；
- departure timeout = 0；
- edge RELEASE ratio ≤ 25%；
- 至少有一筆 support-lost exit；
- max departure steps ≤ 8；
- max support-aligned RELEASE streak ≤ 3。

舊 global aligned streak 保留為 telemetry，但不再跨 `AIRBORNE`／`ON_SUPPORT`
兩個 phase 直接阻擋。離線 r2 的 6-step streak 實際是 3 airborne＋3 support，並非
同一 phase 的 6-step 卡死；因此改用 phase-aware 指標，而不是放寬相同指標。

## 離線回放

Artifact：`artifacts/p36_support_departure_v6_offline_replay_r3.json`

- 8 MP4／476 playing frames；
- effective player missing 0，max missing 2；
- outward wall push 0，wall re-entry 0，max wall burst 0；
- departure active 177 steps；
- same-support departure cycles 0；
- departure target switches 0；
- max support-aligned RELEASE streak 3；
- edge RELEASE 17/96（17.71%）；
- 所有可由舊影片判定的 offline checks PASS。

舊軌跡中有 5 次 departure 達 8-step cap。因 MP4 仍呈現 v5 舊 action 的物理結果，
無法顯示 v6 持續方向本應造成的 support-lost；此數字保留為 counterfactual
telemetry，不用來宣稱通過，也不作離線 blocking。全新真機 Gate 仍硬性要求
timeout=0。

## 自動驗證

- Targeted：86 passed。
- 完整 `pytest -q`：357 passed in 83.27s。
- `python -m compileall -q src scripts tests`：PASS。
- Teacher Real dry-run：PASS，未尋找視窗、未載入 input backend、未送鍵。
- Replay JSON parse：PASS。
- `git diff --check`：PASS（僅既存 LF/CRLF 提示）。

## 下一步

只允許一個全新 bounded 3-episode Teacher Real Gate。新 artifact PASS 前，
P3.6 維持 FAIL／STOP，不進 P4.0、不生成 dataset，也不執行 BC、DAgger、PPO、
DQN 或 NEAT。

## 後續實機與 Gate v2 addendum

v6 後續已完成一次 3 回合真機紀錄：466 steps、parser floors `5,3,10`、3/3
reach-3、2/3 reach-5、0 safety event；departure restart／target switch／timeout
皆為 0，46 次 support exit median 3／max 5 steps。舊 Gate v1 的 FAIL 經 sidecar
確認包含正常 settle、special escape reversal 與安全恢復 dropout 的語意誤判。

Gate v2 重分類全項 PASS，但依 provenance 規則不回溯改寫本報告原本的
OFFLINE PASS／REAL PENDING 結論；目前最新狀態與完整理由請以
`P36_GATE_SEMANTICS_V2_REPORT.md` 與 `docs/CURRENT_STATUS.md` 為準。P3.6 仍需
一次全新 v2 runner 實機確認。
