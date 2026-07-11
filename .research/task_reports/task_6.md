# Task 6 Report — Matched Direct And Residual TD3 Training

## Status

- Lifecycle: `in_progress`; Task 5’s nominal PID is integrated and externally verifiable.
- Implementation is authorized in `E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\impl` on `agent/task-6` at `196fb61155f34194b6d02b74d9be1d036693fbdc`.
- Training remains limited to Task 6’s two 200-step smoke checks; Stage A/B/C budgets and held-out/test/unseen evaluation remain locked.

## Task contract

- One shared training entry point for Direct TD3 and Residual TD3, with identical observation/action/reward, network, TD3 hyperparameters, training distribution and budget.
- Residual actor output layer alone is zero-initialized; all other actor/critic initialization remains matched.
- Every run records Git SHA, protocol hash, frozen PID hash, package versions, interface schema, seed, budget, checkpoint, RUNNING/DONE metadata and immutable output directory.
- CPU-safe concurrency: at most four training processes; every process uses one OMP/MKL/OpenBLAS thread.
- No test/unseen seed or evaluation is authorized in this task.

## Worktree and baseline

- Allowed files: `experiments/circular_tracking/scripts/td3/train_hidden_td3.py` and `tests/circular_tracking/test_hidden_td3_training_config.py` only.
- Baseline: dependency check clean; 311 tests passed with 13 pre-existing warnings; compileall, canonical protocol hash, frozen PID loader, and worktree-clean checks passed.
- Smoke output must use ignored unique directories and contain `RUNNING.json`, `DONE.json`, config, model/checkpoint and compact progress evidence; it is not committed.

## Implementation and root verification

- Implementer commit: `24ab2169d2f2fd623d7648ae817b0e01a0a3fee7`.
- TDD RED: training-config test collection failed with `ModuleNotFoundError` before the production module existed.
- Root verification: 10 focused, 300 circular, and 321 full tests passed with 11 pre-existing warnings; dependency check, compileall, two-file scope, protocol hash and source diff-check passed.
- Smoke evidence: Direct and Residual 200-step seed-0 runs completed with matching RUNNING/DONE/config/progress/model artifacts. The live run directory is `experiments/circular_tracking/results/hidden_disturbance_td3_paper/smoke/task6_20260711_attempt_01`; it is preserved at `E:\rlbk\hidden-td3-task6-smoke-20260711\attempt_01` before worktree rebuild. It is not part of the source commit.
- Status: implementation is paused for an independent scientific-fairness adjudication. No source change or additional training is authorized until that decision is recorded.

## Specification/science review — changes required

- Recovery reviewer: `/root/task6_spec_review_recovery`.
- Verdict: `CHANGES_REQUIRED` — Critical 1, Important 2, Minor 0.
- Critical C1: the Direct environment exposes a 256-dimensional observation while the Residual environment exposes 260 dimensions because only Residual appends PID RPM. The trainer nevertheless declares a shared interface schema. This permits different actor/critic input layers and is not a matched Direct-versus-Residual comparison under the frozen research question.
- Important I1: the smoke metadata records `python -m __main__`, which is not a reproducible importable module command.
- Important I2: smoke `attempt_01` records parent Git SHA `196fb611...`, before the trainer source existed. It remains diagnostic evidence only. After any approved correction, a fresh immutable `attempt_02` smoke must record the committed source SHA and an importable module command.
- Required decision before implementation: reconcile the root plan's “same observable state” rule and frozen research question with its Task 3 allowance that Residual “may read PID command”; select one fair interface, state the protocol/evidence invalidation cascade, and add explicit parity/schema tests. The existing PID-freeze evidence hashes the environment source, so an environment-interface change requires the appropriate regeneration/revalidation before Task 6 can pass.

## Recovery verification while adjudication is pending

- 2026-07-11: root reran Task 6's focused trainer configuration suite in the current implementation worktree: 10 passed; `compileall` and dependency integrity passed.
- Root reran the current circular-tracking suite: 300 passed. The implementation worktree contains only the previously preserved untracked smoke compact evidence and ignored model artifacts; no source was changed during recovery.

## Scientific-fairness adjudication — binding decision

- Decision: `B-4`, Critical C1 upheld. Direct and Residual TD3 must receive one identical 260-dimensional policy observation: the existing eight-frame nonprivileged observable history plus the current four-dimensional RPM command emitted by the same frozen PID at the same control instant. Direct retains full-RPM action parameterization; Residual retains gated delta-RPM action parameterization and zero-output initialization.
- Rationale: PID RPM is not disturbance truth, but its integral controller state cannot necessarily be reconstructed from the eight-frame history. Giving it only to Residual therefore adds a nonprivileged controller-derived policy input and changes actor/critic capacity. Recording unequal schemas cannot make the comparison meet the frozen “identical observable flight-state information” question.
- Required pre-training correction: amend the protocol before a new smoke to make the shared policy schema, dimension, deterministic PID-RPM derivation, and prohibition on controller-specific PID-command features explicit. The Task 3 wording that Residual “may read PID command” must be reconciled to this shared-input contract.
- Required revalidation cascade: modify the environment and add observation parity/hidden-truth invariance tests; rerun Task 4 terminal/reward regressions; re-sign Task 5's PID config because it binds the protocol and environment source hashes, at minimum by proving PID-mode trajectory/action parity and re-evaluating the frozen winner for 30 seconds under the amended source. If parity fails, repeat the validation-only 81-candidate search. Then repair trainer provenance/schema metadata and run fresh Direct/Residual `attempt_02` 200-step smokes from a commit containing the trainer source.
- `attempt_01` is diagnostic-only: its command used `python -m __main__`, its Git SHA precedes the trainer source, and its residual metadata falsely claimed the 256-dimensional shared schema.

## Read-only revalidation impact audit — accepted blocking findings

- The base history is `8 × 32 = 256`; the current environment appends the current four-dimensional PID cache only for `residual_td3` and `residual_td3_no_gate`. The smallest environment repair is to include `direct_td3` in that condition while preserving the PID cache lifecycle and every action-preprocessing branch.
- The frozen PID loader fail-closes on both protocol and environment source hashes. Its old external evidence chain contains the old protocol hash in candidate manifests and records, so it remains historical evidence only rather than a new freeze chain.
- A narrow re-sign is scientifically sufficient only if a new all-candidate PID-mode trajectory/action/metric parity proof shows that the shared-observation repair leaves all 81 PID candidates bitwise-equivalent. Without that exhaustive parity proof, a fresh validation-only 81-candidate four-shard search is required before accepting a new winner. In all cases, a new external provenance attempt and a new 30-second seed-100 acceptance record are required.
- Task 6 cannot resume until the corrected environment, protocol, PID config, actual policy schemas/dimensions and trainer provenance have all passed their review gates.

## Task 6 provenance pre-review after protocol 1.0.2

- Status: still blocked by Task 5 current-evidence re-freeze; `attempt_01` is permanently diagnostic-only and cannot be supplemented or re-signed.
- Minimal future source scope: only `train_hidden_td3.py` and `test_hidden_td3_training_config.py`. Metadata must derive the live Direct/Residual environment schema/bounds and actual model dimensions (policy observation 260, actor observation 260, critic observation 260, Q input 264), rather than read the incomplete class-level shared schema.
- Required identity closure: before creating a run, verify trainer/environment/frozen-config content against the committed HEAD tree; record commit, tree, Git blob and content identities in config, RUNNING and DONE. The command must use the fixed importable module name, never `__main__`.
- Task 5 release conditions: evidence-v2 loader and new external 81-candidate standard seed-100/30-second four-shard `attempt_02` must validate; a new committed frozen config must bind protocol `e6edc37f...`, current source identities and full ranking provenance. Only then may fresh Direct/Residual 200-step seed-0 smoke leaves be created without touching `attempt_01`.
- New smoke evidence must remain controlled untracked compact JSON/CSV under a unique `attempt_02` directory (models remain ignored); verify it is non-overwriting and audit `git status` before/after.

## Stage A minimal-path completion

- Current Task 5 schema-4 PID config was loaded by the training entrypoint. Targeted trainer tests passed (10), and direct runtime inspection confirmed both policies use 260-dimensional observations, four actions and 264-dimensional Q inputs; they share all TD3 hyperparameters and the Residual output is zero initialized.
- Fresh `attempt_02` smokes (seed 0, 200 steps) completed for Direct and Residual. Each has config/RUNNING/DONE plus compact CSV evidence and a saved model; both record the same protocol and PID-config identities. This satisfies the Stage A smoke gate without reusing old `attempt_01` evidence.

## Protocol v2.1 Gate 3 pilot

- Status: **NO-GO**. Four fresh 5k runs (Direct/Residual × training seeds 0/1) completed with Git `0079879968992042b62a6e8e85f3474d7655ca11` and protocol `16781e621b316b2d8b3c9811cefd775b2e4ee2c931b275bcc059edc803d9f259`.
- Direct seed 0 fell from pre-update median 819 to post-update median 11 steps (required at least 409.5); Direct seed 1 fell from 750 to 14 (required at least 375). Both contain repeated 3–4 step episodes after learning starts.
- Direct actor L2 deltas from fresh same-seed models were 24.73 and 24.21, respectively, so this is learned collapse rather than a frozen actor. Residual remained at post-update medians 960 and 808.
- Commands: `py -3.11 -m experiments.circular_tracking.scripts.td3.train_hidden_td3 --mode direct_td3 --seed {0,1} --total-timesteps 5000 --output-folder .../gate_3/train/direct_td3/seed_{000,001}/target_005000/attempt_01`; the same command was run with `--mode residual_td3` in the matching residual folders. All runs used the frozen v2.1 source and no resume input.
- Evidence: `experiments/circular_tracking/results/hidden_disturbance_td3_paper/protocol_v2_1/gate_3/gate_3_summary.json` and the four immutable attempt directories. No Stage A run was launched.
