# Experiments

本目录只放研究任务入口、实验结果和分析脚本；共享仿真环境、控制器和工具仍保留在 `gym_pybullet_drones/` 核心包中。

## 任务分类

- `circular_tracking/`: 当前研究主线，围绕匀速圆周或周期轨迹跟踪比较不同控制方法。
- `circular_tracking/rl_envs/`、`circular_tracking/scripts/td3/`、`circular_tracking/results/td3_residual_paper/`: 计划中的 PyBullet 扰动感知残差 TD3 小论文工作区；具体实施以根目录 `RL_PAPER_EXECUTION_PLAN.md` 为准。
- `circular_tracking/simulink_residual_rl/`: 从干扰环境仿真项目复制进来的 Simulink 圆周抗扰残差强化学习包。
- `hover_rl_reproduction/`: PPO 悬停复现，证明强化学习训练链路可运行，但不是圆周轨迹跟踪任务。
- `hover_fixed_point/`: 定点悬停类传统/自适应控制基线，目前包含 MRAC 定点控制。
