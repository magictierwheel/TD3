# Task 4 Report — Terminal Reward Semantics

## Status

- Lifecycle: `in_progress`; Task 3 is integrated and the isolated `agent/task-4` worktree has passed its clean baseline.
- Read-only pre-review completed by `/root/task4_pre_review`; no files were modified.
- Implementation is not authorized until the Task 3 environment exists and passes its own reviews.

## Protocol 1.0.2 environment revalidation

- Reviewer: `/root/task4_revalidation_auditor`.
- Verdict: `APPROVED` — Critical 0, Important 0, Minor 0; no source modification is required.
- Fresh independent evidence: 132 targeted terminal/failure/reward/zero-residual/action/lifecycle tests passed; the complete environment file passed 264 tests; diff-check and integration worktree were clean.
- The pure current-state failure helper, terminal penalty/fallback, termination callback, and PID cache lifecycle are unchanged by the Direct observation tail. The full circular suite's 279 passes and 14 old-frozen-PID hash failures confirm Task 4 semantics are intact; the 14 failures remain mandatory Task 5 re-freeze work, not a waiver.

## Worktree and baseline

- Worktree: `E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\impl`.
- Branch/base: `agent/task-4` at integrated HEAD `648e49e844bfe43e4f4f10a5a36fbf806ee237fa`.
- Allowed files: `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py` and `tests/circular_tracking/test_hidden_disturbance_td3_env.py` only.
- Baseline: dependency check clean; full repository 264 passed with 13 pre-existing warnings; compileall and canonical protocol SHA-256 `80f78f7af532a7701c97c93b38c0af6f6cd41c5cfb111db72c6a85b150f2cce5` passed; worktree clean.
- Implementer must first preserve the terminal RED tests, then modify only the two whitelisted files. Task 4 is authorized; no training or Task 5 tuning is unlocked.

## Implementation and root verification

- Implementer commit: `11c8253a68e8e2d191d96e32622678495b975109`.
- TDD RED before production edits: 15 selected tests failed and 243 were deselected.
- GREEN implementation: pure `_failure_reason_for_current_state()` uses one completed-substep state snapshot and one current reference; protocol priority and strict thresholds are applied; reward subtracts the exact 50-point failure penalty; termination and info independently call the helper; no legacy coupling or Task 5 scope.
- Root verification at the implementation HEAD: 258 focused, 258 circular, and 279 full tests passed with 13 pre-existing warnings; dependency check, compileall, two-file scope, protocol hash, diff-check, and clean-status checks passed.
- Status: awaiting independent specification/science review before quality review.

## Specification/science review

- Reviewer: `/root/task4_spec_review`.
- Decision: `APPROVED` (Critical 0, Important 0, Minor 0) for `648e49e..11c8253`.
- Verified protocol 1.0.1 priority and strict thresholds, completed-substep reference time, pure helper/no cache or mutation, independent reward/termination/info calls, exact 50-point terminal penalty, and terminal transition outputs. Sixteen focused failure/terminal tests passed under review; Task 5 constructor compatibility and absence of Task 5/6 leakage were confirmed.
- Status: awaiting independent quality/reproducibility review.

## Quality review

- Reviewer: `/root/task4_quality_review`.
- Decision: `WITH_FIXES` (Critical 0, Important 1, Minor 0).
- All lifecycle, boundary/priority, purity, resource, information-boundary, and scope audits passed. One Important numerical issue remains: a nonfinite or overflowing cached state is classified as `non_finite_state`, but the current reward calculation can still return NaN/Inf.
- Required narrow fix: same implementer adds a finite deterministic reward fallback for nonfinite/overflow state plus a regression setting cached position/velocity nonfinite; preserve canonical reason, `terminated=True`, no mutation, and all approved semantics.

## Numerical fix and root re-verification

- Same implementer commit: `e8f6dc52e2bf7e0d237f4437da2cfbcfb5c867aa`, following `11c8253a68e8e2d191d96e32622678495b975109`.
- RED: three selected regressions failed before production edits (NaN position reward `nan`, Inf velocity reward `-inf`, huge finite position reward `-inf`). GREEN: all three pass with finite deterministic fallback and no runtime warning.
- Root re-verification: 261 focused, 261 circular, and 282 full tests passed with 13 pre-existing warnings; dependency check, compileall, two-file cumulative scope, protocol hash, diff-check, and clean-status checks passed.
- Awaiting same quality reviewer numeric rereview; Task 4 remains unintegrated until approval.

## Numeric quality rereview

- Same quality reviewer approved `11c8253..e8f6dc5` (Critical 0, Important 0, Minor 0).
- Three numeric regressions passed: NaN/Inf state gives canonical `non_finite_state`, finite deterministic `-50.0`, and `terminated=True` without runtime mutation; huge finite position gives canonical horizontal failure and finite `-50.0`. Normal reward/terminal behavior and protocol remain unchanged.
- Task 4 is awaiting fresh root post-review verification before serial integration.

## Root post-review verification

- Fresh verification after numeric approval: 261 focused, 261 circular, and 282 full tests passed with 13 pre-existing warnings; `pip check`, compileall, cumulative two-file scope, canonical protocol hash, diff-check, and clean-status checks passed at `e8f6dc52e2bf7e0d237f4437da2cfbcfb5c867aa`.
- Ready for serial cherry-pick of `11c8253a68e8e2d191d96e32622678495b975109` and `e8f6dc52e2bf7e0d237f4437da2cfbcfb5c867aa` onto integration.

## Serial integration

- Reviewed commits integrated in order as `7d25569` and `3889440` on `integration/hidden-td3-rebuild`.
- Integration verification: 261 focused, 261 circular, and 282 full tests passed with 13 pre-existing warnings; dependency check, compileall, protocol hash, diff-check, and clean status passed.
- Task 4 status: `complete`. Task 5 PID tuning is now unlocked; no training runs have started.

## Critical pre-review findings

1. `BaseAviary.step()` computes reward before termination. Reading a cached failure reason reproduces the legacy missing-terminal-penalty bug.
2. The helper must use the completed-physics-substep state/reference time, not the pre-increment Base step counter.
3. Protocol 1.0.1 requires one canonical `altitude_limit`; do not copy the legacy split altitude reasons or use a stale constant height instead of current `reference_z`.
4. `info["failure_reason"]` must independently call the same pure helper and cannot read mutable legacy state.

## Required RED tests

- Terminal `env.step()` returns `terminated`, the current canonical reason, and the failure penalty on that transition.
- Identical safe/failing reward inputs differ by exactly `50.0`, not merely by a loose negative threshold.
- Priority matrix: nonfinite, altitude, tilt, horizontal, safe.
- Strict boundaries tested with `numpy.nextafter` for every max/min threshold.
- Altitude error uses current reference altitude.
- Repeated helper calls are pure/uncached and immediately reflect state mutation without changing state, time, PID, or history.
- Reward, termination, and info agree while calling the helper independently.
- Reference lookup after one control step uses completed-substep time `5/240`.

## Helper contract

`_failure_reason_for_current_state()` reads one state snapshot and one current reference, returns only a protocol reason or `""`, and mutates nothing. Reward subtracts `failure_penalty=50.0` from its local reason; termination converts a fresh result to bool; info stores a fresh result.

## Implementation cautions

- Task 3 must keep `_current_time()` tied to completed physics substeps.
- Applied/previous RPM caches update during action application, not reward.
- Use function-scoped fixtures and `try/finally env.close()`; never globally disconnect PyBullet.
- Keep failure logic and penalty mode-independent.

## Planned verification

```powershell
py -3.11 -m pytest tests/circular_tracking/test_hidden_disturbance_td3_env.py -k "failure or terminal" -vv
py -3.11 -m pytest tests/circular_tracking/test_hidden_disturbance_td3_env.py -v
py -3.11 -m pytest tests/circular_tracking -v
py -3.11 -m compileall experiments/circular_tracking/rl_envs
git diff --check
```
