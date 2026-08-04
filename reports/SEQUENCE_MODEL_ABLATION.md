# P4.1 S0／S1／S2／S3 Sequence Model Ablation

日期：2026-08-03

狀態：**COLAB SCIENTIFIC `FAIL_STOP_SELECTION`；P4.2 BLOCKED**

## 結論

P4.1 的資料manifest、causal timing、四組模型與三初始化Colab bounded selection均已
完成。S1雖提高mean與Q25，但CVaR25、reach-10與bottom death退化；S2/S3的lower tail
更差。三個enhanced variants全部未過預設Gate，runner正確停止且沒有使用final seeds。
P4.1沒有PASS，P4.2仍被阻擋。

## 正式 Colab 結果

- 來源：`20260803T085551Z_p41_ablation.zip`；archive SHA-256
  `b1fd2291d4b84bafc1a4fba0822341e56b1c075ff963d6aae2f53aeb35bc2926`。
- Runtime：CPU；12個模型均完成300 updates上限與100／200／300 checkpoint selection。
- Dataset manifest與本機完全一致：60 episodes／3,529 rows，hash `fa3e111a...`。
- 狀態：`FAIL_STOP_SELECTION`；`selected_architecture=null`；`final_gate=null`。
- Final seeds 4100～4139：**完全未使用**。

三初始化selected checkpoints的平均closed-loop結果：

| Variant | mean deepest | Q25 | CVaR25 | reach-10 | bottom death | health death | 判定 |
|---|---:|---:|---:|---:|---:|---:|---|
| S0 | 54.83 | 33.58 | 18.27 | 88.3% | 13.3% | 0% | baseline |
| S1 | 62.18 | 44.25 | 17.00 | 85.0% | 18.3% | 0% | FAIL；只保留研究方向 |
| S2 | 60.30 | 14.08 | 7.33 | 76.7% | 50.0% | 0% | REJECT |
| S3 | 14.02 | 5.83 | 3.53 | 40.0% | 98.3% | 0% | REJECT |

相對S0的Gate delta（bottom與oscillation為正才代表改善）：

| Variant | ΔQ25 | ΔCVaR25 | Δreach-10 | bottom reduction | oscillation reduction |
|---|---:|---:|---:|---:|---:|
| S1 | +10.67 | -1.27 | -3.33 pp | -5.00 pp | +0.005/100 steps |
| S2 | -19.50 | -10.93 | -11.67 pp | -36.67 pp | -0.185/100 steps |
| S3 | -27.75 | -14.73 | -48.33 pp | -85.00 pp | -0.345/100 steps |

S1是唯一有訊號的enhanced representation：它在成功軌跡上能走更深，但60個selection
rollouts合計bottom deaths由S0的8次增加到11次，reach-10由53/60降至51/60；不能用
mean +7.35或Q25 +10.67掩蓋最差五回合平均與早期死亡退化。S2有明顯雙峰且一半回合
bottom death；S3的22維compact input不足以支持可靠閉迴路，59/60 bottom death。

## 結果後 protocol audit

本輪另發現兩個不改變FAIL結論、但必須在任何新實驗前修正的工程問題：

1. 全域protocol要求bottom／Q25／CVaR優先於reach，但`selection_key`目前先排reach。
   依正確risk-first順序重排既有候選，只會改變S2 seed 2與S3 seeds 1/2；S1及S0的
   selected checkpoints完全不變，S2/S3仍遠低於Gate，因此不需使用final seeds重判。
2. `direction_switches`只計相鄰LEFT↔RIGHT；若中間有RELEASE便不算。S0三初始化平均
   僅0.005/100 steps，因此要求candidate降低0.10在數學上不可能。下一版需另報忽略
   RELEASE間隔的direction reversal，並把oscillation改為非退化constraint，不可藉此
   回頭宣稱本輪PASS。

### Selection-only checkpoint reanalysis

已完成上述最小修正與無訓練重播：

- risk-first重排後，S0 updates仍為`300/300/200`，S1仍為`300/300/300`；因此archive
  內六個checkpoint正是需要重播的版本。S2 seed 2改選200，S3 seed 1改選300，但其
  非oscillation Gate已大幅失敗，且替代checkpoint未封存，拒絕用重訓補造。
- 逐一驗證variant、initialization、update、dataset hash後，在原4000～4019 selection
  seeds重播。舊scalar metrics、terminal reasons與每回合deepest floors全部完全重現。
- S0 release-bridged reversals/100 steps為`10.20/10.46/9.48`，平均10.05；S1為
  `11.16/10.47/10.55`，平均10.73。S1相對delta為`-0.963/-0.007/-1.068`，三個
  初始化方向全負，平均退化0.679。
- 修正Gate為`FAIL_STOP_SELECTION_CONFIRMED`。S1除了原本CVaR、reach、bottom失敗，
  現在也未過reversal consistency與mean non-regression。沒有訓練、沒有使用final seeds。

Machine-readable evidence：`artifacts/p41_checkpoint_reanalysis_v1.json`。

修正後targeted 25 tests與完整438 tests、compileall、artifact JSON及diff check均PASS。

下一個最小工作改為P4.1 Dataset v2 Gap Audit：先量化凍結v1與current Teacher的版本、
branch、early-bottom及recovery coverage差異，再提出明確升版資料的reliability/coverage
Gate。Audit前不得生成v2、重跑P4.1、使用4100～4139或直接進P4.2。

## 凍結資料與發現的 provenance drift

- Dataset：Spike Teacher Dataset v1，60 episodes／3,529 rows；train／validation／test
  2,327／605／597；Teacher `teacher-observable-safe-platform-v2`。
- SHA-256：
  `fa3e111a6204ac53767824e8d71d1ccf841637976427c410c1e14dff308c7a0a`。
- Current source以相同seeds與CLI重建得到3,571 rows，SHA-256
  `04417d1de89535b16f9ee65a3f5910a476437a3ecb28cb4e4acae9a289975205`，action counts
  亦由`1328/1092/1109`變成`1729/975/867`。
- 這表示Teacher控制程式在資料生成後已演進，但policy version沒有升版。P4.1若在
  Colab重建會同時改變dataset與representation，無法判斷S1/S2/S3增益來源。
- 決策：manifest鎖原資料hash；專用bundle攜帶原JSONL；缺檔或hash不符立即停止。
  新Teacher資料必須另升Dataset v2並重跑reliability/coverage Gate。

Machine-readable evidence：`artifacts/p41_dataset_regeneration_drift.json`。

## 四組模型

| Variant | 輸入 | 模型 | 參數量 |
|---|---|---|---:|
| S0 | 268維既有stack | MLP 268→256→128→3 | 102,147 |
| S1 | 268維＋9維past-action causal state | MLP 277→256→128→3 | 104,451 |
| S2 | 268維24-step sequence | GRU hidden 128→3 | 153,219 |
| S3 | 22維compact＋9維causal state之24-step sequence | GRU hidden 128→3 | 62,211 |

9維state只由模型在`t`以前已選動作重建；row t的snapshot建立後才使用label
`action_t`更新。它不含Teacher phase、target、同一步controller sidecar或任何ID。
S3的22維compact observation只取最新frame的16 core＋最近平台6維，排除frame內
action one-hot。

## Sequence／training protocol

- Sequence length 24、burn-in 8；chunk不跨episode。
- `valid_mask`與`loss_mask`分離；每個episode的每筆label恰好計loss一次。
- GRU hidden與causal state每回合reset；deployment逐step維持hidden。
- Hard cross-entropy、Adam 1e-3、gradient norm cap 5。
- 每組300 optimizer updates；candidate 100／200／300。
- Initialization seeds 0／1／2。
- Selection environment seeds 4000～4019。
- Final environment seeds 4100～4139，只在architecture/checkpoint凍結後使用一次。
- MLP batch 112；sequence batch最多8 chunks。凍結train split有2,327 rows／168
  chunks，兩組都是21 updates完整看完一次資料；每update實際label數保存於artifact。

## Gate

每個enhanced variant相對同初始化S0都先看health safety與collapse。五個primary
delta（越高越好；bottom/oscillation已轉為reduction）至少2/3初始化方向非負，且平均：

- Q25至少+1 floor；
- CVaR25至少+0.5 floor；
- reach-floor-10至少+0.05；
- bottom death rate至少降低0.025；
- direction switches／100 steps至少降低0.10；
- health death維持0、無action collapse。

Selection無候選通過即`FAIL_STOP_SELECTION`且不使用final seeds。Final不通過則
`FAIL_STOP_FINAL`並停止P4.2。Mean／maximum與offline accuracy不能單獨使Gate通過。

## 本機 interface smoke

設定：每組4 updates、seed 0、development simulator seeds 3900／3901、每回合最多
120 steps。這兩個seeds永久只作interface，不能進selection或final。

| Variant | test accuracy | mean deepest | Q25 | CVaR25 | reach-10 | bottom rate | max action share |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | 52.93% | 1.0 | 1.0 | 1.0 | 0% | 100% | 68.18% |
| S1 | 50.25% | 0.5 | 0.25 | 0.0 | 0% | 100% | 67.65% |
| S2 | 37.69% | 9.5 | 7.75 | 6.0 | 50% | 100% | 97.96% |
| S3 | 46.90% | 0.5 | 0.25 | 0.0 | 0% | 100% | 64.71% |

Engineering checks為12/12 PASS：四組finite training、checkpoint save/load及兩回合
closed-loop都完成。S2的短樣本樓層較高，但只有兩回合、bottom rate仍100%，max action
share也接近98% collapse門檻；不得解讀為S2優勝。此表只用來確認pipeline會跑。

## Colab／bundle

- `scripts/run_p41_ablation.py`：預設只preflight；`--interface-smoke`為本機短測；
  `--execute-colab`才跑凍結正式budget。
- `scripts/package_p41_colab.py`：clean commit才建立正式bundle，唯一加入manifest吻合
  的ignored JSONL，排除local config、EXE、影片、weights與其他JSONL。
- `notebooks/ns_shaft_colab.ipynb`最後一格預設`RUN_P41_ABLATION=False`；只允許專用
  bundle。科學FAIL正常保存summary/ZIP且return 0，runtime錯誤才非零。

## 測試與證據邊界

新增測試涵蓋causal reset/timing、compact mapping、split leakage、chunk/mask、每row
一次loss、四模型bounded training、GRU hidden reset、selector reset、checkpoint
round-trip、P4.1 Gate與bundle hash/exclusion。Targeted 21 tests與完整**432 tests**
PASS；compileall、artifact/notebook JSON、notebook末格syntax、absolute-path manifest
preflight與diff check亦PASS。

已執行：Colab 300-update／三初始化selection experiment。未執行：final seeds、P4.2
dataset、DAgger、PPO、DQN、NEAT及任何真實遊戲操作。
