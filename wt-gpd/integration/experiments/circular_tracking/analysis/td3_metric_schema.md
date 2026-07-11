# TD3 Metric Schema

This file fixes the output schema for the PyBullet circular-tracking TD3 paper work. All precise numbers in the paper must be traceable to these CSV or JSON files.

## Units And Conventions

- Time is in seconds.
- Position and distance are in meters.
- Linear velocity is in meters per second.
- Angles are in radians.
- Rotor speeds are in RPM.
- Normalized TD3 actions are dimensionless and bounded by `[-1, 1]`.
- `steady_*` metrics are computed over samples with `time >= period`.
- `failure` is `true` when an episode terminates before `duration_sec` due to safety limits or produces non-finite state/action values.

## `trajectory.csv`

| Column | Unit | Definition |
|---|---:|---|
| `time` | s | Control-step timestamp. |
| `x`, `y`, `z` | m | Drone position in world frame. |
| `vx`, `vy`, `vz` | m/s | Drone linear velocity in world frame. |
| `roll`, `pitch`, `yaw` | rad | Drone Euler attitude. |
| `ref_x`, `ref_y`, `ref_z` | m | Circular reference position. |
| `ref_vx`, `ref_vy`, `ref_vz` | m/s | Circular reference velocity. |
| `pos_error` | m | `sqrt((x-ref_x)^2 + (y-ref_y)^2 + (z-ref_z)^2)`. |
| `xy_error` | m | `sqrt((x-ref_x)^2 + (y-ref_y)^2)`. |
| `z_error` | m | `z - ref_z`. |

Optional diagnostic columns may be added after these required columns, but the required names and meanings must not change.

## `control.csv`

| Column | Unit | Definition |
|---|---:|---|
| `time` | s | Control-step timestamp. |
| `rpm_0`, `rpm_1`, `rpm_2`, `rpm_3` | RPM | Final clipped motor commands applied to PyBullet. |
| `action_0` ... `action_4` | normalized | TD3 action. Direct TD3 uses `action_0` through `action_3`; `action_4` is `0` or empty. |
| `gate` | dimensionless | Safety-gate multiplier applied to the residual action. PID and Direct TD3 use `0` or empty. |
| `saturation_fraction` | fraction | Fraction of motors with `rpm <= 0.02 * max_rpm` or `rpm >= 0.98 * max_rpm`. |
| `control_energy` | normalized | `mean((rpm / max_rpm)^2)` for the current step. |
| `action_delta` | normalized | `mean((action - last_action)^2)` for the current step. |

## `episode_summary.json`

Required top-level keys:

```json
{
  "controller": "disturbance_aware_residual_td3",
  "scenario": "compound",
  "seed": 0,
  "radius": 0.3,
  "period": 10.0,
  "height": 1.0,
  "duration_sec": 30.0,
  "disturbance": {
    "wind_x": 0.0,
    "wind_y": 0.0,
    "density_scale": 1.0,
    "thermal_acc_z": 0.0,
    "thrust_efficiency": 1.0,
    "torque_efficiency": 1.0
  },
  "metrics": {
    "position_rmse": 0.0,
    "steady_position_rmse": 0.0,
    "max_position_error": 0.0,
    "final_position_error": 0.0,
    "max_altitude_error": 0.0,
    "max_tilt_angle": 0.0,
    "rotor_saturation_rate": 0.0,
    "control_energy": 0.0,
    "action_smoothness": 0.0,
    "failure": false,
    "failure_reason": ""
  }
}
```

Metric formulas:

| Metric | Unit | Formula |
|---|---:|---|
| `position_rmse` | m | `sqrt(mean(pos_error^2))` over the full episode. |
| `steady_position_rmse` | m | `sqrt(mean(pos_error^2))` for `time >= period`. |
| `max_position_error` | m | `max(pos_error)`. |
| `final_position_error` | m | Last finite `pos_error`. |
| `max_altitude_error` | m | `max(abs(z_error))`. |
| `max_tilt_angle` | rad | `max(sqrt(roll^2 + pitch^2))`. |
| `rotor_saturation_rate` | fraction | Mean of `saturation_fraction` over control steps. |
| `control_energy` | normalized | Mean of stepwise `control_energy`. |
| `action_smoothness` | normalized | Mean of stepwise `action_delta`. |

## `summary_metrics.csv`

One row per controller/scenario/seed rollout:

```text
controller
scenario
seed
radius
period
height
duration_sec
position_rmse
steady_position_rmse
max_position_error
final_position_error
max_altitude_error
max_tilt_angle
rotor_saturation_rate
control_energy
action_smoothness
failure
failure_reason
```

## `summary_metrics_aggregate.csv`

One row per controller/scenario aggregate. The summarizer should include `mean`, `std`, and `num_seeds` for numeric metrics, plus `failure_rate`.

Required grouping columns:

```text
controller
scenario
radius
period
height
duration_sec
num_seeds
failure_rate
```

Column suffix convention:

```text
position_rmse_mean
position_rmse_std
steady_position_rmse_mean
steady_position_rmse_std
...
```

## Claim Links

- C1 uses `failure_rate`, `max_tilt_angle`, `rotor_saturation_rate`, and `max_position_error`.
- C2 uses `position_rmse`, `steady_position_rmse`, and `final_position_error`.
- C3 uses `rotor_saturation_rate`, `action_smoothness`, and `control_energy`.
- C4 uses standard-scene `position_rmse` relative to PID.
- C5 uses wind/thermal/dust/compound `steady_position_rmse` and `failure_rate`.
