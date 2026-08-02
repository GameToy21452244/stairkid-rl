# Control Frequency Experiment

日期：2026-07-30

固定 physics 60 Hz；相同 100 easy seeds 比較 policy 8／10／12 Hz。
真實遊戲仍維持約 8 Hz，本實驗不會送出真實輸入。

| Hz | candidate | mean floors | median | 95% CI | reach 3 | reach 10 | oscillation | steps/s |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 8 | oracle_full | 10.000 | 10.000 | [10.000, 10.000] | 100.0% | 100.0% | 0.4385 | 1621.6 |
| 8 | baseline | 29.750 | 30.000 | [26.079, 33.621] | 99.0% | 82.0% | 0.0000 | 1552.9 |
| 10 | oracle_full | 10.000 | 10.000 | [10.000, 10.000] | 100.0% | 100.0% | 0.3174 | 1743.3 |
| 10 | baseline | 34.680 | 34.000 | [31.840, 37.610] | 100.0% | 93.0% | 0.0000 | 1755.0 |
| 12 | oracle_full | 10.000 | 10.000 | [10.000, 10.000] | 100.0% | 100.0% | 0.2648 | 1932.4 |
| 12 | baseline | 33.480 | 34.500 | [30.610, 36.330] | 100.0% | 93.0% | 0.0000 | 1900.2 |

`missed_platform_proxy_rate` 目前以 bottom death 代理；
`brake_too_late` 無可靠直接觀測，CSV 明確標為 `not_observable`，
不可當成 0。控制率選擇需依整體 gate 結果，不只看 throughput。
