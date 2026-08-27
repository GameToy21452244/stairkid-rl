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
training, fine-tuning, or automatic reset. Repository cleanup and automated
tests never execute the Real game.
