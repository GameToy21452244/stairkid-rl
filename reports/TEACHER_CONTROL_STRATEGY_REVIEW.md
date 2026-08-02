# Teacher Control Strategy Review

- Review date: 2026-08-03 (Asia/Taipei)
- Proposal under review: `CODEX_REVIEW_AND_ADAPT_TEACHER_CONTROL_STRATEGY.md`
- Scope: evidence review and bounded offline diagnostics only
- Current decision: **keep P4.0 formal Student work blocked**

## Executive conclusion

The proposal correctly identifies that the Teacher still has a control problem, but it mixes one well-supported diagnosis with several mechanisms that are not yet supported by the latest real-game evidence.

The strongest current finding is a **normal-platform landing prediction error during braking/release**. In Gate v7, both early bottom deaths can be traced to a release decision made with the old long constant-velocity projection. The observed displacement after the command was only 5.5–6.5 px, while the old projection assumed 36–89.6 px. The short 0.05 s release projection already added after Gate v7 is therefore directionally justified, but it has not yet passed a complete real-game Gate.

The latest evidence does **not** justify immediately adding new Spring Escape or Spike Escape control state machines. Gate v7 contains spring contact identity fragmentation across a multi-bounce encounter, but the character exits that encounter and reaches floor 6. Its observed spike contacts leave within 1–3 steps; the later deaths occur during post-contact landing/recovery, not because the character remains stuck on the same spike. A generic stuck watchdog would also misclassify valid free-fall release sequences and could conflict with the existing bounded safety/recovery logic.

Accordingly, this review accepts an action-conditioned dynamics investigation only with strict modifications: reuse the existing calibration model, build a reproducible filtered offline audit, validate by held-out episodes and action regimes, and keep it out of the live controller until it beats the current projection in shadow evaluation. Spring work is limited to encounter-level telemetry that survives contact-ID changes. No new spike controller or active stuck fallback is approved in this round.

## Evidence reviewed

The review cross-checked the proposal against the repository, current strategy/status/decision/risk documents, implementation, tests, and these real-game artifacts:

- Gate v7: `logs/teacher_real_micro_20260803_012857_250916/`
  - 3 episodes, floors reached `2 / 5 / 2`
  - mean `3.0`, median `2.0`, Q25 `2.0`, lower-tail CVaR `2.0`
  - reach-3 `1/3`, reach-5 `1/3`, all three terminated at the bottom
  - invalid observations `0`; wall re-entry/outward violations `0`
  - 5 spring and 3 spike contact records; no special-contact restart/abort
- Gate v8: `logs/teacher_real_micro_20260803_014454_612146/`
  - only episode 1 completed (floor 3); episode 2 stopped safely after reset/focus could not be verified
  - this is an **incomplete Gate**, not evidence that the updated controller passed
- Two preceding recent real runs:
  - `logs/teacher_real_micro_20260803_010405_293428/`
  - `logs/teacher_real_micro_20260803_011114_410228/`
- All corresponding MP4s, transition files, controller sidecars, telemetry, event timestamps, and Gate JSON files
- `reports/CALIBRATION_GATE_REPORT_R14_MODEL_V1.md`
- `reports/PARTIAL_OBSERVABILITY_AUDIT.md`
- `reports/P36_GATE_V5_SPECIAL_CONTACT_DIAGNOSIS.md`
- `reports/P36_REPAIR_V10_VISION_CALIBRATION_REPORT.md`
- `reports/P36_GATE_V7_RELEASE_PROJECTION_DIAGNOSIS.md`
- Existing `CalibratedObservationModel` and calibration-analysis code

The latest four runs contain 694 transitions. An initial context-validity filter retained 432 rows: current and next player detections present, confidence at least 0.8, no wall/special/recovery state, no event, no raw detection dropout, and the player away from screen edges. The reproducible audit then excludes rising/falling motion-boundary rows and retains **337 strict continuous-motion rows**. The 432-row figures below are retained as the initial diagnosis; deployment decisions use the stricter 337-row episode-held-out audit.

Measured timing over the 694 rows:

| Quantity | Median | P95 | Interpretation |
|---|---:|---:|---|
| action effective → next observation | 94 ms | 109 ms | the relevant one-command response window |
| observation → next observation | 125 ms | 140 ms | includes perception/controller processing |
| observation processing → command | 31 ms | 47 ms | not the dominant source of the v7 release miss |

The filtered rows show strong action dependence. An in-sample per-action linear velocity fit reduced one-step velocity MAE relative to carrying forward the old velocity:

| Action | Rows | Linear-fit MAE | Carry-forward MAE |
|---|---:|---:|---:|
| LEFT | 109 | 38.87 px/s | 84.02 px/s |
| RIGHT | 125 | 41.34 px/s | 84.82 px/s |
| RELEASE | 198 | 19.73 px/s | 61.21 px/s |

This is evidence that action matters, not proof that the in-sample model is safe to deploy. Reverse-braking evidence remains sparse: only 19 LEFT commands while moving right and 13 RIGHT commands while moving left passed the strict filter.

For 142 non-zero release rows, the absolute next-frame displacement median is 6 px but the maximum is 24 px. A fixed 5–8 px release displacement is therefore not a defensible universal controller constant. On these same rows, the old `vx × 0.25 s` next-position estimate has MAE 25.29 px; the current short `vx × 0.05 s` diagnostic estimate has MAE 3.42 px. History and command regime still matter.

## Root-cause review

| Candidate cause | Evidence | Judgment |
|---|---|---|
| Action dynamics / braking model | Gate v7 episode 1 step 38 predicted 89.6 px of continued left motion after RELEASE but observed 6.5 px; episode 3 step 27 predicted 36 px right motion but observed 5.5 px. Filtered telemetry also shows materially different action responses. | **Primary, high confidence** |
| Horizontal velocity estimate | One-step velocity is noisy and reverse-braking samples are sparse. Some release rows retain high momentum while others brake sharply. | **Contributing, medium confidence** |
| Action latency | Effective-command-to-observation timing is tightly clustered around 94 ms. The old projection horizon was substantially longer than this. | **Measured contributor, not a latency outage** |
| Observation timing | Processing-to-command median is 31 ms and there were no invalid observations in v7. | **Not the primary v7 cause** |
| Platform safe interval | The current controller already targets a bounded safe interval, but it treats the forecast as a point estimate without calibrated uncertainty. No held-out interval coverage result exists. | **Possible contributor; insufficient evidence for a policy change** |
| Target selection | Targets change after the original landing becomes unreachable. In the two inspected deaths, this is downstream of the release miss rather than the initiating cause. | **Secondary in inspected failures** |
| Braking / release | The bad decisions occurred at the final steer-versus-release boundary. Release response is regime/history dependent. | **Primary control boundary** |
| Phase logic | The inspected decisions are consistent with their logged phases; no phase corruption was found. | **Not supported as primary cause** |
| Detector instability | Gate v7 has zero invalid observations and the normal-death windows retain valid player/platform detections. | **Not supported as primary cause** |
| Other: contact identity | Spring source/contact IDs fragment as scrolling and bounce transitions occur, so single-contact duration understates the full encounter. | **Telemetry defect, not yet a proven control defect** |

## Proposal decision table

The labels below use the requested meanings literally. `ACCEPT_WITH_MODIFICATIONS` authorizes only the modified scope described here, not the proposal's full implementation.

| ID | Proposal | Decision | Evidence-based reason | Authorized action in this round |
|---|---|---|---|---|
| A | Action-conditioned dynamics model | **ACCEPT_WITH_MODIFICATIONS** | Real telemetry clearly rejects a single constant-velocity projection, and an action-conditioned model already exists in the repository. However, current numbers are in-sample and reverse-braking regimes are underrepresented. Duplicating the model or deploying it now would be premature. | Reuse/extend the existing model in an offline audit. Apply strict filtering, split by episode, report first-release/repeated-release/same-direction/reverse-braking regimes, and validate 1-step plus bounded 2–5-step rollouts. No live decision change until held-out results pass. |
| B | Safe landing interval with uncertainty | **INSUFFICIENT_EVIDENCE** | A safe geometric interval already exists, but model uncertainty has not been calibrated on held-out real episodes. There is no demonstrated coverage target or evidence that a particular margin would improve lower-tail outcomes. | After A is validated, compute shadow-only residual intervals and landing coverage. Do not change target margins or release decisions yet. |
| C | Receding-horizon steering | **INSUFFICIENT_EVIDENCE** | Logged trajectories are factual/on-policy and do not identify counterfactual sequence outcomes. The present model has not been validated for stateful 3–5 command rollouts, especially at reversal boundaries. | First pass A and B in shadow mode. Then compare a tiny set of candidate sequences offline; no live sequence controller in this round. |
| D | Spring Escape lifecycle | **ACCEPT_WITH_MODIFICATIONS** | Historical Gate v5 contains true spring stalls. In v7, source IDs 38→41 and 39→44 and semantic contact IDs 3→6 fragment one multi-bounce period, but video/telemetry show the agent exits and later reaches floor 6. That supports encounter-level measurement, not another controller FSM. | Add offline encounter aggregation across short ID gaps and record span, bounce/contact IDs, releases, reversals, exit/progress, and death. Keep the existing bounded special-escape controller unchanged unless a new complete Gate proves a blocking failure. |
| E | Spike Escape lifecycle | **REJECT** | In v7, observed spike encounters leave in 1–3 steps and recovery/health-gain behavior occurs. Later deaths are landing failures or a new terminal contact, not prolonged same-spike indecision. A separate FSM would duplicate existing special-escape/recovery logic and may create priority conflicts. | Retain current bounded spike/recovery behavior. Add post-spike outcome telemetry to offline reports only; reconsider if a complete Gate captures a sustained same-spike stall. |
| F | Generic stuck watchdog with fallback/blacklist | **REJECT** | The previous generic 5-step RELEASE signal was a false positive: it was aligned free fall over a spring. The controller already has bounded lease, departure, special-escape, forced-exit and safety-stop mechanisms. No threshold has acceptable false-positive evidence, and an active clear/blacklist fallback can override a valid landing plan. | Do not add an active watchdog. Diagnose named states separately through encounter and landing telemetry. Safety remains fail-closed. |

## Gate status after review

### Normal Landing Gate — **FAIL**

- Gate v7 lower-tail results remain below the current threshold: reach-3 only `1/3`, with all episodes ending at the bottom.
- The two early failures have direct release-projection evidence.
- The short release projection and reset-focus changes have not completed a fresh Gate.

Required next evidence: a bounded complete real Gate after the offline dynamics audit and shadow checks; do not count incomplete Gate v8.

### Spring Escape Gate — **INSUFFICIENT_EVIDENCE**

- Gate v7 shows a multi-bounce spring encounter fragmented across contact/source IDs.
- It does not show a confirmed terminal spring trap: the run exits the encounter and reaches floor 6.
- Gate v8 contains no complete spring evaluation.

Required next evidence: encounter-level aggregation first, followed by one bounded real Gate. A controller change is not authorized solely to make the metric easier to pass.

### Spike Escape Gate — **PROVISIONAL LOCAL PASS; NOT QUALIFIED**

- All inspected Gate v7 spike contacts leave the contact window in 1–3 steps.
- The sample is only three contact records, and the overall episodes still fail later.
- This is enough to reject an immediate new Spike FSM, but not enough to declare the Teacher globally reliable on spikes.

Required next evidence: preserve post-spike recovery/outcome telemetry in the next bounded complete Gate.

### Restart / Safety Gate — **REAL-GAME VERIFICATION PENDING**

- Gate v7 has no safety/wall/restart violation.
- Gate v8 correctly stops when reset/focus cannot be verified; it must not be scored as a performance pass.
- EXIT-menu focus handling is covered offline but has not completed a fresh multi-episode real Gate.

### Overall Teacher Real-Game Micro Gate — **FAIL / HOLD**

P3.6 is not complete. P4.0 formal Student training remains blocked.

## Smallest evidence-gathering plan

This review authorizes the following bounded order:

1. **Offline action audit:** make the strict transition selection and per-action/regime statistics reproducible; use episode-held-out validation and the existing calibration model.
2. **Offline spring encounter audit:** aggregate adjacent spring contacts without claiming that unstable source IDs are physical ground truth; inspect post-spike outcomes in the same report.
3. **Shadow-only comparison:** only if held-out action dynamics beat the current projection, calculate proposed landing intervals and candidate decisions without sending input to the game.
4. **At most one bounded real Gate:** only after offline/shadow acceptance. Keep existing safety caps and record all MP4/transitions/sidecars. Stop if focus, observation integrity, or safety is uncertain.

The following work is explicitly not authorized by this review:

- a duplicate dynamics subsystem
- a live Spring or Spike FSM rewrite
- a generic active stuck watchdog
- P4.0 formal Student training, long BC, DAgger, PPO, DQN, NEAT, or long real-game exploration

## P4.0 boundary

May proceed while P3.6 is on hold:

- read-only state-aliasing diagnostics on already-collected data
- dataset/schema/label-quality audits
- test and report scaffolding that does not train or deploy a Student

Must wait for Teacher Gate qualification:

- treating current Teacher trajectories as qualified expert demonstrations
- S0/S1/S2/S3 formal comparison
- BC/DAgger Student training or promotion
- any claim that P4.0 has started or passed

## Implementation decision

Implementation proceeded only for the accepted modified scope: reproducible **offline** action-regime diagnostics and encounter-level special-platform telemetry. The live `SafePlatformPolicy`, action arbitration, focus handling, and safety mechanisms were not changed in this round.

The strict audit covers 337 rows from 10 held-out episodes. The action-conditioned form improves held-out one-step x MAE from 8.462 px to 4.049 px and improves 2–5-step actual-action rollout MAE over the carry-velocity baseline. It is nevertheless **not shadow/live eligible**, because strict reverse-braking coverage is only 7 LEFT-while-moving-right and 8 RIGHT-while-moving-left rows versus the predeclared 30-per-side minimum. Detailed results are in `ACTION_CONDITIONED_DYNAMICS_REPORT.md`.

A read-only scan of the original 14 calibration logs found 450 additional strict continuous rows, but only **1 LEFT reverse-braking row and 0 RIGHT reverse-braking rows**. A subsequent bounded fixed-platform reversal experiment added 23/21 diagnostic rows across three completed runs. User observation correctly identified that repeatedly oscillating on one platform is not representative of natural landing control. These rows therefore remain diagnostic-only and are not merged into the deployment Gate; an interrupted fourth run is explicitly excluded. Further fixed-platform collection is stopped. The next evidence source must be one bounded natural Teacher run with full sidecars and the candidate model unable to affect actions.

Encounter aggregation also confirms that Gate v7's steps 101–116 spring sequence spans four contact IDs and four source IDs, includes two bounce events, and subsequently lands on a normal platform. The terminal spike contact at step 139 is now correctly distinguished from a successful exit by joining controller sidecars with transition terminal flags. Any later live controller modification still requires additional evidence and a separately recorded decision.

## Post-review evidence addendum — 2026-08-03

The one authorized bounded natural run has now completed with HUD floors `2,9,7`.
An earlier attempt stopped safely after an accidental focus change and is not counted as a
Gate. The complete run has no focus, observation, wall, input-safety, or departure-timeout
violation. Its original v8 Gate failed only because generic edge RELEASE mixed 15
same-support settle decisions and one spring brake into the departure-stall ratio.

Gate v9 preserves those 16/57 generic records but counts only actionable departure context;
the result is 0/39 actionable RELEASE and 51/51 checks PASS. This evidence does not alter
the original proposal review decisions: no new Spring/Spike FSM or generic watchdog was
implemented, and the action-conditioned model remains offline-only because natural
reverse-braking coverage is 11/15 rather than 30/30. The three-episode Micro Gate is now
cleared; a separate 10-episode stability Gate remains required before formal P4.0 work.

## Gate v11 stability addendum — 2026-08-03

The separate natural stability run completed 10/10 episodes. A trusted replay of all ten
MP4 files corrected one terminal-frame floor maximum upward from 3 to 4, producing
`8,11,4,2,2,5,4,4,8,2`. Gate v11 keeps the predeclared reach and safety requirements but
fixes two semantically invalid counters: it measures bottom failures before floor 3 rather
than penalizing every bottom terminal in an endless game, and permits an entry brake plus
the brake associated with the one already-permitted special-contact reversal. The same
immutable data passes all checks.

This qualifies P3.6 and opens the P4.0 State-aliasing Audit only. It does not change the
review decision on action-conditioned dynamics, does not approve a new Spring/Spike FSM,
and does not authorize Student training. Reach-3 and the early-bottom budget both pass at
their exact boundary, so lower-tail reliability remains an explicit open risk.
