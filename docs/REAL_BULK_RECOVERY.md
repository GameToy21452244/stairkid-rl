# Real Bulk Evaluation Recovery Audit

This feature restores the reviewed Windows Real-evaluation workflow without
restoring retired models or research orchestration. The current canonical model
registry remains the only model source of truth (`v3` and `r4`).

## Historical sources

| Historical source | Commit | Recovered contract |
|---|---|---|
| `START_REAL_MODEL_TEST.cmd` and `scripts/run_real_model_launcher.py` | `17a7057a8ab05849ef9d1b236868ab2bc1aaf859` | UTF-8 `cmd.exe` launcher, repo-relative paths, interactive plan, exact `RUN` gate, separate child runner |
| `START_BULK_FRESH_V3_REAL_EVAL_V1.cmd` and bulk entrypoint | `cf6cbf56bda7c4a90f37b592a9fd1f03554c84d3` | Windows path checks, canonical checkpoint verification, passive preflight, session reports and CRC-checked ZIP |
| `src/stair_agent/bulk_real_evaluation.py` and `final_guarded_real_control.py` | `204e0f34e4c70259fbfa90e80d87d941d984af73` | bounded multi-episode lifecycle, JSONL telemetry, failure diagnostics, F8/focus/tracking fail-closed behavior, reset/input capability separation |
| `src/stair_agent/real_video_retention.py` | `b6b0637a1a20ae317430ea4641e5a6a93eb4b271` | confirmed video modes `none`, `best`, `all`; best means greatest observed floor, with an earlier episode winning ties |

## Compatibility decisions

- Retired V2, Hybrid, R1, R2 and R3 selectors are not restored.
- Model lookup and archive integrity come from
  `stair_agent.core.model_registry`; there is no fallback.
- The historical 1–30 batch bound is safely generalized to 1–100 while each
  episode remains bounded by steps and wall-clock duration.
- The launcher uses only the repository-local `.venv`; historical sibling-venv
  fallback is intentionally removed.
- Shadow mode never sends input. Control keeps two independent gates: exact
  `RUN` in the launcher and exact model-specific Python authorization after a
  passive preflight.
- Automatic reset is retained only through the existing single-Enter resetter
  and a narrow, explicitly authorized menu capability. It is never training or
  unattended model adaptation.
- `scripts/evaluate.py` remains simulator-only.

The recovered path performs deterministic inference only. It contains no
`learn`, gradient update, replay-buffer update, or model save operation.
