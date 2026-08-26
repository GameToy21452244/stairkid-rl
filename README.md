# StairKid RL

StairKid RL is a real-game-anchored NS-SHAFT simulator and PPO runtime. The
repository retains two explicitly pinned policies, one corrected simulator
physics core, a 60 FPS human viewer, and a guarded Real observation stack.

```text
Real-game calibration
→ handcrafted / real-anchored simulator
→ RL training in the simulator
→ simulator evaluation
→ bounded Real-game validation
```

V2 is retired. There is no default model and no fallback: every model command
requires either `--model v3` or `--model r4`, and the checkpoint SHA-256 must
match `models/manifest.json` before PPO is loaded.

## Install

Python 3.11–3.13 is supported.

```powershell
git clone https://github.com/GameToy21452244/stairkid-rl.git
cd stairkid-rl
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

PPO model execution additionally needs the pinned RL extra:

```powershell
python -m pip install -e ".[rl]"
```

Canonical model binaries are not committed. Place the exact assets at the
paths in `models/manifest.json`; the download workflow will be consolidated in
M3.

## Play the simulator

```powershell
python scripts/play_simulator.py
```

Controls: `A`/Left = LEFT, `D`/Right = RIGHT, release both = RELEASE_ALL,
`R` = reset, `N` = next seed, and `Esc` = exit. Rendering, physics, and default
human control run at 60 Hz. See [Simulator](docs/SIMULATOR.md).

## Run a model in the simulator

```powershell
python scripts/run_simulator_agent.py --model v3
python scripts/run_simulator_agent.py --model r4
```

Both controllers use the same corrected simulator, 268-D observation, and
`Discrete(3)` action contract.

## Real runtime

The default live mode is observation/prediction-only shadow mode:

```powershell
python scripts/run_real_agent.py --model v3
python scripts/run_real_agent.py --model r4
```

A deliberately side-effect-free validation mode is available without a game:

```powershell
python scripts/run_real_agent.py --model v3 --dry-run
python scripts/run_real_agent.py --model r4 --dry-run
```

Dry-run verifies the checkpoint and constructs the perception graph, but does
not construct screen capture or an input controller and sends zero actions.
Actual control additionally requires `--control` and the exact interactive
authorization phrase printed by the runner. See [Real Game](docs/REAL_GAME.md).

## Retained models

- `v3`: Fresh V3 seed 17 at 524288 steps, `STABLE_BASELINE`.
- `r4`: V3.5 R4 seed 142 at 655360 steps, `EXPERIMENTAL_FINAL`. Its formal
  simulator gate failed, it was not promoted, and safety remains unresolved.

Exact hashes and evidence are documented in [Models](docs/MODELS.md).

## Training

Unified training configuration and the single Git-clone Colab notebook are M3
work. No training is performed by any M2 runtime command.

## Tests

```powershell
python -m pytest -q
python -m compileall src scripts tests
```

Architecture and provenance are in [Architecture](docs/ARCHITECTURE.md), the
[branch audit](docs/BRANCH_CLEANUP_AUDIT.md), and the
[consolidation plan](docs/CONSOLIDATION_PLAN.md).
