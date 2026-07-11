> [!WARNING]
> **LEGACY METHOD.** 本文档描述旧 oracle/PID-FF pilot，不是 revised hidden-disturbance 方法。新实现不得复制其中的 disturbance observation、PID-FF warm-start 或 disturbance-magnitude gate。

# Method Draft

## Overview

The proposed controller is a disturbance-aware residual TD3 architecture for single-quadrotor circular trajectory tracking. The baseline PID controller produces a stabilizing motor command, and the learned actor produces a bounded residual correction. The current implementation contains the full controller interface set, six disturbance scenarios, TD3 training scripts, optional PID-FF imitation warm-start, model-loading evaluation, traceable CSV/JSON outputs, metric aggregation, validation-based checkpoint selection, and figure generation.

## Simulator

- Platform: PyBullet/Gymnasium through `gym-pybullet-drones`.
- Vehicle model: `CF2X`.
- Main task: one quadrotor tracks a horizontal circular trajectory.
- State/output logging: `trajectory.csv`, `control.csv`, and `episode_summary.json`.
- Windows path issue: PyBullet cannot reliably load URDF files from non-ASCII project paths, so `CircularResidualTD3Env` mirrors assets to an ASCII temp directory before loading the URDF.

## Reference Trajectory

The circular reference is:

```text
omega = 2*pi / period
x_ref = radius * cos(omega * t)
y_ref = radius * sin(omega * t)
z_ref = height
vx_ref = -radius * omega * sin(omega * t)
vy_ref =  radius * omega * cos(omega * t)
vz_ref = 0
ax_ref = -radius * omega^2 * cos(omega * t)
ay_ref = -radius * omega^2 * sin(omega * t)
az_ref = 0
```

The nominal paper configuration remains:

```text
radius = 0.3 m
period = 10 s
height = 1.0 m
formal evaluation duration = 30 s
```

Phase 1 smoke tests use shorter durations for fast validation.

## Disturbance Model

The environment implements:

- `standard`: no disturbance.
- `wind`: horizontal wind sampled from the configured range.
- `thermal`: density scaling plus vertical thermal acceleration.
- `dust`: thrust and torque efficiency loss.
- `compound`: wind, thermal, and dust together.
- `unseen`: stronger out-of-distribution disturbance range.

Wind and thermal forces are applied inside the overridden `_physics()` method, so they are applied at every PyBullet substep before `p.stepSimulation()`. A bug found during the July 10 execution pass is now fixed: when `applyExternalForce()` uses `WORLD_FRAME`, the force application point is the current drone base position, not `[0, 0, 0]`. This avoids injecting a non-physical torque from applying wind or thermal forces at the world origin.

## PID Baseline

The PID baseline uses `DSLPIDControl`. Phase 1 found that the unmodified horizontal PID gains and full reference-velocity feed-forward are too aggressive for the `R = 0.3 m, T = 10 s` circular trajectory: the drone exceeds the tilt termination threshold. The current prototype therefore exposes the following explicit configuration:

```text
reference_velocity_gain = 0.0
pid_target_step_limit = 0.03 m
pid_xy_p_scale = 0.5
pid_xy_d_scale = 1.0
```

This is a conservative reference-shaped PID baseline. It is stable in the standard Phase 1 smoke test but should be further tuned before final main-experiment claims.

## PID-FF Baseline

`pid_ff` is implemented as an analytic feed-forward baseline. It keeps the same PID structure but adds disturbance compensation before the RPM command is applied:

- wind drag compensation is estimated from the current relative velocity and the same drag model used in `_physics()`;
- thermal updraft compensation reduces the vertical acceleration demand;
- dust compensation scales RPM by the inverse square root of thrust efficiency.

This baseline is intentionally simple and fixed. It is useful as an engineering reference, but it should not be treated as a fully optimized model-based controller.

## Residual TD3 Interface

Residual TD3 uses a 5-dimensional normalized action:

```text
delta_ax
delta_ay
delta_az
delta_thrust_scale
delta_torque_scale
```

The acceleration-like residuals perturb the PID target position and target velocity:

```text
target_pos_residual = target_pos + k_acc_to_pos * delta_acc
target_vel_residual = target_vel + k_acc_to_vel * delta_acc
```

The thrust and torque residuals gently scale the final RPM pattern. All RPM commands are clipped to legal motor limits.

The Phase 1 prototype uses separate PID controller instances for the base PID path and residual PID path. This prevents the residual mode from accidentally advancing the same PID controller state twice. With zero residual action, `residual_td3` now exactly matches `pid` in the standard smoke test.

## Safety Gate

The full disturbance-aware residual TD3 mode computes:

```text
gate = gate_disturbance * gate_saturation
```

where `gate_disturbance` is based on normalized disturbance magnitude and `gate_saturation` suppresses residuals when PID RPM is close to lower or upper motor limits. In the standard environment, disturbance magnitude is zero, so the full method should fall back toward PID.

An implementation bug found during smoke evaluation was fixed: the gate now multiplies the acceleration residuals as well as thrust and torque residuals. This makes the full method exactly match PID in the standard no-disturbance smoke test.

The later conservative warm-start experiments add an explicit deployment parameter:

```text
residual_gate_min
```

When the disturbance magnitude is zero, the gate is still forced to `0.0`, so the standard scene falls back to PID. When disturbance magnitude is nonzero, the gate can be clamped to at least `residual_gate_min`, subject to the saturation gate. This was introduced because the original disturbance gate suppressed the PID-FF-inspired residual too strongly in wind and compound scenes. The reported conservative checkpoint uses `residual_gate_min = 0.8`; `residual_gate_min = 1.0` is retained as a sensitivity probe, not the main adopted setting.

## Observations

Implemented observation dimensions:

- PID diagnostic mode: 30
- Direct TD3: 33
- Residual TD3: 34
- Disturbance-aware residual TD3: 41

The residual and direct TD3 modes include normalized position, velocity, attitude, angular velocity, circular reference, tracking error, phase, and last action. Disturbance-aware mode adds wind, density loss, thermal acceleration, thrust loss, and torque loss.

## Metrics

All metric formulas and output schemas are fixed in:

```text
experiments/circular_tracking/analysis/td3_metric_schema.md
```

The main metrics are:

- `position_rmse`
- `steady_position_rmse`
- `max_position_error`
- `final_position_error`
- `max_altitude_error`
- `max_tilt_angle`
- `rotor_saturation_rate`
- `control_energy`
- `action_smoothness`
- `failure`
- `failure_reason`

## Training And Evaluation Implementation

TD3 training entry points:

```text
experiments/circular_tracking/scripts/td3/train_direct_td3.py
experiments/circular_tracking/scripts/td3/train_residual_td3.py
```

Evaluation and reporting entry points:

```text
experiments/circular_tracking/scripts/td3/evaluate_td3_controllers.py
experiments/circular_tracking/scripts/td3/summarize_td3_results.py
experiments/circular_tracking/scripts/td3/plot_td3_results.py
experiments/circular_tracking/scripts/td3/run_td3_paper_pipeline.py
experiments/circular_tracking/scripts/td3/analyze_td3_diagnostics.py
experiments/circular_tracking/scripts/td3/select_td3_models.py
```

The evaluation script supports optional TD3 model paths for `direct_td3`, `residual_td3`, and `disturbance_aware_residual_td3`. If a model path is omitted for a TD3 controller, the script uses zero actions, which is useful for wiring and interface checks but not for performance claims.

The batch pipeline script trains seed-specific TD3 models, evaluates controller/scenario/seed matrices, writes `summary_metrics.csv`, and runs the aggregate summarizer. It also supports reusing trained models for radius/period generalization pilots.

The residual TD3 training script can optionally generate PID-FF-inspired imitation targets from `CircularResidualTD3Env.feedforward_residual_action()` before TD3 fine-tuning:

```text
--warm-start-samples
--warm-start-epochs
--warm-start-batch-size
--warm-start-scenario-set
```

Warm-start outputs are saved as `warm_start_dataset.npz`, `warm_start_loss.csv`, and `warm_start_model.zip` before the subsequent TD3 model is saved as `model.zip`.

The conservative warm-start run also supports retention updates during TD3 fine-tuning:

```text
--warm-start-retain-freq
--warm-start-retain-updates
--warm-start-retain-batch-size
--warm-start-retain-start
```

These updates periodically apply supervised actor losses on the warm-start dataset, so exploration does not immediately erase the PID-FF residual initialization. The run used in the latest main evidence additionally lowers the learning rate to `1e-4`, delays learning starts to `1000`, and reduces action noise to `0.02`. The conservative protocol has now been run for TD3 training seeds `0,1,2`; validation can select different candidates for different seeds, so selected-model reporting includes both training seed and checkpoint/warm-start/final candidate identity.

The matched no-disturbance-observation ablation uses the same conservative protocol for `residual_td3`: PID-FF imitation warm-start, retention updates, `5000` TD3 timesteps, checkpoints every `1000` steps, validation seeds `100,101,102`, and selected-model reporting over training seeds `0,1,2`. The only intended structural difference is that `residual_td3` has no disturbance observation channels and therefore uses the 34-dimensional residual observation instead of the 41-dimensional disturbance-aware observation.

The training scripts now support optional checkpointing through `--checkpoint-freq`. The selection script evaluates final models or saved checkpoints on fixed validation scenarios and seeds, writes `validation_summary.csv`, `validation_model_scores.csv`, and `selected_models.json`, and ranks candidates using a failure-dominated score:

```text
selection_score = 100 * failure_rate + mean_steady_position_rmse + 0.1 * mean_action_smoothness
```

The diagnostics script derives gate and action statistics from rollout `control.csv` files, including mean gate, active-gate rate, action norm, action smoothness, and flight time.
