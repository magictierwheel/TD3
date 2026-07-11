# gym-pybullet-drones 四旋翼强化学习控制复现说明

这份说明面向没有强化学习、Python、Docker 基础的学习者。你只要按步骤复制命令，就可以在本机复现“用 PPO 强化学习算法训练四旋翼无人机悬停控制策略”的最小实验。

## 1. 我选择的 GitHub 项目

项目：`learnsyslab/gym-pybullet-drones`

地址：https://github.com/learnsyslab/gym-pybullet-drones

选择理由：

- 主题匹配：项目说明是 “PyBullet Gymnasium environments for single and multi-agent reinforcement learning of quadcopter control”，也就是四旋翼无人机控制的强化学习环境。
- 收藏量高：GitHub API 查询时为 `2042 stars`、`540 forks`，明显高于其他同类四旋翼强化学习项目。
- 入门友好：项目自带 `gym_pybullet_drones/examples/learn.py`，直接使用 Stable-Baselines3 的 PPO 算法训练单无人机悬停。
- 依赖清晰：主要依赖 Python、PyBullet、Gymnasium、Stable-Baselines3、PyTorch。

本机复制位置：

```powershell
C:\Users\audib\Desktop\强化学习\gym-pybullet-drones
```

## 2. 本机已完成的复现环境

本机 Windows 原生 Python 3.14 太新，不适合这个项目；项目声明需要 Python 3.10 以上，并且 PyBullet 在 Windows/Python 3.10/3.11 下没有合适的预编译包，直接 pip 安装会尝试源码编译，容易失败。

所以本次复现采用 Docker 容器方式。容器里是 Linux + Python 3.10，PyBullet 有现成 wheel，依赖安装更稳。

已完成：

- Docker Desktop 已启动。
- Docker 镜像已构建：`gym-pybullet-drones-repro:latest`
- 镜像大小约 `14.7GB`，大是因为 PyTorch 会带较多依赖。
- 本机还在 `D:\rl_quadrotor_envs` 安装过 Python 3.10/3.11 作为备选，但复现主路线使用 Docker。

如果以后镜像不存在，可以在项目目录运行：

```powershell
docker build -f reproducibility/docker/Dockerfile.repro -t gym-pybullet-drones-repro .
```

第一次构建可能需要几十分钟。

## 3. 最快复现步骤

打开 PowerShell，进入项目目录：

```powershell
cd C:\Users\audib\Desktop\强化学习\gym-pybullet-drones
```

运行短训练复现：

```powershell
docker run --rm -v "${PWD}\experiments\hover_rl_reproduction\scripts\reproduce_hover_short.py:/workspace/experiments/hover_rl_reproduction/scripts/reproduce_hover_short.py:ro" -v "${PWD}\experiments\hover_rl_reproduction\results:/workspace/experiments/hover_rl_reproduction/results" gym-pybullet-drones-repro python experiments/hover_rl_reproduction/scripts/reproduce_hover_short.py --timesteps 2048 --eval-episodes 3 --rollout-steps 240 --output-folder experiments/hover_rl_reproduction/results/repro_hover_short
```

这条命令做了四件事：

- 创建单架四旋翼无人机悬停环境。
- 用 PPO 算法训练 2048 个时间步。
- 保存训练后的模型。
- 评估模型并保存一段飞行轨迹 CSV。

本机已验证成功，输出文件在：

```powershell
experiments\hover_rl_reproduction\results\repro_hover_short
```

关键文件：

```powershell
experiments\hover_rl_reproduction\results\repro_hover_short\ppo_hover_short.zip
experiments\hover_rl_reproduction\results\repro_hover_short\summary.json
experiments\hover_rl_reproduction\results\repro_hover_short\rollout.csv
```

本机短训练结果：

```text
timesteps: 2048
mean_reward: 355.7683
std_reward: 0.1818
rollout_steps: 240
final_z: 0.2163
```

注意：短训练用于验证“项目能跑通、能训练、能生成模型”。目标高度是 `z = 1.0`，短训练后的 `final_z` 还没有到 1.0，说明它只是快速复现，不代表已经训练出高质量控制器。

## 4. 官方示例也已验证

我还运行了项目自带的 PPO 示例 `gym_pybullet_drones/examples/learn.py` 的快速模式。

复现命令：

```powershell
docker run --rm -v "${PWD}\experiments\hover_rl_reproduction\results:/workspace/experiments/hover_rl_reproduction/results" gym-pybullet-drones-repro python -c "from gym_pybullet_drones.examples.learn import run; run(gui=False, plot=False, local=False, output_folder='experiments/hover_rl_reproduction/results/original_learn_quick')"
```

本机已验证成功，生成了：

```powershell
experiments\hover_rl_reproduction\results\original_learn_quick\save-06.06.2026_19.44.11\best_model.zip
experiments\hover_rl_reproduction\results\original_learn_quick\save-06.06.2026_19.44.11\final_model.zip
experiments\hover_rl_reproduction\results\original_learn_quick\save-06.06.2026_19.44.11\evaluations.npz
```

官方快速示例评估输出：

```text
1000 steps reward: 336.0107
2000 steps reward: 336.0137
Mean reward: 336.0134 +- 0.0009
```

这证明项目原始强化学习示例也能在本机环境里完整运行。

## 5. 如何看懂输出文件

`ppo_hover_short.zip`：训练后的 PPO 模型。可以理解为“无人机控制策略的大脑”。

`summary.json`：本次实验摘要。里面有训练步数、平均奖励、模型保存路径、轨迹文件路径。

`rollout.csv`：一次测试飞行的轨迹表格，可以用 Excel 打开。重要列：

- `step`：第几步。
- `x, y, z`：无人机位置。
- `action`：算法给电机的控制动作。
- `reward`：当前动作得到的奖励。
- `terminated / truncated`：本轮是否结束。

在这个任务里，无人机目标是悬停在：

```text
x = 0
y = 0
z = 1
```

`z` 越接近 `1.0`，说明高度控制越接近目标。`mean_reward` 越高，整体策略通常越好。原项目里单机悬停的目标奖励大约是 `474`，短训练不会直接达到这个水平。

## 6. 如果想训练更久

可以把 `--timesteps` 调大，例如：

```powershell
docker run --rm -v "${PWD}\experiments\hover_rl_reproduction\scripts\reproduce_hover_short.py:/workspace/experiments/hover_rl_reproduction/scripts/reproduce_hover_short.py:ro" -v "${PWD}\experiments\hover_rl_reproduction\results:/workspace/experiments/hover_rl_reproduction/results" gym-pybullet-drones-repro python experiments/hover_rl_reproduction/scripts/reproduce_hover_short.py --timesteps 100000 --eval-episodes 5 --rollout-steps 240 --output-folder experiments/hover_rl_reproduction/results/repro_hover_100k
```

本机也跑过 100000 步，命令成功完成并生成模型：

```text
mean_reward: 336.1666
std_reward: 121.5352
```

这次结果没有比短训练稳定，说明强化学习训练存在随机性，并且当前脚本是为了“快速复现链路”而写的最小实验。如果要得到更好的悬停效果，应优先使用原项目 `learn.py`，并把训练时间加到更长，例如几十万到数百万步。

## 7. 常见问题

如果提示找不到 Docker：

```powershell
docker --version
```

如果这个命令失败，说明 Docker Desktop 没装好或没有加入 PATH。

如果提示 Docker daemon 没启动：

```powershell
Start-Process "D:\Docker\Docker\Docker Desktop.exe"
```

等 Docker Desktop 启动后再运行复现命令。

如果提示找不到镜像：

```powershell
docker images gym-pybullet-drones-repro
```

如果没有结果，就重新构建：

```powershell
docker build -f reproducibility/docker/Dockerfile.repro -t gym-pybullet-drones-repro .
```

如果看到这些 warning，通常可以忽略：

```text
Box low's precision lowered by casting to float32
Evaluation environment is not wrapped with a Monitor wrapper
```

它们是 Gymnasium / Stable-Baselines3 的提示，不是复现失败。

## 8. 这个项目的核心文件

```text
gym_pybullet_drones/envs/HoverAviary.py
```

定义单无人机悬停任务，包括目标位置、奖励函数、结束条件。

```text
gym_pybullet_drones/envs/BaseRLAviary.py
```

定义强化学习环境的动作空间、观测空间、动作预处理。

```text
gym_pybullet_drones/examples/learn.py
```

官方 PPO 训练示例。

```text
gym_pybullet_drones/examples/play.py
```

加载训练好的模型并播放策略。

```text
experiments/hover_rl_reproduction/scripts/reproduce_hover_short.py
```

本次新增的短复现脚本，适合快速验证环境和训练链路。

```text
reproducibility/docker/Dockerfile.repro
```

本次新增的 Docker 复现环境文件。

## 9. 给初学者的理解路线

先不用急着理解全部数学。建议按这个顺序看：

1. 先运行第 3 节命令，确认能生成 `summary.json`。
2. 打开 `rollout.csv`，看 `z` 这一列如何变化。
3. 阅读 `HoverAviary.py`，重点看 `TARGET_POS` 和 `_computeReward()`。
4. 阅读 `learn.py`，知道 PPO 是从哪里创建、在哪里训练、在哪里保存模型。
5. 增大 `--timesteps`，观察奖励和轨迹是否变化。

能做到这五步，就已经完成了一个四旋翼强化学习控制项目的基础复现。
