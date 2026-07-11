> [!WARNING]
> **LEGACY OUTLINE.** 新论文只比较 PID、Direct TD3 和 hidden-disturbance Residual TD3。新 outline 应写入 `docs/paper/revised_outline.md`。

# Disturbance-Aware Residual TD3 Control For Quadrotor Circular Trajectory Tracking

## Title

Chinese:

复合环境扰动下四旋翼匀速圆周轨迹跟踪的扰动感知残差 TD3 控制方法

English:

Disturbance-Aware Residual TD3 Control for Quadrotor Circular Trajectory Tracking under Compound Environmental Disturbances

## Abstract Draft

This paper studies quadrotor circular trajectory tracking under compound environmental disturbances in PyBullet/Gymnasium simulation. A classical PID controller provides a stable baseline, while a TD3 actor learns bounded residual compensation from normalized tracking state and disturbance observations. The implementation includes safety gating, PID-FF imitation warm-start, warm-start retention, and validation checkpoint selection. Current evidence supports a bounded multiseed pilot result: Direct TD3 is unsafe, gated residual control preserves PID in the standard scene, and conservative validation-selected models improve wind/compound tracking relative to plain PID across three training seeds. The same evidence also shows clear limits: the selected models remain weaker than analytic PID-FF and do not generalize reliably to unseen disturbance settings.

## 1 Introduction

- Quadrotor trajectory tracking is central to inspection, monitoring, and repeated patrol tasks.
- Circular tracking is a compact benchmark for persistent tracking rather than one-shot point-to-point motion.
- PID is reliable in nominal conditions but degrades when aerodynamics and actuator efficiency shift under compound disturbances.
- End-to-end reinforcement learning can learn compensation but may be unstable during exploration and may output unnecessary actions in nominal conditions.
- Residual reinforcement learning offers an engineering compromise: PID handles the stabilizing backbone; TD3 learns bounded corrections.
- Disturbance observations and safety gating are the two mechanisms to be tested by ablation.

## 2 Related Work

To be developed from `docs/paper/related_work.md`.

Expected groups:

- PID, MPC, ADRC, and model-based quadrotor trajectory tracking.
- RL-based quadrotor control under wind disturbances.
- Hybrid PID/RL and residual RL controllers.
- Wind-aware or disturbance-aware policies.
- Reproducibility and evaluation practices for continuous-control RL.

## 3 Problem Formulation

- Simulator: PyBullet/Gymnasium via `gym-pybullet-drones`.
- Vehicle: single Crazyflie-style quadrotor, `CF2X`.
- Task: follow a horizontal circular reference trajectory:
  - `radius = 0.3 m`
  - `period = 10 s`
  - `height = 1.0 m`
  - formal evaluation duration `30 s`
- Disturbances:
  - wind drag
  - density-scaled drag
  - thermal upward acceleration
  - dust-induced thrust and torque efficiency loss
- Objective: minimize tracking error while avoiding tilt, saturation, excessive energy, and action roughness.

## 4 Method

### 4.1 Circular Reference

Define position, velocity, acceleration, and phase for the circular trajectory. The reference must be generated identically for all controllers.

### 4.2 PID Baseline

Use `DSLPIDControl.computeControl()` with both `target_pos` and `target_vel`. Fixed yaw is the first default; tangent yaw is allowed only if applied consistently to all controllers.

### 4.3 Direct TD3

The actor outputs four normalized motor commands. Actions are mapped around hover RPM and clipped to legal motor limits.

### 4.4 Residual TD3

The actor outputs bounded residual terms over acceleration-like reference corrections and thrust/torque scale adjustments. PID remains the stabilizing controller.

### 4.5 Disturbance-Aware Residual TD3

The residual policy observes wind, density loss, thermal acceleration, thrust loss, and torque loss in addition to tracking state. A safety gate suppresses residual action in nominal conditions or near actuator saturation.

### 4.6 Reward

Use normalized tracking, velocity, altitude, tilt, action-energy, action-smoothness, and saturation penalties. The exact field definitions are fixed in `experiments/circular_tracking/analysis/td3_metric_schema.md`.

## 5 Experiments

### 5.1 Controllers

- PID
- PID-FF, only if the fixed analytic feed-forward definition is implemented
- Direct TD3
- Residual TD3
- Disturbance-aware residual TD3

### 5.2 Main Scenarios

- standard
- wind
- thermal
- dust
- compound

### 5.3 Generalization

- unseen disturbance range
- radius/period changes: `(0.4, 8)` and `(0.5, 12)`

### 5.4 Seeds And Duration

- main seeds: `0, 1, 2`
- validation seeds: `100, 101, 102`
- formal evaluation: `30 s`
- smoke tests: `12 s`, not for main paper claims

## 6 Results

Results should be organized by claims:

- C4 first: nominal behavior relative to PID.
- C5: disturbance tracking improvements.
- C1: residual stability versus Direct TD3.
- C2/C8: value and limits of disturbance observations plus conservative warm-start retention.
- C3: safety-gate effect on saturation and smoothness.
- C6: unseen and trajectory-parameter generalization.

Every numeric claim must trace to `summary_metrics.csv`, `summary_metrics_aggregate.csv`, or `claim_evidence_ledger.csv`.

## 7 Discussion

- Why residual control improves stability.
- Why explicit disturbance information may help under compound disturbances.
- Why oracle disturbance observations limit direct real-world claims.
- Why PyBullet and Simulink numbers are discussed separately.
- Failure cases, bounded positive results, and negative results where PID-FF/unseen criteria are not met.

## 8 Conclusion

The intended conclusion is not that TD3 universally beats all controllers. The intended conclusion is that bounded residual learning, disturbance observations, safety gating, and conservative warm-start checkpoint selection can make learning-based compensation more stable and partly useful for disturbed circular tracking, while PID-FF and unseen generalization remain unresolved limits.

## Required Artifacts Checklist

- `experiments/circular_tracking/analysis/claim_evidence_ledger.csv`
- `experiments/circular_tracking/analysis/td3_metric_schema.md`
- `docs/paper/related_work.md`
- `docs/paper/method.md`
- `docs/paper/results.md`
- `experiments/circular_tracking/results/td3_residual_paper/summaries/summary_metrics.csv`
- `experiments/circular_tracking/results/td3_residual_paper/summaries/summary_metrics_aggregate.csv`

