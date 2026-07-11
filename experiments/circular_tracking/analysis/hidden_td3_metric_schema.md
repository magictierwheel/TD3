# Hidden-TD3 Stage-A Metric Schema

This schema applies only to the frozen validation seeds `100` through `109`.
It supports the Stage-A PID, Direct TD3, and Residual TD3 comparison. Test and
unseen seeds are deliberately not accepted by the evaluator or its CLI.

## Paired rollout record

`stage_a_rollouts.json` contains one raw record for every
`controller × scenario × training_seed × disturbance_seed` rollout. A paired
worker evaluates PID, Direct TD3, and Residual TD3 sequentially with the same
scenario and validation seed. The environment rebuilds its deterministic local
disturbance process from that seed, so all three see the same realization.

Required identifiers are:

| Field | Meaning |
|---|---|
| `controller` | `pid`, `direct_td3`, or `residual_td3`. |
| `training_seed` | TD3 training replicate; Stage A uses one seed. |
| `disturbance_seed` | One of validation seeds `100`–`109`. |
| `scenario` | `standard`, `random_wind`, `actuator_loss`, or `compound`. |
| `checkpoint` | Frozen PID marker or the common TD3 checkpoint budget. |
| `model_path`, `model_sha256` | Exact evaluated model identity; PID is marked `frozen_pid`. |
| `source_git_sha`, `evaluation_source_sha256`, `environment_source_sha256` | Evaluation and environment source identities. |
| `protocol_path`, `protocol_sha256` | Frozen protocol identity. |
| `pid_config_path`, `pid_config_sha256`, `pid_config_payload_hash` | Frozen PID configuration identity. |

`rollout_metadata.disturbance_truth` is an offline trace only. The evaluator
never passes it to `model.predict`; the policy receives only the environment's
shared observable observation.

## Failure-first per-rollout metrics

| Metric | Unit | Definition |
|---|---:|---|
| `flight_time_sec` | s | Last completed control-step timestamp, capped at the 30-s horizon. |
| `failure` | boolean | `true` only for safety termination before the full horizon. |
| `completion_rate` | fraction | `flight_time_sec / 30`. |
| `path_length_ratio` | fraction | Actual XY path increments divided by reference XY path increments. |
| `mean_phase_error` | rad | Mean wrapped XY phase difference over completed control steps. |
| `steady_position_rmse_success_only` | m | `sqrt(mean(position_error^2))` at `time >= 10 s`, only when `failure` is false; otherwise `NaN`. |
| `failure_penalized_horizon_error` | m | `completion_rate * completed_prefix_RMSE + (1 - completion_rate) * 3.0` for failures, and completed-prefix RMSE for successes. |

Failure count is always compared before tracking error. The fixed 3-m unflown
horizon penalty makes a brief low-error prefix worse than an otherwise similar
completed flight.

## Hierarchical aggregation

`summarize_hierarchical` first averages the paired disturbance rollouts within
each `training_seed`, then reports means and sample standard deviations across
training seeds. It records `num_training_seeds`, `num_disturbance_seeds`, and
`num_rollouts`; `analysis_unit` is `training_seed`. Repeated disturbance seeds
across TD3 training replicates are therefore not labelled as independent pooled
samples. No bootstrap confidence interval is emitted in this Stage-A path.

Checkpoint selection uses the fixed global lexicographic order:

1. lower failure rate;
2. lower failure-penalized horizon error;
3. lower success-only steady RMSE;
4. smaller checkpoint budget.

## Frozen Stage-A decision

`stage_a_decision.json` contains `GO` or `NO-GO`, its selected checkpoint,
per-controller summaries, the evaluated rule branches, and all raw paired rows.
The decision is `GO` only when:

1. in `standard`, Residual TD3 has zero failures and success-only steady RMSE
   no greater than `1.10 × PID`; and
2. in `compound`, Residual TD3 improves against PID **or** Direct TD3 by at
   least one fewer failure among all ten validation disturbances, **or**, when
   failure counts are equal, by at least 5% lower failure-penalized horizon
   error.

The gate rejects incomplete groups: every controller/scenario must have exactly
one record for each validation seed `100`–`109` and one Stage-A training seed.
