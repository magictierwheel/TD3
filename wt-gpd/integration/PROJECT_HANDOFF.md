# 项目交接说明

更新时间：2026-07-10

这份文档面向之后接手本项目的智能体和人类工作者。它说明当前研究问题、旧成果边界、失败原因和下一步，不再复述已经废弃的 oracle/PID-FF 路线。

## 一句话概括

本项目基于 `gym-pybullet-drones` 研究四旋翼圆周轨迹跟踪。新论文比较传统 PID、端到端 Direct TD3 和 PID-based Residual TD3 在**未知、随机、时变扰动**下的表现；三者只能使用相同可测飞行状态，均不知道真实环境干扰信息。

## 当前状态

已经完成：

- PyBullet 圆周 TD3 原型环境、训练、评估、汇总和作图链路。
- 多种旧 TD3 变体、PID/PID-FF、warm-start、checkpoint 和泛化 pilot。
- 对旧成果的审稿式复核和根因分析。
- 新研究问题、设计 brief、主计划和实施计划。

尚未完成：

- 新 hidden-disturbance environment。
- 新 terminal-reward 和 information-boundary tests。
- 能真正完成圆周的 frozen PID baseline。
- 新 Direct/Residual TD3 matched action/reward interface。
- 新 20k/50k/100k 分阶段训练。
- 新论文主结果与 revised manuscript。

因此当前状态是：**研究设计已重置，代码重构和新实验尚未开始。**

## 必读文件

```text
RL_PAPER_EXECUTION_PLAN.md
.research/design_brief.md
docs/superpowers/specs/2026-07-10-hidden-disturbance-td3-paper-redesign.md
docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md
AGENTS.md
PROJECT_STRUCTURE.md
```

## 新论文研究问题

> 在扰动不可直接观测、训练预算和可测状态信息相同的条件下，PID 稳定先验能否使 Residual TD3 比端到端 Direct TD3 更安全、更省样本，并改善普通 PID 在随机复合扰动下的圆周轨迹跟踪？

三种核心控制器：

| 控制器 | 输入 | 输出 | 扰动信息 |
|---|---|---|---|
| PID | reference + measured flight state | 4 motor RPM | 无 |
| Direct TD3 | same observable state/error history | 4 motor RPM | 无 |
| Residual TD3 | same history + PID RPM | 4 bounded RPM deltas | 无 |

普通 PID 保留正常反馈和积分状态，但没有显式扰动观测器。若以后增加 PID-DOB、ADRC、PID-FF 或 MPC，必须作为第四基线，不能作为 actor teacher 或偷偷并入 PID。

## 新论文不再使用什么

新主实验移除：

```text
oracle disturbance observation
disturbance-aware policy name
PID-FF imitation warm-start
warm-start retention
residual_gate_min based on disturbance magnitude
per-training-seed favorable checkpoint selection
legacy test seeds 0,1,2
```

Residual actor 使用零输出初始化，初始行为严格等于 PID。新 safety gate 只能依赖 tracking error、姿态/高度安全余量和 motor headroom。

## 旧成果为什么不能继续作为主论文

### 1. Terminal reward bug

旧环境在 reward 计算后才更新 failure reason，导致描述中的 `-50` 失败惩罚没有进入 terminal transition。旧策略没有获得正确的失控学习信号。

### 2. 只训练半圈

旧训练 episode 为 5 秒，参考周期为 10 秒。策略每次只看到前半圈和同一初始相位。

### 3. 训练量极小

旧 5000 steps 约等于 20 个 episode，五类场景平均只有约四个 episode，不能视为 TD3 收敛实验。

### 4. Nominal PID 不合格

旧 PID standard 稳态 RMSE 与圆半径相当，实际路径长度远小于三圈参考长度。Residual actor 同时在补偿 PID 圆周滞后和环境扰动。

### 5. Oracle 信息削弱 RL 动机

旧 actor 获得仿真器真实风、热、密度和效率参数；PID-FF 又用同一模型提供 imitation target。已知扰动和模型时，解析前馈本来就比有限数据的 TD3 更直接。

### 6. 消融不公平

旧 DA-Residual 有 safety gate，旧 residual_td3 固定 gate=1；所谓 no-disturbance-observation ablation 同时改变了 observation 和 gate。

### 7. Test leakage

旧 test seeds 0-2 被多次用于选择 warm-start、retention、gate 和 checkpoint，不再是未触碰测试集。

### 8. 统计与指标问题

旧 early failure 可能得到偏低 RMSE；三个训练模型反复使用相同三个扰动 seed，九行数据不等于九个独立环境样本。

### 9. 图表不完整

旧 manuscript 以 smoke 图为主，部分 combined trajectory 图为空，主图缺少分层置信区间。

这些问题不是靠继续增加旧模型训练步数就能修复，因此采用新 namespace 和新环境，而不是在旧结果目录上追加实验。

## Legacy 材料

旧代码：

```text
experiments/circular_tracking/rl_envs/circular_residual_td3_env.py
experiments/circular_tracking/scripts/td3/train_direct_td3.py
experiments/circular_tracking/scripts/td3/train_residual_td3.py
experiments/circular_tracking/scripts/td3/evaluate_td3_controllers.py
```

旧结果：

```text
experiments/circular_tracking/results/td3_residual_paper/
```

旧论文与分析：

```text
docs/paper/manuscript.md
docs/paper/manuscript.docx
docs/paper/method.md
docs/paper/results.md
experiments/circular_tracking/analysis/claim_evidence_ledger.csv
experiments/circular_tracking/analysis/plan_completion_audit.md
```

不要删除这些文件。它们是研究演化、物理 bug、奖励 bug、训练退化和统计问题的诊断证据。但不要再从这些结果导出新论文主张。

## 新实验 namespace

计划创建：

```text
experiments/circular_tracking/rl_envs/disturbance_processes.py
experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py
experiments/circular_tracking/scripts/td3/tune_hidden_pid.py
experiments/circular_tracking/scripts/td3/train_hidden_td3.py
experiments/circular_tracking/scripts/td3/evaluate_hidden_td3.py
experiments/circular_tracking/scripts/td3/summarize_hidden_td3.py
tests/circular_tracking/
```

新结果只写入：

```text
experiments/circular_tracking/results/hidden_disturbance_td3_paper/
```

## 新扰动场景

```text
standard       no disturbance
random_wind    hidden time-varying horizontal wind
actuator_loss  hidden time-varying thrust/torque efficiency
compound       random_wind + actuator_loss
unseen         stronger or faster hidden disturbances, final test only
```

Disturbance truth 可以记录在离线 metadata，便于复核；不得进入 policy observation、gate 或 model-selection feature。

## 执行门槛

### Stage 0: 先验证实验有效性

必须通过：

- terminal failure penalty test。
- same-seed disturbance reproducibility test。
- no privileged observation test。
- zero residual equals PID test。
- PID nominal circular-tracking acceptance。
- matched reward/action bound test。

### Stage A: 20k seed 0

用最小预算判断方向。Residual 若无法保持 PID 安全性或改善 PID/Direct 中至少一个主要指标，立即停止。

### Stage B: 50k seeds 0-2

至少 2/3 training seeds 同方向改善才进入下一阶段。使用一个全局 checkpoint budget。

### Stage C: up to 100k seeds 0-4

只在 Stage B GO 后运行。完成后冻结协议，再打开 test seeds 200-219 和 unseen seeds 300-319。

不默认运行 500k。

## PID 首要验收

在任何 RL 训练前，PID 必须在 standard 30 秒中满足：

```text
failure = false
steady_position_rmse < 0.10 m
path_length_ratio in [0.90, 1.10]
```

PID 只能在 nominal validation 上调参，随后冻结。若此项失败，不得启动 TD3。

## 其他项目线

### PPO hover reproduction

```text
experiments/hover_rl_reproduction/
```

只说明 PPO 悬停训练链路可运行，不是新圆周论文证据。

### Fixed-point controllers

```text
experiments/hover_fixed_point/
```

当前主要是定点任务，不与圆周方法直接比较。

### Simulink residual RL

```text
experiments/circular_tracking/simulink_residual_rl/
```

保留为方法背景和历史材料。平台、动力学和扰动模型不同，不与新 PyBullet 数值混表。

## 环境和命令

当前 Windows 工作区优先使用：

```powershell
py -3.11
```

基础检查：

```powershell
py -3.11 -m pytest tests -q
py -3.11 -m compileall experiments/circular_tracking/rl_envs experiments/circular_tracking/scripts/td3
```

新环境实现后，正式训练前运行：

```powershell
py -3.11 -m pytest tests/circular_tracking -v
```

## 推荐接手顺序

1. 读 `RL_PAPER_EXECUTION_PLAN.md`。
2. 读 `.research/design_brief.md`。
3. 读 implementation plan。
4. 检查 `tests/circular_tracking/` 和新 result namespace 是否存在。
5. 从 implementation plan 第一个未完成 checkbox 开始。
6. 每项先写 failing test，再改实现。
7. Stage 0 全部通过后才启动 Stage A。

## 当前最合理的下一步

创建 `tests/circular_tracking/test_hidden_disturbance_td3_env.py`，首先复现 terminal reward bug 和 privileged-information boundary，然后实现新的 hidden disturbance process 和 fair three-controller environment。

当前不应继续旧 5000-step 模型，不应追加 PID-FF warm-start，也不应直接启动 50k/100k 训练。
