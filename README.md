# StairKid RL

StairKid RL is a real-game-anchored NS-SHAFT simulator, PPO runtime, and
guarded Windows Real-game interface. It retains one corrected simulator core,
a 60 FPS human viewer, two explicitly pinned policies, shared evaluation, and
one reproducible training workflow.

```text
Real-game calibration
→ handcrafted / real-anchored simulator
→ RL training in the simulator
→ simulator evaluation
→ bounded Real-game validation
```

## Features

- Corrected 60 Hz simulator physics, including flipping, spikes, springs,
  conveyors, platform recycling, health, and top/bottom hazards.
- Human play and PPO inference over the same simulator implementation.
- Exact V3/R4 model identity with fail-closed SHA and PPO-contract checks.
- Guarded Real shadow/control runner with explicit model selection.
- Self-contained Colab V3/R4 training orchestration with three top-level
  SHA-pinned external assets, resume validation, and provenance manifests.
- A retained Python trainer/CLI reference for regression and headless automation.
- A single Git-clone Google Colab notebook; no project source ZIP.

## Install

Python 3.11–3.13 is supported. On Windows, clone to an ASCII-only path to avoid
legacy code-page issues with editable-install metadata.

```powershell
git clone https://github.com/GameToy21452244/stairkid-rl.git
cd stairkid-rl
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Install the pinned PPO stack when running models or training:

```powershell
python -m pip install -e ".[rl]"
```

Windows users can instead double-click `FIRST_RUN_SETUP.cmd`. It creates the
repository-local `.venv`, installs the PPO/runtime dependencies, verifies the
canonical model files, creates the ignored local `config.yaml`, and installs
the included SHA-verified detector templates for the canonical 634x431
NS-SHAFT profile. If the
model Release is private, download its two model assets in the browser and
enter that download directory when prompted; SHA verification remains
fail-closed.

## Fetch models

Canonical binaries are external and are never committed. Until Release URLs
are published, provide a directory containing the exact filenames from
`models/manifest.json`:

```powershell
python scripts/fetch_models.py --all --source-dir C:\path\to\canonical-models
```

No checkpoint is guessed or substituted on failure.

## Play the simulator

```powershell
python scripts/play_simulator.py
```

Controls: `A`/Left = LEFT, `D`/Right = RIGHT, release both = RELEASE_ALL,
`R` = reset, `N` = next seed, and `Esc` = exit. Rendering, physics, and default
human input target 60 Hz.

## Run a policy in the simulator

```powershell
python scripts/run_simulator_agent.py --model v3
python scripts/run_simulator_agent.py --model r4
```

Generic headless evaluation:

```powershell
python scripts/evaluate.py --model v3 --episodes 64 --output runs/v3_eval.json
```

## Run a policy against the Real game

Safe source/model preflight that sends zero actions:

```powershell
python scripts/run_real_agent.py --model v3 --dry-run
python scripts/run_real_agent.py --model r4 --dry-run
```

Bounded shadow mode observes and predicts without dispatching policy actions:

```powershell
python scripts/run_real_agent.py --model v3
python scripts/run_real_agent.py --model r4
```

Live control is never implicit: it additionally requires `--control` and the
model-specific interactive authorization phrase. See `docs/REAL_GAME.md`.

For supervised multi-episode Real evaluation on Windows, double-click:

```text
START_REAL_MODEL_TEST.cmd
```

Before the first Real run, complete `FIRST_RUN_SETUP.cmd`. Users of the same
canonical game build and resolution normally do not need calibration. Run the
passive `CALIBRATE_REAL_GAME.cmd` wizard only if the game build/capture geometry
differs or passive detector preflight reports incompatibility. Calibration
captures the visible NS-SHAFT client and lets the user crop detector templates;
it sends no game keys. The Real launcher refuses missing/placeholder
configuration before displaying the run menu.

The launcher selects V3/R4, Shadow/Control, 1–100 episodes, diagnostics, and
the historically verified `none`/`best`/`all` video modes. Exact `RUN` is only
the outer launch gate; Control still requires the model-specific Python
authorization after a passive preflight. F8 remains the emergency stop.

## Train in Colab

Open `notebooks/StairKid_Training_Colab.ipynb`. The notebook clones GitHub,
checks out `GIT_REF`, installs the reusable environment package, and exposes
the complete V3/R4 PPO orchestration directly in readable cells—including
`PPO(...)`, `model.learn(...)`, resume and asset validation, curricula,
evaluation, checkpointing, and manifests. Use an exact commit/tag for a formal
reproducible run. The default is precheck, and full mode has an explicit
authorization guard.

Local source precheck and the retained reference CLI remain available:

```powershell
python scripts/train.py --target v3 --mode precheck
python scripts/train.py --target r4 --mode precheck
python scripts/verify_project.py
```

## Project structure

```text
configs/          corrected simulator profiles and V3/R4 training presets
models/           canonical model manifest; binaries live in ignored cache
notebooks/        one active Git-clone self-contained training notebook
real_assets/      canonical, SHA-verified Real detector profile
scripts/          current user/developer entrypoints, including guarded Real bulk evaluation
src/stair_agent/  simulator, Real, reference training, evaluation, and core runtime
tests/            current regression suite
training_assets/  SHA-pinned external training-asset manifest
docs/             current architecture, usage, models, and project history
```

## Retained models and safety status

- `v3`: Fresh V3 seed17@524288, `STABLE_BASELINE`.
- `r4`: V3.5 R4 seed142@655360, `EXPERIMENTAL_FINAL`. Its formal simulator
  gate failed, it was not promoted, and safety remains unresolved.

R4's exploratory Real20 result was descriptively worse than historical Fresh
V3 on the retained summary metrics. The samples differ in size, so no
statistical superiority was claimed. `STOP_V3_5` remains unchanged. Neither
model is a default, champion, or fallback.

## Documentation

- `docs/ARCHITECTURE.md`
- `docs/MODELS.md`
- `docs/SIMULATOR.md`
- `docs/REAL_GAME.md`
- `docs/TRAINING.md`
- `docs/PROJECT_HISTORY.md`
