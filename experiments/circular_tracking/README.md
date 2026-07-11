# Circular Tracking Experiments

本目录是四旋翼圆周/周期轨迹跟踪研究主线。2026-07-10 起，论文方向已经重置为：在隐藏随机扰动下公平比较 PID、端到端 Direct TD3 和 PID-based Residual TD3。

## Authoritative Plan

```text
../../RL_PAPER_EXECUTION_PLAN.md
../../.research/design_brief.md
../../docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md
```

新控制器不得读取真实扰动信息或场景标签。普通 PID 没有 disturbance observer；它只依靠闭环反馈和积分作用。Residual TD3 的在线底座是普通 PID，actor 使用零输出初始化，不使用 PID-FF imitation。

## Revised Study Namespace

计划新增：

```text
rl_envs/disturbance_processes.py
rl_envs/hidden_disturbance_td3_env.py
scripts/td3/tune_hidden_pid.py
scripts/td3/train_hidden_td3.py
scripts/td3/evaluate_hidden_td3.py
scripts/td3/summarize_hidden_td3.py
analysis/hidden_td3_metric_schema.md
analysis/hidden_td3_claim_evidence_ledger.csv
results/hidden_disturbance_td3_paper/
```

当前这些新文件尚未实现。第一步是测试 terminal reward、privileged-information boundary、zero-residual invariant 和 nominal PID tracking；不是直接训练。

## Legacy Oracle/PID-FF Pilot

以下材料属于旧路线：

```text
rl_envs/circular_residual_td3_env.py
scripts/td3/train_direct_td3.py
scripts/td3/train_residual_td3.py
scripts/td3/evaluate_td3_controllers.py
results/td3_residual_paper/
analysis/claim_evidence_ledger.csv
analysis/plan_completion_audit.md
```

旧路线包含 oracle disturbance observation、PID-FF warm-start、retention、gate-min 和 per-seed checkpoint selection。它记录了重要失败原因，但不得继续作为 revised paper 主实验。

关键失败包括：

- terminal failure penalty 未进入 reward。
- 5 秒 episode 只覆盖 10 秒圆周的前半圈。
- 5000 steps 每模型约 20 个 episode。
- nominal PID 没有真正完成圆周。
- disturbance observation ablation 同时改变 gate。
- test seeds 0-2 被反复用于调参。
- early termination RMSE 和 pooled rows 造成误导。

## Existing Circular/Periodic Scripts

- `scripts/position_pid/run_position_pid_circle.py`
  - 现有 X-Y 圆周参考与 DSL PID 示例。
  - 新论文需要单独调优并冻结通过 acceptance 的 PID 配置。
- `scripts/downwash_periodic/run_downwash_periodic.py`
  - X-Z 周期运动和 downwash；不是 revised main scenario。
- `scripts/velocity_input/run_velocity_input_periodic.py`
  - 周期速度输入；不是 revised main controller。

## Simulink Package

- `simulink_residual_rl/`
  - 历史 Simulink RL-v1/RL-v2、PID-FF、MPC、ADRC 和报告。
  - 可作为方法背景，但不得与 revised PyBullet 数值混表。

## New Experiment Stages

```text
Stage 0: tests + valid nominal PID
Stage A: Direct/Residual seed0 to 20k
Stage B: seeds0-2 to 50k after GO
Stage C: seeds0-4 to 100k after GO
```

Validation 使用 seeds 100-109；最终 test 使用 200-219；unseen 使用 300-319。必须选择统一 checkpoint budget，不能为每个 training seed 单独挑结果。

## Runtime

Windows 本地优先使用：

```powershell
py -3.11
```

新实现开始后，每项先写 failing test，并在训练前运行：

```powershell
py -3.11 -m pytest tests/circular_tracking -v
py -3.11 -m compileall experiments/circular_tracking/rl_envs experiments/circular_tracking/scripts/td3
```
