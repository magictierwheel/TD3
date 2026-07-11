# Task 2 Report — Deterministic Hidden Disturbance Processes

## Status

- Lifecycle: `complete`.
- Implementation is authorized under protocol `1.0.1` after final science approval.
- Read-only pre-review completed by `/root/task2_pre_review`; no files were modified.
- Fresh worktree: `E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\impl`, branch `agent/task-2`, base `fe3f17df233d77ddef029b0c4977261fb7482da5`.
- Baseline: 21 passed with 13 existing warnings; compileall and dependency check clean; protocol hash matches.

## Implementation

- Implementer: `/root/task2_implementer`.
- Commit: `61321f4e1f50c4d1406447fd798fd96e341b7e19`.
- RED: focused pytest collection failed with the expected missing `disturbance_processes` module before production code existed.
- Implementer verification: 40 focused/circular tests passed; 61 full tests passed with 13 existing warnings; compileall and all scope/protocol/seed checks passed.
- Root independent verification: same 40 focused and 61 full tests passed; explicit seeds are within `9000-9021`; protocol hash, two-file scope, protected diff, diff-check, and clean worktree verified.
- First specification/science review: production matches the protocol, but tests do not lock the exact stochastic law.
- Required fix: deterministic scripted-RNG tests for `sqrt(U)` radius/angle, independent interval and thrust/torque draws, stochastic `t=0`, and changed values after 20 seconds, with a temporary mutant RED demonstration.
- Test-only fix commit: `d4ec0ce96e3af50e7af0366085b974b721ff88c4`.
- Mutation RED: radius-without-sqrt mutant caused 3 failures; post-20 frozen-value mutant caused 1 failure.
- GREEN/root verification: 3 scripted tests, 43 focused tests, and 64 full tests passed; production file is unchanged; task scope/diff/status clean.
- Second specification review: scripted angles were all zero, leaving an angle-ignoring one-dimensional wind mutant undetected.
- Required fix: nonzero angle with explicit cosine/sine component assertions and temporary mutant RED proof.
- Test-only angle fix commit: `e78df981c53396eefd792649430532bffa7aceb6`.
- Mutation RED: an angle-ignoring mutant produced `(0.75, 0.0)` instead of the expected nonzero cosine/sine components and failed the affected test.
- GREEN/root verification: affected test 1 passed; focused file 43 passed; full suite 64 passed with 13 existing warnings; compileall, production-byte diff, task diff check, and worktree status all clean.
- Final specification/science rereview: `APPROVED`; nonzero-angle coverage now verifies both wind components, production is unchanged, protocol hash matches, and the two-file scope is respected.
- Quality/reproducibility review: no Critical issues; one Important issue requires an explicit stable `PCG64` bit generator and an exact fixed-seed golden schedule fingerprint because `default_rng` and same-runtime equality do not protect the experimental seed mapping across NumPy upgrades.
- Two Minor issues are recorded but non-blocking: public mutability of process metadata and uncommon malformed-input error normalization.
- Quality fix commit: `08e8d306bfa8d1ab76e3c1a60ce9d8a3eddeb50d`; production now explicitly constructs `Generator(PCG64(seed))`.
- RED: a substituted `PCG64DXSM` stream changed the fingerprint from `fbfc…95c1` to `c7fb…12e7`.
- Golden contract: seed `9025`, `compound`, 20 seconds, canonical `float.hex()` schedule encoding, SHA-256 `fbfc4bcb19f850f153984ae0f3eed0044427ac9de8e0458aa6f6b4e8f9dd95c1`.
- Root verification: 5 affected, 45 focused, and 66 full tests passed with 13 existing warnings; compileall, protocol hash, scope, protected-diff, diff-check, and clean status passed.
- Quality rereview: prior Important issue `CLOSED`; no Critical, Important, or newly introduced Minor issues; Python `3.11.9`, NumPy `2.4.6` recorded by reviewer.
- Final pre-integration verification: dependency check clean; 5 affected, 45 focused, and 66 full tests passed with 13 existing warnings; compileall, seed partition, protocol hash, scope, protected diff, diff-check, and clean status passed.
- Serial integration commits: `f40ced1` (implementation), `3aa7d0c` (stochastic-law tests), `eedaf72` (angle regression), and `808fcbb` (explicit PCG64/fingerprint).
- Integrated verification: dependency check clean; 5 affected, 45 focused, and 66 full tests passed with 13 existing warnings; compileall, implementation-content match, protocol hash, corrected diff-check, and clean status passed.
- Lifecycle: `complete`; the two prior Minor findings remain recorded and non-blocking for later hardening.

## Critical pre-review findings

1. The implementation-plan example uses `seed=7`, which violates the frozen unit-test partition `9000–9099`. All explicit Task 2 test seeds must be moved into that range.
2. The sketch's `min(horizon_sec, previous + interval)` can create a final interval below the frozen lower bound. Generate a bracketing knot at or beyond the horizon, or stop and formally reconcile the protocol before implementation; do not silently shorten the final interval.
3. A default `horizon_sec=20.0` plus clipped sampling can silently freeze the last ten seconds of a 30-second evaluation. Prefer an explicit required horizon and validate the query domain.
4. The frozen protocol gives ranges but not the complete stochastic law. The implementation and tests must document a deterministic choice for radial wind sampling, interval distribution, efficiency correlation, and initial-knot semantics before research runs.

## Root protocol-reconciliation draft

- Unit-test examples now use seeds in `9000–9099` and require an explicit rollout horizon.
- Non-standard knot intervals are independent continuous-uniform draws; the final full interval creates a bracketing knot at or beyond the horizon and is never shortened.
- Valid queries are finite times in the closed interval `[0, horizon_sec]`; out-of-domain values fail instead of clamping.
- Horizontal wind is uniform by area in the bounded disk using `r = limit * sqrt(U)` and a uniform angle.
- Thrust and torque efficiencies are independent continuous-uniform draws at each knot; the stochastic initial value is drawn at `t=0`.
- `standard` is constant zero wind and unit efficiencies and is exempt from stochastic knot scheduling.
- This draft requires independent science review and a new canonical protocol hash before implementation authorization.
- Draft protocol version/hash: `1.0.1` / `80f78f7af532a7701c97c93b38c0af6f6cd41c5cfb111db72c6a85b150f2cce5`.
- Review status: pending `/root/protocol_reconciliation_review`.
- First science review: one Medium plan-only seed-partition issue; Task 4 uses training seed `0` in a unit-test example. All disturbance-process protocol checks passed.
- Root fix: Task 4 now uses unit-test seed `9003`; explicit Task 2-4 test seeds are `9000-9003`; protocol bytes and hash are unchanged. Awaiting same-reviewer rereview.
- Final science rereview: approved. Protocol 1.0.1 and the synchronized Task 2 plan are authorized for implementation after a fresh worktree baseline.

## Required test additions before production code

- Immutable scalar sample value object with tuple-valued `wind_xy`.
- Exact same-seed reproducibility and query-order independence.
- No mutation of global NumPy RNG state.
- Parameterized invariants for all five profiles using only seeds `9000–9099`.
- Strictly increasing knot schedule with declared intervals and horizon coverage.
- Piecewise-linear interpolation at knots and midpoints.
- A 30-second process with fresh knots/samples after 20 seconds.
- Fail-fast validation for invalid profile, seed, horizon, and nonfinite/out-of-range sample times.

## Implementation cautions

- Do not copy the legacy sampler: it bounds components rather than wind-vector norm and uses incompatible unseen efficiency ranges.
- Use a private local `numpy.random.Generator`; pre-generate all knots so results do not depend on query order.
- `standard`, `random_wind`, `actuator_loss`, `compound`, and `unseen` must each enforce their exact disabled-component invariants.
- Task 2 imports the process from its direct module; package export changes remain reserved for Task 3.

## Planned verification

```powershell
py -3.11 -m pytest -q tests/circular_tracking/test_hidden_disturbance_td3_env.py -k "hidden_disturbance"
py -3.11 -m pytest tests/circular_tracking/test_hidden_disturbance_td3_env.py -v
py -3.11 -m pytest tests/circular_tracking -v
py -3.11 -m compileall -q experiments/circular_tracking/rl_envs/disturbance_processes.py tests/circular_tracking/test_hidden_disturbance_td3_env.py
py -3.11 -m pytest tests -q --durations=5
```

Before dispatch, root must persist the exact allowed files, base SHA, branch, RED command, and the reconciled knot/horizon semantics.
