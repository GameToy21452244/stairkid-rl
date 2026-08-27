# Simulator

The human viewer and PPO runner share the exact same corrected simulator core:

```text
Fidelity V3/V3.5 profiles and V3 layout generator
                    ↓
       ShaftSimulator + SimulatorRenderer
              ↙               ↘
    human keyboard             PPO policy
```

There is no second demonstration physics implementation.

## Human viewer

```powershell
python scripts/play_simulator.py
```

- `A` / Left Arrow: LEFT (`1`)
- `D` / Right Arrow: RIGHT (`2`)
- neither or both: RELEASE_ALL (`0`)
- `R`: reset current seed
- `N`: next seed
- `Esc`: clean exit

The default is 60 FPS rendering, 60 Hz physics, and 60 Hz human input. For a
human comparison while rendering remains 60 FPS:

```powershell
python scripts/play_simulator.py --control-hz 8
python scripts/play_simulator.py --control-hz 10
python scripts/play_simulator.py --control-hz 12
```

Formal RL always uses 60 Hz physics but policy decisions at 8/10/12 Hz. Those
cadences do not mean that the game or physics runs at 8–12 FPS: physics advances
at 60 Hz between decisions.

## Corrected flipping diagnostic

```powershell
python scripts/play_simulator.py --flipping-test
```

This deterministic scenario uses the existing scenario helper and runtime
state machine. READY and TRIGGERED platforms remain active/collidable. After
the active duration, INACTIVE is dark gray, noncollidable, and cannot support
the player. Only `_update_flipping_states()` restores READY after the complete
inactive duration; global episode elapsed time cannot override INACTIVE.

Automated no-window smoke:

```powershell
python scripts/play_simulator.py --headless-smoke --flipping-test --control-hz 60
```

## PPO simulator runtime

```powershell
python scripts/run_simulator_agent.py --model v3
python scripts/run_simulator_agent.py --model r4
```

The loader verifies the selected canonical SHA and PPO contract before
deterministic inference. No fallback, training, or Real-game I/O is available.
