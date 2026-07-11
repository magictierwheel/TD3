# Hidden-Disturbance TD3 Parallel Execution Runbook

## Authority

This runbook controls execution and recovery. Scientific requirements remain defined by `RL_PAPER_EXECUTION_PLAN.md`, `.research/design_brief.md`, and the rebuild implementation plan. The frozen machine-readable contract is `experiments/circular_tracking/config/hidden_td3_protocol.json`.

## Recovery

Never resume from chat memory. Read, in order:

1. `AGENTS.md`.
2. Root execution plan and rebuild implementation plan.
3. Frozen protocol.
4. `.research/execution_state.json`.
5. The current `.research/task_reports/task_N.md`.
6. The final 20 journal records.
7. Current Git/worktree/process state.

Re-run the recorded verification and execute only `next_action`.

## Roles

- Root coordinator: sole writer of shared state, stage status, global summaries, gates, and manuscript integration.
- Implementer: one task, one file whitelist, TDD, narrow commit, self-review.
- Spec/science reviewer: checks exact plan compliance, information boundaries, seed discipline, and fair comparison.
- Quality/reproducibility reviewer: starts only after spec approval and checks maintainability, numerical behavior, tests, metadata, and reproducibility.
- Experiment operator: runs immutable code/config shards in unique output directories and never edits source or shared summaries.

Only one implementation subagent may write code at a time. Independent read-only analysis and frozen experiment runs may be parallel.

## Per-task lifecycle

```text
pending
-> in_progress
-> awaiting_spec_review
-> awaiting_quality_review
-> awaiting_integration
-> complete
```

Before dispatch, persist agent, branch, worktree, allowed files, base SHA, and expected tests. After every transition, increment `state_revision`, append a journal record, and set an exact `next_action`.

No task is complete until the root coordinator independently checks the diff and runs fresh verification.

### Mandatory batched preflight before formal reviews

After every implementation submission and root verification, the root coordinator dispatches two complementary, read-only preflight reviewers concurrently before formal specification review:

1. **Implementation/reproducibility preflight** — concurrency and atomicity, import and source identity isolation, recovery paths, filesystem and process behavior, numerical/resource safety, and metadata reproducibility.
2. **Scientific/contract preflight** — frozen protocol, information boundary, paired-seed and held-out locks, controller fairness, validation scope, test adversarial coverage, and claim/gate implications.

Each reviewer returns one exhaustive Critical/Important/Minor list for its risk domain. The root writes a de-duplicated, single repair manifest into the task report. If that manifest has any Critical or Important issue, exactly one TDD implementation pass addresses all entries together; do not dispatch one implementer per finding or repeatedly re-review individual fixes. The root then reruns verification and the two-agent preflight. Only a clean preflight permits the normal serial `awaiting_spec_review -> awaiting_quality_review` lifecycle. A formal-review escape is added to a new full batch manifest rather than patched in isolation.

The batch is diagnostic only: reviewers never write source or shared state, and it does not relax the required formal specification and quality reviews.

### Stage A minimal-scientific fast path (user override, 2026-07-11)

The batched-preflight policy above is suspended until Stage A records a GO/NO-GO decision. Before then, reviewers may block only for controller unfairness, privileged/held-out leakage, wrong reward/termination/statistics, wrong run source/config/model identity, or undetectable result corruption. Record all other security, recovery, concurrency, compatibility, and production-hardening findings in `.research/deferred_hardening_stage_a.md`.

Use one implementation pass, one focused root test, one full root verification, and one joint specification/quality review per task. Do not run repeated broad suites or spawn additional repair cycles for non-blocking findings. For PID and training runs, use a new external `attempt_NN` directory and never overwrite; a failed run is rerun completely in a new attempt rather than auto-recovered.

## Waves

- P0: backup, durable state, protocol freeze, clean baseline, isolated worktrees.
- W1: implementation-plan Tasks 1-4, strictly serial code lane.
- W2: PID tuning/freezing; candidate evaluation may use four processes.
- W3: training, evaluation, and statistics entrypoints.
- W4: Stage 0 integrated acceptance.
- W5: Stage A Direct/Residual parallel diagnostic and gate.
- W6: Stage B in 4+2 training waves and gate.
- W7: three-seed 50k gate/history ablations only after Stage B GO.
- W8: Stage C in 4+4+2 waves, protocol freeze, held-out test, nominal unseen.
- W9: revised evidence, manuscript, and final audit.

Stage A or B NO-GO immediately stops budget expansion and routes work to the diagnostic-paper path.

## Runtime isolation

Training uses at most four OS processes; evaluation uses at most six workers. Each process uses one BLAS/Torch thread and an independent PyBullet DIRECT client. A paired disturbance cell remains within one evaluation worker.

Every run uses a unique `attempt_NN` directory and records `config.json`, `RUNNING.json`, logs, checkpoints/metrics, and `DONE.json`. Only infrastructure failures may create a new attempt. Scientific failures are retained as results.

## Shared-file lock

Subagents must not edit:

```text
.research/execution_state.json
.research/execution_journal.jsonl
experiments/circular_tracking/config/hidden_td3_protocol.json
docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md
experiments/circular_tracking/results/hidden_disturbance_td3_paper/stage_status.md
global summaries
docs/paper/manuscript.md
```

Legacy code, results, and paper evidence remain read-only.
