# Spike Curriculum v0 Report

日期：2026-07-31

## 結論

**Generator／Reachability／Oracle／Baseline／Dataset gates 全部 PASS。**

本階段沒有訓練模型，也沒有開啟真實遊戲。只將 spikes 作為第一種特殊平台
加入 easy generator；conveyor、spring、flipping 仍不生成。

## 凍結課程

- spike proposal probability：10%。
- 前 3 層：固定 normal。
- 尖刺間至少 5 個 normal。
- spike damage：5；normal heal：1。
- policy／physics：10／60 Hz。
- version：`ns-shaft-sim-v0.2+health-v1+spikes-v1+spike-curriculum-v0`。

五個普通平台可完整恢復一次尖刺傷害，避免 generator 製造 health 必死序列。

## Gate 結果

| Gate | 結果 |
|---|---:|
| Reachability 100 seeds | PASS |
| Reachability 1,000 seeds | PASS |
| Health-safe 1,000 seeds | PASS |
| Realized spike ratio | 5.11%（門檻 4%～7%） |
| Oracle reach floor 10 | 100% |
| Oracle health deaths | 0 |
| Baseline mean floors | 33.07 |
| Plain baseline mean floors | 34.68 |
| Baseline retention | 95.36%（門檻 80%） |
| Baseline reach floor 3 | 99%（門檻 90%） |
| Baseline health deaths | 0 |

可重現 artifact：`artifacts/spike_curriculum_v0_gate.json`。

## Teacher Dataset v0

- seeds：1000～1059，未參與 Gate；
- 60 episodes／3,541 rows；
- train／validation／test：2,367／572／602 rows；
- actions RELEASE／LEFT／RIGHT：1,553／983／1,005；
- spike contacts／damage：16／16；
- health gains：37；
- spike-visible train／validation／test：909／123／232；
- episodes with visible spike：41／60；
- minimum observed health：7；
- validator errors：0。

大型 JSONL 維持 git ignored；summary artifact 可提交。

## 下一步

本機 5-epoch interface smoke 已通過，詳見
`SPIKE_BC0_INTERFACE_SMOKE_REPORT.md`。正式多初始化 seed 的 spike BC0
移到 Colab；若任一 seed 未保留 action diversity、低於 80% baseline 或出現
health death，不追加 epochs，先診斷 platform kind／health signal 與標籤覆蓋。
