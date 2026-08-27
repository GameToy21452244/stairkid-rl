# Unified training

StairKid uses one simulator-only PPO trainer with two explicit reproducibility
targets: `v3` and `r4`. The trainer imports the same corrected simulator core
used by the human and model viewers. It never connects to the Real game and it
cannot promote a checkpoint.

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
identity. Embedded child hashes are not separate user-managed pins. GitHub
Release URLs are intentionally marked unpublished until the asset is actually
released; no similar checkpoint is substituted.

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
notebook. It clones GitHub, checks out `GIT_REF`, installs the repository, runs
one precheck, and invokes this CLI. For R4, set the training-asset source; an
R4 smoke also needs its canonical model source. Google Drive contains outputs
only. Full mode cannot run from **Run all** without
`AUTHORIZE_STAIRKID_FULL_TRAINING`.
