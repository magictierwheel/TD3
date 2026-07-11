> [!WARNING]
> **LEGACY AUDIT.** 本审计只证明旧 oracle/PID-FF pilot 的材料包曾经完整，不代表 2026-07-10 revised hidden-disturbance plan 已完成。当前阶段见 `../results/hidden_disturbance_td3_paper/stage_status.md`。

# Plan Completion Audit

Date: 2026-07-10

This audit checks the current worktree against `RL_PAPER_EXECUTION_PLAN.md`.
It is intentionally conservative: a requirement is marked complete only when
there is traceable evidence in files or command outputs.

## Phase Status

| Phase | Status | Evidence |
|---|---|---|
| Phase 0: docs and ledger | Complete | `claim_evidence_ledger.csv`, `td3_metric_schema.md`, `docs/paper/outline.md`, `docs/paper/related_work.md` |
| Phase 1: environment prototype | Complete | `CircularResidualTD3Env`; smoke rollouts; fixed observation/action dimensions |
| Phase 2: disturbances and controllers | Complete | modes include PID, PID-FF, Direct TD3, Residual TD3, DA-Residual TD3, no-gate; scenarios include standard/wind/thermal/dust/compound/unseen |
| Phase 3: TD3 training | Complete for pilot scale, not formal 500k scale | 12 fixed-physics 5000-step models saved with `model.zip`, `monitor.csv`, `progress.csv`, `config.json`; checkpoint support and PID-FF imitation warm-start added |
| Phase 4: main experiment | Complete as fixed-physics pilot | `pilot_force_point_fix_5000td3_30s/eval/summary_metrics.csv` has 90 rows for 6 controllers x 5 scenarios x 3 seeds |
| Phase 5: ablation and generalization | Complete as pilot evidence with generalization failure | matched no-disturbance-observation conservative ablation; no-gate and no-residual/direct comparisons; two radius/period generalization folders; diagnostic Figure 6 |
| Phase 6: manuscript draft | Complete as bounded pilot/diagnostic draft | `docs/paper/manuscript.md`, `docs/paper/manuscript.docx`, `docs/paper/results.md`, `docs/paper/method.md` |
| Conservative warm-start retention extension | Complete as three-training-seed bounded pilot | training seeds `0,1,2`; multiseed checkpoint validation; selected-model main test; gate=1.0 sensitivity; multiseed compound/unseen generalization checks |
| Matched residual_td3 retention ablation | Complete as bounded C2 evidence | `residual_td3` training seeds `0,1,2`; 315 validation rollouts; selected-model main and generalization tests; combined aggregate tables |

## Verification Evidence

Key fixed-physics result folders:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_disturbance_force_point_fix_seed0_5s
experiments/circular_tracking/results/td3_residual_paper/eval_force_point_fix_baselines_30s
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_generalization_r04_t8_5000td3
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_generalization_r05_t12_5000td3
```

Additional traceability:

```text
pilot_force_point_fix_5000td3_30s/eval/diagnostic_summary.csv
pilot_force_point_fix_5000td3_30s/eval/diagnostic_summary_aggregate.csv
pilot_force_point_fix_5000td3_30s/validation/validation_summary.csv
pilot_force_point_fix_5000td3_30s/validation/validation_model_scores.csv
pilot_force_point_fix_5000td3_30s/validation/selected_models.json
warm_start_da_4096x10_seed0/warm_start_loss.csv
eval_warm_start_da_imitation_seed0_30s/summary_metrics_aggregate.csv
eval_warm_start_da_td3_seed0_30s/summary_metrics_aggregate.csv
warm_start_da_checkpoint_selection_seed0/validation_model_scores.csv
eval_warm_start_da_selected4000_seed0_30s/summary_metrics_aggregate.csv
warm_start_retain_gate08_4096x10_seed0/warm_start_retention_loss.csv
warm_start_retain_gate08_checkpoint_selection_seed0/validation_model_scores.csv
eval_warm_start_retain_gate08_selected1000_seed0_30s/summary_metrics_aggregate.csv
eval_warm_start_retain_gate08_selected1000_gate10_seed0_30s/summary_metrics_aggregate.csv
warm_start_retain_gate10_checkpoint_selection_seed0/validation_model_scores.csv
eval_warm_start_retain_gate10_selected_warmstart_seed0_30s/summary_metrics_aggregate.csv
warm_start_retain_gate08_checkpoint_selection_multiseed/validation_model_scores.csv
eval_warm_start_retain_gate08_selected_multiseed_combined_30s/summary_metrics_aggregate.csv
eval_warm_start_retain_gate08_selected_multiseed_generalization_combined/summary_metrics_aggregate.csv
eval_warm_start_retain_gate08_residual_selected_multiseed_combined_30s/summary_metrics_aggregate.csv
eval_warm_start_retain_gate08_residual_selected_multiseed_generalization_combined/summary_metrics_aggregate.csv
eval_warm_start_retain_gate08_selected1000_generalization_r04_t8/summary_metrics_aggregate.csv
eval_warm_start_retain_gate08_selected1000_generalization_r05_t12/summary_metrics_aggregate.csv
```

## Acceptance Criteria Audit

| Requirement | Current evidence | Status |
|---|---|---|
| Standard full method RMSE <= 1.10 x PID | Multiseed selected DA and PID both have standard steady RMSE 0.3458 and failure_rate 0 | Pass |
| Compound full method RMSE < Residual TD3 | Matched conservative selected DA compound steady RMSE 0.6821 and failure_rate 0.111; matched residual_td3 compound steady RMSE 0.7580 and failure_rate 0.111 | Pass for steady RMSE under matched protocol |
| Compound full method RMSE < PID | Multiseed selected DA compound steady RMSE 0.6821 vs PID 0.9537; failure_rate 0.111 vs PID 0.333 | Pass against PID |
| Full method failure_rate < Direct TD3 | Multiseed selected DA failure_rate is 0 in standard/dust/thermal and 0.111 in wind/compound; Direct TD3 fixed-physics pilot failure_rate 1.0 in all main scenes | Pass |
| Full method saturation <= Direct TD3 | Multiseed selected DA rotor_saturation_rate remains 0 in main scenes; Direct saturation is not the limiting failure mode but is not better | Weak pass |
| Disturbance observation improves compound | Matched conservative no-disturbance-observation ablation completed: main compound steady RMSE is 0.6821 for DA-Residual vs 0.7580 for residual_td3, with the same 0.111 failure_rate. Compound radius/period transfer also favors DA. Unseen reverses and remains a failure mode. | Pass for compound/main distribution; fail for unseen |
| PID-FF warm-start improves initialization | Warm-start/retention selected models improve wind/compound relative to PID/prior DA-Residual in multiseed aggregate | Pilot pass |
| TD3 fine-tuning preserves warm-start benefit | Selected candidate differs by training seed: seed0 1000-step, seed1 warm-start, seed2 final. Validation selection helps, but seed2 still fails one wind and one compound test rollout | Partial pass only with retention and validation selection |
| PID-FF comparison | Multiseed selected DA remains worse than PID-FF in wind (0.6914 vs 0.3545) and compound (0.6821 vs 0.4838), and worse in thermal/dust | Fail |
| Unseen generalization | Multiseed selected DA unseen failure_rate is 0.778 at both tested radius/period settings; PID-FF is stronger | Fail |

## Current Conclusion

The implementation plan is substantially executed as a reproducible pilot paper
package. The latest conservative retention/checkpoint experiment changes the
paper from a purely negative result to a bounded multiseed positive result:
Direct TD3 is unsafe, safety-gated residual TD3 preserves PID in standard
conditions, and validation-selected warm-start-retained models can beat plain
PID in wind and compound on average while reducing failure_rate.

The original stronger positive TD3 claims are still not complete. The selected
models remain weaker than PID-FF, do not improve thermal/dust tracking, and
fail unseen generalization in two radius/period settings. The manuscript should
therefore claim only the bounded pilot result and explicitly report PID-FF/unseen
as unresolved limits.

The matched conservative no-disturbance-observation residual_td3 ablation is now
complete. It gives clean support for C2 on main-distribution wind/compound and
compound radius/period transfer, but it also shows that disturbance observations
do not solve unseen robustness. In unseen stress tests, residual_td3 has lower
failure_rate and lower steady RMSE than DA-Residual. This keeps the manuscript's
claim bounded rather than globally positive.

The `residual_gate_min=1.0` sensitivity pass is complete. Re-running validation
under gate=1.0 selected `warm_start_model.zip` rather than the 1000-step
checkpoint; it improved wind relative to the gate=0.8 checkpoint but was worse
on compound. This reinforces early-checkpoint/warm-start preservation as the
useful mechanism, not late TD3 fine-tuning.

The execution plan can be treated as complete for a bounded small-paper package:
the environment, training/evaluation pipeline, main experiments, matched C2
ablation, generalization tests, evidence ledger, audit, and manuscript draft are
all present and traceable. It is not complete as a strong positive-control claim:
PID-FF remains better, and unseen generalization remains failed. Any future work
should be framed as extending this bounded result rather than filling a missing
minimum paper artifact.
