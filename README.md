# 强化学习

本仓库集中保存四旋翼圆周跟踪中的两条正式研究线：MATLAB/Simulink 圆周抗扰与残差强化学习，以及 PyBullet 中的 PID-based Residual TD3。

| 研究线 | 平台 | 入口 | 当前状态 |
|---|---|---|---|
| MATLAB/Simulink 圆周抗扰 | MATLAB/Simulink | `experiments/circular_tracking/matlab_simulink/` | 已完成多控制器、RL-v1 和 RL-v2/MPC 研究 |
| PyBullet 圆周跟踪 | Python/PyBullet | `experiments/circular_tracking/pybullet_td3/` | Bootstrap NO-GO，等待方法修订 |

当前进展见 [STATUS.md](STATUS.md)，稳定路线见 [ROADMAP.md](ROADMAP.md)，智能体规则见 [AGENTS.md](AGENTS.md)。项目交接见 [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md)；研究历史和公开文件政策分别见 [docs/project/research_history.md](docs/project/research_history.md) 与 [docs/project/public_snapshot_policy.md](docs/project/public_snapshot_policy.md)。

## 安装

```sh
pip install -e .
```

推荐使用 Python 3.11，并确保 PyBullet、Gymnasium 和 Stable-Baselines3 依赖已安装。MATLAB/Simulink 研究线需要 MATLAB/Simulink 及相应工具箱；仅查看已归档文件不需要运行 MATLAB。

## PyBullet 基础示例

```sh
python gym_pybullet_drones/examples/pid.py
python gym_pybullet_drones/examples/pid_velocity.py
python gym_pybullet_drones/examples/downwash.py
```

## 研究边界

- PyBullet 主线比较 PID、Direct TD3 与 PID-based Residual TD3；三者不读取真实扰动参数。
- `experiments/circular_tracking/pybullet_td3/archive/` 保存旧协议和失败诊断，不与当前证据混表。
- MATLAB/Simulink 与 PyBullet 的数值结果不得跨平台合并。
- Replay、checkpoint、原始 MAT、日志和视频只保留在本地，不上传到公开仓库。

## 引用

本仓库保留原 `gym-pybullet-drones` 的许可证和引用信息，详见 [CITATION.cff](CITATION.cff)。
