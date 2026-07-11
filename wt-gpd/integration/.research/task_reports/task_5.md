# Task 5 Report — PID Tuning And Freeze

## Protocol 1.0.2 revalidation pre-review

- Status: the previously complete Task 5 evidence is historical under protocol 1.0.2 because its config and immutable artifacts bind the prior protocol and environment source hashes. This is an expected fail-closed invalidation, not a PID acceptance failure.
- Recommendation: run a new validation-only standard seed-100, 30-second 81-candidate four-shard grid plus winner recheck after Task 3/4 correction integration, rather than create an old/new all-81 trajectory-parity attestation. The latter requires at least 162 old/new trajectories, a dual-source proof format, and more audit surface than a direct current-environment 81+1 validation run.
- Before that run, harden the provenance loader/producer to a new evidence schema that indexes and verifies `RUNNING`, manifest, all 81 candidate records, all 4 shards, coverage, ranking, winner recheck and `DONE`, then recomputes ranking from the candidate records. A bare winner recheck cannot prove that the current protocol's grid was exhaustive or that the winner remains globally ranked first.
- Prohibited: test/unseen seeds, TD3 training, overwriting/continuing the old external attempt, or manually transplanting old hashes/metrics into a new config.

## Evidence-v2 correction worktree baseline

- Isolated worktree: `E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\task5-refreeze`, branch `agent/task-5-refreeze`, base `031788f8c54b6009d38e5e589384e058291a6187`.
- Baseline acceptance suite: 15 passed and 14 failed. Every failure is the intentionally stale protocol-1.0.1 frozen config rejecting protocol 1.0.2 before its original tamper/acceptance assertion; this is the expected pre-refreeze state and is not waived.
- Phase A file scope: only `tune_hidden_pid.py` and `test_hidden_pid_acceptance.py`. The frozen config and all external artifacts must remain untouched until the evidence-v2 code has passed both reviews and a new immutable external validation grid is authorized.

## Evidence-v2 root verification — boundary fix required

- Implementer commit under review: `1f5bfbeafa552e03030ba3fdf538b31ea2603c00`; scope is limited to the two authorized files and synthetic evidence-v2 tests pass.
- Root full acceptance verification: 35 passed and 4 failed. One failure is expected: the real repository nominal PID acceptance cannot load the deliberately stale schema-2 frozen config. Three failures are not accepted yet: invalid validation duration/seed requests must reject at the public validation boundary before they attempt to load the stale default config, but currently fail with `schema version is unsupported` instead of `validation`.
- Required same-implementer correction: preserve the fail-closed stale-config behavior for valid nominal acceptance, while restoring pre-simulation validation-scope rejection for the three invalid-scope cases. No grid, config write, external artifact, TD3, test or unseen action is authorized.

## Evidence-v2 implementation and root verification

- Implementation commits: `1f5bfbeafa552e03030ba3fdf538b31ea2603c00` (complete evidence chain) and `9b22dc4b0f5080e46cc433b79c55bf04e0879c0a` (validate public scope before default-config loading).
- TDD: synthetic evidence-v2 RED had 10 failures for absent old schema/index closure; GREEN had 21 evidence tests passing. The scope-boundary RED had 3 failures; its GREEN restored 3/3 invalid duration/seed rejections before default config loading.
- Root full acceptance verification: 38 tests passed. The only remaining failure is the intentional real nominal PID acceptance against the repository's stale schema-2 config; it fails closed as unsupported and will be resolved only by the new full validation grid/config generation.
- Root checks: compileall and dependency integrity passed; the cumulative range contains exactly the two whitelisted tuner/test files; diff-check and worktree-clean checks passed. No real PID rollout, external attempt, grid, TD3 run, test or unseen seed was executed in this code phase.

## Evidence-v2 specification review — changes required

- Reviewer: `/root/task5_evidence_v2_spec_review`.
- Verdict: `CHANGES_REQUIRED` — Critical 1, Important 3, Minor 1.
- Critical: PID freeze scope accepts validation seed 101–109 although this task must use only canonical seed 100. Require exact seed 100 before config/simulation and a seed-101 RED regression.
- Important: verify source identities against the exact evaluation Git commit blobs, not merely current-worktree digests plus an existing SHA; add a consistent Git-SHA/index tamper regression.
- Important: make the post-`DONE`/pre-config-write state recoverable, so an immutable complete attempt can finish the frozen-config write without rerunning or overwriting the grid.
- Important: explicitly classify the repository nominal acceptance as stale-evidence expected failure until the current config is generated; it must automatically become a real acceptance test after regeneration.
- Minor: rehash/rebind a tampered candidate and index while leaving a dependent shard/ranking stale, proving graph reconstruction rather than only an immediate self-hash mismatch.
- Positive audit: synthetic v3 chain, full 81/4-shard traversal, ranking recomputation, 30-second duration, standard profile, worker/thread limits, external root and non-overwrite guards are otherwise present; no experiment was run.

## Evidence-v2 specification fixes submitted

- Follow-up commit: `cbc3518186eab4aa400478fdc36376be9a36217e` (`fix: harden PID freeze provenance recovery`).
- RED: four targeted failures for seed-101 scope, re-bound existing Git SHA/source identity, post-DONE missing-config recovery, and candidate graph reconstruction.
- GREEN: 15 closure tests passed and the deliberately stale nominal acceptance is dynamically xfailed; broader pre-grid classification is 40 passed, 1 xfailed, 1 deselected (the deselected test is the synthetic 81-candidate tuner exercise). No real PID rollout, external attempt, grid, TD3, held-out seed, config rewrite, or persistent synthetic artifact was created.
- Claimed fixes awaiting root verification: exact seed 100; `git show <evaluation_sha>:path` blob/digest validation including RUNNING; recover immutable DONE evidence to write an identical missing config without rerunning; dynamic stale-schema nominal classification that resumes real acceptance once schema-3/current config exists; rehashed/reindexed candidate tamper that retains stale dependent graph records.

## Final evidence-v2 blocker before re-review

- Re-review found one remaining Critical issue: Git blob identities were computed from the evaluation SHA but not compared to the actual protocol/environment/tuner files used by the process. A dirty worktree could therefore execute altered source while metadata claimed clean blobs.
- Required narrow repair: both producer and loader must compare each current source digest with the matching `git show <evaluation_sha>:<repo-relative-path>` digest and fail closed on mismatch; add a synthetic dirty-source mismatch RED/GREEN test. The original implementer is no longer live, so a fresh single implementer is assigned to the same isolated branch and whitelist.

## Dirty-source identity repair submitted

- Recovery implementer commit: `0d2281d01efd2fe5d7cf3468057c3b0a85273671` (`fix: bind PID evidence to clean source blobs`).
- RED: producer dirty-source test incorrectly reached candidate-grid work; loader dirty-source test accepted evidence. GREEN: both tests pass.
- The evidence index/config now record and compare both Git-blob and actual working-tree canonical SHA-256 identities for protocol, environment and tuner. Producer preflights before candidate enumeration; loader and recovery revalidate. Reported full pre-grid acceptance is 43 passed and one explicit stale nominal xfail; no real experiment occurred.

## Final specification re-review

- Reviewer verdict: `APPROVED` — 7 checks approved, 0 changes required.
- Closed: exact seed 100, Git blob versus current-source binding in producer/loader/recovery, post-DONE missing-config recovery, dynamic stale nominal xfail, and full candidate/shard/ranking/DONE graph reconstruction.
- Reviewer could complete static inspection, syntax and diff checks, but its isolated runtime lacked PyBullet; root local runtime verification remains mandatory before quality review.

## Quality/reproducibility review — fixes required

- Reviewer: `/root/task5_evidence_v2_quality_review`.
- Verdict: `WITH_FIXES` — Critical 2, Important 2, Minor 1.
- Critical 1: current immutable output/config writes use check-then-replace semantics and fixed temporary names, permitting concurrent writers to overwrite evidence. Require an attempt-level exclusive lock, unique temporary writes, atomic exclusive commit/re-read-hash semantics, and a concurrent-writer regression.
- Critical 2: producer checks the working tree before/after but workers can execute a transiently modified source in between. Workers must run from an immutable evaluation-SHA snapshot/archive (or equivalent per-worker executable identity evidence), not the mutable worktree.
- Important: validate the complete evidence graph in memory before writing a recovered config; otherwise an interrupted incomplete DONE can leave an unresumable config. Make stale nominal xfail precise to schema 2 only and automatically execute a schema-4 current config; remove hard-coded stale expectations. Ensure environment construction failure and close paths cannot leak or mask exceptions.
- Positive: full 81/4-shard graph reconstruction, fixed validation-only scope, external roots, and nonexperimental runtime subset are otherwise sound. No real grid, TD3, test or unseen work has run.

## Post-fix root verification

- Fresh targeted closure suite, compileall and dependency integrity exited successfully on `cbc3518186eab4aa400478fdc36376be9a36217e`; the complete acceptance file also exited successfully with the explicitly classified stale nominal xfail. The cumulative change remains limited to the two approved tuner/test files with a clean diff check.
- Authorized next action: the same independent specification reviewer must re-review all five closed findings before a quality review or any external validation grid.

## Status

- Lifecycle: `in_progress`; Tasks 3 and 4 are integrated and the isolated `agent/task-5` worktree has passed its clean baseline.
- Read-only pre-review completed by `/root/task5_pre_review`; no grid or simulation was run and no files were modified.
- Implementation is authorized for validation-only PID tuning; no disturbed test/unseen evaluation or TD3 training is unlocked.

## Worktree and baseline

- Worktree: `E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\impl`.
- Branch/base: `agent/task-5` at `843885b848ffcb276906aa6caa0d08a9d4da289e`.
- Allowed files: `experiments/circular_tracking/scripts/td3/tune_hidden_pid.py`, `experiments/circular_tracking/config/hidden_pid_frozen.json`, and `tests/circular_tracking/test_hidden_pid_acceptance.py` only.
- Baseline: dependency check clean; 282 tests passed with 13 pre-existing warnings; compileall and canonical protocol SHA-256 `80f78f7af532a7701c97c93b38c0af6f6cd41c5cfb111db72c6a85b150f2cce5` passed; worktree clean.

## Critical pre-review findings

1. Every candidate needs a fresh environment/controller. `DSLPIDControl.computeControl()` is stateful and must run exactly once per control instant.
2. Freeze phase error, path length, steady window, acceptance filtering, and ranking/tie-break definitions before launching 81 candidates.
3. Never use the legacy fallback that substitutes full-prefix RMSE when a steady window is missing.
4. `hidden_pid_frozen.json` records the clean evaluation Git SHA containing the tuner/environment; it cannot self-reference the later config commit SHA.

## Frozen interface expectations

- `reference_velocity_gain` multiplies the analytic reference velocity.
- XY P and D scales start from fresh stock DSL coefficients and never compound across reset.
- `pid_target_step_limit=0.0` means disabled; nonzero behavior must be frozen against the Task 3 public interface.
- Ordinary PID feedback/integral memory is allowed; oracle disturbance, PID-FF, truth-derived gates, and legacy action semantics are forbidden.

## Deterministic four-process plan

- Enumerate indices with the declared parameter order and last dimension fastest; exactly 81 unique candidates.
- Assign `shard = candidate_index % 4`, producing sizes `21,20,20,20` with complete non-overlapping coverage.
- Windows spawn; one BLAS thread and one independent PyBullet DIRECT client per worker.
- Workers evaluate only. Root/parent validates immutable `candidate_NNN.json` records, coverage, hashes, and performs deterministic central ranking.
- Scientific failures are completed results and never retried. Only infrastructure failure may create `attempt_02`.
- Rank the finite failure-free accepted pool by steady RMSE, mean absolute wrapped phase error, absolute path-ratio deviation, then candidate index.
- If no candidate passes every acceptance condition, emit NO-GO and do not create/replace the frozen config.

## Required tests before the grid

- Candidate enumeration/index round-trip and first/last values.
- Four-shard union, no overlap, and sizes `21/20/20/20`.
- Failure/nonfinite exclusion, deterministic lexicographic ranking, and index tie-break.
- Strict RMSE `<0.10`; inclusive path ratio `[0.90,1.10]`; finite phase/motor metrics and complete 1440-step horizon.
- Canonical JSON/hash round-trip and schema/protocol tamper rejection.
- Resume/attempt semantics, one fresh/closed environment per candidate, and non-compounding gain scaling.
- Phase wrap, near-center invalid phase, initial-point path length, and no early-failure steady fallback.
- Legacy conservative PID is preserved as a negative diagnostic and must be rejected by acceptance.

## Metric definitions to freeze

- Steady samples start after the first 10-second period using completed-substep time.
- Float64 3-D position RMSE over the steady window only.
- XY path ratio includes reset state and all 1440 transitions; use stable summation.
- Mean absolute wrapped phase error; near-zero radius is invalid under a frozen epsilon.
- Failure includes termination, nonfinite values, motor-bound violation, or incomplete horizon; normal 30-second truncation is success.
- Energy, smoothness, and saturation use final applied RPM.

## Expected evidence artifacts

```text
attempt_01/RUNNING.json
attempt_01/candidate_manifest.json
attempt_01/candidates/candidate_NNN.json
attempt_01/shards/shard_NN.json
attempt_01/coverage.json
attempt_01/ranking.json
attempt_01/winner_recheck.json
attempt_01/DONE.json
```

The future frozen config must include parameters, winner index/metrics, exact command and definitions, protocol hash/basis, evaluation Git SHA, environment/schema/source digest, geometry/frequencies/seed/profile, Python/platform/package versions, manifest/ranking digests, and a canonical PID payload hash.

## Specification review

- Reviewer: `/root/task5_spec_review`.
- Decision: `CHANGES_REQUIRED` (Critical 0, Important 3, Minor 1). The baseline winner is valid, but the tuner is not yet compliant enough to freeze.
- Important 1: central ranking trusts a caller-provided `accepted` flag. It must independently recompute finite, failure-free, complete-horizon and metric acceptance before ranking.
- Important 2: public tuning entry points accept arbitrary seeds and rollout durations. They must fail closed to validation seeds 100–109 and the 30-second/1440-step nominal validation contract.
- Important 3: the four worker shards need immutable per-candidate records plus manifest, shard, coverage, ranking, winner-recheck, `RUNNING.json`, and `DONE.json` provenance; the parent remains the only ranking/config writer and runtime thread limits must be set.
- Minor: reject noncanonical candidate lists and non-four-way shard requests rather than accepting arbitrary input.
- Status: same implementer must add RED/GREEN regressions for all four findings, then this reviewer re-reviews before quality review.

## Specification-fix implementation and root verification

- Fix commit: `5d724c25cf08faa2b7b868cbb2e0631cf8524799`; it changes only the tuner and acceptance tests. The original frozen PID config is deliberately unchanged.
- RED: 7 failed and 4 passed against `c76c724`, covering spoofed acceptance, noncanonical shards, invalid duration/seeds, seed-0 tune, and absent evidence/resume API.
- GREEN/root verification: 11 acceptance, 272 circular, and 293 full tests passed with 13 pre-existing warnings; dependency check, compileall, two-file scope, frozen-config load, protocol hash, diff-check, and clean-status audits passed.
- Evidence behavior: exact four canonical shards; parent-only ranking/config output; immutable RUNNING/manifest/candidate/shard/coverage/ranking/winner-recheck/DONE records with hashes; resumed candidate collection and crash-after-config-before-DONE recovery are exercised in external temporary paths.
- Status: awaiting same specification reviewer rereview of the 3 Important and 1 Minor findings.

## Specification rereview

- Decision: `CHANGES_REQUIRED` (Critical 0, Important 1, Minor 0).
- Closed: validation-only seed/duration boundary; canonical four-shard immutable evidence, parent-only writer, BLAS caps, resume/no-overwrite behavior; no tracked attempt artifacts.
- Remaining defect: `completed_steps` is coerced through `int()`, allowing a spoofed `1440.9` to satisfy the exact 1440-step acceptance criterion and enter ranking.
- Required narrow fix: accept only an exact integral numeric value of 1440; reject strings and nonintegral floats (including 1440.1 and 1440.9) with RED/GREEN regression, then use the same specification reviewer again.

## Exact-step-count fix and root verification

- Fix commit: `7b609d87181c6810c75dc90cc5581a3c9c68d18e`.
- RED: 3 failed and 3 passed before production edits; 1440.1, 1440.9, and string `"1440"` were incorrectly accepted, while `None` and booleans were already rejected.
- GREEN: only integer/integer-numpy 1440 or finite floating 1440.0 is accepted; strings, booleans, and nonintegral values fail closed.
- Root verification: 17 acceptance, 278 circular, and 299 full tests passed with 13 pre-existing warnings; dependency check, compileall, two-file scope, frozen config, protocol hash, diff-check, and clean-status audits passed.
- Status: awaiting same specification reviewer’s final narrow rereview.

## Final specification rereview

- Decision: `APPROVED` (Critical 0, Important 0, Minor 0).
- Accepted: integer/numpy-integer 1440 and finite 1440.0. Rejected without ranking: 1440.1, 1440.9, string `"1440"`, booleans, numpy booleans, and null.
- Scope remains tuner/tests only; frozen config unchanged. Reviewer reran 17 targeted and 278 circular tests with clean compile/diff status.
- Status: awaiting independent quality/reproducibility review.

## Quality review

- Decision: `WITH_FIXES` (Critical 0, Important 1, Minor 0).
- The hardened tuner mechanics pass review, but the committed frozen config was produced before that evidence chain existed. It lacks manifest/coverage/ranking/winner-recheck provenance digests, and the loader still accepts tampered seed, metrics, command and related provenance fields.
- Required fix: run one fresh validation-only standard 30-second seed-100 four-shard attempt under the hardened tuner; regenerate the tracked frozen config with immutable evidence/config hashes and complete control/physics metadata; make the loader reject provenance, metric and schema tampering; add tests. Generated attempt evidence remains external/untracked; compact digests and paths belong in the config.

## Immutable-evidence fix and root verification

- Code/schema commit: `5c92801dc493a934a7b88853a417486d743aa62e`; ranking-tamper test: `37085d6`; regenerated config-only commit: `d9901de4b0c367e0cc11b322e7b6738934b98020`.
- Fresh validation-only command exited 0 using `standard`, seed `100`, 30 seconds/1440 steps, 81 canonical candidates and 4 workers. The external immutable attempt is [attempt_01](E:\rlbk\hidden-td3-pid-validation-20260711\attempt_01), while the compact tracked config contains its paths and content/file hashes.
- Config uses non-self-referential `evaluation_git_sha=5c92801…`; it records manifest, coverage, ranking, winner-recheck, DONE and config-payload hashes. Loader contract tests now reject provenance, metric, seed/duration, geometry/frequency, schema and hash tampering.
- Root verification: 27 acceptance, 288 circular, and 309 full tests passed with 13 pre-existing warnings; dependency check, compileall, three-file scope, external evidence loader, config payload, protocol hash, diff-check and clean-status audits passed.
- Status: awaiting same quality reviewer’s narrow immutable-evidence rereview.

## Immutable-evidence quality rereview

- Decision: `WITH_FIXES` (Critical 0, Important 1, Minor 0).
- Closed: the committed config’s external seed-100/30-second evidence chain independently loads and validates all immutable hashes, coverage, winner, non-self evaluation SHA and schema tampering.
- Remaining issue: the producer’s repository-local default attempt root contradicts the loader’s external-provenance policy; it could run 81 candidates and only then create a config the loader rejects.
- Required narrow fix: reject repository-local/default attempt roots before candidate enumeration (or otherwise require a durable external root), update the safe invocation behavior, and add a regression proving no candidate evaluation begins.

## External attempt-root preflight fix

- Fix commit: `6f976ecc51017db001050691bbd1f0226af5ee2c`.
- Producer/CLI now rejects missing, relative, and repository-local attempt roots before output creation, grid enumeration, worker creation, or artifact writes; help requires a durable absolute directory outside the repository. The valid external evidence/config remains unchanged.
- Root verification: 29 acceptance, 290 circular, and 311 full tests passed with 13 pre-existing warnings; dependency check, compileall, two-file scope, frozen config loader, protocol hash, diff-check, and clean-status audits passed.
- Status: awaiting final same-quality-reviewer rereview.

## Final quality rereview

- Decision: `APPROVED` (Critical 0, Important 0, Minor 0).
- External attempt-root enforcement happens before output handling, candidate enumeration, worker creation, or artifact writes; CLI requires `--attempt-root`. Tests use an enumeration sentinel to prove omitted/repository-local roots do not start evaluation.
- The existing external schema-v2 config and attempt remain independently valid (evaluation SHA `5c92801…`, seed 100, 30 seconds, 81 candidates, winner 78). No generated `pid_tuning` evidence is tracked.
- Task 5 is awaiting a final fresh root verification before serial integration.

## Final root verification

- Fresh post-quality verification at `6f976ecc51017db001050691bbd1f0226af5ee2c`: 29 acceptance, 290 circular, and 311 full tests passed with 13 pre-existing warnings; dependency check, compileall, three-file scope, external evidence/config loader, protocol hash, diff-check and clean-status audits passed.
- Ready to serially integrate `208ee97`, `c76c724`, `5d724c2`, `7b609d8`, `5c92801`, `37085d6`, `d9901de`, and `6f976ec`.

## Serial integration

- Source commits integrated in order as `2c0e80b`, `ebaff27`, `ba88443`, `ab1f2fd`, `c0aff3d`, `dee352d`, `de6bc1e`, and `6d327bd`.
- Integration verification: 29 acceptance, 290 circular, and 311 full tests passed with 13 pre-existing warnings; dependency check, compileall, external evidence/config loader, protocol hash, diff-check and clean status passed.
- Task 5 status: `complete`. The frozen PID configuration is now the only valid nominal PID baseline for downstream training.

## Evidence-v2 quality-fix implementation and root verification

- Corrective implementation commit: `0746d1e52d3af3bd5c74cc4b30c5137b57c96e29`; relative to `0d2281d…`, it changes only `tune_hidden_pid.py` and `test_hidden_pid_acceptance.py`.
- TDD RED: 9 failed, 1 passed before production fixes. GREEN: acceptance 54 passed, 1 known schema-2 xfailed; circular 318 passed, 1 known schema-2 xfailed; full 339 passed, 1 known schema-2 xfailed, 13 pre-existing warnings.
- Independent root verification repeated all three suites with distinct external pytest temporary roots; `pip check`, targeted `compileall`, diff-check, source-scope, clean-status, canonical protocol hash and protected protocol/frozen-config diff audits passed.
- Closure includes atomic no-overwrite records and attempt lock, evaluation-SHA source snapshot execution, graph validation before config write, known-schema-only stale classification, and resource-safe evaluation environment teardown. No PID grid, TD3, test or unseen execution occurred.
- Status: awaiting narrow read-only specification/scientific rereview of this quality-fix range before quality rereview and integration.

## Evidence-v2 quality-fix specification rereview

- Decision: `CHANGES_REQUIRED` (Critical 1, Important 0, Minor 0).
- The archive only contained `experiments/circular_tracking/**`, but the isolated evaluator imports `experiments.circular_tracking...`. Without the top-level `experiments/__init__.py`, Python can resolve the package from the mutable worktree after the archive is created; the current monkeypatched loader test proves routing only, not actual import isolation.
- Required narrow repair: archive the complete package closure and add a real import-isolation RED/GREEN regression that marks/mutates the live environment after snapshot creation, then proves worker-side evaluation imports the immutable evaluation-SHA archive. The implementation remains limited to the tuner and its acceptance tests; PID grid, config rewrite, TD3 and held-out work remain prohibited.

## Snapshot import-isolation repair

- Fix commit: `38d20deaf49a32d83f3ed69a12fcc919b9eaa4f4`, limited to the same tuner/test whitelist.
- The new real import-isolation test creates a snapshot, marks the live top-level `experiments/__init__.py` to raise, and demonstrates RED failure before the fix and GREEN success after it. The archive now includes the top-level `experiments/__init__.py`, closing the absolute-import fallback to the mutable worktree.
- Implementer verification: isolated test 1 passed (four duplicate Gym registration warnings); acceptance 55 passed, 1 known schema-2 xfailed, four warnings; compileall and diff-check passed. Full root verification and same-spec rereview remain required.

## Snapshot repair root verification and batched preflight

- Root verification at `38d20de…`: real isolation 1 passed; acceptance 55 passed/1 known schema-2 xfailed; circular 319 passed/1 known xfailed; full 340 passed/1 known xfailed with 17 warnings. Dependency, compile, diff-check, two-file scope, clean worktree and protected protocol/frozen-config diff audits passed.
- In accordance with the durable batch-preflight policy, two read-only agents now concurrently inspect the full range for (a) implementation/reproducibility/import/recovery risks and (b) protocol/scientific/fairness/test-contract risks. Their combined findings will become one deduplicated repair manifest; no formal review or isolated repair starts before consolidation.

## Batched preflight: consolidated one-pass repair manifest

The two concurrent read-only preflights examined the same `0746d1e…38d20de` range and produced the following deduplicated manifest. One implementation pass must close every non-deferred entry before another batch preflight; no entry may trigger its own repair/review loop.

| Severity | Consolidated finding | Required closure |
|---|---|---|
| Critical | Loader verifies a ZIP hash/path list but not that every ZIP member exactly matches the `evaluation_git_sha` blob; a placeholder-only archive can be accepted. | Require exact duplicate-free member set and compare every member’s bytes/digest to `git show <sha>:<path>`; test placeholder, missing, extra, duplicate and altered members. |
| Important | Relative attempt roots can be resolved outside the repo before the relative-path rejection. | Reject non-absolute input before resolution; test relative outside-repo inputs without enumeration/artifact creation. |
| Important | Windows `spawn` can import the live tuner/package before the snapshot loader runs. | Use a bootstrap entrypoint that installs the verified snapshot before any application import; exercise a real spawned worker with a live-package poison guard. |
| Important | Snapshot imports are restored before evaluator execution, allowing lazy imports to resolve from the live worktree. | Keep a snapshot-only import context/module graph throughout worker evaluation; test a deferred import during execution. |
| Important | A pre-existing incomplete output may run work before ultimately failing no-overwrite validation. | Reject it before creating a pool/evaluator unless it is the exact complete recovery case; test with sentinels. |
| Important | The current isolation test overwrites tracked `experiments/__init__.py`, creating crash/concurrency residue. | Use only process-local import guards or temporary external path fixtures; prove tracked source bytes remain unchanged. |
| Minor | `main(argv=...)` certifies global `sys.argv`, not the parsed command. | Record the supplied effective argv; add a no-rollout metadata regression. |

The preflight also confirms one **deferred scientific gate**, not a code patch: the checked-in schema-2 default PID config is intentionally stale and must remain rejected. The next authorized Task 5 stage, after code integration, is a fresh external validation-only grid that creates a schema-4 config/evidence chain; no PID acceptance or TD3 work may proceed before that occurs.

## Batched manifest submission

- The implementation lane produced clean commit `32700bbed5f3b41da00cb6f9f42822aa8ddbad5a` (same two-file whitelist) after concentrating the full manifest in one repair pass. Its agent did not return a reliable final summary after committing, so no implementation-side result is accepted as evidence beyond the clean SHA and the earlier 9-test selection.
- The root must independently verify every manifest item and all required suites against this exact SHA before repeated preflight. This preserves verification integrity while preventing an idle implementation turn from delaying the pipeline.

## Root-verification timeout diagnosis

- The 10 targeted manifest regressions pass at `32700b…`. However, the full PID acceptance suite timed out twice without an exit result, once at 110 seconds and again at 200 seconds, each with a new external pytest temporary root. A timeout is not accepted as a pass.
- Two read-only diagnoses are running concurrently: snapshot-subprocess/import lifecycle analysis and acceptance-suite order/bisection analysis. Their consolidated evidence will determine one minimal repair or verification adjustment; no source, grid, frozen-config, TD3 or held-out execution is authorized during diagnosis.

## Timeout diagnosis: consolidated one-pass repair manifest

- The full suite is slow rather than deadlocked: a real worker probe passed, while snapshot creation calls `git show` independently for roughly 78 members on about 36 test paths. Measured snapshot creation is 5.86 s, so these writes alone account for about 211 s before validation/pytest overhead. Raising the timeout would only mask the regression.
- A real product regression is independently reproduced: `test_tune_attempt_writes_and_resumes_immutable_four_shard_evidence` fails after intentionally removing `DONE.json`, because the new incomplete-output guard rejects existing `frozen.json` before validating the strict no-rerun recovery case.
- Snapshot extraction also leaks about 16 MB `hidden_pid_snapshot_*` directories per real worker probe. Subprocess execution currently lacks an explicit deadline; that is a separate fail-closed reliability gap.
- One implementation pass must: cache/batch Git blob/tree material by evaluation SHA for both write and validation while retaining exact tamper detection; clean extraction directories in all paths; add an explicit tested worker deadline; and allow only fully matching immutable missing-DONE recovery before the no-overwrite guard (no snapshot/grid/worker and frozen bytes unchanged). Full verification must complete; a timeout remains a failure.

## Timeout-manifest implementation submission

- Final one-pass fix: `a0d9508c449d9a03009ba18ef0d3eeb861d2a01f`, restricted to the tuner and PID acceptance tests.
- RED: 4 failed, 1 passed, 64 deselected. GREEN: 5 selected passed, 64 deselected (four warnings); complete acceptance 68 passed, 1 known schema-2 xfailed, five warnings; dependency, compile and diff checks passed. The fix claims shared Git blob/tree caching, extraction cleanup, worker deadline semantics, and strict no-rerun missing-DONE recovery.
- Root verification must independently confirm that the entire acceptance suite completes (not merely a longer timeout), then re-run circular/full suites and repeated batched preflight.

## Timeout-manifest root verification and repeated preflight

- Root verification at `a0d9508…` passed: diagnostic target 5 passed/64 deselected; acceptance 68 passed/1 known xfailed in 64.05 s; circular 332 passed/1 known xfailed in 88.58 s; full 353 passed/1 known xfailed in 116.12 s. Thus the prior 110/200-second acceptance timeout is eliminated without relaxing its test requirement.
- Dependency, compile, diff-check, two-file scope, clean worktree and protected protocol/frozen-config audits passed. Two complementary read-only preflights are now repeated over the full combined repair range; only a clean combined result can unlock formal specification review.

## Repeated batched preflight: consolidated one-pass repair manifest

Both repeated preflights found no Critical issue but agreed that the following must be closed together before formal review:

| Severity | Finding | Required closure |
|---|---|---|
| Important | Missing-DONE recovery checks artifact hashes but not the complete candidate→shard→coverage→ranking→winner semantics or RUNNING command identity before writing a new DONE. | Reuse/extract complete graph validation that works without a pre-existing DONE, then add rebound-artifact and command-identity recovery regressions. |
| Important | A real `subprocess.run(timeout=...)` kills the child before its `finally`, so its extracted snapshot can leak even though normal cleanup tests pass. | Use parent-controlled cleanup or equivalent and prove cleanup after an actual timed-out child, not a mocked exception. |
| Minor | Git snapshot blob cache grows without a resource bound across many SHA values. | Bound/evict cache while preserving SHA isolation and exact byte checks. |
| Minor | Known schema-2 stale xfail is only path+schema based. | Bind the temporary historical exception to the canonical legacy artifact fingerprint; a modified schema-2 default must fail. |

The implementation lane must address all four in one TDD pass; no grid/config rewrite, TD3 or held-out execution is authorized.

## Stage A minimal-scientific viability pivot

- By explicit user direction (2026-07-11), Task 5 now blocks only on fairness, information leakage, reward/termination/statistics correctness, actual source/config/model identity, and silent controlled-result corruption.
- The selected scientific source is `a0d9508…`; later recovery/LRU/fingerprint hardening and the uncommitted test work in `agent/task-5-refreeze` are deferred to `.research/deferred_hardening_stage_a.md` and are not part of the Stage A experiment source.
- Remaining Task 5 fast path: one focused core verification, one full root verification, one joint final review, serial integration, then a fresh external standard seed-100/30-second/81-candidate/four-shard PID attempt that produces the current schema-4 frozen config. No new repair review cycle may start unless it exposes a scientific hard blocker.

## Joint Stage A review

- Existing selected-source evidence at `a0d9508…` is reused to avoid duplicate broad tests: focused 5 passed; PID acceptance 68 passed/1 expected stale-schema xfail; full suite 353 passed/1 expected stale-schema xfail.
- One read-only joint review is limited to scientific hard blockers. Engineering/recovery findings are deferred and cannot trigger another Task 5 repair loop.

## Fresh PID freeze completed

- Fresh external attempt: `E:\rlbk\hidden-td3-pid-validation-20260711\attempt_02`; source SHA `f19e991…`, protocol hash `e6edc37…`, standard seed 100, 30 seconds/1440 steps, 81 candidates and four workers.
- `DONE=GO`; candidate 78 was rechecked. The new schema-4 default config passed independent loader validation and has SHA-256 `c7530d…`. Winner metrics: steady RMSE 0.009598 m, path-length ratio 1.02267, saturation rate 0.
- Task 5 evidence-v2 refreeze is complete. Task 6 is unblocked; prior engineering hardening remains deferred.

## Joint Stage A review decision

- Decision: `APPROVE_FOR_INTEGRATION`.
- Scientific checks passed: canonical 81 candidates; seed 100, 30 seconds and 1440 steps; source identity binding; no TD3/test/unseen interaction; invalid rollout rejection before ranking/freezing. Deferred engineering items remain in `.research/deferred_hardening_stage_a.md`.

## Integrated verification classification

- The one allowed post-integration full suite produced 352 passed, 1 expected stale-schema xfail, and one non-scientific assertion-text failure. The code correctly rejected an evidence index rebound to a different Git SHA; the test expected a narrower legacy error phrase while the actual explicit rejection was `PID source snapshot record does not match the evaluation Git SHA`.
- This does not affect run identity, fairness, leakage, reward/termination, statistics, or silent result corruption. It is deferred as test hardening under the Stage A policy; no re-test loop is authorized. The next action is a new external PID validation attempt and schema-4 freeze.
