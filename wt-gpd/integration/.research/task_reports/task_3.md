# Task 3 Report — Fair Three-Controller Environment

## Corrective addendum A1 — shared TD3 observation contract

- Status: `in_progress` under the pre-Stage-A protocol 1.0.2 fairness correction; the original Task 3 integration remains preserved as historical implementation evidence.
- Binding correction: Direct TD3, Residual TD3, and residual-no-gate must all expose the same 260-dimensional policy observation: eight 32-dimensional history frames plus current cached frozen PID RPM. The PID mode and all action, reward, termination, gate, and hidden-disturbance semantics are out of scope and must remain bitwise-equivalent.
- Required RED/GREEN evidence: equal schema/shape/Box bounds after reset and synchronized step; Direct tail exactly equals cached PID RPM; no policy-observation change if hidden truth/profile/seed metadata changes; preserved zero-residual-equals-PID and action/reward invariants.
- Downstream dependency: Task 4 must rerun terminal/reward regressions, Task 5 must re-sign the PID freeze under the new protocol/environment hashes, and Task 6 must restart from fresh provenance and attempt_02 smoke evidence.

## Correction worktree baseline

- Isolated worktree: `E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\task3-fairness`, branch `agent/task-3-fairness`, base `93ee2aea327d17b606fd1f1c41cd2da324481b78`.
- Baseline classification: 276 circular-tracking tests pass; 14 Task 5 frozen-PID tests fail closed because protocol 1.0.2 intentionally invalidates the old `hidden_pid_frozen.json` protocol hash. This is the expected downstream dependency and is not waived; Task 5 revalidation must remove these failures after the environment correction is integrated.

## Corrective implementation and root verification

- Implementation commit: `c254da9e50a04d58d0491261b29733423aeea622` (`fix: share pid RPM observation across TD3 modes`).
- TDD RED: the new parity/boundary selection produced 2 failed and 3 passed before production edits; Direct lacked `pid_rpm` in its schema and its final four values did not match the cached PID RPM.
- TDD GREEN: the same selection passed 5 tests. The complete environment file passed 264 tests.
- Root fresh verification: focused contract 5 passed; complete environment file 264 passed; `compileall` and dependency integrity passed; the commit range contains exactly the two allowed source/test files; `git diff --check` and worktree-clean checks passed.
- Root circular-suite classification: 279 passed and 14 failed, all fail closed at the intentionally stale Task 5 frozen-PID protocol hash. No other error occurred. Those failures are a required downstream Task 5 revalidation, not an accepted completion condition for the overall pipeline.
- Behavioral boundary: Direct now joins only the existing TD3 PID-RPM schema/Box/observation concatenation condition. PID mode remains 256-dimensional; PID cache timing, PID action path, Direct hover-centered action mapping, residual mapping/gate, reward, termination, disturbance physics and offline truth logging are unchanged.

## Specification/science review

- Reviewer: `/root/task3_fairness_spec_review`.
- Verdict: `APPROVED` — Critical 0, Important 0, Minor 0.
- Verified: the only production changes are the three TD3-mode condition expansions for observation schema, Box bounds, and `_computeObs()`; Direct, Residual and no-gate have equal 260-dimensional contracts after reset and synchronized step; Direct tail equals current PID cache; all direct hidden-truth/profile/seed perturbation tests preserve observation/gate/reward; PID remains 256-dimensional and all action/reward/termination/physics/offline truth semantics are unchanged.
- Independent reviewer evidence: 264 environment tests passed; explicit new seed `9031` remains in the 9000–9099 unit-test partition; only the two authorized files changed. Task 5 acceptance has 14 expected stale-freeze failures and 15 passes, with every failure rooted in the old protocol/environment hashes; no failure was skipped or masked.

## Quality/reproducibility review

- Reviewer: `/root/task3_fairness_quality_review`.
- Verdict: `APPROVED` — Critical 0, Important 0, Minor 0.
- Verified: all three TD3 modes provide finite float32 260-dimensional observations with matching Box bounds; reset/step probes find no cache aliasing; PID cache updates once at reset/control-step and `_computeObs()` is read-only; tests exercise real reset/step behavior and valid unit-test seeds; no hidden truth/profile/seed access is introduced.
- Independent quality evidence: 7 focused tests passed, 264 environment tests passed, diff-check clean and correction worktree clean. The Task 5 stale-hash failure is correctly fail-closed and remains a downstream dependency.

## Post-review root verification

- Fresh root verification after both approvals: 5 focused contract tests and all 264 environment tests passed; `compileall` and dependency integrity passed; the correction range still contains only the two whitelisted files; diff-check and worktree-clean checks passed.
- Protocol hash: `e6edc37f6f89ec6684917f71f20444dd45b6e745f299b8ea6bf165d71e294359` (LF-normalized canonical bytes).
- Authorized next step: serially integrate only `c254da9e50a04d58d0491261b29733423aeea622`, then repeat integration verification. The stale Task 5 frozen PID remains intentionally invalid until its own reviewed re-sign workflow.

## Integration

- Source commit `c254da9e50a04d58d0491261b29733423aeea622` was serially cherry-picked as integration commit `1b0f9fc`.
- Fresh integration verification: complete environment file 264 passed in 30.99 seconds; compileall and dependency check passed; reviewed source/test content matches the implementation commit and integration worktree is clean.
- Corrective addendum A1 Steps 2–3 are complete. Task 4 terminal/reward revalidation and Task 5 current-evidence re-freeze remain mandatory dependencies; no TD3 training is authorized.

## Status

- Lifecycle: `in_progress`; retry implementer `/root/task3_fail_closed_retry` is running from the preserved RED-test state after the original 403 exit.
- Implementation is authorized: Tasks 1 and 2 are complete, and protocol reconciliation was independently approved in protocol `1.0.1`.
- Read-only pre-review completed by `/root/task3_pre_review`; no files were modified.
- Protocol reconciliation is required before dispatch because exact termination thresholds and the wind-drag model/coefficient are not yet machine-readable in the frozen protocol.

## Critical pre-review findings

1. `BaseAviary.step()` calls `_physics()` multiple times but advances `step_counter` only after reward/info. A dedicated physics-substep clock is required so each substep samples a distinct disturbance time.
2. A world-frame external wind force must use `linkIndex=-1` and the live world-space base position on every substep. Applying at `[0, 0, 0]` recreates the historical artificial-moment bug.
3. `DSLPIDControl.computeControl()` mutates integral/counter/history state. Compute the PID command exactly once per control instant and cache it; observation and diagnostics must not advance the controller.
4. `_computeObs()` must be idempotent. Repeated calls cannot append history, resample disturbance, or mutate PID state.
5. Base reward ordering is before termination. Reward and termination must independently call the same pure current-state failure-reason helper so terminal penalty appears on the terminal transition.
6. The frozen protocol currently omits exact termination thresholds and wind-drag physics parameters. These must be reconciled by root before Task 3/4 implementation; subagents may not invent them.

## Root protocol-reconciliation draft

- Freeze `Physics.PYB` at 240 Hz with 48 Hz control and five physics substeps per action.
- Sample disturbance with a dedicated substep counter at `substep_index / 240`; use completed-substep time for the post-step reference, reward, termination, and info.
- Apply an incremental quadratic wind force relative to the still-air PYB baseline, with `rho=1.225 kg/m^3` and `CDA=0.05 m^2`, so standard zero wind produces exactly zero extra force.
- Apply the force to `linkIndex=-1` at the live base world position in `WORLD_FRAME` on every substep.
- Scale all four motor thrusts by one sampled thrust-efficiency scalar and all four reaction torques by one sampled torque-efficiency scalar.
- Freeze the Task 4 failure priority and thresholds: nonfinite state; altitude reference error `>1.5 m` or absolute altitude outside `[0.1,3.0] m`; roll/pitch absolute angle `>0.9 rad`; horizontal error `>2.0 m`.
- This draft requires independent science review and a new canonical protocol hash before Task 2/3 implementation authorization.
- Draft protocol version/hash: `1.0.1` / `80f78f7af532a7701c97c93b38c0af6f6cd41c5cfb111db72c6a85b150f2cce5`.
- Review status: pending `/root/protocol_reconciliation_review`.
- First science review: one Medium plan-only seed-partition issue in Task 4; all physics, hidden-information, termination, and unchanged-range/gate checks passed.
- Root fix: Task 4 now uses unit-test seed `9003`; protocol bytes/hash are unchanged. Awaiting same-reviewer rereview.
- Final science rereview: approved. Task 3 remains pending behind Task 2 but no protocol ambiguity remains.

## Worktree and baseline

- Worktree: `E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\impl`.
- Branch/base: `agent/task-3` at `43c9aee09fdfe1ff364862284a5f91fc15c36ce9`.
- Allowed files: `hidden_disturbance_td3_env.py`, `rl_envs/__init__.py`, and `test_hidden_disturbance_td3_env.py` only.
- Fresh baseline: dependency check clean; 66 tests passed with 13 existing warnings; compileall and canonical protocol hash passed; worktree clean.
- Required discipline: strict missing-module RED before production code, minimal GREEN, no legacy subclass/copy, self-review, and narrow commit.

## Implementation

- Implementer: `/root/task3_implementer`.
- Commit: `ffb3f42bf244abb276039fe75290081e96cb9b1d`.
- RED evidence: missing-module collection error; 15 interface/mapping failures; 3 observation/PID lifecycle failures; 13 gate failures; 5 physics/info/truncation failures.
- Architecture: direct `CtrlAviary` subclass; dedicated started/completed substep clocks; per-substep disturbance sampling; one cached PID update per control instant; eight-frame history outside `_computeObs`; live-position incremental wind force; separate thrust/torque efficiency; cached offline truth only.
- Task 4 boundary: terminal current-state failure helper and penalty were intentionally not implemented.
- Root verification: 94 focused, 94 circular, and 115 full tests passed with 13 existing warnings; compileall, seed partition, protocol hash, three-file scope, protected/legacy diff, no-legacy-dependency, diff-check, and clean status passed.

## Root questions for specification review

1. Task 5's whitelist excludes the environment but its 81-candidate grid requires `reference_velocity_gain`, `pid_xy_p_scale`, `pid_xy_d_scale`, and `pid_target_step_limit`; the current Task 3 constructor does not visibly expose these four immutable PID configuration inputs.
2. Confirm the outer `step()` wrapper preserves required BaseAviary lifecycle semantics while correctly leaving Task 4 terminal penalty unresolved.
3. Confirm info/schema naming is sufficient for downstream tuning/evaluation without privileged leakage.

## Specification review

- Decision: `CHANGES_REQUIRED` with one Critical issue.
- Missing interface: keyword-only `reference_velocity_gain`, `pid_xy_p_scale`, `pid_xy_d_scale`, and `pid_target_step_limit`, with behavior-preserving defaults `1.0, 1.0, 1.0, 0.0`.
- Required semantics: finite real validation; reference velocity gain applies only to PID target velocity; a 3-D current-position-to-analytic-reference target step limit with `0.0` disabled; only fresh stock XY P/D gains are scaled; immutable/read-only normalized config; repeated reset cannot compound; fresh environments cannot contaminate one another.
- Required tests: accepted grid values and invalids, frozen config, exact captured target position/velocity, untouched remaining coefficients, multiple-reset noncompounding, fresh-env isolation, and preserved once-per-control PID computation.
- Other audit results passed: outer step lifecycle, downstream info sufficiency, no legacy coupling, no extra terminal implementation, and Task 4 remains a valid RED follow-up.

## PID interface fix

- Commit: `7f9795c8d77b4d4fc75676804658b9dd03277d31`.
- RED: 39 affected tests failed against the pre-fix head.
- API: frozen slotted `PIDShapingConfig` with keyword-only defaults `1.0, 1.0, 1.0, 0.0` and domain validation.
- Behavior: stock-relative XY P/D scaling once per fresh controller; exact reference-velocity gain; 3-D target-position step limit with zero disabled; no reset compounding or cross-environment array sharing; reference/observation/reward/gate unchanged.
- Root verification: 39 affected, 133 focused, 133 circular, and 154 full tests passed with 13 existing warnings; compileall, two-file fix scope, cumulative three-file scope, seed/protocol/protected/Task4/diff/status audits passed.
- Final specification rereview: `APPROVED`; exact defaults/domains, frozen config, stock-relative isolated gains, target shaping, reset noncompounding, default rollout compatibility, and all 81 public Task 5 candidates independently verified. Task 4 remains a valid RED follow-up.

## Quality review

- Decision: `WITH_FIXES`; no Critical issues, two Important issues, one deferred Minor.
- Important 1: invalid public actions can mutate variable-shaped caches or advance physics before failing. Required: exact shape/real/finite/bounds validation before any mutation; public out-of-range rejection; fixed-shape cache reallocation on reset; unchanged-state and reset-recovery regressions.
- Important 2: arbitrary positive durations and post-done steps can partially advance beyond the disturbance horizon. Required: control-step-aligned duration validation, pre-step done/reset-required guards, and reset-required state after injected physics failures; exact 20/30 s and unchanged-counter regressions.
- Deferred Minor: `info` mixes applied interval values with next-control PID/gate and omits the exact disturbance sample time. It remains recorded but does not block integration.
- Task 4 remains structurally implementable after these fixes.

## Fail-closed retry and root verification

- Retry implementer: `/root/task3_fail_closed_retry`; original implementer session was unavailable, so the preserved RED tests were continued without discarding them.
- Commit: `1c9346ebe15433130153541251f0a6b0be66f321` (supersedes the amended intermediate commit and follows `7f9795c8d77b4d4fc75676804658b9dd03277d31`).
- TDD RED against the PID-interface head: 106 failed, 4 passed, 133 deselected.
- Fix scope: only `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py` and `tests/circular_tracking/test_hidden_disturbance_td3_env.py`; no Task 4 terminal implementation and no protocol change.
- Closed behaviors: exact pre-mutation action validation; fixed-shape cache reallocation on reset; control-step-aligned finite durations; pre-step done/reset-required guards; reset-required state after physics exceptions; exact 20/30 second horizon and unchanged-counter regressions.
- Root verification at implementation HEAD: affected quality selection 110 passed; focused Task 3 243 passed; circular suite 243 passed; full repository 264 passed with 13 pre-existing warnings; `pip check`, compileall, explicit-seed audit, protocol hash, scope/protected-diff audits, Task 4 absence audit, diff check, and clean-status check all passed.
- Status: awaiting same quality reviewer rereview of both Important issues. Deferred info timing/sample-time Minor remains recorded and is not expanded in this fix.

## Quality rereview

- Reviewer: `/root/task3_quality_review`.
- Decision: `APPROVED` (Critical 0, Important 0, Minor 0; the previously deferred info timing/sample-time Minor remains non-blocking).
- Evidence: 132 targeted fail-closed tests passed; 243 Task 3/circular tests passed; invalid-action runtime fingerprints remained unchanged; reset recovery, exception latching, aligned duration, and exact 20/30-second horizon checks passed; protocol hash, compileall, diff-check, and information-boundary audits passed.
- Task 3 is now awaiting fresh root post-review verification before serial integration. Task 4 terminal semantics remain intentionally absent until integration.

## Root post-review verification

- Fresh implementation-worktree verification after approval: focused 243 passed; circular 243 passed; full repository 264 passed with 13 pre-existing warnings; `pip check` and compileall passed.
- Canonical LF-normalized protocol SHA-256 remained `80f78f7af532a7701c97c93b38c0af6f6cd41c5cfb111db72c6a85b150f2cce5`; Task 3 code/test seed literals were all within 9000–9099; protected shared/legacy diff, Task 4 method absence, diff-check, and clean-status audits passed.
- Ready for serial cherry-pick of `ffb3f42bf244abb276039fe75290081e96cb9b1d`, `7f9795c8d77b4d4fc75676804658b9dd03277d31`, and `1c9346ebe15433130153541251f0a6b0be66f321` onto integration.

## Serial integration

- Source commits were cherry-picked in chronological order as integration commits `e80f535`, `d1ae8b2`, and `8f17ff1` on `integration/hidden-td3-rebuild`.
- Integration verification: 243 focused, 243 circular, and 264 full tests passed with 13 pre-existing warnings; dependency check and compileall passed; canonical protocol hash remained unchanged and the integration worktree is clean.
- Task 3 status: `complete`. Task 4 is now unlocked; its terminal reward helper and penalty are still absent from the integrated environment by design.

## Existing hook map

- Subclass `CtrlAviary` directly; do not subclass the legacy residual environment.
- `reset()`: validate mode/profile/seed, create the rollout-length process before initial observation, clear eight-frame history, reset PID/caches.
- `_actionSpace()`: identical `Box(-1, 1, (4,))` for Direct, Residual, and no-gate Residual; PID may use the planned dummy action.
- `_computeObs()`: measurable state/reference/error/history and permitted cached PID RPM only; no mutation.
- `_preprocessAction()`: implement the exact frozen Direct/Residual mappings; do not reuse Base's asymmetric normalized mapping.
- `_physics()`: one cached sample per true substep; separate thrust and torque efficiencies; live-position world-frame wind force.
- `_computeReward()` and `_computeTerminated()`: same pure failure helper.
- `_computeInfo()`: log only the disturbance sample actually applied, without resampling.
- Package export: add the new class while preserving the legacy export.

## Required focused tests before production code

- Exact supported mode set and matched four-vector TD3 action spaces.
- Direct and residual formula checks at zero, bounds, clipping, and mixed actions.
- Zero residual equals PID over a 50-step same-seed rollout, including reward/termination.
- Observation excludes truth/profile/seed and is idempotent/PID-pure.
- Shared eight-step history and only the permitted residual PID-RPM extension.
- Gate threshold/headroom formula plus truth invariance and no-gate value.
- Reward mode invariance for identical applied RPM and terminal current-state penalty.
- Disturbance sampled exactly once at each physics substep using a monotonic substep clock.
- Wind force applied at current non-origin base position in `WORLD_FRAME`.
- Thrust and torque efficiency scaling verified independently.

## Plan-sketch corrections

- The current leak-test sketch mutates an assumed private field and calls `_computeObs()` in a way that may change history; replace it with a side-effect-free state/history fixture.
- The sketch's wind `(1.5, -1.5)` exceeds the declared 1.5 m/s vector norm.
- Decide whether standard includes aerodynamic still-air drag; the protocol says no disturbance, so no hidden extra drag model may be assumed.

## Planned verification

```powershell
py -3.11 -m pytest tests/circular_tracking/test_hidden_disturbance_td3_env.py -v
py -3.11 -m pytest tests/circular_tracking -v
py -3.11 -m pytest tests/test_asset_paths.py -v
py -3.11 -m compileall experiments/circular_tracking/rl_envs
git diff --check
git diff --exit-code -- experiments/circular_tracking/rl_envs/circular_residual_td3_env.py experiments/circular_tracking/results/td3_residual_paper
rg -n "wind|efficiency|scenario|profile|seed|disturbance_truth" experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py
```
