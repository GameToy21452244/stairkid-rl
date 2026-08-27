# Architecture

The final active tree consolidates verified behavior without changing its
physics, observation, action, reward, or PPO semantics.

```text
Canonical model registry ───────┬── corrected simulator ── human controller
                                │                       └── PPO controller
                                └── guarded Real perception ── shadow/control

Git source ── unified configs ── self-contained Colab orchestration ── outputs
                         └────── retained Python trainer/CLI reference
```

| Layer | Active implementation | Responsibility |
| --- | --- | --- |
| Core | `stair_agent.actions`, `stair_agent.core` | Action identity, 268-D contract, canonical model pins and loading |
| Simulator | `stair_agent.simulator`, `stair_agent.envs`, `stair_agent.sim` | Corrected physics/layout/renderer and PPO adapter |
| Real | detection/tracking modules, `real_observation_pipeline`, `stair_agent.real` | Calibrated frame observations and guarded bounded execution |
| Training | `notebooks/StairKid_Training_Colab.ipynb`, `stair_agent.training`, Fresh V3/R4 curriculum modules | Primary visible Colab orchestration plus reusable/reference training mechanics, assets, resume, and manifests |
| Evaluation | `stair_agent.evaluation` | Generic metrics and JSON reporting |

The action contract is fixed: `0=RELEASE_ALL`, `1=LEFT`, `2=RIGHT`.
Observation is `(268,)`; action space is `Discrete(3)`. Physics advances at
60 Hz while formal policy decisions use the real-system-anchored 8/10/12 Hz
cadence distribution.

Human play and model play call the same corrected simulator. Real dry-run does
not construct capture or input backends. Live control requires both `--control`
and an exact interactive authorization phrase. Training never imports the Real
controller and canonical model paths are write-protected.

The Colab notebook is the primary human-facing training interface and exposes
PPO construction, learning, curriculum transitions, resume/asset validation,
evaluation, checkpointing, and manifest generation directly. `scripts/train.py`
and `stair_agent.training` remain as the validated CLI/reference surface for
regression comparison and headless automation rather than as an opaque backend
that the notebook delegates to.

The active architecture contains no retired-model selection, mixed-policy
routing, automatic model fallback, online learning, promotion gate, or source
package workflow. Historical research is recorded in `PROJECT_HISTORY.md` and
Git history rather than executable parallel architectures.
