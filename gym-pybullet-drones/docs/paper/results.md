> [!WARNING]
> **LEGACY RESULTS.** 下列数字对应旧环境和旧协议，包含 stale terminal reward、半圈训练、oracle observation、失配消融与反复使用的旧测试 seeds。不得进入 revised main table。

# Results Draft

## Evidence Level

The current evidence is implementation, smoke-test, short-training, and conservative multiseed pilot evidence. It is enough to support a formed draft paper and a reproducible experimental pipeline, and it supports a bounded claim that validation-selected DA-Residual improves wind/compound tracking relative to plain PID and matched residual_td3. It is not enough to claim superiority over PID-FF or unseen generalization.

Safe current claim:

> The PyBullet circular-tracking environment, TD3 training scripts, model-loading evaluation pipeline, metric aggregation, and figure generation are implemented. Zero-action residual control preserves PID behavior; disturbance-aware safety gating now makes the full method fall back to PID in the standard no-disturbance scenario. Conservative warm-start retention and validation checkpoint selection provide bounded positive evidence in wind/compound, while PID-FF and unseen remain limiting baselines.

Additional update after the first warm-start pass:

> PID-FF imitation warm-start can initialize a meaningful disturbance-aware residual actor, but the current 5000-step TD3 fine-tuning run degrades wind/compound performance instead of improving it. The warm-start evidence strengthens the paper's diagnostic framing rather than turning it into a positive TD3 performance claim.

Latest update after adding conservative fine-tuning:

> Warm-start retention, lower learning rate, lower exploration noise, `residual_gate_min = 0.8`, and validation checkpoint selection produce a more useful pilot controller. Across three training seeds, selected DA-Residual models improve wind/compound tracking relative to plain PID and reduce failure_rate from 0.333 to 0.111. They still do not beat the analytic PID-FF baseline, and they still fail often in unseen generalization. The strongest defensible result is therefore a bounded positive claim against plain PID/direct TD3, with PID-FF and unseen transfer reported as unresolved limits.

Matched no-disturbance-observation ablation update:

> The same conservative warm-start retention protocol has now been run for `residual_td3`, which removes disturbance observations while keeping the residual structure. In the main 30-second test, DA-Residual improves wind/compound steady RMSE relative to matched residual_td3 (`0.6914/0.6821 m` vs `0.7528/0.7580 m`) with the same `0.111` failure_rate. Compound radius/period generalization shows the same direction, but unseen stress tests reverse it: residual_td3 fails less often (`0.667` vs `0.778`) and has lower unseen steady RMSE. C2 is therefore supported only for main-distribution and compound-transfer tracking, not for unseen generalization.

## Traceable Result Folders

```text
experiments/circular_tracking/results/td3_residual_paper/eval_phase1_smoke
experiments/circular_tracking/results/td3_residual_paper/eval_phase1_standard_12s
experiments/circular_tracking/results/td3_residual_paper/eval_gate_fix_smoke
experiments/circular_tracking/results/td3_residual_paper/eval_td3_model_smoke_all
experiments/circular_tracking/results/td3_residual_paper/eval_td3_short_seed0_standard
experiments/circular_tracking/results/td3_residual_paper/eval_phase2_zero_action_all_scenarios_seed0_5s
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s
experiments/circular_tracking/results/td3_residual_paper/warm_start_da_4096x10_seed0
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_da_imitation_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_da_td3_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/warm_start_da_checkpoint_selection_seed0
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_da_selected4000_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_4096x10_seed0
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_gate08_imitation_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_td3_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_selection_seed0
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_gate10_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate10_checkpoint_selection_seed0
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate10_selected_warmstart_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_runs/disturbance_aware_residual_td3_seed1
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_runs/disturbance_aware_residual_td3_seed2
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_selection_multiseed
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected_multiseed_combined_30s
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected_multiseed_generalization_combined
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_residual_checkpoint_runs
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_residual_checkpoint_selection_multiseed
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_residual_selected_multiseed_combined_30s
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_residual_selected_multiseed_generalization_combined
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_generalization_r04_t8
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_generalization_r05_t12
```

Training outputs:

```text
experiments/circular_tracking/results/td3_residual_paper/runs/direct_td3_smoke_seed0
experiments/circular_tracking/results/td3_residual_paper/runs/residual_td3_smoke_seed0
experiments/circular_tracking/results/td3_residual_paper/runs/disturbance_aware_residual_td3_smoke_seed0
experiments/circular_tracking/results/td3_residual_paper/runs/direct_td3_short_seed0
experiments/circular_tracking/results/td3_residual_paper/runs/residual_td3_short_seed0
experiments/circular_tracking/results/td3_residual_paper/runs/disturbance_aware_residual_td3_short_seed0
```

Figures:

```text
experiments/circular_tracking/results/td3_residual_paper/figures
experiments/circular_tracking/results/td3_residual_paper/figures/short_seed0_standard
experiments/circular_tracking/results/td3_residual_paper/figures/matched_residual_ablation_main
experiments/circular_tracking/results/td3_residual_paper/figures/matched_residual_ablation_generalization
```

## Phase 1 Invariants

Standard 5-second smoke:

| Controller | Scenario | Duration (s) | Position RMSE (m) | Max tilt (rad) | Failure |
|---|---:|---:|---:|---:|---|
| PID | standard | 5 | 0.2905 | 0.0228 | false |
| Residual TD3, zero action | standard | 5 | 0.2905 | 0.0228 | false |

Standard 12-second smoke:

| Controller | Scenario | Duration (s) | Position RMSE (m) | Steady RMSE (m) | Max tilt (rad) | Failure |
|---|---:|---:|---:|---:|---:|---|
| PID | standard | 12 | 0.3885 | 0.3932 | 0.0290 | false |
| Residual TD3, zero action | standard | 12 | 0.3885 | 0.3932 | 0.0290 | false |

Interpretation: residual wiring is correct when the policy outputs zero.

## Safety-Gate Fix

A bug was found during model smoke evaluation: the full disturbance-aware mode gated thrust/torque residuals but not acceleration residuals. This allowed actor output to change behavior in the standard scenario even when disturbance magnitude was zero.

The environment was fixed so the gate multiplies all residual components. After the fix:

| Controller | Scenario | Duration (s) | Position RMSE (m) | Max tilt (rad) | Failure |
|---|---:|---:|---:|---:|---|
| PID | standard | 2 | 0.1534 | 0.0213 | false |
| Disturbance-aware Residual TD3 | standard | 2 | 0.1534 | 0.0213 | false |

Interpretation: the full method now falls back to PID in the no-disturbance case.

## Disturbance Force Application Fix

A second, more important physics bug was found during the execution pass. Wind and thermal forces were computed correctly, but `applyExternalForce(..., flags=WORLD_FRAME)` used `posObj=[0, 0, 0]`. In PyBullet this is the world-origin application point, not the drone center of mass. The resulting artificial torque caused the old wind/thermal/compound rollouts to hit `tilt_limit` almost immediately.

The environment now applies these forces at the current drone base position. A 5-second seed-0 all-scenario check after the fix shows that PID, PID-FF, zero-action Residual TD3, and zero-action DA-Residual TD3 no longer fail in any scenario, including `unseen`.

Traceable folder:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_disturbance_force_point_fix_seed0_5s
```

A 30-second, three-seed baseline check was then run with PID, PID-FF, zero-action Residual TD3, and zero-action DA-Residual TD3:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_force_point_fix_baselines_30s
```

Key aggregate results:

| Controller | Scenario | Failure rate | Position RMSE (m) | Steady RMSE (m) |
|---|---:|---:|---:|---:|
| PID | standard | 0.00 | 0.3607 | 0.3458 |
| DA-Residual TD3, zero action | standard | 0.00 | 0.3607 | 0.3458 |
| PID | wind | 0.33 | 0.8425 | 0.9970 |
| PID-FF | wind | 0.00 | 0.3738 | 0.3545 |
| PID | compound | 0.33 | 0.8028 | 0.9537 |
| PID-FF | compound | 0.00 | 0.4731 | 0.4838 |
| PID | unseen | 1.00 | 1.1343 | 1.2382 |
| PID-FF | unseen | 0.33 | 0.7420 | 0.7594 |

Interpretation: the earlier immediate tilt failures were not valid controller evidence. After the force-point fix, disturbed scenarios become meaningful long-horizon tracking tasks. The simple analytic PID-FF baseline is stronger than plain PID in wind and compound settings, so final TD3 claims must compare against PID-FF as well as PID.

## Three-Seed 5000-Step Fixed-Physics Pilot

After fixing the disturbance force application point, a new three-seed pilot was run:

```text
run = experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s
train controllers = direct_td3, residual_td3, disturbance_aware_residual_td3, disturbance_aware_residual_td3_no_gate
seeds = 0, 1, 2
train timesteps = 5000
training scenario_set = train
evaluation duration = 30 s
scenarios = standard, wind, thermal, dust, compound
```

All 12 training runs saved `model.zip`, `config.json`, `monitor.csv`, and `progress.csv`. The evaluation folder contains 90 rollout summaries and both per-seed and aggregate metric tables.

Key aggregate results:

| Controller | Standard failure | Standard RMSE (m) | Wind failure | Wind RMSE (m) | Thermal failure | Dust failure | Compound failure | Compound RMSE (m) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PID | 0.00 | 0.3607 | 0.33 | 0.8425 | 0.00 | 0.00 | 0.33 | 0.8028 |
| PID-FF | 0.00 | 0.3691 | 0.00 | 0.3738 | 0.00 | 0.00 | 0.00 | 0.4731 |
| Direct TD3 | 1.00 | 0.0154 | 1.00 | 0.0194 | 1.00 | 1.00 | 1.00 | 0.0197 |
| Residual TD3 | 0.33 | 0.8569 | 0.33 | 1.3638 | 0.33 | 0.33 | 0.33 | 1.1803 |
| DA-Residual TD3 | 0.00 | 0.3607 | 0.33 | 1.1501 | 0.00 | 0.00 | 0.67 | 0.9669 |
| DA-Residual TD3, no gate | 0.33 | 0.6518 | 0.33 | 0.9843 | 0.33 | 0.00 | 0.33 | 1.0746 |

Interpretation:

- Direct TD3 fails in every main scenario. Its very low RMSE is an artifact of terminating almost immediately and must not be read as good tracking.
- The gated DA-Residual controller exactly preserves PID behavior in standard and remains close to PID in dust and thermal.
- Safety gating improves standard/dust/thermal stability relative to no-gate and ordinary residual TD3, and it greatly reduces action smoothness penalties.
- The learned DA-Residual policy does not yet improve wind or compound tracking. In compound, PID-FF remains the best controller in this pilot.
- Therefore, the current paper should not claim that TD3 outperforms PID-FF. The defensible claim is narrower: the environment and evidence pipeline are valid, direct TD3 is unsafe, and gating is necessary for residual TD3 to preserve baseline behavior.

Pilot figures:

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s/figures
```

Additional gate/action diagnostics were generated from `control.csv`:

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s/eval/diagnostic_summary.csv
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s/eval/diagnostic_summary_aggregate.csv
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s/figures/figure6_gate_action_diagnostics.png
```

The diagnostics explain why the gated method preserves PID in standard conditions. In `standard`, the DA-Residual actor still emits nonzero raw actions (`mean_action_norm_mean = 1.0509`), but the mean gate is exactly `0.0`, so the residual is suppressed before it affects the PID command. By contrast, the no-gate controller has `action_smoothness_mean = 0.1936` and failure_rate `0.33` in the same standard scene. In `dust` and `thermal`, the gated controller keeps failure_rate `0.0` with much smaller action smoothness than no-gate or ordinary residual TD3. This supports safety gating as a stability mechanism even though it does not yet produce compound-scene performance gains.

## Validation And Model Selection

The fixed-physics 5000-step models were also evaluated on validation seeds `100,101,102` and the same five main scenarios:

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s/validation
```

This folder contains:

```text
validation_summary.csv
validation_model_scores.csv
selected_models.json
```

The first fixed-physics run only had final models, but the same script supports saved checkpoints when future training uses `--checkpoint-freq`. Validation results reinforce the main conclusion. Direct TD3 has validation failure_rate `1.0` for every seed. Residual TD3 seed 1 has validation failure_rate `0.0`, but its mean steady RMSE remains high at `0.8557 m`. DA-Residual seed 0 has lower mean steady RMSE (`0.6779 m`) but still has validation failure_rate `0.13`. Thus validation-based selection can identify less-bad TD3 models, but the current 5000-step training budget still does not produce a policy competitive with PID-FF.

## PID-FF Warm-Start Pilot

A supervised warm-start pass was added for the disturbance-aware residual actor. The dataset was generated from `CircularResidualTD3Env.feedforward_residual_action()` over the train scenario set, using `4096` imitation samples and `10` supervised epochs before `5000` additional TD3 timesteps:

```text
experiments/circular_tracking/results/td3_residual_paper/warm_start_da_4096x10_seed0
```

The imitation loss decreased from `0.05537` to `0.00054`, indicating that the actor can fit the PID-FF-inspired residual target. Three 30-second test evaluations were then run:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_da_imitation_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_da_td3_seed0_30s
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_da_selected4000_seed0_30s
```

Key comparison against the same PID/PID-FF baselines:

| Controller/model | Wind failure | Wind steady RMSE (m) | Compound failure | Compound steady RMSE (m) |
|---|---:|---:|---:|---:|
| PID | 0.33 | 0.9970 | 0.33 | 0.9537 |
| PID-FF | 0.00 | 0.3545 | 0.00 | 0.4838 |
| DA-Residual, warm-start imitation | 0.33 | 0.8983 | 0.00 | 0.5990 |
| DA-Residual, warm-start + 5000 TD3 final | 0.33 | 1.3744 | 0.67 | 1.1741 |
| DA-Residual, validation-selected 4000-step checkpoint | 0.33 | 1.3204 | 0.67 | 1.1197 |

Interpretation:

- Warm-start imitation improves the residual actor relative to the previous learned DA-Residual policy in compound and can outperform plain PID there, but it still does not beat PID-FF.
- Subsequent TD3 fine-tuning degrades wind and compound performance, including the validation-selected 4000-step checkpoint.
- The selected checkpoint was chosen on validation seeds `100,101,102` with `selection_score = 20.7959`, but testing still shows 1/3 wind failure and 2/3 compound failure.
- The next training change should not simply be "train longer"; it should constrain or regularize fine-tuning so TD3 does not move away from the PID-FF residual behavior before it has learned a better one.

Warm-start figures were generated here:

```text
experiments/circular_tracking/results/td3_residual_paper/figures/warm_start_imitation_seed0
experiments/circular_tracking/results/td3_residual_paper/figures/warm_start_td3_seed0
experiments/circular_tracking/results/td3_residual_paper/figures/warm_start_selected4000_seed0
```

## Warm-Start Retention And Gate-Min Checkpoint Pilot

The first warm-start run showed that naive TD3 fine-tuning can destroy the PID-FF imitation policy. A more conservative pilot was therefore run with:

```text
warm_start_samples = 4096
warm_start_epochs = 10
total_timesteps = 5000
learning_rate = 1e-4
learning_starts = 1000
action_noise_sigma = 0.02
residual_gate_min = 0.8
warm_start_retention = 1 supervised actor update every 10 TD3 callback steps
checkpoint_freq = 1000
training_seed = 0
```

The run is traceable here:

```text
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_4096x10_seed0
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_selection_seed0
```

Validation on seeds `100,101,102` selected the 1000-step checkpoint rather than the final model. The selected candidate had validation `failure_rate = 0.0`, mean steady RMSE `0.5611 m`, and `selection_score = 0.5611`; the warm-start model was a very close second with mean steady RMSE `0.5656 m`. Later checkpoints and the final model degraded.

The selected 1000-step checkpoint was then evaluated for 30 seconds on test seeds `0,1,2`:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_seed0_30s
```

Key aggregate results:

| Controller/model | Standard failure | Standard steady RMSE (m) | Wind failure | Wind steady RMSE (m) | Thermal steady RMSE (m) | Dust steady RMSE (m) | Compound failure | Compound steady RMSE (m) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PID | 0.00 | 0.3458 | 0.33 | 0.9970 | 0.3495 | 0.3566 | 0.33 | 0.9537 |
| PID-FF | 0.00 | 0.3551 | 0.00 | 0.3545 | 0.4084 | 0.3441 | 0.00 | 0.4838 |
| DA-Residual, selected 1000-step checkpoint | 0.00 | 0.3458 | 0.00 | 0.6873 | 0.5116 | 0.4313 | 0.00 | 0.5676 |

Interpretation:

- The conservative selected checkpoint preserves PID exactly in the standard scene because the zero-disturbance gate remains `0.0`.
- It removes the PID failures in wind and compound and reduces steady RMSE in those two scenes relative to plain PID.
- It is worse than PID in thermal and dust and remains worse than PID-FF in every disturbed scene except standard fallback.
- It is therefore valid as partial positive evidence for the residual TD3 framework against plain PID/direct TD3, but not as evidence that learned TD3 compensation surpasses a simple analytic feed-forward baseline.

A `residual_gate_min = 1.0` sensitivity evaluation was also run. First, the gate-1.0 setting was applied to the selected 1000-step checkpoint:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_gate10_seed0_30s
```

It kept zero failure and improved wind steady RMSE to `0.6438 m`, but worsened compound to `0.5871 m`, thermal to `0.5845 m`, and dust to `0.4619 m`. The gate-1.0 setting is therefore reported as a probe rather than the main setting.

For rigor, checkpoint selection was also repeated with `residual_gate_min = 1.0`:

```text
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate10_checkpoint_selection_seed0
```

That validation run had 105 rollouts and selected `warm_start_model.zip` rather than the 1000-step checkpoint. The selected warm-start model had validation failure_rate `0.0`, mean steady RMSE `0.5184 m`, and selection_score `0.5184`; the 1000-step checkpoint was second at `0.5239 m`.

The corresponding test evaluation is:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate10_selected_warmstart_seed0_30s
```

It also kept zero failure in all main scenes. Its wind steady RMSE improved to `0.6125 m`, thermal to `0.4642 m`, and dust to `0.4323 m`, but compound was `0.6015 m`, worse than the gate-0.8 selected checkpoint's `0.5676 m`. Thus gate=1.0 is useful as a robustness/sensitivity check and strengthens the conclusion that early warm-start-like policies are safer than later TD3 checkpoints, but the main compound claim remains tied to the gate-0.8 selected 1000-step checkpoint.

The conservative protocol was then extended to training seeds `1` and `2` using the same configuration. Both new training runs saved `warm_start_model.zip`, final `model.zip`, and checkpoints at 1000-step intervals:

```text
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_runs/disturbance_aware_residual_td3_seed1
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_runs/disturbance_aware_residual_td3_seed2
```

Validation selection over training seeds `0,1,2` is stored here:

```text
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_checkpoint_selection_multiseed
```

It contains 315 validation rollouts. The selected candidates were:

| Training seed | Selected candidate | Validation failure | Validation steady RMSE (m) | Selection score |
|---:|---|---:|---:|---:|
| 0 | model_1000_steps | 0.00 | 0.5611 | 0.5611 |
| 1 | warm_start | 0.00 | 0.5404 | 0.5404 |
| 2 | final | 0.00 | 0.5196 | 0.5197 |

The combined test table is:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected_multiseed_combined_30s
```

DA-Residual rows include three training seeds and three test seeds (`9` rollouts per scenario). PID and PID-FF are deterministic baselines over the three test seeds.

| Controller/model | Scenario | Failure rate | Steady RMSE mean (m) | Steady RMSE std (m) |
|---|---|---:|---:|---:|
| PID | wind | 0.333 | 0.9970 | 0.5950 |
| PID-FF | wind | 0.000 | 0.3545 | 0.0098 |
| DA-Residual selected multiseed | wind | 0.111 | 0.6914 | 0.2915 |
| PID | compound | 0.333 | 0.9537 | 0.6055 |
| PID-FF | compound | 0.000 | 0.4838 | 0.2251 |
| DA-Residual selected multiseed | compound | 0.111 | 0.6821 | 0.3264 |

This multiseed result is less optimistic than the original seed-0-only result but much more credible. The selected DA-Residual policies improve over plain PID in wind and compound on both failure rate and steady RMSE. They remain weaker than PID-FF, and seed2 still fails one wind and one compound test rollout.

A matched no-disturbance-observation ablation was then run with the same conservative training protocol, warm-start retention, checkpoint candidates, validation seeds, and test matrix. This isolates the value of the seven disturbance-observation channels by comparing DA-Residual to `residual_td3` under a comparable selection protocol:

```text
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_residual_checkpoint_runs
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_residual_checkpoint_selection_multiseed
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_residual_selected_multiseed_combined_30s
```

The no-disturbance-observation selected candidates were seed0 `warm_start`, seed1 `final`, and seed2 `model_1000_steps`; all had validation failure_rate `0.0`. Main-test comparison against the DA-Residual selected models gives:

| Scenario | Residual TD3 failure | Residual TD3 steady RMSE (m) | DA-Residual failure | DA-Residual steady RMSE (m) |
|---|---:|---:|---:|---:|
| standard | 0.000 | 0.3788 | 0.000 | 0.3458 |
| wind | 0.111 | 0.7528 | 0.111 | 0.6914 |
| thermal | 0.000 | 0.3865 | 0.000 | 0.4403 |
| dust | 0.000 | 0.4293 | 0.000 | 0.4239 |
| compound | 0.111 | 0.7580 | 0.111 | 0.6821 |

This is a cleaner C2 result than the earlier pilot comparison. Disturbance observation improves the main-distribution wind and compound steady RMSE without changing failure_rate, and it also improves standard fallback. It does not improve every disturbance type: thermal is worse with DA-Residual, and dust is only marginally better. The claim should therefore be written as a bounded compound/wind benefit, not as a universal disturbance-observation advantage.

Updated generalization checks for the selected 1000-step checkpoint were also run:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_generalization_r04_t8
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected1000_generalization_r05_t12
```

The multiseed selected models were also evaluated on `compound` and `unseen` for both radius/period changes:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_selected_multiseed_generalization_combined
```

For `R=0.4,T=8`, DA-Residual selected multiseed has compound failure_rate `0.111` and steady RMSE `0.7511 m`, better than PID (`0.333`, `0.9781 m`) but worse than PID-FF (`0.000`, `0.5864 m`). For `R=0.5,T=12`, the same pattern holds: DA-Residual has compound failure_rate `0.111` and steady RMSE `0.9039 m`, better than PID but worse than PID-FF.

Unseen remains the clearest failure mode. DA-Residual selected multiseed has unseen failure_rate `0.778` at both radius/period settings, with steady RMSE `1.2079 m` for `R=0.4,T=8` and `1.3708 m` for `R=0.5,T=12`. PID-FF is still stronger with failure_rate `0.333` in both unseen tests.

The matched residual_td3 ablation was also evaluated on the same two radius/period settings:

```text
experiments/circular_tracking/results/td3_residual_paper/eval_warm_start_retain_gate08_residual_selected_multiseed_generalization_combined
```

| Case | Scenario | Residual TD3 failure | Residual TD3 steady RMSE (m) | DA-Residual failure | DA-Residual steady RMSE (m) |
|---|---|---:|---:|---:|---:|
| R=0.4,T=8 | compound | 0.111 | 0.8644 | 0.111 | 0.7511 |
| R=0.4,T=8 | unseen | 0.667 | 0.9992 | 0.778 | 1.2079 |
| R=0.5,T=12 | compound | 0.111 | 0.9580 | 0.111 | 0.9039 |
| R=0.5,T=12 | unseen | 0.667 | 0.9387 | 0.778 | 1.3708 |

Thus the disturbance observations help on compound transfer cases but do not improve out-of-distribution unseen robustness. This is important for the manuscript: explicit disturbance channels appear useful when the test distribution remains near the modeled compound disturbances, but they may encourage over-specialized compensation under stronger unseen disturbance ranges.

## TD3 Training Smoke

Stable-Baselines3 TD3 runs now complete for:

```text
direct_td3
residual_td3
disturbance_aware_residual_td3
```

Each run saves:

```text
config.json
monitor.csv
model.zip
```

The evaluation script can load controller-specific TD3 model paths and roll them out through the same CSV/JSON metric pipeline.

## Seed-0 Short Training Diagnostics

The 1000-step standard-scene short training run is diagnostic only:

| Controller | Duration (s) | Position RMSE (m) | Max tilt (rad) | Failure | Reason |
|---|---:|---:|---:|---|---|
| PID | 5 | 0.2905 | 0.0228 | false |  |
| Residual TD3, 1000 steps | 5 | 0.1860 | 1.1128 | true | tilt_limit |
| DA-Residual TD3, 1000 steps | 5 | 0.2905 | 0.0228 | false |  |
| Direct TD3, 1000 steps | 5 | 0.0503 | 1.6978 | true | tilt_limit |

Important interpretation: the lower RMSE for Direct TD3 and Residual TD3 is not a success, because both terminated early. Failure status and max tilt dominate the interpretation.

## Three-Seed 1000-Step Pilot

A pilot pipeline was run with:

```text
run = experiments/circular_tracking/results/td3_residual_paper/pilot_multiseed_1000td3_30s
train controllers = direct_td3, residual_td3, disturbance_aware_residual_td3, disturbance_aware_residual_td3_no_gate
seeds = 0, 1, 2
train timesteps = 1000
training scenario_set = train
evaluation duration = 30 s
scenarios = standard, wind, thermal, dust, compound
```

This is still pilot evidence, not final paper evidence. It was also generated before the disturbance force application point was fixed, so its wind/thermal/compound failures should be treated as historical diagnostic evidence rather than formal controller evidence. The main value is that it exercised the full multi-seed pipeline and exposed the need for better physics validation.

| Controller | Standard failure | Standard RMSE (m) | Dust failure | Dust RMSE (m) | Compound failure |
|---|---:|---:|---:|---:|---:|
| PID | 0.00 | 0.3590 ± 0.0000 | 0.00 | 0.3742 ± 0.0094 | 1.00 |
| PID-FF | 0.00 | 0.3550 ± 0.0000 | 0.00 | 0.3585 ± 0.0009 | 1.00 |
| Direct TD3 | 1.00 | 0.0389 ± 0.0130 | 1.00 | 0.0374 ± 0.0094 | 1.00 |
| Residual TD3 | 1.00 | 0.0533 ± 0.0224 | 1.00 | 0.0538 ± 0.0218 | 1.00 |
| DA-Residual TD3 | 0.00 | 0.3590 ± 0.0000 | 0.33 | 0.3475 ± 0.0253 | 1.00 |
| DA-Residual TD3, no gate | 1.00 | 0.0711 ± 0.0378 | 1.00 | 0.0690 ± 0.0301 | 1.00 |

The low RMSE values for failed TD3 runs are not success indicators. They are computed on short pre-failure rollouts. The more important finding is that Direct TD3, ordinary Residual TD3, and no-gate disturbance-aware residual TD3 fail even in standard/dust settings after only 1000 training steps, while the gated full method preserves PID behavior in standard.

In wind, thermal, and compound scenarios, every controller in this pilot has `failure_rate = 1.0`. After the force-point fix, this statement should not be reused as a controller conclusion; the run remains useful only as a trace of the bug discovery process and an early training-pipeline check.

Pilot figures:

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_multiseed_1000td3_30s/figures
```

## Generalization Pilot

The same 1000-step pilot models were evaluated without retraining on:

```text
radius = 0.4, period = 8, scenarios = compound/unseen
radius = 0.5, period = 12, scenarios = compound/unseen
```

Result folders:

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_generalization_r04_t8_1000td3
experiments/circular_tracking/results/td3_residual_paper/pilot_generalization_r05_t12_1000td3
```

All controller/scenario combinations in both generalization pilots have `failure_rate = 1.0`. This is useful negative evidence: the current pilot models do not generalize, and the formal paper must either train longer with disturbance curriculum/PID tuning or present generalization as a limitation.

After the force-point fix, the 5000-step models were also evaluated without retraining:

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_generalization_r04_t8_5000td3
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_generalization_r05_t12_5000td3
```

For both `R=0.4,T=8` and `R=0.5,T=12`, Direct TD3, Residual TD3, and DA-Residual TD3 have `failure_rate = 1.0` on `unseen`. PID-FF is again the strongest reference controller, but still fails one of three unseen seeds. This should be reported as a limitation and motivation for longer training, curriculum design, or supervised warm-start from the analytic feed-forward baseline.

## All-Scenario Interface Check

Zero-action rollout covered:

```text
controllers = pid, residual_td3, disturbance_aware_residual_td3, direct_td3
scenarios = standard, wind, thermal, dust, compound, unseen
seed = 0
duration = 5 s
```

Findings:

- Before the force-point fix, PID/residual/full zero-action rollouts completed standard and dust.
- Before the force-point fix, wind, thermal, compound, and unseen commonly terminated by `tilt_limit`.
- After the force-point fix, a 5-second seed-0 all-scenario check completes every scenario without early failure for PID, PID-FF, residual zero action, and DA-residual zero action.
- Direct TD3 zero action is not a meaningful controller; it mainly checks action mapping and logging.

This confirms that the environment and logging pipeline cover all planned scenarios, while also showing that physics-level validation must precede any controller claim.

## Claim Status

| Claim | Current status |
|---|---|
| C1: Residual TD3 is more stable than Direct TD3 | Partially supported after the fixed-physics 5000-step pilot: Direct TD3 fails in every main scenario, while residual variants often survive, but residual tracking quality remains weak. |
| C2: Disturbance observation improves compound tracking | Supported for matched main-distribution wind/compound and compound radius/period transfer in steady RMSE, with equal failure_rate; not supported for unseen stress tests. |
| C3: Safety gating reduces saturation/abnormal action | Supported as a safety mechanism in standard/dust/thermal; compound evidence remains mixed. |
| C4: Full method does not degrade PID in standard | Supported: PID and gated DA-Residual have identical standard RMSE and failure rate in the fixed-physics 5000-step pilot. |
| C5: Full method improves disturbed tracking | Supported against plain PID in wind/compound by the conservative multiseed selected models, but not supported against PID-FF and not supported in thermal/dust. |
| C6: Unseen generalization | Not supported for current TD3 models; report as limitation. |
| C7: PID-FF warm-start helps residual initialization | Supported as an initialization mechanism; naive fine-tuning degrades it, while retention plus checkpoint selection preserves part of the benefit. |
| C8: Conservative retention/checkpoint selection improves main-distribution safety | Supported as a bounded multiseed pilot against PID/direct TD3. It remains below PID-FF and does not solve unseen generalization. |

## Next Result-Producing Steps

1. Keep PID-FF in all main tables as the strongest analytic baseline.
2. Use the completed matched no-disturbance-observation ablation to qualify C2: main compound benefit, no unseen benefit.
3. Keep checkpoint validation as mandatory; selected candidates differ by training seed.
4. Treat `unseen` as a limitation section until a curriculum or stronger disturbance observer exists.
