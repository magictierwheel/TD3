# 圆周跟踪研究

本目录包含两个并列平台，分别回答不同层面的圆周抗扰问题：

| 平台 | 入口 | 内容 |
|---|---|---|
| MATLAB/Simulink | `matlab_simulink/` | 环境模型、多控制器比较、RL-v1、RL-v2/MPC 研究与证据 |
| Python/PyBullet | `pybullet_td3/` | 隐藏时变扰动下 PID、Direct TD3、PID-based Residual TD3 |

两条研究线的模型、采样率、奖励和指标不同，禁止跨平台合并数值结论。PyBullet 当前状态、阶段门槛和唯一下一步以根目录 [STATUS.md](../../STATUS.md) 与 [docs/projects/pybullet_td3/implementation_plan.md](../../docs/projects/pybullet_td3/implementation_plan.md) 为准。

## PyBullet 研究边界

主实验中的控制器只能使用相同的可测状态、参考轨迹、误差历史和冻结 PID 当前输出；不得读取风速、效率、场景标签或随机种子。旧 oracle/PID-FF 协议和结果均位于 `pybullet_td3/archive/`，仅用于研究历史和失败诊断。
