# Revised Experiment Stage Status

Updated: 2026-07-11

Current stage: `Protocol v2.1 — Gate 1 standard confirmation`

## Stage 0 evidence

- [x] Frozen hidden-disturbance protocol and separate seed partitions.
- [x] Hidden-information, terminal-reward, action-fairness and zero-residual invariants.
- [x] Frozen PID nominal acceptance: external 81-candidate grid, GO, winner 78.
- [x] Matched Direct/Residual 200-step seed-0 smoke attempts.
- [x] Validation-only, paired failure-first Stage-A evaluator and seed-0 gate lock.

## Preserved protocol-v1 evidence

- Training seed `0`; train budget `20,000`; validation seeds `100–109` only; all four frozen validation scenarios.
- Both controllers completed fresh immutable `attempt_02` training runs with 5k, 10k and 20k checkpoints.
- Global checkpoint selection: `5,000` by the frozen lexicographic rule.
- Decision: **GO**. Residual passed the standard gate (0 failures; success-only steady RMSE `0.0095981 m`, equal to PID) and, in compound, matched Direct's 10/10 failures while reducing failure-penalized horizon error from `2.99170` to `2.40367` (>5%). It did not improve compound performance over PID.
- Evidence: `stage_A/aggregate/attempt_02/aggregation_manifest.json`, `stage_a_rollouts_merged.csv`, `stage_a_hierarchical_summary.json`, and `stage_a_gate_compact.json`. Local raw decision JSON remains available for audit but is not committed.

These are protocol-v1 diagnostic artifacts only. They are retained without deletion or overwrite and cannot support protocol-v2 claims.

## Protocol-v2 restart

- Reopen Task 6 for fixed physical observation scaling, Direct safe initialization, safe warm-up, physical-scale noise and resumable state.
- Reopen Task 7 so evaluation uses exactly the same frozen observation transformation.
- Restart Task 8 at Gate 0 and run only a new Stage A after Gates 0–3 pass.
- Do not start protocol-v2 Stage B without fresh user authorization.

## Protocol-v2 gates

- [x] Gate 0: focused tests, fixed-scale forward/gradient check, and reward/termination preflight passed. Evidence: `protocol_v2/gate_0/attempt_01/gate_0.json`.
- [x] Gate 1: **CONDITIONAL PASS**. v2.1 standard confirmation completed 200 steps safely. Compound's `altitude_limit` at step 73 is retained as unlearned hover-center control insufficiency, not unsafe exploration.
- [ ] Gate 2: 2k safe data collection.
- [x] Gate 2: PASS. Every controller/seed run included at least one full 960-step episode; replay nonterminal fractions were 99.85%–99.90%.
- [~] Gate 3: 5k two-seed pilot running.
