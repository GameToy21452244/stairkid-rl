# Spring Curriculum v0 Gate Report

日期：2026-08-03  
最終狀態：**FAIL_STOP_ORACLE**

## 結論

低比例 spring 已以 test-first 方式加入既有 `normal + spikes` 一般生成器；工程、
Reachability 100／1,000 與兩種 spawn ratio Gate 均通過，但 Oracle-full 只有
71/100 回合實際到達第 10 層，低於預先固定的 95%。依 Gate 順序，本輪在 Oracle
立即停止，沒有執行 Baseline、沒有生成 Dataset v2、沒有訓練模型，也沒有操作原版遊戲。

這次失敗不是 spring 太常出現，也不是 health sequence 不安全。100 個 Oracle 回合中，
沒有遇到 spring 的 65 回合全部到達第 10 層；遇到 spring 的 35 回合只有 6 回合成功，
其餘 29 回合全部 top death。失敗回合各有 2～4 次 `spring_contact`，顯示現有
190 px/s 強彈跳、平台向上捲動、top termination 與 Oracle 離台控制之間有系統性衝突。

目前證據只能證明「spring-conditioned Oracle path 不可靠」，還不能單靠 aggregate
結果判定應修改 spring 物理或 Oracle escape。190 px/s 本來就沒有真機 telemetry
校正，因此不應直接為了過 Gate 降低彈力，也不應只加一條未驗證的逃離 heuristic。

## 凍結實驗

- Protocol：`reports/SPRING_CURRICULUM_V0_PROTOCOL.md`，先於實作與執行建立。
- Candidate：10 Hz／60 Hz physics、spike proposal 10%、spring proposal 6%。
- 前 3 層 normal；spring 前 3 個平台必須全是 normal；兩個 spikes 間最後 5 個
  平台必須全是 normal，spring 不算回血。
- Reachability：9000～9099及9000～9999。
- Oracle：10000～10099，最多600 steps／episode，target deepest floor 10。
- 保留的 fresh reliability seeds 6000～6099未使用。
- Artifact：`artifacts/spring_curriculum_v0_gate.json`，拒絕覆寫。

## Gate 結果

| Gate | 結果 | 證據 |
|---|---:|---|
| Engineering／feature-off | PASS | 100 seeds序列完全相同；前置normal、gap、每層一平台全通過 |
| Reachability 100 | PASS | 可重現、幾何可達、health safe |
| Reachability 1,000 | PASS | 9,000 platforms；0 unreachable／0 unsafe |
| Spring ratio | PASS | 243/9,000 = 2.70%，門檻2%～5% |
| Spike retention ratio | PASS | 432/9,000 = 4.80%，門檻3.5%～7% |
| Oracle spring coverage | PASS | 35個episodes有spring contact，門檻至少20 |
| Oracle health safety | PASS | 0 health death |
| Oracle reach floor 10 | **FAIL** | 71%，門檻至少95% |
| Baseline retention | NOT RUN | Oracle FAIL後依序停止 |

Oracle 共6,635 steps，動作分布為RELEASE 2,928、LEFT 1,871、RIGHT 1,836，最大
action share 44.13%，沒有單動作collapse。Mean deepest floor 8.67、median 10、
Q25 8.75、CVaR25 4.84；終局為71 `target_reached`、29 `top`。

## 根因界線

已支持：

- 失敗與 spring encounter 完全共現；未遇spring的65/65全部成功。
- 29個失敗都是top death，不是bottom、health或timeout。
- 失敗前重複接觸同一類spring 2～4次，和使用者先前觀察的「在彈簧反覆彈」一致。
- Reachability目前只驗幾何與health，沒有把spring-induced top hazard納入，因此
  Reachability PASS不能覆蓋Oracle FAIL。

尚未證明：

- 190 px/s是否高於真機有效彈跳；
- 問題主要來自physics、top boundary/camera semantics，還是Oracle缺少spring escape；
- 一條spring-specific escape rule能否改善而不傷害normal/spike路徑。

## 下一個最小實驗

下一輪先凍結 **Spring Failure Trace／Fidelity Audit**，不重用10000～10099作選模：

1. 對既有失敗產生逐step trace，保存player y/vy、spring/source、target safe interval、
   action、contact count、camera scroll與top margin；只作診斷。
2. 用既有real alignment packet的spring短序列比較rising duration、vertical response、
   repeated-contact與top-margin語意；若獨立contact不足，再明確提出最小補充資料需求。
3. 分離兩個假說：physics/top semantics與Oracle spring escape。只有可觀測證據支持時，
   才預先凍結一個候選與全新seeds重跑Oracle Gate。
4. Oracle達95%後才准第一次執行Baseline；未通過前conveyor、flipping、Dataset v2及
   Student／純RL長訓維持BLOCKED。

## 驗證

- 新增spring curriculum／event coverage tests，相關24 tests PASS。
- 完整回歸 **475 tests passed in 69.02s**。
- 正式artifact完整保存config、seed ranges、protocol/source/git fingerprints。
- 本輪未開啟遊戲、未送鍵、未產生dataset、未啟動任何模型訓練。
