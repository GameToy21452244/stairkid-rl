# Real-game runtime

The retained Real stack consists of the calibrated screen/object/HUD
detectors, tracking and event logic, 268-D observation construction, action
mapping, and guarded Windows controller primitives from canonical R4 source.
Historical V2 and Hybrid routing are not dependencies of the active runner.

## M2 safe validation

```powershell
python scripts/run_real_agent.py --model v3 --dry-run
python scripts/run_real_agent.py --model r4 --dry-run
```

The model argument is mandatory. Dry-run validates SHA, loads PPO, checks
`(268,)` / `Discrete(3)`, parses the Real config, and constructs only the
side-effect-free frame-to-observation graph. It does not instantiate
`WindowManager`, `ScreenCapture`, `InputController`, or `SafetyMonitor`, and it
sends zero actions.

Dry-run is the mode used for M2 automated validation; it never requires a game
window and cannot send input.

## Shadow and explicitly authorized control

```powershell
python scripts/run_real_agent.py --model v3
python scripts/run_real_agent.py --model r4
```

These commands run one bounded shadow episode: capture and prediction are live,
but policy actions are not dispatched. The game must already be in PLAYING and
menu/reset input remains manual.

Adding `--control` enables action dispatch only after the user types the exact
model-specific authorization phrase shown by the runner. It retains the
foreground, related-window, F8 emergency-stop, hold-watchdog, and release-all
guards from the canonical Real stack. There is no automatic reset, V2, Hybrid,
fallback, ensemble, or online learning. No Real game was executed during M2.
