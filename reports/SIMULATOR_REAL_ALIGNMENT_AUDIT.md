# Simulator / Real-Game Alignment Audit

日期：2026-08-03  
最終狀態：**FAIL_STOP_SIMULATOR_REAL_ALIGNMENT**

## 結論

真機 alignment packet 已通過完整性與coverage，控制時間及左右鍵反應方向也與
Simulator大致相容；但目前仍不能生成正式 Dataset v2 或啟動 Student 訓練。

阻擋原因有兩個：

1. 真機已實際觀測到 normal、spikes、spring、conveyor、flipping 五種重要平台，
   目前 Simulator Teacher 診斷／訓練生成器只會產生 normal與spikes。Spring、conveyor、
   flipping雖有獨立mechanism scenario，並未進入一般episode分布。
2. 真機把bounce rising期間的幾何重疊長時間視為同一support。主要run有125/308
   records（40.58%）為rising-support persistence，最長11步；episode 3 step 47可確認
   同一source 12連續跨滿8個departure steps並觸發timeout，step 50又從同一source重啟。
   Simulator相同行為只有311/1838（16.92%）、最長2步，且0 timeout／0 restart。

因此，使用者觀察到的「可以從一側下去，卻先往另一側再回頭」不是單純視覺錯覺；
主要run有5次同一次support departure內的方向反轉，Simulator為0。它未必每次都造成死亡，
但若直接當BC label，會把不一致的短序列教給Student，增加猶豫、煞車與反覆換向風險。

## 凍結範圍

- Protocol：`reports/SIMULATOR_REAL_ALIGNMENT_AUDIT_PROTOCOL.md`，先於執行建立。
- 主要真機資料：`teacher_real_micro_20260803_205952_924961`，3 episodes／308 records，
  `PASS_REAL_ALIGNMENT_PACKET`。
- 次要低表現對照：`teacher_real_micro_20260803_205750_137469`，3 episodes／136 records；
  未因表現較差而排除。
- Simulator：`departure_delayed` profile、目前spike Teacher config、seeds 8000～8029、
  30 episodes／1,838 records、最多300 steps。
- 保留的fresh reliability seeds 6000～6099未使用。
- 本輪沒有開啟／控制原版遊戲，也沒有訓練模型。

權威machine-readable結果：`artifacts/simulator_real_alignment_audit_v3.json`。

## Gate結果

| Check | 結果 | 證據 |
|---|---:|---|
| Primary packet PASS | PASS | 3 episodes／308 records，Integrity與Coverage已通過 |
| 真機cadence 70～140 ms | PASS | median 125 ms |
| Simulator cadence在真機±25% | PASS | 100 ms，相差20% |
| LEFT/RELEASE/RIGHT各至少10筆 | PASS | 真機97/108/102；Simulator 422/1069/347 |
| 真機左右反應方向正確 | PASS | median delta-vx LEFT -44、RIGHT +63.27 px/s |
| Simulator左右反應方向正確 | PASS | median delta-vx LEFT -104.8、RIGHT +104.8 px/s |
| 重要平台皆在Simulator分布啟用 | **FAIL** | 缺spring、conveyor、flipping |
| 無confirmed support-phase alias | **FAIL** | episode 3 step 47 timeout具有8/8 rising-support persistence |
| support-departure timeout=0 | **FAIL** | 1 |
| same-support restart=0 | **FAIL** | episode 3 step 50，source 12 |

整體依預先固定停止條件判為`FAIL_STOP_SIMULATOR_REAL_ALIGNMENT`。

## 時間與action response

真機loop實際median為125 ms，雖設定capture target為15 Hz，受到80 ms action duration及
擷取／推論成本影響，實際接近8 Hz。Simulator目前10 Hz，時間差20%，落在本Gate的25%
容許範圍。這代表控制節奏不是這次最先阻擋的問題。

方向鍵的median delta-vx符號一致，但Simulator動量變化較強：絕對median ratio約
LEFT 2.38、RIGHT 1.66。依protocol，視覺velocity有追蹤雜訊，這些比例只作後續物理校正
依據，沒有用單一尺度事後阻擋或放行。

## 平台分布差異

| 資料 | normal | spikes | spring | conveyor | flipping |
|---|---:|---:|---:|---:|---:|
| 主要真機重要context records | 219 | 23 | 7 | 15 | 52 |
| 次要真機重要context records | 115 | 11 | 0 | 7 | 0 |
| Simulator重要context records | 1517 | 77 | 0 | 0 | 0 |

Simulator physics已有spring／conveyor／flipping的固定scenario與feature flag，但一般
generator的`next_platform_kind()`只抽normal與spikes。故「功能已寫好」不等於「Teacher
資料分布已對齊」，這也是純RL現在直接大量探索仍會學歪的原因：agent只會最佳化它實際
看見的模擬分布，沒看過的實機機制不會憑空學會。

## Support phase與反向操作

| 指標 | 主要真機 | 次要真機 | Simulator |
|---|---:|---:|---:|
| records | 308 | 136 | 1838 |
| rising-support records | 125 (40.58%) | 61 (44.85%) | 311 (16.92%) |
| max rising-support streak | 11 | 15 | 2 |
| departure timeout | 1 | 0 | 0 |
| same-support restart | 1 | 0 | 0 |
| ≤3-step directional reversals | 27 (8.77%) | 9 (6.62%) | 93 (5.06%) |
| target-conflicting directional steps | 16 (5.19%) | 3 (2.21%) | 128 (6.96%) |
| 同一次departure方向反轉 | 5 | 0 | 0 |

Target-conflicting比例本身不是充分根因：Simulator甚至略高，卻沒有departure timeout。
真正有辨識力的是「rising仍持續擁有同一support」加上「同一次departure方向反轉」的
時間序列。主要run episode 3的關鍵序列為：

- step 39開始從source 12向RIGHT離台；
- step 40～47 player已是rising，但nearest/support仍持續判為source 12；
- step 43因target safe interval已移到左側，先RELEASE brake，再改LEFT；
- step 47 pre-departure steps=8，觸發`support_departure_safety_abort`；
- step 48～49 cooldown後，step 50又從source 12重新開始LEFT departure。

這證明timeout不是單純tracker統計誤報，而是phase語意與真機bounce/scroll時序不一致。

## 對「不用Teacher、直接純RL」的影響

純RL不是被永久排除，而是現在不適合當第一步。YouTube常見案例通常能直接取得遊戲狀態、
reward、快速reset，並以多環境加速到數百萬步；本專案只能從Windows畫面估測部分狀態，
真機約8次決策/秒，死亡/reset成本高，而且舊PPO已出現全RELEASE或全RIGHT collapse。

更重要的是，純RL不會自動修復本報告發現的reality gap。如果在只生成normal/spikes、
rising-support最多2步的Simulator大量訓練，模型可能在模擬器分數很好，到了實機卻第一次
遇到spring/conveyor/flipping及11步support alias。Teacher的用途是提供安全bootstrap、
branch語意及可稽核baseline；等環境分布與觀測對齊、Student先取得可用初始化後，roadmap
仍允許在Simulator做bounded RL fine-tuning，再用少量實機回合驗證。

## 決策與下一個最小工作

本輪不放寬Gate、不生成Dataset v2、不啟動Student或任何長訓練。下一輪應依序：

1. 先建立Simulator mixed-special distribution v0 protocol：分別凍結spring、conveyor、
   flipping的低比例與最小間隔，重新跑Reachability／Oracle／Baseline，不直接混成長訓練。
2. 對real Teacher建立phase-aware support ownership的shadow replay：rising只保留最多1～2步
   contact grace，之後必須釋放source ownership；先用現有308+136 records計算會影響哪些
   decisions，不直接送鍵。
3. 只有shadow不增加普通／特殊平台安全衝突，才建立一個test-first Teacher候選並跑一次
   bounded真機Gate；timeout、restart及同departure反轉仍必須為0。
4. 上述兩項都過Gate，才重新產生版本化Dataset v2，之後再比較Teacher-bootstrap Student
   與固定預算pure-RL-from-scratch對照。

這條路保留純RL作公平對照與後期fine-tuning，但不讓它在尚未對齊的環境中消耗大量算力。

## 驗證

- 新增alignment audit tests：6 passed。
- Alignment／profile相關：14 passed。
- 完整回歸：468 passed in 63.52s。
- `compileall`、artifact JSON/source fingerprint及`git diff --check`通過。
