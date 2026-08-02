# P3.6 Repair v9 Report

日期：2026-08-02

狀態：**CODE／TEST READY；Gate v5 FRESH REAL PENDING；P3.6 HOLD**

## 1. 輸入證據

來源 run：`logs/teacher_real_micro_20260802_021704_107779`。Gate v4 floors `9,2,2`，
35/36 checks PASS；唯一 failure 是 reach-floor-3 只有1/3。影片與 sidecar 將早死分成：

- EP2：長距離向左下降仍以固定0.25秒投影，煞車／收油太晚後越過落點。
- EP3：在 spring 右緣沿用先前 RIGHT，下一個安全落點位於左側時已來不及反向。

本輪不放寬 lower-tail Gate，也不以 EP1 floor9 取代後兩回合。

## 2. Repair v9

### 2.1 Adaptive airborne landing intercept

- 原本0.25秒保留為最小 horizon；最大0.55秒。
- rising 使用0.55秒；falling 使用
  `delta_y / max(velocity_y, 80 px/s)` 並 clamp 至0.25～0.55秒。
- 每個選中 target 記錄 prediction seconds、projected x 與 safe left/right。
- Gate v4 EP2 regression 在 x=231、vx=-208、rising 時投影 x=116.6，位於
  target safe interval 50～126，因此提早 RELEASE，不再繼續 LEFT。

### 2.2 Phase isolation

長 airborne horizon 不直接控制仍有 support 的 departure。離台方向改由 destination
safe interval、已存在的水平動量與來源平台邊界決定，避免初版修改把已在離台的方向
反轉。v8 的8-step cap、2-step abort cooldown 與 lifecycle telemetry 不變。

### 2.3 Destination-aware special escape

- 排除 special source 後，優先選 source 下方、可達且安全的 visible landing。
- 尚無可見 destination 時，只有距 source edge 12 px 內且 outward velocity 超過
  40 px/s 才反向煞車。
- Persistent special contact 可在新 destination 出現時有限 replan。
- Sidecar 記錄 direction source、destination ID 與 replan flag。

## 3. Gate v5

Gate v5 新增：

- `landing_intercept_telemetry_available`；
- `special_escape_destination_telemetry_available`；
- landing decision、visible-destination、edge-momentum 與 special replan counts。

Gate v4 的 safety、dropout<=8、blind action=0、wall re-entry=0、outward=0、departure
timeout=0、floor-1 bottom=0、reach-floor-3>=2/3、reach-floor-5>=1/3 全部保留。

## 4. 離線驗證

- Targeted policy／config／Gate tests：107 passed。
- 完整回歸：379 passed in 68.31s。
- `compileall`：PASS。
- `config.yaml` 新參數 parse：PASS。
- Gate v5 dry-run：PASS；未尋找遊戲、未載入 input backend、未送鍵。
- `git diff --check`：PASS，只有既有 CRLF 提示。

最新三支 v4 MP4 反事實重播顯示 EP2 frame23 提早 RELEASE、EP3 提早 brake→LEFT，
outward wall push、wall re-entry、same-support cycle 皆為0。凍結舊影片在 EP1 產生一次
departure timeout：新 policy 持續 LEFT，但影片角色仍依舊 action 向右回到 source；
這是 counterfactual mismatch，不能證明 closed-loop 成功或失敗。Gate v5 仍嚴格要求
真機 timeout=0。

Artifacts：

- `artifacts/p36_repair_v9_gate_v4_offline_replay.json`
- `artifacts/teacher_real_game_micro_gate_v5_repair_v9_dry_run.json`

## 5. 下一步

下一個唯一允許實驗是使用者監督的一次 bounded 3-episode Gate v5。未全項 PASS 即
停在 P3.6，分析新影片與 landing/special telemetry；不得進 P4.0 或任何長訓練。
