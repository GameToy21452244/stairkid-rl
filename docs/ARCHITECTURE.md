# Architecture

M2 consolidates verified behavior without redesigning its semantics.

| Layer | Active implementation | Responsibility |
| --- | --- | --- |
| Core | `stair_agent.core.model_registry` | Explicit V3/R4 identity, hashes, PPO compatibility, deterministic prediction |
| Simulator | `stair_agent.simulator`, `stair_agent.envs`, `stair_agent.sim` | Corrected 60 Hz physics, V3 layout, observations, human/PPO controller adapters |
| Real perception | detection/tracking modules and `real_observation_pipeline` | Frames to structured observation; no input side effects |
| Real composition | `stair_agent.real.runtime` | Fail-closed model/perception dry-run in M2 |
| Evaluation | `stair_agent.evaluation.metrics` | Generic descriptive metrics and JSON serialization |

The action contract is fixed: `0=RELEASE_ALL`, `1=LEFT`, `2=RIGHT`. Both model
spaces are `(268,)` and `Discrete(3)`. Simulator physics, observation semantics,
and cadence were imported at module level from canonical R4 source
`4a4d093ccb2591d8f922e4965b01f82211748c0c`; corrected flipping provenance is
`0cb23aca7dcb112b2c49347a4777b4234d4ead92`.

Importing core, simulator, evaluation, or Real modules does not launch the
game. Live imports and I/O occur only after the CLI leaves dry-run; control also
requires an exact interactive authorization phrase. Unified training belongs
to M3; historical/obsolete removal belongs to M4.
