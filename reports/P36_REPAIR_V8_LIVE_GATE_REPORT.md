# P3.6 Repair v8／Gate v4 Fresh Real Report

日期：2026-08-02

Run：`logs/teacher_real_micro_20260802_021704_107779`

狀態：**FAIL／P3.6 HOLD；不得進 P4.0**

## 1. 結果

| 指標 | 結果 | Gate |
|---|---:|---:|
| HUD／影片 max floors | 9／2／2 | — |
| mean floors | 4.33 | — |
| median／Q25／CVaR25 | 2／2／2 | lower-tail evidence |
| reach floor 3 | 1/3 | **FAIL；需至少2/3** |
| reach floor 5 | 1/3 | PASS |
| floor-1 bottom death | 0 | PASS |
| Gate checks | 35/36 | FAIL |

`audit_floor_counter_video.py` 對三支 MP4 的逐幀重播同樣得到 `9,2,2`；artifact 為
`artifacts/teacher_real_micro_20260802_021704_floor_audit.json`。第一回合的高表現是真實
進展，但不能取代後兩回合的 lower-tail 可靠度。

## 2. Repair v8 真機確認

本次沒有重現 Repair v8 要處理的永久停住與長漏偵測：

- safety event／blind directional action：0；
- outward wall push／wall re-entry：0／0；
- support departure timeout／same-support cycle：0／0；
- unrecovered／recovered observation dropout：0／0；
- raw player missing streak 最大1；3/3 forensic manifests available；
- action max share 42.07%，沒有 action collapse。

因此 v8 的安全與停滯修復可視為在本次真機樣本中通過，但整個 P3.6 Gate 仍受
lower-tail 失敗阻擋。

## 3. 兩次早死的證據

### Episode 2：late braking／landing overshoot

Controller steps 21–26 連續向左追逐下方 flipping landing；錄影顯示角色由中央向左
下降，step 27 才進 `direction_change_brake`。角色已帶有明顯左向動量，越過下方平台
右緣後 bottom death。這不是 detector dropout、wall collision 或 departure timeout。

### Episode 3：destination-unaware special escape

角色在 step 18–19 以 RIGHT 離開平台，step 20 對 spring braking，step 21 又以 RIGHT
執行 `escape_special_contact`。錄影顯示更深的安全落點位於左側；step 23 才改 LEFT
追 flipping platform，當時已低於有效攔截窗口，step 24 `no_reachable_landing` 後死亡。

兩者的共同根因是 controller 只用固定 lookahead／距離判斷落點，尚未完整考慮目前
水平速度、剩餘下降時間與反向煞車距離；special escape 方向也未由後續安全落點約束。

## 4. Gate 決策與下一步

唯一 blocking check 是 `reach_floor_3_case=false`，但它正是防止單一 best case 掩蓋
早死的核心門檻，因此不能放寬或忽略。決策為：

1. 不進 P4.0，不啟動 BC、DAgger、PPO、DQN 或 NEAT 長訓練。
2. Repair v9 僅加入 momentum／braking-aware landing intercept。
3. special／launch escape 必須依可達的下一個安全落點選方向，無安全出口時保守重規劃。
4. 先把本次 EP2／EP3 建成 recorded-scenario regression，確認不犧牲 wall、dropout、
   departure 與 input safety。
5. 所有離線測試通過後，只允許一次 fresh bounded 3-episode Gate v5；仍須至少2/3
   reach floor 3、至少1/3 reach floor 5，其他 v4 checks 全數保留。
