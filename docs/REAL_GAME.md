# Real-game runtime

The retained Real stack consists of calibrated screen/object/HUD detectors,
tracking and event logic, 268-D observation construction, shared action
mapping, and guarded Windows controller primitives. Model selection is always
explicitly `v3` or `r4`.

## Side-effect-free dry-run

```powershell
python scripts/run_real_agent.py --model v3 --dry-run
python scripts/run_real_agent.py --model r4 --dry-run
```

Dry-run verifies SHA, loads PPO, checks `(268,)` / `Discrete(3)`, parses the
Real config, and constructs only the frame-to-observation graph. It does not
instantiate `WindowManager`, `ScreenCapture`, `InputController`, or
`SafetyMonitor`; actions sent are exactly zero.

## Shadow mode

```powershell
python scripts/run_real_agent.py --model v3
python scripts/run_real_agent.py --model r4
```

Shadow mode performs bounded live capture and deterministic prediction, but
does not dispatch policy actions. The game must already be in PLAYING state;
menu and reset input remain manual.

## Explicitly authorized control

Add `--control` only when Real control is deliberately intended. The runner
then requires the exact model-specific phrase it prints. Foreground checks,
related-window blocking, F8 emergency stop, hold watchdog, and release-all on
exit/error remain enforced.

There is no automatic model selection, fallback model, ensemble, online
training, or fine-tuning. The single-episode runner never resets automatically.
Repository cleanup and automated tests never execute the Real game.

## Supervised bulk evaluation

On Windows, double-click `START_REAL_MODEL_TEST.cmd`. It requires the
repository-local `.venv\Scripts\python.exe` and never falls back to a global
Python installation. The menu provides:

- exactly `v3` or `r4`, resolved through the canonical model registry;
- Shadow or Control;
- 1–100 bounded episodes;
- optional failure diagnostics;
- the historically audited video modes `none`, `best`, and `all`.

Before the child runner starts, the launcher prints project/model provenance,
the output directory and child command, then requires exact `RUN`. The child
performs a passive capture preflight. Control subsequently requires exact
`AUTHORIZE_V3_REAL_CONTROL` or `AUTHORIZE_R4_REAL_CONTROL`; the launcher never
passes or bypasses this second authorization.

Shadow sends zero actions and asks the supervising user to manually prepare
each episode. Control reuses the existing single-Enter reset coordination,
but only through a separately scoped, explicitly authorized menu capability.
F8, focus loss, tracking loss, exceptions, and termination all release held
keys and stop fail-closed.

Outputs under `runs/real_bulk/` include a session manifest, per-episode JSON
and JSONL, aggregate floor statistics, optional failure snapshots and video,
and a CRC-verified session ZIP. Recorded video includes the historical-style
diagnostic overlay; it does not alter captured observations or actions. In
`best` mode the greatest observed floor wins and the earlier episode wins a
tie, matching the audited historical contract. See `REAL_BULK_RECOVERY.md` for
provenance.
