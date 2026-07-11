# Task 7 — minimum Stage-A evaluation

## Initial implementation

- Commit `96ed48c…` adds validation-only paired evaluation, failure-aware metrics, hierarchical seed counts and Stage-A aggregation.
- Root focused verification: 6 passed.

## Joint scientific review

- Scientific blocker: Stage-A evaluation and aggregation admitted training seeds 1–4, but Stage A is pre-registered for training seed 0 only. This could produce a non-pre-registered GO/NO-GO decision.
- Authorized narrow repair: reject nonzero Stage-A training seeds in both evaluation and aggregation, add focused RED/GREEN tests, then recheck this blocker only.

## Seed-0 correction

- Final corrective commit: `a8e0411…`; focused metrics suite: 9 passed.
- The Stage-A CLI/API rollout, paired worker, hierarchical aggregation, gate and checkpoint selector now reject training seeds 1–4. Only the pre-registered seed 0 can produce a Stage-A decision.

## Integration

- Joint recheck decision: `APPROVE` (seed-0 boundary only; no Stage-A leakage or statistics blocker found).
- Integrated commits: `82b1341` and `f72f7a9`; integration focused verification: `9 passed`.
- Task 7 is complete. Stage A may now evaluate only validation seeds 100–109 and only training seed 0.
