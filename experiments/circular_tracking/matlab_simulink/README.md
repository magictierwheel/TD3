# MATLAB/Simulink 圆周抗扰研究

本目录是从 `E:\1-AI辅助工作\科研项目\干扰环境仿真\quadrotor_env_comparison` **复制**进强化学习项目的四旋翼匀速圆周抗扰控制包。原目录保留一份，不依赖本目录。

它是当前项目中最接近研究主线的强化学习内容：在同一条匀速圆周轨迹上，对比原 PID、PID 扰动补偿、MPC、ADRC、RL-v1 和 RL-v2 在标准、温度扰动、粉尘扰动三类环境下的跟踪效果。

## 目录分类

- `models/`
  - Simulink 模型，包括标准/温度/粉尘环境模型，以及 PID、PID-FF、MPC、ADRC、RL、RL-v2 策略模型。
- `scripts/`
  - MATLAB 仿真、训练、策略启用和控制核心函数。
  - `scripts/reporting/` 存放 Python/PowerShell 报告生成脚本。
- `results/policies/`
  - 已训练策略权重。
  - `rl_v1/quadrotor_rl_policy.mat`: 5 参数残差策略。
  - `rl_v2/quadrotor_rl_v2_policy.mat`: 120 槽位前瞻残差策略。
- `results/data/`
  - 训练日志、对比指标 CSV/Markdown、仿真 MAT 数据。
- `results/figures/`
  - 圆周轨迹、误差、指标柱状图和控制努力图。
- `reports/`
  - `rl_v1/`: 强化学习残差策略圆周抗扰报告。
  - `rl_v2/`: RL-v2 与 MPC 对比报告。
  - `strategy_comparison/`: 多控制策略圆周抗扰对比报告。
  - `assets/`: 报告公式图片等素材。
- `tests/`
  - MATLAB 单元测试，重点检查 RL-v2 模仿学习读出层和特征映射。
- `docs/`
  - RL-v2 设计说明、实施计划和原交付 README 备份。
- `audit/`
  - 原交付包的审核摘要备份。

## 关键脚本

```matlab
setup_matlab_simulink_paths
train_quadrotor_rl_policy
run_rl_circle_comparison
train_quadrotor_rl_v2_policy
run_rl_v2_mpc_benchmark
run_strategy_circle_comparison
```

## MATLAB 运行方式

在 MATLAB 中进入本目录，或显式设置路径：

```matlab
projectRoot = 'E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\integration\experiments\circular_tracking\matlab_simulink';
addpath(projectRoot);
setup_matlab_simulink_paths;
```

运行 RL-v1 圆周抗扰对比：

```matlab
run_rl_circle_comparison;
```

运行 RL-v2 与 MPC/多控制器对比：

```matlab
run_rl_v2_mpc_benchmark('smoke');
```

运行五类控制策略对比：

```matlab
run_strategy_circle_comparison;
```

## 当前结果要点

- RL-v1 在温度扰动下将全程 RMS 从约 `0.2660 m` 降到 `0.0995 m`。
- RL-v1 在粉尘扰动下将全程 RMS 从约 `0.1143 m` 降到 `0.0857 m`。
- RL-v2 最新指标以 `results/data/quadrotor_rl_v2_mpc_benchmark_metrics.csv` 为准；旧报告中的验收文字可能来自更早一次运行。

## 和 PyBullet 圆周示例的关系

- `experiments/circular_tracking/scripts/position_pid/` 是 PyBullet 版本的圆周 PID 示例。
- 本目录是 Simulink 版本的圆周抗扰与残差强化学习对比包。
- 后续若要做 TD3，建议优先参考本目录的状态量、评价指标和多控制器对比框架，再决定是否接到 PyBullet 或 Simulink。
