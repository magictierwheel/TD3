# Hover RL Reproduction

本目录放 PPO 悬停复现实验。它验证强化学习训练、评估、保存模型和导出轨迹的链路，但任务目标是定点悬停，不是匀速圆周轨迹跟踪。

## 主要文件

- `scripts/reproduce_hover_short.py`: 新增的短训练/评估复现脚本。
- `scripts/learn_hover_ppo.py`: 原 `gym_pybullet_drones/examples/learn.py` 的实现位置。
- `scripts/play_hover_policy.py`: 原 `gym_pybullet_drones/examples/play.py` 的实现位置。
- `results/`: 已保存的 PPO 悬停训练和评估结果。

旧入口仍然可用：

```text
python -m gym_pybullet_drones.examples.learn
python -m gym_pybullet_drones.examples.play
```
