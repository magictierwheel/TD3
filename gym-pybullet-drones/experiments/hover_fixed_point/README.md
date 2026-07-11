# Hover Fixed-Point Baselines

本目录放定点悬停类传统或自适应控制基线。

## 已分出的版本

- `scripts/adaptive_mrac/run_mrac_fixed_point.py`
  - 原 `gym_pybullet_drones/examples/mrac.py` 的实现位置。
  - 当前目标位置是 `[0, 0, 1]`。
  - 它可以作为后续 MRAC 圆轨迹对比的起点，但现在还不是匀速圆周运动脚本。

旧入口仍然可用：

```text
python -m gym_pybullet_drones.examples.mrac
```
