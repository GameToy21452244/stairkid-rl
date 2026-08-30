# Unified training

The primary human and Colab interface is
`notebooks/StairKid_Training_Colab.ipynb`. Its cells directly expose the full
simulator-only PPO workflow for the two explicit reproducibility targets, `v3`
and `r4`: artifact and resume validation, environment/PPO factories,
curriculum transitions, `model.learn(...)`, deterministic evaluation,
checkpoint saves, and training manifests.

The notebook imports the same corrected simulator, environment, reward, and
curriculum environment classes used by the rest of the project. Those reusable
mechanics remain package code; training orchestration is visible in the
notebook. It never connects to the Real game and cannot promote a checkpoint.

`scripts/train.py` and `src/stair_agent/training/` remain the validated Python
reference implementation and CLI compatibility surface. They are deliberately
retained for regression comparison; the notebook no longer delegates its
training operation to that CLI.

## Source, assets, and outputs

These are deliberately separate:

- Source is a Git checkout. The resolved commit SHA is recorded in every run
  manifest. A project source ZIP is not a supported training input.
- Canonical models and the single R4 training bundle are external SHA-pinned
  files. They are stored only in ignored local caches.
- Outputs are written below `runs/` locally or an explicitly selected Google
  Drive directory. The canonical V3 and R4 cache paths are write-protected.

For a reproducible run, check out an exact commit or release tag rather than a
moving branch:

On Windows, prefer an ASCII-only checkout path; some legacy code pages cannot
decode editable-install metadata containing box-drawing or CJK path symbols.

```powershell
git clone https://github.com/GameToy21452244/stairkid-rl.git
cd stairkid-rl
git checkout <exact-commit-or-tag>
python -m pip install -e ".[rl]"
```

Formal training requires a clean Git worktree by default. `--allow-dirty` is
provided for deliberate local diagnostics, and the dirty state is still
recorded in the manifest.

## Training targets

The target registry contains exactly `v3` and `r4`. There is no default, V2,
historical-round, or automatic fallback target.

### V3

`configs/training/v3.yaml` reproduces the Fresh V3 method from commit
`213bf77bdd30df20ff5407b20a028618956afeb7`:

- PPO `MlpPolicy`, SB3 2.9.0 default architecture
- seeds 17, 42, and 83; default seed 17
- four environments, 1024 rollout steps, batch size 256, 10 epochs
- learning rate 0.0003; gamma 0.99; GAE lambda 0.95
- clip 0.2; entropy 0.01; value coefficient 0.5; max gradient norm 0.5
- staged Fresh V3 self-curriculum ending at 196608, 393216, and 655360
- checkpoints at 98304, 196608, 294912, 393216, 524288, and 655360

The retained canonical V3 is the historical seed-17 checkpoint at 524288. A
training run never overwrites it.

### R4

`configs/training/v3_5_r4.yaml` preserves the final R4 method from commit
`4a4d093ccb2591d8f922e4965b01f82211748c0c`, using corrected flipping
physics provenance `0cb23aca7dcb112b2c49347a4777b4234d4ead92`:

- PPO settings match V3, with seeds 117 and 142
- `edge_landing_penalty = 1.10`
- frozen R1 checkpoint at 589824 plus frozen targeted-bank reuse
- continuation checkpoints at 655360 and 720896
- fixed lanes: ordinary, ordinary, failure, success
- R1 retraining and bank recollection are forbidden

The retained canonical R4 is seed 142 at 655360. The preset exists for
reproducibility and controlled experimentation; it does not reopen the frozen
V3.5 promotion process. `STOP_V3_5` remains in force, the formal simulator gate
is `FAIL`, formal promotion is `NO`, and safety is unresolved.

All requested training parameters were recovered from the audited sources;
both configuration files therefore have an empty `unresolved_fields` list.

## External assets

Model assets:

```powershell
python scripts/fetch_models.py --model v3 --source-dir C:\path\to\models
python scripts/fetch_models.py --model r4 --source-dir C:\path\to\models
python scripts/fetch_models.py --all --source-dir C:\path\to\models
```

Training assets:

```powershell
python scripts/fetch_training_assets.py --target v3
python scripts/fetch_training_assets.py --target r4 --source-dir C:\path\to\assets
```

V3 needs no external training input. R4 needs the exact historical frozen-R1
bundle declared in `training_assets/manifest.json`. The bundle archive SHA is
the single external integrity gate. After extraction, staging still validates
the required seed/checkpoint pairs, checkpoint metadata and ZIP integrity,
targeted-bank schema/content, snapshot integrity, and checkpoint-to-bank
identity. Embedded child hashes are not separate user-managed pins. Canonical
URLs point to the `real-data-preservation-v1` GitHub Release and remain
SHA-verified; no similar checkpoint is substituted.

## Precheck, smoke, and full mode

The CLI supports a UX target or its canonical config path:

```powershell
python scripts/train.py --target v3 --mode precheck
python scripts/train.py --config configs/training/v3_5_r4.yaml --mode precheck
```

A tiny local path check can construct PPO, learn eight simulator steps, save a
throwaway checkpoint, and write a manifest:

```powershell
python scripts/train.py --target v3 --mode smoke --output C:\temp\stairkid-runs
python scripts/train.py --target r4 --mode smoke --output C:\temp\stairkid-runs
```

Smoke outputs are labelled `SMOKE_ONLY`; they are not canonical results.
Full mode additionally requires the exact explicit authorization phrase:

```powershell
python scripts/train.py --target v3 --mode full \
  --authorization AUTHORIZE_STAIRKID_FULL_TRAINING
```

## Resume validation

Resume is explicit:

```powershell
python scripts/train.py --target r4 --mode full \
  --resume C:\path\to\checkpoint.zip \
  --resume-metadata C:\path\to\training_manifest.json \
  --authorization AUTHORIZE_STAIRKID_FULL_TRAINING
```

Before learning, the loader verifies target/config metadata, PPO load,
observation `(268,)`, action `Discrete(3)`, and the permitted starting
timestep. It computes the local checkpoint SHA automatically for provenance;
the user does not provide a resume SHA and the recorded output SHA is not a
resume prerequisite. Remaining work is
`target_total_timesteps - checkpoint.num_timesteps`; the target total is not
mistaken for additional steps. Any incompatibility fails closed.

## Run outputs and manifests

Each run gets a unique directory:

```text
runs/<target>/<run-id>/
  config_resolved.yaml
  training_manifest.json
  checkpoints/
  evaluation/
  logs/
```

The manifest records Git commit/dirty state, dependency versions, target,
seed, start and target timesteps, config SHA, source checkpoint and assets,
observation/action contracts, output checkpoint SHA, timestamps, and whether
the run was `SMOKE_ONLY` or full training.

## Google Colab

Open `notebooks/StairKid_Training_Colab.ipynb`. It is the sole active training
notebook. It clones GitHub, checks out `GIT_REF`, installs the reusable package,
then executes notebook-local training orchestration. The cells visibly map the
canonical YAML values into `PPO(...)`, show the V3 and R4 curriculum paths, and
contain both smoke/full `model.learn(...)` calls.

The top settings cell selects `TRAIN_TARGET`, `TRAINING_MODE`, seed, device,
resume paths, asset source directories, and output location without CLI
arguments. The default mode is `precheck`; smoke is fixed to eight steps. For
R4 full training, set the training-asset source. Smoke requires the canonical
model archives when they are not already cached. Google Drive contains outputs
only. Full mode cannot run from **Run all** without the exact phrase
`AUTHORIZE_STAIRKID_FULL_TRAINING`.

The notebook validates resume target/config metadata, PPO environment spaces,
allowed current timesteps, and remaining-step arithmetic. It computes the
resume checkpoint SHA as output provenance but never asks the user for a resume
SHA. R4 bundle staging visibly validates the single external bundle SHA, ZIP
integrity, seed/checkpoint pairs, bank schema/snapshots, and checkpoint-to-bank
identity without restoring separate child SHA gates.
