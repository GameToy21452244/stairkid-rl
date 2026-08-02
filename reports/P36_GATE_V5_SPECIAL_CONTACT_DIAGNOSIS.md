# P3.6 Gate v5 Special-Contact Diagnosis

日期：2026-08-03

狀態：**Gate v5 aggregate FAIL／P3.6 HOLD；Repair v10 SPECIFIED**

## 1. 結論

使用者觀察的「彈簧上卡住」與「尖刺上失去反應」已由 MP4 逐幀畫面及同 step
controller sidecar 證實。主因不是角色偵測不到，也不是遊戲沒有接受按鍵，而是：

1. 同一特殊平台在捲動／反彈時換了 tracker ID，escape lifecycle 被當成新 contact，
   12-step counter 與規劃狀態反覆歸零；
2. destination、edge momentum 與 fallback direction 每幀互搶，使 LEFT／RIGHT
   頻繁翻轉；
3. stateful action adapter 在每次反轉前插入 `direction_change_brake`／
   `RELEASE_ALL`，視覺上就像暫時失去反應；
4. 現行 max-step 到期會清除 state，但同一平台下一幀又能被重新偵測，因此 nominal
   hard cap 並未限制完整的「語意接觸 episode」。

這是控制狀態 identity／hysteresis 缺陷，不是需要增加 BC、DAgger、PPO 或資料量的
問題。Gate 修復前繼續訓練只會把不穩定 Teacher 行為寫進資料。

## 2. 實機結果

| Run | Gate | 回合 floors | terminal |
|---|---|---|---|
| `teacher_real_micro_20260803_000245_302026` | FAIL | 1, 3, 2 | bottom, top, bottom |
| `teacher_real_micro_20260803_000317_350484` | PASS | 5, 3, 5 | top, top, top |
| `teacher_real_micro_20260803_000508_945764` | FAIL | 4, 2, 6, 3, 5 | top, bottom, bottom, top, top |

11回合合併：mean floors 3.55、median 3、reach-3 8/11、reach-5 4/11、
reach-10 0/11、bottom death 4/11。中間3回合雖通過現有 Gate，該組 EP1 仍有
21-step spring contact；因此「單組 Gate PASS」與特殊平台實際可控性並不等價。

## 3. 影片與 sidecar 證據

逐幀 contact sheets：

- `captures/gate_v5_special_contact_review/spring_ep5_80_104.jpg`
- `captures/gate_v5_special_contact_review/spring_pass_ep1_124_144.jpg`
- `captures/gate_v5_special_contact_review/spikes_ep1_20_31.jpg`
- `captures/gate_v5_special_contact_review/spikes_ep2_45_56.jpg`

合併所有 controller sidecar：

- special escape active：152 steps；
- `direction_change_brake`／`RELEASE_ALL`：50 steps（32.9%）；
- 最長連續 special contact：25 steps；
- contact 內方向變更：50次；
- 同 kind contact 內 raw track ID 變更：11次。

代表案例：最新5回合 EP5 steps 80～104，畫面持續為同一個 spring 區域，但 source
ID 依序為 27、30、34、38、41。每次 ID 變更都把 `special_escape_steps` 重設為1，
方向來源則在 `nearest_edge`、`edge_momentum_guard` 與 `visible_landing` 之間切換。
動作呈現 RIGHT→RELEASE→LEFT→RELEASE→RIGHT 的反覆循環。

Spikes 的 ID 即使穩定仍可失敗。最新 EP1 steps 20～31 在 source 14 上先 LEFT，
edge guard 改 RIGHT，之後又改 LEFT；另一組 EP2 steps 45～56 更在 visible landing
與 edge guard 之間多次反轉。角色持續留在刺面並出現受傷閃爍，與使用者描述一致。

player missing streak 在這些片段不是主要訊號；畫面、raw/tracked observation 與
動作 sidecar 都持續存在。因此本輪不把問題歸因於 detector dropout。

## 4. Repair v10 規格

### 4.1 Semantic special-contact identity

- active contact 期間，使用 kind、水平 bounds overlap／center distance、角色相對
  platform gap 與時間連續性重新關聯 source；raw track ID 只作 telemetry。
- camera scroll 導致絕對 top 改變時，不可單靠 top 或 ID 判定新 contact。
- 重新關聯同一 source 時更新可見 bounds，但不得重設 elapsed steps、已選方向、
  destination stability 或 replan budget。
- 真正 safe landing、角色跨出 source clearance，或明確 safety abort 才結束 episode。

### 4.2 Direction latch and bounded replan

- contact 開始時計算一次 exit direction，至少承諾短期連續方向，避免每幀改向。
- visible landing 必須連續穩定至少2個 observation，且相較現方向有明顯安全優勢，
  才能使用唯一一次 replan。
- `edge_momentum_guard` 只在 contact 初始或持續向不可行邊界移動時介入，不能在
  velocity 因前一次反向後再立刻翻回。
- 真實 wall safety 保持最高優先權；不能為減少 reversal 而允許 outward wall push。

### 4.3 Bounded forced exit

- 到達一般 escape cap 且仍在相同 semantic source 時，進入短而有界的 forced-exit：
  選定一個可行 edge 後不再做 destination replan。
- forced-exit 仍未清除 contact 則記 `special_escape_safety_abort`，釋放按鍵並讓 Gate
  FAIL；同 source 在 cooldown／空間未清除前不得立即重新啟動。
- 這維持硬上限，不用無限方向輸入或無限 restart 掩蓋錯誤。

## 5. Gate v6 與驗證門檻

新增逐 contact telemetry：semantic episode ID、raw source reacquire 次數、contact
duration、direction reversal、replan、same-source restart、forced-exit 與 safety abort。

最低 blocking checks：

- `same_special_source_restart_count == 0`；
- `special_escape_safety_abort_count == 0`；
- 每次 semantic contact direction reversal `<= 1`；
- contact duration 不得超過新的 absolute hard cap；
- controller／transition／video 記錄完整；
- Gate v5 的 outward push、wall re-entry、dropout、departure、bottom death、reach-3
  與 reach-5 門檻全部保留。

Recorded regression 必須涵蓋：ID 27→30→34→38→41 不重設 lifecycle；spikes 的
visible/edge alternation 不得超過一次 replan；max-step 不得 clear 後立即 restart；
safe landing 正確清除；wall guard 仍能立即向內；special contact 不再出現連續改向
造成的多次 brake RELEASE。

## 6. Go／No-Go

- **No-Go**：P4.0 State-aliasing Audit、S0～S3、rare-branch dataset、BC、DAgger、
  PPO、DQN、NEAT 或其他長訓練。
- **Go**：只實作 Repair v10、Gate v6 telemetry、recorded regression 與離線測試。
- Repair v10 全部離線 checks 通過後，只允許一次使用者監督的 fresh bounded Gate v6；
  未全項通過立即停止並診斷，不連續重跑碰運氣。
