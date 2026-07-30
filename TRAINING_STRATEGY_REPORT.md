# NS-SHAFT 訓練策略調整與新實驗方案

更新日期：2026-07-30（Asia/Taipei）

## 1. 結論摘要

本專案不再把「從隨機策略開始，直接對單一真實遊戲執行長時間 PPO
訓練」視為主要訓練方案。

新的主要實驗路線確定為：

1. 完成目前尚未接完的目標平台方向 reward，恢復全綠測試。
2. 補齊方向符合率、下降階數、傷害、死亡與平台類型等評估指標。
3. 收集規則策略與人工遊玩的結構化示範資料。
4. 先以 Behavior Cloning（BC）學習基本左右控制。
5. 使用 DAgger 式資料聚合，補入模型實際會遇到的失敗狀態。
6. 最後才使用具有 replay buffer 的 DQN／DQfD 式方法進行真實環境微調。
7. 簡化模擬器列為後續獨立階段，不阻塞前述方案。

PPO 可保留為對照組，或在 BC 權重初始化後進行小規模微調，但不再從純隨機
策略直接進入 10,000 步以上長訓。

## 2. 目前實驗結果

目前重要的真實遊戲 PPO 實驗累計約 5,120 步。最新模型的 deterministic
評估結果為：

- 128/128 步全部選擇 `RELEASE_ALL`。
- 完成 2 回合。
- 總 reward 約 `-22.17`。
- 平台水平對齊 reward 累計僅約 `+0.008`。
- 傷害、死亡、idle、平台停留與頂端危險等負 reward 明顯占優勢。

真實環境約只能執行 6～7 control steps/s，選單重設等待期間可能更慢。單一
Windows 遊戲視窗不能安全地在背景接收鍵盤輸入，也不能像 emulator 一樣建立
大量 headless vectorized environments。

因此，目前的瓶頸不是 GPU 或 PPO 更新速度，而是：

- 真實互動資料取得速度太慢。
- PPO 是 on-policy 方法，昂貴的舊資料不能像 replay buffer 一樣長期重複利用。
- 從隨機動作開始探索，浪費大量資料重新發現已知的左右控制規則。
- reward 仍有延遲、稀疏及畫面辨識噪音。
- 回合數與狀態多樣性不足，難以判斷參數調整是否具有可重現效果。

## 3. 最大問題分析

### 3.1 資料規模不足

5,120 個高度相關的單一環境控制步，對具有約數萬參數的策略網路仍是很小的
資料量。即使增加 PPO epoch，模型看到的仍是同一小批相近狀態，無法取代跨
大量回合與平台配置的經驗。

### 3.2 資料利用率不足

PPO 每輪主要使用最新 rollout 更新策略。舊軌跡雖可保留作診斷，卻不會自然
成為之後每次更新都能抽樣的 replay memory。

本專案的每個真實步驟都具有時間、安全與重設成本，因此應優先使用能保存並
反覆利用資料的訓練方法。

### 3.3 初始策略不應是純隨機

專案已經具有：

- 角色、平台、平台種類、血量與事件辨識。
- 268 維時序結構化觀測。
- 安全平台 baseline policy。
- 目標平台與落腳區判斷。
- reward component 與軌跡記錄。

這些資訊已足以建立 observation→action 示範資料。繼續要求 PPO 從隨機策略
自行發現「平台在右側應往右」等基本規則，不符合樣本效率需求。

### 3.4 Reward 對局部策略的誘因不平衡

目前死亡、傷害與各項停留懲罰明顯大於已觀察到的水平對齊 reward。模型可能
把 `RELEASE_ALL` 學成避免立即撞牆或反向懲罰的局部策略，而沒有足夠正訊號
理解如何到達下一平台。

正在完成的 `platform_target_action_reward` 可以提供即時方向教師訊號，但它
只能改善 reward credit assignment，不能單獨解決資料量與 on-policy
資料浪費。

### 3.5 視覺環境具有部分可觀測性與噪音

平台動畫、短暫漏判、track ID 改變、捲動速度估計與角色動作慣性，都可能讓
相近觀測產生不同結果。四幀堆疊能提供基本時序資訊，但現階段不應先擴大模型
或加入複雜 recurrent architecture；資料不足時，更大的模型通常更難穩定。

## 4. 相關 NS-SHAFT 專案

### 4.1 2022 年 DQN 研究

論文
[Application of Deep Reinforcement Learning to NS-SHAFT Game Signal Control](https://www.mdpi.com/1424-8220/22/14/5265)
直接研究 NS-SHAFT，採用：

- 左、右、不動三種離散動作。
- 畫面裁切、灰階化與 `84×84` 縮放。
- 連續四幀輸入。
- CNN DQN 與 target network。
- replay memory 30,000 transitions。
- replay 累積 1,000 筆後開始訓練。
- mini-batch size 32。
- 每 4 frame 更新一次。
- target network 每 10,000 frame 更新。
- ε-greedy 從 1 降至 0.1。
- 探索衰減範圍為 1,000,000 transitions。
- 最終採 20 Hz 取樣，不使用 frame skipping。

研究比較 12、20、32 與 60 Hz，結果以 20 Hz 較佳；reward 版本比較合計使用
約 26,000 回合，最終方法以 2,600 回合中最佳 100 回合的平均下降階數評估。

該研究使用 Cheat Engine 讀取遊戲記憶體中的狀態、生命、座標與樓層。這種
資料取得方式違反本專案安全邊界，因此不可採用；本專案只能參考其 replay、
取樣率、DQN 與 reward 實驗方法。

### 4.2 NS-SHAFT with NEAT

[NS-SHAFT with NEAT 專案報告](https://hackmd.io/@libao3128/S1tc3yGnO)
使用自行重建的遊戲環境，而不是直接控制原始 Windows `.exe`。

其主要設計為：

- 每代 population size 50。
- 12 個結構化輸入，包括角色座標、生命、最近平台邊界、平台種類與牆壁距離。
- 兩個輸出控制左、右；兩者皆未觸發時不動。
- fitness 主要由下降樓層、生命值與尖刺傷害組成。
- 執行大量 generation，並保存 checkpoint 與最佳 genome。

該專案回報曾達 60 層，但其關鍵優勢是自製環境可以大量生成角色與回合，與
本專案只能操作一個真實前景視窗的吞吐量完全不同。

它同樣觀察到彈簧難以脫離、靠牆失敗、尖刺風險取捨與平台隨機性造成策略表現
波動，這些現象可作為本專案場景分類與評估設計的參考。

## 5. 新實驗方案

### 階段 A：完成 reward 與量化基準

先完成目前工作樹中的 `platform_target_action_reward`：

- 下一安全平台在右側：
  - `RIGHT +0.05`
  - `LEFT -0.05`
  - `RELEASE_ALL -0.025`
- 下一安全平台在左側時反向處理。
- 角色已位於安全落腳區間內時，不強迫移動。
- 只使用畫面辨識得到的角色與平台資訊。

完成後執行：

```powershell
python -m pytest -q tests\test_gym_env.py tests\test_config.py
python -m pytest -q
python scripts\check_ppo.py
python -m compileall -q src scripts tests
git diff --check
```

本階段不得啟動訓練，直到所有測試全綠。

### 階段 B：新增評估指標

訓練與 deterministic 評估至少記錄：

- `target_direction_agreement_rate`
- `average_floors_descended`
- `average_damage_segments`
- `death_rate`
- `average_episode_length`
- `average_episode_reward`
- RELEASE／LEFT／RIGHT 分布
- 最長連續同動作步數
- 左右切換次數
- 各 reward component 累計
- 普通、彈簧、輸送帶、翻轉、尖刺平台的落地次數與成功率
- 彈簧平台脫離成功率
- 靠近左右牆時朝場內動作比例
- 頂端危險區脫離成功率

所有方法必須使用相同的硬性步數、回合與時間上限比較。

### 階段 C：建立示範資料集

每筆 transition 建議保存：

```text
episode_id
step
observation
action
reward
reward_components
next_observation
terminated
truncated
events
policy_source
target_platform_id
target_platform_kind
target_signed_offset
timestamp
```

其中 `policy_source` 至少區分：

- `human`
- `baseline`
- `model`
- `corrected`

資料來源分為：

1. 現有 baseline policy 產生的示範。
2. 使用者人工遊玩並同步記錄的示範。
3. 後續模型 rollout 中由人工或規則重新標註的失敗狀態。

資料集必須以完整 episode 分割 train、validation、test，不可將同一回合的相鄰
觀測拆到不同集合。

初期資料目標不是追求單純筆數，而是覆蓋：

- 目標平台在左／右／已對齊。
- 普通平台。
- 彈簧平台。
- 左右輸送帶。
- 翻轉平台。
- 尖刺平台與無安全落點。
- 靠近左右牆。
- 頂端危險區。
- 上升、下降與穩定三種 motion。
- 傷害前後與死亡前狀態。

### 階段 D：Behavior Cloning

第一版模型維持小型 MLP：

```text
268 維 observation
→ hidden layers
→ RELEASE / LEFT / RIGHT logits
```

訓練目標使用三分類 cross-entropy。若動作分布不平衡，可使用 class weight 或
平衡抽樣，但必須同時保留原始分布下的評估結果。

BC 的驗收條件：

- validation 不可塌縮成單一動作。
- LEFT、RIGHT、RELEASE 各自都有合理 recall。
- 目標方向符合率明顯高於隨機策略與舊 PPO。
- 在未見過的完整 test episodes 上仍保持表現。
- deterministic 真實評估至少不劣於 baseline policy。

在 BC 離線指標未達標前，不進行 RL 微調。

### 階段 E：DAgger 式資料聚合

Behavior Cloning 可能在第一次錯誤後進入示範資料未涵蓋的狀態，造成後續錯誤
累積。DAgger 的核心做法是：

1. 讓目前模型產生受限 rollout。
2. 收集模型實際到達的 observation。
3. 由人工或安全規則提供修正 action。
4. 把修正資料加入原資料集。
5. 重新訓練並比較固定 test set。

參考：
[A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning](https://proceedings.mlr.press/v15/ross11a.html)。

本專案可先採離線修正版，不要求使用者即時接管：

- 模型 rollout 仍受前景、F8、related-window、回合與時間限制保護。
- 將死亡前、傷害前、錯失平台與長時間停留的片段標為高優先審查。
- 事後使用 baseline 或人工選擇較佳 action。

### 階段 F：Replay-based RL 微調

BC／DAgger 已建立可用初始策略後，優先研究 DQN／DQfD 式微調：

- 三個離散動作適合 value-based learning。
- replay buffer 能重複利用昂貴的真實 transition。
- 示範資料可以保留在 replay buffer。
- 可提高傷害、死亡、成功下降與人工修正 transition 的抽樣優先度。
- 訓練與資料收集可分離，不必每個 gradient update 都等待遊戲。

DQfD 參考：
[Deep Q-learning from Demonstrations](https://ojs.aaai.org/index.php/AAAI/article/view/11757)。

第一版可先做標準 Behavior Cloning，再決定是否完整實作 DQfD 的 supervised
margin loss、n-step return 與 prioritized replay。

PPO 只保留兩種用途：

1. 作為固定預算的比較基準。
2. 載入 BC 初始化權重後進行小規模微調。

不得直接續訓已塌縮成 `RELEASE_ALL` 的 5,120 步模型。

## 6. 實驗比較設計

至少比較以下四組：

| 組別 | 初始策略 | 訓練方法 | 是否使用舊資料 |
|---|---|---|---|
| A | 隨機 | PPO | 否 |
| B | Baseline | 無訓練 | 不適用 |
| C | 示範 | Behavior Cloning | 是 |
| D | BC／DAgger | DQN 或 DQfD 式微調 | 是 |

每組至少使用多個獨立執行或不同平台序列。不得只取單一最佳回合做結論。

主要指標：

1. 平均下降階數。
2. 中位數下降階數。
3. 死亡率。
4. 平均傷害。
5. 平均 episode reward。
6. 目標方向符合率。
7. deterministic 動作是否塌縮。

次要指標：

- 最佳下降階數。
- 回合長度。
- 平台類型成功率。
- reward component 比例。
- 每取得一個成功下降階數所需的真實環境步數。
- 每一小時真實互動所獲得的改善。

## 7. Go／No-Go 門檻

### 允許進入 Behavior Cloning

- reward 與設定測試全綠。
- transition schema 固定。
- 動作與 observation 時間對齊已用 mock 測試。
- 至少具有多個完整示範回合。

### 允許進入真實 BC 評估

- 離線 test episodes 上不塌縮成單一動作。
- 三個 action 都有有效預測。
- 目標方向符合率高於隨機策略。
- 所有真實輸入仍通過既有安全控制器。

### 允許進入 RL 微調

- BC 或 DAgger deterministic 表現不劣於 baseline。
- 至少一項主要遊戲指標具有可重現改善。
- replay buffer 的 terminal、truncated 與跨回合邊界已驗證。
- 不載入目前已塌縮的 PPO checkpoint。

### 允許 10,000 步以上真實訓練

- 至少兩次短實驗呈現同方向改善。
- deterministic 動作不是 100% 單一動作。
- 平均下降階數提高，或傷害／死亡率明顯下降。
- reward component 數量級合理。
- 沒有新增失焦、額外視窗、錯誤 Enter 或按鍵未釋放事件。

任一條件未滿足時，停止擴大真實互動步數，先回到資料、reward 或評估診斷。

## 8. 模擬器的定位

簡化模擬器可能是長期提高吞吐量的最佳方法，但屬於大型獨立階段。

可能收益：

- 平行執行多個角色。
- 快於實時。
- 任意 reset。
- 進行 curriculum learning。
- 大量測試 reward 與演算法。

主要風險：

- 角色慣性、碰撞與平台動畫不一致。
- 平台生成分布不一致。
- 辨識噪音在模擬器中不存在。
- 模型可能學到無法轉移至原遊戲的策略。

若進入此階段，應使用真實 observation/action logs 校正簡化物理，並加入
domain randomization。模擬器策略仍須通過有限真實環境評估，不得直接假設可
轉移。

## 9. 永久安全限制

所有新訓練方法仍必須遵守：

- 不修改、注入、掛鉤、反編譯遊戲或讀取程序記憶體。
- 不使用 Cheat Engine 或類似方式取得內部狀態。
- 不自動執行來源不明的 `.exe`。
- `auto_launch` 維持預設 `false`。
- 只有已驗證的 `NS-SHAFT / NsShaftClass` 前景視窗可接收輸入。
- related window 出現時立即停止。
- 保留 F8、Ctrl+C 與 PyAutoGUI fail-safe。
- 失焦、例外、終止與正常結束都呼叫 `release_all()`。
- 姓名輸入外部視窗仍不自動處理。
- 自動測試不得操作真實鍵盤、滑鼠或啟動遊戲。
- 實機實驗必須具有確認字串、倒數、步數、回合與時間上限。

## 10. 建議實作順序

下一輪專案工作依序為：

1. 完成 `platform_target_action_reward`。
2. 恢復完整測試全綠。
3. 實作新的評估摘要欄位。
4. 定義並測試 demonstration transition schema。
5. 增加 baseline／人工軌跡的 observation-action 記錄。
6. 建立離線 dataset validator。
7. 實作 Behavior Cloning 訓練與離線評估。
8. 執行一次受限 BC 真實評估。
9. 根據失敗片段建立 DAgger 式修正資料。
10. BC／DAgger 表現合格後，再選擇 DQN／DQfD 微調。

此順序能最大程度沿用現有辨識、觀測、baseline、安全控制與軌跡工具，並避免
在尚未證明有效前投入長時間真實 PPO 訓練。
