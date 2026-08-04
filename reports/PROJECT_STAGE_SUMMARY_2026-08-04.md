# 專案階段與問題總結（2026-08-04）

## 一句話結論

專案不是卡在「模型訓練不夠久」，而是卡在 **Simulator v0.3可解性Oracle的lower-tail
仍不夠穩健**。在這個上游Gate通過前繼續BC、DAgger、PPO或Colab長訓，只會把不可靠的
環境／Teacher行為放大，所以目前暫停是合理的。

## 整體階段

| 主階段 | 狀態 | 結論 |
|---|---|---|
| Repository／安全控制／schema／validator | PASS | 真實遊戲只看畫面、送一般鍵盤；安全鏈與資料契約完成 |
| Simulator v0.1／v0.2骨架與Colab管線 | 工程PASS | Gymnasium/Pymunk、checkpoint、resume、影片與Colab可執行 |
| Easy curriculum／早期BC0／DAgger | 歷史部分PASS後STOP | 平均可提升，但lower-tail、bottom／health reliability曾退化 |
| 特殊平台mechanism | 工程PASS | 尖刺、彈簧、輸送帶、翻板機制存在；分布與實機fidelity未全通過 |
| Teacher真機P3.6 | PASS | 10回合Gate通過，但仍有lower-tail風險 |
| P4.0 State-aliasing Audit | PASS | causal memory確實降低action conflict |
| P4.1 S0～S3 sequence ablation | FAIL／STOP | S1改善mean/Q25，但CVaR、reach、bottom與反轉退化 |
| Simulator／Real Alignment | FAIL後部分修正 | 找到平台穿透、錯誤場寬與support phase差異；升級至v0.3 |
| Simulator v0.3 edge semantics | 工程PASS | 已改為實機場地、邊緣離台與support ownership |
| v0.3 Observable route intent development | PASS | reach-floor-3由73%升至97%，但上游Oracle holdout先FAIL |
| Oracle v6首次holdout | FAIL／STOP | development 96%，holdout 93%，低於95% |
| Oracle v7全域receding | REJECT | 新development只有76%，bottom 2→22 |
| Oracle v8 terminal-risk guard | CODE／TEST READY，正式Gate中止 | 尚無正式結果；依使用者要求暫停 |

## 目前Oracle問題的演進

### v6：大致有效，但lower-tail不足

- 12-step／24-beam privileged planner；正常route plan整段快取執行。
- Development 13000～13099 reach10 96%。
- 第一次holdout 14000～14099只有93%，4 bottom／3 top，正式FAIL。
- 7個失敗seeds永久退休，不能重判為holdout。

### v7：修法套用範圍過大

- 在7個retired failures上，每decision重規劃救回4/7，看似有希望。
- 全新development 16000～16099卻由v6 96%降至v7 76%。
- 配對只有1個v6 failure被救回，卻破壞21個v6 successes；bottom由2增至22。
- 結論：全域receding造成時間不一致與額外切換，正式REJECT。

### v7 paired audit：單一首次分歧證據不足

- 21 regressions首次分歧為replan RELEASE 11、反向5、fallback／trigger 5。
- 沒有任何單類達預先門檻16/21，狀態`INSUFFICIENT_EVIDENCE_STOP`。
- Regression的v7-v6 action switch平均+4.76，controls只有+1.7；震盪是共同結果，
  但不足以合理選擇commit length，故沒有掃參數。

### Terminal-plan audit：找到窄而乾淨的風險訊號

- v6成功96回合：terminal-plan exposure 0/96。
- v6 top failures：2/2有terminal plan。
- v6 bottom failures：0/2。
- retired `search_found_no_survival`：3/3有terminal plan。
- 因此v8只在planner自己已預測terminal時暫時replan；其他route完全保留v6 cache。

## 暫停時的v8狀態

- Production mode `terminal_guarded`已test-first實作；v6 cached、v7 receding仍保留。
- 正常non-terminal seed的v8與v6 trajectory完全一致測試PASS。
- terminal plan會進入bounded replan、不保存危險suffix；12／24 bounds與snapshot restore
  測試PASS。
- v8與相關Gate共43項targeted tests PASS，compileall PASS。
- 正式runner開始後約42秒依使用者要求中止；沒有artifact、沒有殘留程序。
- 已知完整100-seed v6重播需約76秒，因此本次中止仍在development，未進17000 holdout。
- v8不能宣稱PASS或FAIL；下次若恢復，必須從頭跑一次並增加stage journal以留下明確
  holdout-start證據。

## 尚未解決的核心問題

1. **Oracle lower-tail**：v6在不同seed partition由96%掉至93%，表示可解性證明不穩。
2. **Planner時間一致性**：全域replanning會增加方向／RELEASE切換與bottom death。
3. **Simulator／real gap**：v0.3基本邊緣語意已修，但特殊平台分布與support phase仍未完成
   逐項新版Gate；Simulator不能宣稱1:1。
4. **Student lower-tail**：P4.1 sequence模型與早期BC／DAgger都曾改善平均卻惡化CVaR、
   reach或bottom，不能用長訓掩蓋。
5. **Teacher／Dataset版本可靠性**：真機Teacher、Simulator Teacher與凍結Dataset必須分離；
   舊資料不能因程式更新而重建同名。
6. **實機資料量有限**：現有alignment packet足夠找語意差異，不足以直接當大量BC標籤。

## 為何現在不需要Colab或開遊戲

目前做的是 deterministic Simulator Oracle可解性與控制邏輯Gate，不是神經網路長訓。
本機CPU即可重播固定seeds；開原版遊戲或使用GPU不會修復planner／physics語意。只有上游
Reachability、Oracle、observable Teacher、特殊平台新版Gate都通過，進入多初始化BC／
sequence訓練時才需要Colab。

## 恢復工作的安全選項

1. **建議**：保留目前暫停點，先審查v8實作與protocol，再從頭執行development；PASS才
   允許一次性17000 holdout。
2. 若不再投資privileged Oracle：重新檢討95%可解性Gate與Simulator用途，但不能事後降
   門檻；必須另立新策略文件並說明為何不再以它解鎖Student。
3. 不建議：回到長PPO／DQN、加epochs、直接用實機大量探索、或用retired seeds宣稱成功。

