# 仓库结构

## 根目录入口

- `README.md`：面向人的项目入口。
- `AGENTS.md`：智能体接手规则。
- `PROJECT_HANDOFF.md`：简明交接状态。
- `STATUS.md`：由 `.research/execution_state.json` 生成的当前状态页。
- `ROADMAP.md`：稳定路线图。
- `docs/project/`：仓库政策、历史和决策记录。
- `docs/projects/pybullet_td3/`：PyBullet 研究计划、实施清单和协议历史。

## 两条研究线

```text
experiments/circular_tracking/
├── matlab_simulink/     # MATLAB/Simulink 圆周抗扰与残差 RL
└── pybullet_td3/        # Python/PyBullet 隐藏扰动 TD3
```

两条研究线并列存在，不共享数值结果表。PyBullet 的当前实现、阶段骨架和历史证据都在 `pybullet_td3/` 内；共享飞行器环境和控制器仍在 `gym_pybullet_drones/`。

## 证据与大文件

公开仓库只跟踪源码、配置、清单、小型 CSV/JSON/Markdown 证据和九个 Simulink 源模型。Replay Buffer、checkpoint、原始 MAT、日志、视频和临时 worktree 只在本地保留，详见 [public_snapshot_policy.md](public_snapshot_policy.md)。

## 归档边界

`experiments/circular_tracking/pybullet_td3/archive/` 保存旧 oracle、PID-FF、Gate 诊断和协议历史。归档内容只用于复现研究演化，不得与当前方法的结果混表或被静默改写。
