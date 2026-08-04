# Simulator v0.3 Edge-Departure Fidelity Protocol

日期：2026-08-03  
狀態：已執行；正式 v3 Gate 於 Oracle development FAIL／STOP

> 執行後發現原協議尚未凍結實機 playfield 邊界。v1／v2 使用整張
> 634 px 畫布當可玩區，因此只保留為診斷。v3 在不改原門檻與 seeds 的
> 前提下，加入實機量測的 x=40～423、y=60～416、頂刺下緣 y=88 與
> 初始平台／角色位置後重跑；結果記錄於
> `reports/SIMULATOR_V03_EDGE_FIDELITY_REPORT.md`。

## 問題與停止結論

Simulator v0.2 把平台當作 sensor，並以絕對垂直速度處理 landing。
普通落台將 player 設為 +95 px/s，平台則以 +96 px/s 上捲；結果
平台會從下方穿過 player，不需從左右邊緣離台也能計數新樓層。
種子 10007 的舊畫面與追蹤已重現此問題。

在本 Gate 通過前：

- Simulator v0.2 的 Oracle／Baseline／Spring 成功率全部降為歷史診斷；
- 不得產生新 Teacher Dataset；
- 不得開始 Student、BC、DAgger、PPO、DQN 或 NEAT 訓練；
- 本輪不開啟或操作原版遊戲。

## 實機語意基準

使用既有、不可訓練的 alignment packet：

- `logs/teacher_real_micro_20260803_205952_924961`；
- 3 episodes／308 records；
- packet 狀態 `PASS_REAL_ALIGNMENT_PACKET`；
- episode 3 step 39 為可重現的 normal landing，step 40 開始同平台
  support，後續操作顯示角色必須向平台邊緣移動才能離台。

本 Gate 只驗證已有證據支持的語意：

1. active 平台在水平重疊時持續支撐 player；
2. support 期間 player 跟隨平台垂直上捲；
3. 普通、尖刺、輸送帶與 active flipping 只有在 player 離開左／右
   footprint 後才可解除 support；
4. spring bounce 與 inactive flipping 是明確例外；
5. 從下方上升穿越 one-way platform 仍允許。

未有實機證據的離台初速、精確 sprite foot width 與彈簧衝量，不宣稱
1:1 數值完成。

## 版本與凍結設定

- 新版：`ns-shaft-sim-v0.3`；
- physics：60 Hz；policy：10 Hz；
- 第一個 Gate 只使用 easy／normal-platform distribution；
- development seeds：13000～13099；
- untouched holdout seeds：14000～14099，development 全過後只跑一次；
- horizon：每回合最多 600 policy steps；
- target：floor 10。

## Gate 順序與門檻

### E1 Engineering

- RELEASE 8 steps 不得出現 `floor_descended`；
- support 期間 player 與平台 y displacement 誤差 <= 1e-6 px；
- `support_departed` 發生時 player body 已無水平 overlap；
- 從上方下降可取得 support，從下方上升不碰撞；
- 原地 RELEASE 的 20 seeds 全部 floor=0；
- 新樓層前必須已有對上一支撐平台的合法 edge departure，0 violations。

### E2 Reachability

- 100 seeds，通過後再 1,000 seeds；
- 生成序列可重現、無 geometry unreachable；
- 版本必須是 `ns-shaft-sim-v0.3`。

### E3 Oracle-full development

- reach floor 10 >= 95%；
- reach floor 3 >= 99%；
- edge-departure invariant violations = 0；
- RELEASE／LEFT／RIGHT 都有使用；
- 無 action collapse。

### E4 Baseline development

- mean deepest floor >= 5；
- reach floor 3 >= 90%；
- 明顯優於 RELEASE；
- edge-departure invariant violations = 0；
- 無 action collapse。

### E5 Untouched holdout

development 全過才執行，門檻與 E3／E4 相同。任一項未過即停止，
不得重跑到幸運通過。

### E6 視覺驗收

輸出至少：

- v0.2 錯誤穿透影片；
- v0.3 normal-platform edge-departure 影片；
- 實機 normal landing／support／edge departure 片段；
- 實機／v0.3 並排對照或 montage；
- machine-readable 指標與人工驗收注意事項。

視覺輸出是驗收必要條件，不能只以 floor counter 宣稱成功。
