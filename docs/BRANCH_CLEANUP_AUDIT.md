# StairKid RL Branch Cleanup Audit

Audit date: 2026-08-27 (Asia/Taipei)

This document is the M1 inventory for functional consolidation. No branch was
merged or deleted while producing it.

## Audit baseline and method

- Repository: `https://github.com/GameToy21452244/stairkid-rl.git`
- Cleanup branch: `cleanup/v3-r4-simulator-final`
- Cleanup base: `origin/main` at
  `f3aae72102be78b480939e794260716e735f8a36`
- Remote refs were refreshed with `git fetch origin --tags` before inspection.
- There are 49 remote branch refs including `origin/main`; the tables below
  cover all 48 historical remote branches.
- For every historical remote branch, `git merge-base` with `origin/main` is
  `f3aae72102be78b480939e794260716e735f8a36` and
  `git merge-base --is-ancestor <branch> origin/main` is false.
- `U commits` means `git rev-list --count origin/main..<branch>`.
- `Files` means changed paths in `merge-base..<branch>`. It is cumulative and
  is not a count of branch-exclusive features.
- `Exclusive` means commits reachable from that remote tip and from no other
  historical remote tip or `origin/main`.
- `git cherry origin/main <branch>` reported no patch-equivalent commits for
  any historical branch; its plus count equals `U commits` in every row.

The source audit used `git merge-base`, `git merge-base --is-ancestor`,
`git rev-list`, `git log`, `git diff`, `git cherry`, `git branch --contains`,
`git ls-tree`, and targeted `git grep` queries.

## Functional classification

The `Class` column encodes the required semantic fields:

| Class | Current simulator | Current Real runtime | Current training | Useful tests | Useful docs | Interpretation |
|---|---|---|---|---|---|---|
| SIM-H | No; historical ancestor | No | No | Yes, already inherited by R4 | Yes, historical | Simulator/oracle evolution superseded by V3/V3.5 R4. |
| TRAIN-H | No | No | No; historical curriculum | Yes, already inherited | Yes, historical | Old Colab/curriculum workflow, not final training UX. |
| REAL-H | Inherited only | No; historical ancestor | No | Yes, generic safety regressions inherited by R4 | Yes, historical | Generic capture/control/reset work is already in the later R4 lineage. |
| V3-H | Historical V3 | Historical Real | Historical V3 | Yes | Yes | V3 lineage; only exact Fresh V3 policy contract is retained actively. |
| V3-C | Fresh V3 contract | Fresh V3 runtime | Fresh V3 source | Yes | Yes | Canonical Fresh V3 source milestone. |
| V35-H | Corrected status varies; not final R4 | Fresh runtime inherited | Historical V3.5 round | Yes | Yes | Superseded R1/R2/R3 packaging or experiment round. |
| R4-C | Yes, corrected | Yes | Yes, formal R4 reference | Yes | Yes | Canonical source reference for consolidation. |
| DOC-U | Corrected R3 inherited | Fresh runtime inherited | Historical only | Inherited | Unique useful history | Port conclusions into `PROJECT_HISTORY.md`, not the experiment tree. |
| EXP-U | No active requirement | No active requirement | Obsolete experiment | Possibly historical | Possibly historical | Preserve concise history only; do not retain active workflow. |
| TMP | Candidate/inherited only | Inherited only | Bootstrap/materializer only | No active requirement | No active requirement | Temporary source construction machinery; retire. |
| DUP | Same as named source branch | Same | Same | Same | Same | Duplicate ref; no unique content. |

## Complete remote branch table

`MB` is the abbreviated common merge-base `f3aae72`; `Merged?` is the tested
relationship to `origin/main`, not whether another historical branch contains
the branch. Every row is retained until the M6/M7 deletion gate passes.

| Branch | HEAD | MB | Merged? | U commits | Files | Exclusive | Class | Superseded by / M1 recommendation |
|---|---|---:|:---:|---:|---:|---:|---|---|
| agent/colab-ppo-special-platform-curriculum-250k | `8262dfb7b505e46190ad27650c3b2cae31e7e65d` | f3aae72 | No | 45 | 578 | 0 | TRAIN-H | Included in later lineage; retain generic curriculum ideas only. Delete after final tag. |
| agent/fidelity-v1-oracle-compatibility | `4fc5dd1c3ce4d9d37a354537916be6bf2d59a3fd` | f3aae72 | No | 34 | 537 | 0 | SIM-H | Superseded by later oracle audits and final R4 simulator. |
| agent/fidelity-v1-ppo-readiness-measurement-fix | `8b1a72ca7057f7751c7a64f9d430d1abf6a100ef` | f3aae72 | No | 41 | 568 | 0 | TRAIN-H | Fix is inherited by later lineage; retain only generic smoke semantics. |
| agent/fidelity-v1-ppo-readiness-smoke | `8a6772e3e93d8871c6f596c8add7cff6c52ce0da` | f3aae72 | No | 40 | 565 | 0 | TRAIN-H | Superseded by measurement fix and later training tests. |
| agent/final-sim-validation-real-alignment | `168ae586595cb01c6dbf6bd00d74c54456282560` | f3aae72 | No | 51 | 589 | 0 | REAL-H | Generic reset/alignment fixes are inherited by R4. |
| agent/oracle-fidelity-v1-cache-invalidation | `cf34de0c79e2d26c7b4da25e349b1706ee47f74d` | f3aae72 | No | 36 | 546 | 0 | SIM-H | Candidate was followed by ablation and dynamics audit. |
| agent/oracle-fidelity-v1-dynamics-audit | `0157914e0586ce75eda5532f28917c64d88e1196` | f3aae72 | No | 38 | 554 | 0 | SIM-H | Superseded by dynamics-audit-v2. |
| agent/oracle-fidelity-v1-dynamics-audit-v2 | `f6e60d3d198ec0c0d1bc24be3dfb4174f21868ec` | f3aae72 | No | 39 | 558 | 0 | SIM-H | Findings are historical; regressions are inherited by R4. |
| agent/oracle-fidelity-v1-failure-audit | `1ece02251db1271aaf88d4c3131770e7978f691f` | f3aae72 | No | 35 | 541 | 0 | SIM-H | Superseded by invalidation and dynamics audits. |
| agent/oracle-fidelity-v1-invalidation-ablation | `c59839c4f75a38b8a980b1cb283a935edebb564d` | f3aae72 | No | 37 | 550 | 0 | SIM-H | Historical ablation; no active oracle runtime required. |
| agent/real-sim-system-identification-v1 | `b6b0637a1a20ae317430ea4641e5a6a93eb4b271` | f3aae72 | No | 74 | 633 | 0 | REAL-H | Calibration/recording functionality is inherited by the V3/R4 lineage. |
| agent/simulator-fidelity-v1-core | `c2d342d8bbd99afdb8c5f986e0a0f731e96d3fa1` | f3aae72 | No | 33 | 532 | 0 | SIM-H | Fidelity V1 is superseded by Fresh V3/V3.5 corrected physics. |
| agent/simulator-learnability-colab | `e5ab8a9a57f8a19f9c462fcf21dc1201d9b0bcc3` | f3aae72 | No | 17 | 516 | 0 | SIM-H | Earliest simulator line; all commits are contained by later branches. |
| agent/simulator-mixed-distribution-v07 | `2c601b32c9884aaf09296998d54de2cb9e49a25f` | f3aae72 | No | 32 | 527 | 0 | SIM-H | Mixed/special mechanics are inherited by final simulator; old defaults retire. |
| agent/simulator-normal-fidelity-v05 | `4c0b058aabd120f513806dbd76b052b205c65fcc` | f3aae72 | No | 24 | 521 | 0 | SIM-H | Superseded by v06/v07 and later real-anchored profiles. |
| agent/simulator-special-platform-fidelity-v06 | `f8db4a273af606c4fd7aceb26cbc5e94559906d0` | f3aae72 | No | 27 | 523 | 0 | SIM-H | Special-platform behavior is inherited by later simulator code. |
| analysis/v3-5-r3-postmortem-v1 | `e95ed79ab5384fc792a01ea887e127782e5e73e8` | f3aae72 | No | 331 | 1278 | 3 | DOC-U | Three unique postmortem commits; summarize in project history, then delete. |
| experiment-data/bulk-v2-real-eval-v1 | `ed5d3701d2451f3f86761cacfdb7842cd944e53e` | f3aae72 | No | 118 | 1066 | 0 | REAL-H | Bulk/guard code is inherited; V2-specific runner and docs retire. |
| experiment-data/final-guarded-v2-real-control-v1 | `fabba3ecf81153f78c086ac61be1847dba3531d1` | f3aae72 | No | 117 | 1061 | 0 | REAL-H | Keep generic fail-closed reset/control behavior, remove V2 binding. |
| experiment-data/live-action-history-alignment-v1 | `9a1b8fd1213a0468275040d14cb857f75238d5a4` | f3aae72 | No | 114 | 1056 | 0 | REAL-H | Executed-action alignment is inherited by Fresh/R4 runtime. |
| experiment-data/live-executed-action-shadow-v2 | `7cf85a9da0b31b9b5342696b2ce614eb7ca3892f` | f3aae72 | No | 112 | 1047 | 0 | REAL-H | Keep generic executed-action semantics; retire one-shot shadow workflow. |
| experiment-data/live-real-shadow-v1 | `a7d36df0095d804669399e96241408203fc0057c` | f3aae72 | No | 110 | 1025 | 0 | REAL-H | DLL/load and passive shadow fixes are inherited by later runtime. |
| experiment-data/live-release-action-history-diagnostic-v1 | `35fabb53178111d8318b524b56bcb7afd1715b0e` | f3aae72 | No | 111 | 1038 | 0 | REAL-H | Diagnostic only; action-history contract is retained in shared runtime/tests. |
| experiment-data/model-library-seed2-real-ab-v1 | `204e0f34e4c70259fbfa90e80d87d941d984af73` | f3aae72 | No | 119 | 1076 | 0 | REAL-H | Registry mechanics are reusable; Seed2/V2 entries and A/B UX retire. |
| experiment-data/offline-real-shadow-v1 | `b4d622d1afb395d407e2587726a587a3880e02a6` | f3aae72 | No | 105 | 962 | 0 | REAL-H | Historical offline diagnostic; generic parsing only if still used by evaluation. |
| experiment-data/real-platform-detector-recovery-v1 | `37ae55369e6971e46116660e4f8305be64757a0e` | f3aae72 | No | 108 | 1015 | 0 | REAL-H | Detector recovery is inherited and must remain regression-covered. |
| experiment-data/real-reuse-audit-v1 | `952f5172a4684e8c2a9f0096bd1dec738bd25625` | f3aae72 | No | 104 | 942 | 0 | REAL-H | Audit artifacts retire; reusable parser/runtime changes are inherited. |
| experiment-data/real-runs-20260814 | `468c0899237c1246c96547768501207c1b276749` | f3aae72 | No | 136 | 948 | 22 | EXP-U | Unique Choice Window evaluator/package/docs; obsolete under V2 retirement. Preserve only historical conclusion. |
| experiment-data/real-runs-20260814-fixcheck | `57667c897e302a4b4ddde6129f53f7c78b8042a7` | f3aae72 | No | 114 | 942 | 0 | EXP-U | Contained by `real-runs-20260814`; delete after audit gate. |
| experiment-data/v3-5-r2-finalizer-hotfix-v1 | `f22c327df5778752e1cccf51ae1c708a5a884422` | f3aae72 | No | 298 | 1272 | 1 | EXP-U | Unique one-shot R2 finalizer; obsolete after unified manifest/resume flow. |
| experiment-data/v3-5-safety-refinement-final-v1 | `8073af216871724253f608297231419b39801733` | f3aae72 | No | 288 | 1269 | 0 | V35-H | Initial V3.5 contract; superseded by R2/R3/R4. |
| experiment-data/v3-5-safety-refinement-r2-v1 | `8aed115e20c4fcb0ac8ecfff655185e386814098` | f3aae72 | No | 297 | 1271 | 0 | V35-H | R2 active architecture retires; history only. |
| experiment-data/v3-5-safety-refinement-r3-corrected-flipping-v1 | `24e285699dc5f6da0a8cae50bee48fe7ce0dc6b2` | f3aae72 | No | 328 | 1276 | 0 | V35-H | Contains corrected flipping commit `0cb23a…`; superseded by formal R4. |
| experiment-data/v3-5-safety-refinement-r3-v1 | `fc1091d98499b20abe43f688c9c043dd79e7a883` | f3aae72 | No | 306 | 1273 | 0 | V35-H | Legacy flipping R3; superseded by corrected branch and R4. |
| experiment-data/v3-5-safety-refinement-r4-edge-sign-corrected-flipping-v1 | `4a4d093ccb2591d8f922e4965b01f82211748c0c` | f3aae72 | No | 336 | 1280 | 2 | R4-C | Canonical R4 source reference. Select verified modules/config/tests; do not merge whole artifact tree. |
| experiment-data/v3-5-safety-refinement-r4-safety-scale2-corrected-flipping-v1 | `24e285699dc5f6da0a8cae50bee48fe7ce0dc6b2` | f3aae72 | No | 328 | 1276 | 0 | DUP | Exact same HEAD as corrected R3 branch; no unique content. |
| experiment-data/v3-adaptation-readiness-v1 | `2c8f932cc00b9d7b402fb372c29c818ba30b1da8` | f3aae72 | No | 123 | 1200 | 0 | V3-H | Diagnostic ancestor; blocker fix and Fresh final supersede it. |
| experiment-data/v3-blocker-fix-v1 | `1e78959c859b40d499bf92cd2cfec291260d86ba` | f3aae72 | No | 124 | 1212 | 0 | V3-H | Generic blocker fixes are inherited by canonical Fresh and R4. |
| experiment-data/v3-final-calibration-lr5e5-v1 | `b921b5a13f46c1b716d12a9b8832ec3a60824923` | f3aae72 | No | 172 | 1237 | 0 | V3-H | Calibration round is historical; Fresh final supersedes its active workflow. |
| experiment-data/v3-final-training-v1 | `9d987811a992d0a60c0ac446ee335a0db148f58d` | f3aae72 | No | 145 | 1220 | 0 | V3-H | Training source ancestor; reusable training primitives are inherited. |
| experiment-data/v3-fresh-production-final-v1 | `213bf77bdd30df20ff5407b20a028618956afeb7` | f3aae72 | No | 227 | 1254 | 0 | V3-C | Canonical Fresh V3 milestone and policy pin; runtime/training functionality must remain. |
| experiment-data/v3-real-anchored-implementation-v1 | `66165a5440e1e948a78976e197bd1455512e93e3` | f3aae72 | No | 122 | 1187 | 0 | V3-H | Real-anchored simulator basis inherited by Fresh/R4. |
| experiment-data/v3-real-sim-distribution-audit-v1 | `0b8bda9311b115df9a62fb108fbdb422e4a875a0` | f3aae72 | No | 121 | 1100 | 0 | V3-H | Findings feed real-anchored V3; one-shot audit architecture retires. |
| experiment-data/v3-retention-final-v1 | `a118ca2188491b632da7e3096b41906327dad9f7` | f3aae72 | No | 159 | 1227 | 0 | V3-H | Retention experiment superseded by Fresh final decision. |
| experiment-data/v3-retention-final-v2 | `9dd8ff03c9369cde07d1976840413f705de576f7` | f3aae72 | No | 174 | 1233 | 15 | EXP-U | Unique retention-v2 trainer/notebook/package/tests; obsolete experimental path, history only. |
| tmp-should-not-create | `57667c897e302a4b4ddde6129f53f7c78b8042a7` | f3aae72 | No | 114 | 942 | 0 | DUP | Exact duplicate of `real-runs-20260814-fixcheck`; delete after gate. |
| tmp/r4-frozen-r1-finalize-source | `d991fa3dfabf6252626abcefb84afac9fd6431a6` | f3aae72 | No | 362 | 1304 | 28 | TMP | Unique patch chunks/bootstrap workflows only; formal R4 has permanent workflows and source. Retire. |
| tmp/r4-frozen-r1-safety-checkpoint | `8cbc1ceddfca2d7696d11dc972ee18b0fc729801` | f3aae72 | No | 334 | 1280 | 0 | TMP | Contained by both formal R4 and tmp finalizer; delete after gate. |

## Local-only and divergent refs

These are not current remote branches but contain required local evidence or
functionality and therefore must be considered before local branch cleanup.

| Ref | HEAD | Relationship / unique content | M1 disposition |
|---|---|---|---|
| `main` (local) | `c4cd5718a4452be8930208811c2c3d74429dd5f1` | Ten commits ahead of `origin/main`, zero behind. It is an ancestor of formal R4, so its behavior is already in the R4 lineage. | Do not merge separately; final main will receive selected later-lineage code. |
| `fix/flipping-runtime-state-v1` | `0d70ba63f534bfddf1268a995275f6cb8b210a51` | One fix over R3; two changed files. The audited physics/test blobs have no diff from remote corrected commit `0cb23aca7dcb112b2c49347a4777b4234d4ead92`. | Use remote corrected semantics already present in R4; retain local commit only until final tag/audit. |
| `feature/manual-simulator-60fps-v1` | `fdae1dbdb7eb47ede42a2bf672a37a43ceb5b282` | Three commits over R3: 60 FPS viewer, flipping fix cherry-pick, deterministic flipping mode. Required unique paths are `tools/manual_simulator_60fps.py`, `docs/manual_simulator.md`, and `tests/test_manual_simulator_60fps.py` (plus a small README section). | Port these paths onto selected R4 simulator core; do not merge the old R3 tree. |
| `experiment-data/v3-5-corrected-flipping-baseline-v1` | `e0ea06e2d35f0533fc9b267a648ae01c7cb60e7a` | Corrected Fresh V3 DEV64 evaluation script and machine-readable comparison artifacts. | Preserve baseline conclusions in history/evaluation docs; evaluator is optional, not an active runtime requirement. |
| `experiment-data/v3-5-safety-refinement-r3-v1` (local) | `fc1091d98499b20abe43f688c9c043dd79e7a883` | Matches the remote R3 head. | No separate action. |

## Canonical source and asset findings

### Simulator

- Final source reference: formal R4 commit
  `4a4d093ccb2591d8f922e4965b01f82211748c0c`.
- Corrected flipping semantics are present through remote commit
  `0cb23aca7dcb112b2c49347a4777b4234d4ead92`.
- The audited local correction `0d70ba…` produces identical target physics and
  flipping-test files.
- Human 60 FPS functionality exists only on local branch
  `feature/manual-simulator-60fps-v1` and must be file-level ported.
- The final tree should retain the existing `src/stair_agent/simulator` core,
  Fresh V3 generator, V3/V3.5 envs, and special-platform regression tests.
  Mechanics must not be rewritten during consolidation.

### Real runtime

- The latest reusable guarded stack is in the R4 lineage:
  `live_env.py`, `screen_capture.py`, `input_controller.py`,
  `episode_reset.py`, `final_guarded_real_control.py`,
  `bulk_real_evaluation.py`, the 268-D observation pipeline, and Fresh V3
  verified policy loading.
- `scripts/run_real_model_launcher.py` is not suitable as the final UX: it is
  explicitly V1/V2/Hybrid-oriented and defaults to V2.
- The generic safety behavior is retained; V2 menus, V2 manifests, Hybrid
  routing, fallbacks, and one-off bulk runners are removed from active code.

### Training

- Reusable implementations already exist in the R4 lineage under
  `src/stair_agent/rl/`, notably Fresh V3 and V3.5 training, checkpointing,
  evaluation, curriculum, and resume-safe validation.
- The current code is fragmented across target-specific scripts and notebooks.
  M3 should wrap verified primitives in one config-driven trainer, not copy PPO
  implementation into the notebook.
- Source-ZIP builders, package verifiers, fingerprint bootstrap workflows, and
  R1/R2/R3/R4 one-off orchestration are not final active architecture.

### Models

Neither canonical binary is tracked in Git, which is correct. Exact local
copies were found and verified:

| Model | Local evidence | Size | SHA256 | Result |
|---|---|---:|---|---|
| Fresh V3 seed17 @524288 | `fresh_v3_real_eval_overlay_v3/artifacts/fresh_v3_real_eval_v1/fresh_v3_seed17_524288.zip` (also duplicated under `stairkid-rl-v05/artifacts/fresh_v3_real_eval_v1/`) | 558445 | `e539ad8e9a39991d738ef9d4113968d933d4f2535e3b08fabe27f3b4ffd9f51e` | Exact canonical asset available locally. |
| V3.5 R4 seed142 @655360 | `stairkid-rl-v05/artifacts/r4_exploratory_real20/model/v3_5_seed142_t655360.zip` | 558445 | `6a9e966ae69c1b3f5610bc5c8a009dcc5519e94fa20d754e54ef0ac445399e10` | Exact canonical asset available locally. |
| R4 handoff | `C:/Users/jeffr/Downloads/v3_5_safety_refinement_handoff_20260826T151023Z.zip` | 3784861 | `6b8628c839070be034cf990142a6d49c3998906fba8065a4d223fa0386786eaa` | Exact handoff available locally. |

The formal R4 tree contains no PPO binary. Its existing model registry has V1,
V2, V2.1 and experiment entries but neither final `v3`/`r4` registry pair. It
must be replaced, not extended with fallback behavior.

## Unique-tip decisions

Only six historical remote tips have commits that no other remote tip contains:

| Branch | Exclusive commits | Decision |
|---|---:|---|
| analysis/v3-5-r3-postmortem-v1 | 3 | Summarize audited conclusions in project history. |
| experiment-data/real-runs-20260814 | 22 | Choice Window/V2 experimental path is retired; history only. |
| experiment-data/v3-5-r2-finalizer-hotfix-v1 | 1 | Obsolete one-shot finalizer; unified resume/manifest replaces it. |
| experiment-data/v3-5-safety-refinement-r4-edge-sign-corrected-flipping-v1 | 2 | Required canonical R4 source changes. |
| experiment-data/v3-retention-final-v2 | 15 | Superseded retention experiment; no active trainer/notebook. |
| tmp/r4-frozen-r1-finalize-source | 28 | Patch chunks and temporary bootstrap workflows only; retire. |

## M1 deletion status

No local or remote branch was deleted. No tag was created or pushed. No merge
to main was performed. Branch deletion remains blocked until all M2-M6 gates in
`CONSOLIDATION_PLAN.md` pass and tags are verified on the remote.
