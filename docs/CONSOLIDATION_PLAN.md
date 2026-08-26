# StairKid RL Functional Consolidation Plan

This is the M1 plan for M2-M7. It deliberately avoids literal merges of the
historical branches.

## Fixed decisions

- Work only on `cleanup/v3-r4-simulator-final` until validation is complete.
- Use `origin/main` at `f3aae72102be78b480939e794260716e735f8a36`
  as the clean base.
- Use formal R4 source commit
  `4a4d093ccb2591d8f922e4965b01f82211748c0c` as the primary verified code
  reference.
- Use exact Fresh V3 commit
  `213bf77bdd30df20ff5407b20a028618956afeb7` for canonical V3 provenance.
- Use corrected flipping commit
  `0cb23aca7dcb112b2c49347a4777b4234d4ead92`; it matches the audited local
  correction in the relevant physics and regression-test files.
- Port the human simulator from `feature/manual-simulator-60fps-v1` at the
  file level. Never merge its older R3 source tree.
- Do not commit model binaries, experiment artifacts, videos, captures, source
  packages, or training outputs.
- Preserve observation 268-D, `Discrete(3)` action semantics, simulator
  mechanics, 60 Hz physics, policy cadence, PPO behavior, and Real safety
  controls.

## M2 — Main architecture consolidation

### Import policy

Do not restore or merge the entire R4 tree. Its 1,280 cumulative changed paths
include 249 artifacts, 381 diagnostics, 128 reports, 16 notebooks, 186 scripts,
historical V2/Hybrid runtime, and packaging workflows.

Select verified modules by responsibility:

| Final responsibility | Verified source to adapt | Keep behavior | Exclude |
|---|---|---|---|
| Simulator core | R4 `src/stair_agent/simulator/` | Physics, collisions, health, special platforms, recycling, renderer, scenarios | Historical oracle executables and generated evidence |
| Simulator envs | R4 V3/Fresh/V3.5 env/profile modules | 268-D observation, Discrete(3), corrected flipping, cadence | V2/V2.1 envs and configs |
| Human simulator | Local manual branch launcher/docs/test | 60 FPS render/physics/manual control, deterministic flipping test | Duplicate physics or renderer |
| Real core | R4 capture/detection/tracking/live env/reset/control modules | Foreground checks, F8, release_all, deterministic action history, guarded reset | V2/Hybrid selection and fallback |
| Model registry | Refactor R4 registry loader | SHA/timestep/space fail-closed loading | Default model, champion invariant, V2 entries, automatic fallback |
| Evaluation | R4 generic simulator evaluation/metrics | Deterministic inference and machine-readable reports | R1/R2/R3/R4 one-shot gates and promotion machinery |
| Tests | R4 focused regression tests plus manual viewer test | Physics and safety contracts | V2/Hybrid active dependency tests and package-builder tests |

### Target public entrypoints

- `scripts/fetch_models.py --all`
- `scripts/play_simulator.py`
- `scripts/run_simulator_agent.py --model v3|r4`
- `scripts/run_real_agent.py --model v3|r4`
- `scripts/train.py --config configs/training/v3.yaml`
- `scripts/train.py --config configs/training/v3_5_r4.yaml`
- `scripts/evaluate.py`
- `scripts/verify_project.py`

The Real entrypoint must require an explicit model. Dry-run validates registry,
model and pipeline without finding a game window or loading an input backend.
Live control retains a separate exact interactive authorization boundary.

### Model registry

Create exactly two active entries:

- `v3`: Fresh V3, seed 17, 524288 steps,
  `e539ad8e9a39991d738ef9d4113968d933d4f2535e3b08fabe27f3b4ffd9f51e`,
  status `STABLE_BASELINE`.
- `r4`: V3.5 R4, seed 142, 655360 steps,
  `6a9e966ae69c1b3f5610bc5c8a009dcc5519e94fa20d754e54ef0ac445399e10`,
  policy-parameter SHA
  `2bb3910e0f0be001caaafe9e2f8ea2feec186003fca9737988a8d8927a69a104`,
  status `EXPERIMENTAL_FINAL`, formal simulator gate `FAIL`, promotion `NO`,
  exploratory Real20 `COMPLETE`, safety `UNRESOLVED`.

The cache path is local and ignored. Missing assets and every identity mismatch
fail closed. `fetch_models.py` uses pinned release/manual asset locations and
never substitutes another checkpoint.

## M3 — Unified training and Colab

Build a thin config-driven facade over verified R4/Fresh training primitives:

- `src/stair_agent/training/trainer.py`: target dispatch and very small smoke.
- `curriculum.py`: retained V3 and V3.5-R4 curriculum adapters.
- `checkpointing.py`: atomic checkpoint plus SHA/timestep/space/config checks.
- `callbacks.py`: checkpoint/evaluation callbacks.
- `presets.py`: schema parsing and compatibility checks.

Create `configs/training/v3.yaml` and `v3_5_r4.yaml`. Each declares seed,
algorithm, total timesteps, learning rate, environment/profile, distributions,
curriculum, checkpoint interval, evaluation, training assets, and resume rules.
The R4 preset is historical/reproducible and does not imply authorization to
train or promote.

Create one notebook, `notebooks/StairKid_Training_Colab.ipynb`, that:

1. accepts `TRAIN_TARGET`, `REPO_URL`, `GIT_REF`, `OUTPUT_TO_DRIVE`, `RESUME`;
2. clones GitHub and checks out the exact ref;
3. runs `pip install -e .`;
4. executes fail-closed PRECHECK;
5. invokes repository training code;
6. writes outputs and training manifest outside the source checkout.

No source ZIP, `sys.path` hack, embedded PPO implementation, or mixed
source/assets archive remains in the standard workflow.

Training assets receive a separate SHA-pinned manifest and fetch script. Resume
validates checkpoint SHA, timesteps, observation/action spaces, target, config
fingerprint, and required asset provenance before loading.

## M4 — V2 and obsolete cleanup

Remove from the active tree:

- V2/V2.1 configs, envs, training modules, launchers, binaries and registry rows;
- `frozen_v2` runtime dependencies;
- Hybrid router, Hybrid runner and fallback paths;
- V2/Choice Window active analyses, tests and docs;
- R1/R2/R3/R4 one-shot training/evaluation/package scripts;
- source ZIP builders/verifiers, patch chunks, bootstrap workflows and manual
  upload package glue;
- generated artifacts, reports, diagnostics, captures and logs.

Retain only concise historical facts in `docs/PROJECT_HISTORY.md`. Run a scoped
`git grep` audit that permits V2 only in that history document.

## M5 — Validation matrix

Validation is fail-closed and performs no Real action. The training test is a
throwaway smoke only and may not write to canonical model locations.

1. Registry schema and exactly two IDs.
2. V3/R4 exact file and optional package SHA validation.
3. PPO load, timesteps, 268-D observation and Discrete(3) action validation.
4. Simulator import/reset/step, platform generation and corrected flipping.
5. Human simulator headless initialization at 60 Hz.
6. Simulator inference smoke for both models.
7. Real runner dry-run for both models with capture/input backends unconstructed.
8. Training config parse for both targets.
9. Trainer throwaway smoke only.
10. Colab JSON parse and compilation of every code cell.
11. No V2 active dependency and no Hybrid/V2 fallback.
12. Full `pytest`, `compileall`, and `git diff --check`.

Manual simulator play remains unclaimed until the user actually runs
`python scripts/play_simulator.py` and confirms it.

## M6 — Tag and main merge gate

Only after M2-M5 pass:

1. commit the reviewed cleanup branch;
2. create/verify milestone tags at the exact requested commits;
3. push tags successfully;
4. merge cleanup to main without force push;
5. push and re-fetch main;
6. verify remote main tree, model pins, tests and tag targets;
7. create/push `stairkid-final` at the consolidated main commit.

Requested immutable tag targets:

- `v3-fresh-final` -> `213bf77bdd30df20ff5407b20a028618956afeb7`
- `corrected-flipping-physics` ->
  `0cb23aca7dcb112b2c49347a4777b4234d4ead92`
- `v3.5-r4-final` -> `4a4d093ccb2591d8f922e4965b01f82211748c0c`
- `stairkid-final` -> final consolidated main commit

## M7 — Branch deletion gate

No deletion begins until tags and remote main are verified and every M5 gate is
green. Re-run branch containment and unique-tip audit immediately before
deletion. Delete only audited remote historical branches, then re-fetch and
confirm `origin/main` is the only remote branch. Finally remove the cleanup
branch after its commits are confirmed on main.

## Safety flags for M1

```text
FORMAL_TRAINING_PERFORMED=NO
REAL_GAME_EXECUTED=NO
BRANCHES_DELETED=NO
MAIN_MERGED=NO
TAGS_PUSHED=NO
V2_ACTIVE_UNCHANGED_DURING_M1=YES
```
