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

### First run on Windows

Double-click `FIRST_RUN_SETUP.cmd`. It uses the Windows `py` launcher only to
create `.venv` with Python 3.11–3.13, then all project commands use that local
interpreter. It installs `.[rl]`, initializes the local-only `config.yaml`, and
verifies both canonical model archives. No Real window, capture, controller,
or action backend is constructed during setup.

The repository now ships a small canonical detector profile under
`real_assets/canonical_v1/`. `FIRST_RUN_SETUP.cmd` SHA-verifies its eight
templates and copies any missing files into the ignored local
`captures/templates/` directory. Existing user calibration is never
overwritten. The canonical profile targets the project-standard NS-SHAFT build
and 634x431 client capture, so a same-build user normally proceeds directly to
`START_REAL_MODEL_TEST.cmd`.

Use `CALIBRATE_REAL_GAME.cmd` only when using a different game build/geometry,
or when passive preflight reports detector incompatibility. Its menu captures
one passive client frame per selected object and lets the user crop replacement
dialog/platform templates. It never sends keyboard input. Missing templates
still stop the Real launcher with `REAL_SETUP_REQUIRED` before its model menu.

The shipped example profile contains the standard `NS-SHAFT` title,
`NsShaftClass`, 634x431 reference geometry, HUD/playfield calibration, and
local template paths. Menu reset rectangles remain unset so a fresh clone uses
the supervised manual episode reset path instead of unverified menu input.

The canonical templates were recovered from the preserved
`real-data-preservation-v1` evidence and revalidated offline on 46 held-out
Real videos (6,716 frames): player detection 97.25% and platform-context
detection 99.29%. Those videos contain historical diagnostic overlays, so the
per-type counts are diagnostic rather than manual ground truth. No Real input
was sent during asset construction or validation. Full provenance and per-file
SHA values are in `real_assets/canonical_v1/manifest.json`.

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
passes or bypasses this second authorization. The child runner prints the
required phrase in a dedicated `TYPE EXACTLY (case-sensitive)` block and also
includes it directly in the input prompt, so the user never has to guess what
`Authorization` means. A mismatch rejects control and releases all keys.

Shadow sends zero actions and asks the supervising user to manually prepare
each episode. Control reuses the existing single-Enter reset coordination,
but only when all menu focus coordinates exist and only through a separately
scoped, explicitly authorized menu capability. If the local Real config lacks
that calibration, Control safely falls back to supervised manual reset: the
user starts each episode and types exact `READY`, while the runner sends no
menu/reset input. Because typing `READY` necessarily focuses the terminal, the
runner then releases all keys, focuses only the already-verified NS-SHAFT hwnd,
waits briefly, and repeats focus/player/platform safety checks before starting
the episode. Failure to refocus or revalidate remains fail-closed. F8, focus
loss, tracking loss, exceptions, and termination all release held keys and
stop fail-closed.

Outputs under `runs/real_bulk/` include a session manifest, per-episode JSON
and JSONL, aggregate floor statistics, optional failure snapshots and video,
and a CRC-verified session ZIP. Recorded video includes the historical-style
diagnostic overlay; it does not alter captured observations or actions. In
`best` mode the greatest observed floor wins and the earlier episode wins a
tie, matching the audited historical contract. See `REAL_BULK_RECOVERY.md` for
provenance.
