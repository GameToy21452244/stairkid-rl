# Real-Game Alignment Packet Protocol

日期：2026-08-03  
狀態：**FROZEN_BEFORE_FIRST_RUN**

## 目的

Simulator observation-schema probe已證明launch-handoff介入整體有害，但舊真機
transition只有268維encoded observation，controller sidecar又是在當步決策後寫入。
本Gate只補齊Simulator／真機對齊所需的診斷資料；不修改Teacher action、不訓練模型，
也不把packet直接當Student dataset。

## 執行限制

- 初次只跑3 episodes；每回合最多300 steps／60秒，總計900 steps／180秒。
- 若自然分支coverage不足，可在人工監督下累積到最多10 episodes；不得自動追加。
- 使用者手動啟動遊戲；`auto_launch=false`、唯一前景視窗、明確確認、3秒倒數及F8維持。
- 失焦、未知modal、例外、Ctrl+C、回合／時間／步數上限一律`release_all()`。
- 不修改、注入、掛鉤、反編譯或讀取遊戲記憶體。

## 每一步必須同步保存

- decision frame index及next frame index，對應同episode MP4。
- decision前與next structured `GameObservation`，不是只存268維encoder輸出。
- `pre_decision_memory`與`post_decision_memory`；step 0必須為reset state，後續
  pre-memory必須等於前一步post-memory。
- action、Teacher reason、target kind／signed offset及可見target box／safe interval。
- observation、command、effective、next-observation四個時間點、held action與duration。
- events、terminal/truncated與episode/step continuity。

Raw track ID只為同幀對齊與診斷保存；packet固定
`diagnostic_only=true`、`training_eligible=false`。任何後續Student schema不得直接使用ID。

## Integrity Gate

全部通過才可評估coverage：

- requested episodes完整且每回合至少1 record；
- JSON schema、有限數值、動作與時間順序正確；
- step及frame index連續；decision frame=`step`、next frame=`step+1`；
- observation timestamps與timing一致；
- step 0 memory為reset，跨步pre/post memory 100%連續；
- safety events為0；packet／transition／controller record數相同。

任一失敗：`FAIL_STOP_ALIGNMENT_DATA_INTEGRITY`，不得用猜值修補。

## Coverage Gate

完整run合計至少：

- 30 records；normal/ordinary target context 20 records；
- target已選擇的rows中，可見geometry match率至少90%；
- support edge context 10 records；
- spring context 3 records；spikes context 3 records；wall guard context 3 records。

不足時為`INSUFFICIENT_EVIDENCE_STOP_ALIGNMENT_COVERAGE`。只准再蒐集尚缺的自然分支，
累積上限10 episodes；不得以固定平台左右震盪或手工填label湊數。

全部通過為`PASS_REAL_ALIGNMENT_PACKET`，只解鎖Simulator／real target與timing alignment
audit，不直接解鎖Teacher候選、fresh100、Dataset v2、BC、DAgger、PPO、DQN或NEAT。

