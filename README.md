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

Canonical model binaries are not committed. Fetch exact local assets with
SHA verification (the current manifests support local source directories while
Release URLs remain unpublished):

```powershell
python scripts/fetch_models.py --all --source-dir C:\path\to\canonical-models
```

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

The single active notebook is
[`notebooks/StairKid_Training_Colab.ipynb`](notebooks/StairKid_Training_Colab.ipynb).
It clones this Git repository directly, checks out a branch/tag/exact commit,
installs the package, performs precheck, and invokes the shared trainer. No
project source ZIP is required.

Local precheck and explicitly bounded smoke commands are also available:

```powershell
python scripts/train.py --target v3 --mode precheck
python scripts/train.py --target r4 --mode precheck
python scripts/train.py --target v3 --mode smoke --output C:\temp\stairkid-runs
```

Training targets are exactly `v3` and `r4`. Full mode requires an explicit
authorization phrase, writes a provenance manifest, never writes canonical
model paths, and never controls the Real game. See [Training](docs/TRAINING.md).

## Tests

```powershell
python -m pytest -q
python -m compileall src scripts tests
```

Architecture and provenance are in [Architecture](docs/ARCHITECTURE.md), the
[training guide](docs/TRAINING.md), the
[branch audit](docs/BRANCH_CLEANUP_AUDIT.md), and the
[consolidation plan](docs/CONSOLIDATION_PLAN.md).
