# 项目交接说明

## 项目身份

这是《强化学习》研究仓库，根目录与唯一正式 worktree 一一对应。仓库保留 MATLAB/Simulink 和 Python/PyBullet 两条并列的圆周跟踪研究线。

## 两条研究线

- MATLAB/Simulink：`experiments/circular_tracking/matlab_simulink/`，保存环境模型、多控制器比较、RL-v1 与 RL-v2/MPC 研究证据。
- PyBullet：`experiments/circular_tracking/pybullet_td3/`，研究隐藏时变扰动下的 PID、Direct TD3 与 PID-based Residual TD3。

两条研究线的数值结果不可混合统计。PyBullet 旧协议和失败诊断统一放在 `pybullet_td3/archive/`。

## 最新 PyBullet 状态

Bootstrap Preflight 为 **NO-GO**：Gate 3 v2.1 中 Direct TD3 在更新后发生崩溃，因此新的 Stage A 训练尚未授权。当前唯一下一步是先完成方法修订并冻结新的协议；不得通过延长预算或更换种子绕过门槛。

## MATLAB 资产位置

已迁移的 MATLAB/Simulink 源模型、脚本和小型证据位于 `experiments/circular_tracking/matlab_simulink/`。本地大文件和外部原始工程保持在原位置，不纳入公开仓库。

## 接手顺序

1. 阅读 [AGENTS.md](AGENTS.md) 和 [STATUS.md](STATUS.md)。
2. 阅读 [docs/projects/pybullet_td3/research_plan.md](docs/projects/pybullet_td3/research_plan.md) 与 [docs/projects/pybullet_td3/implementation_plan.md](docs/projects/pybullet_td3/implementation_plan.md)。
3. 读取 `.research/execution_state.json`，只执行其中的 `next_action`。
4. 需要了解历史时，阅读 [docs/project/research_history.md](docs/project/research_history.md) 和 [docs/projects/pybullet_td3/protocol_history.md](docs/projects/pybullet_td3/protocol_history.md)。

## 规则

不启动训练、PID 调优或长时间仿真，除非状态文件明确授权；不上传 Replay、checkpoint、原始 MAT、日志或视频；不改写归档证据的身份。
