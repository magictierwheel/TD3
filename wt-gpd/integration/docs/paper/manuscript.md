> [!WARNING]
> **LEGACY DRAFT.** 本文对应已废弃的 oracle 扰动观测、PID-FF imitation 和 gate-min 路线。它不是当前投稿稿；旧数字只能作为失败诊断。新方向见根目录 `RL_PAPER_EXECUTION_PLAN.md`。

# 复合环境扰动下四旋翼匀速圆周轨迹跟踪的扰动感知残差 TD3 控制方法

## 摘要

四旋翼无人机在巡检、监测和周期巡航任务中常需要沿固定轨迹长期稳定飞行。传统 PID 控制器在标准环境中实现简单、响应可靠，但在风场、热上升、空气密度变化和粉尘导致的推力衰减等复合扰动下，轨迹误差和执行器饱和风险会显著增加。端到端强化学习具有通过交互学习扰动补偿的潜力，但直接输出电机控制量容易带来训练不稳定、探索失控和无扰动环境下动作冗余等问题。本文提出一种面向四旋翼匀速圆周轨迹跟踪的扰动感知残差 TD3 控制框架：以 PID 作为稳定底座，由 TD3 actor 学习有界残差补偿，并将环境扰动量显式输入策略，同时通过安全门控抑制无扰动或接近饱和状态下的残差动作。当前工作完成了 PyBullet/Gymnasium 圆周跟踪环境、六类扰动场景、TD3 训练脚本、PID-FF imitation warm-start、warm-start retention、模型加载评估脚本、validation checkpoint 选模、图表生成脚本、指标 schema 和证据账本，并修复了扰动外力在世界坐标系中施加点错误导致的非物理倾角失效。修复后的三训练种子、三测试扰动种子、30 秒 pilot 表明：Direct TD3 在所有主场景中均早停失败；安全门控使扰动感知残差 TD3 在标准场景中与 PID 完全一致；朴素 TD3 微调会破坏 warm-start 策略；更保守的 retention 微调、`residual_gate_min = 0.8` 和 validation 选模可在 wind 与 compound 中相对普通 PID 降低失败率和稳态 RMSE。三训练种子合并后，DA-Residual 在 wind/compound 中的 failure_rate 均为 0.111，低于普通 PID 的 0.333；稳态 RMSE 分别为 0.6914 m 和 0.6821 m，优于普通 PID 的 0.9970 m 和 0.9537 m，但仍弱于解析 PID-FF 的 0.3545 m 和 0.4838 m。进一步的 matched no-disturbance-observation 消融显示，DA-Residual 在主测试 wind/compound 的稳态 RMSE 低于同协议 residual_td3，但在 unseen 强扰动泛化中反而更差。泛化评估中，DA-Residual unseen failure_rate 仍为 0.778。因此，本文当前形成的是一个可复现实验框架和有边界的诊断型小论文：它支持“端到端 TD3 不安全”“门控残差结构必要”和“保守 warm-start 选模可改善普通 PID 及无扰动观测残差策略在风/复合扰动中的表现”，但不能声称 TD3 已经全面优于 PID-FF 或具备可靠外推泛化能力。

关键词：四旋翼无人机；轨迹跟踪；残差强化学习；TD3；扰动感知控制；PyBullet

## 1 引言

四旋翼无人机因结构简单、机动性强、可悬停等特点，被广泛用于巡检、环境监测、目标跟踪和复杂场景采样任务。与点到点飞行或定点悬停不同，周期轨迹跟踪要求控制器在较长时间内持续处理参考轨迹变化、机体姿态约束和环境扰动。匀速圆周轨迹是一类紧凑而具有代表性的周期任务：它同时包含持续横向加速度、相位变化和稳态误差积累，因此适合作为不同控制方法的统一对比基准。

传统 PID 控制器具有实现简单、计算量小和工程可解释性强等优点。在标准仿真环境下，PID 往往能够形成稳定飞行底座。然而，当环境存在水平风、热上升、空气密度变化和粉尘导致的电机效率损失时，固定参数 PID 的轨迹误差可能增大，甚至出现姿态角过大或执行器饱和。MPC、ADRC 和扰动观测器等模型控制方法可增强抗扰性，但通常需要更明确的系统模型、扰动假设或在线优化资源。

强化学习为复杂扰动下的控制补偿提供了另一条路径。DDPG、PPO、TD3 等连续控制算法已经被用于无人机抗风、轨迹跟踪和混合控制结构中。不过，端到端强化学习直接输出电机控制量时，训练阶段容易出现不稳定探索；同时，在无扰动环境中，学习策略也可能产生不必要的动作修正。残差强化学习提供了一种更保守的折中方案：保留传统控制器作为稳定底座，只让学习策略输出受限补偿量。

本文围绕“复合环境扰动下四旋翼匀速圆周轨迹跟踪”构建 PyBullet/Gymnasium 实验框架，目标不是证明 TD3 在所有条件下替代 PID，而是验证三个更可落地的机制：残差结构是否比直接控制更稳定，扰动显式观测是否提升复合扰动补偿能力，安全门控是否减少饱和和异常动作。

本文当前贡献如下：

1. 构建了单无人机圆周轨迹跟踪的 PyBullet RL 环境原型。
2. 设计了风、热上升、空气密度变化和粉尘效率损失的统一扰动参数接口。
3. 定义了 PID、Direct TD3、Residual TD3 和 Disturbance-aware Residual TD3 的对比框架。
4. 建立了 CSV/JSON 可追溯指标 schema 和 claim-evidence 证据账本。
5. 完成三训练种子 conservative retention pilot、30 秒主场景评估、泛化评估、validation checkpoint 选模、PID-FF warm-start 和结果合并，验证代码链路可训练、可评估、可追溯。

## 2 相关工作

Ma 等人在 Drones 2024 中提出基于 PID-DRL 的无人机风扰动抑制控制策略，说明传统控制和深度强化学习结合可改善风场中的轨迹跟踪表现。Liu 等人在 Sensors 2025 中研究了风扰环境下四旋翼轨迹跟踪的持续强化学习控制，强调策略在动态风场中的适应性。Ishihara 等人的 arXiv 预印本研究了 cascaded PID 四旋翼的残差强化学习抗风性能，是残差结构的重要相关工作。Zhang 等人的 arXiv 预印本提出 Cascaded TD3-PID 混合控制器，进一步说明 TD3 与 PID 的组合在风扰动轨迹跟踪中具有潜力。Al Tasim 和 Sun 的 arXiv 预印本则强调了显式风估计或风感知信息对小型四旋翼 RL 控制的重要性。

现有工作多集中于单一风扰动、端到端或级联混合控制。本文希望突出以下差异：第一，任务聚焦匀速圆周轨迹而非单纯悬停或点到点；第二，扰动设计包含风、热、密度和粉尘效率变化；第三，学习策略采用有界残差而非完全替代 PID；第四，扰动观测和安全门控作为明确消融变量；第五，所有实验数字必须追溯到统一 CSV/JSON 输出。

## 3 问题定义

考虑一架 `CF2X` 四旋翼无人机在 PyBullet 仿真环境中跟踪水平圆周参考轨迹。参考轨迹定义为：

```text
x_ref = R cos(omega t)
y_ref = R sin(omega t)
z_ref = h
omega = 2 pi / T
```

其中默认半径 `R = 0.3 m`，周期 `T = 10 s`，高度 `h = 1.0 m`。正式评估计划持续 `30 s`，覆盖三个完整周期。当前 Phase 1 smoke test 使用 `5 s` 快速验证代码链路。

控制目标是在扰动环境下最小化位置跟踪误差，同时限制姿态倾角、电机饱和、动作能耗和动作突变。主要评价指标包括全程位置 RMSE、稳定段 RMSE、最大位置误差、终端误差、最大高度误差、最大倾角、电机饱和率、控制能耗和动作平滑度。

## 4 方法

### 4.1 PID 基础控制器

基础控制器采用 `DSLPIDControl`。在当前 Phase 1 原型中，直接使用完整圆周参考速度会使默认 PID 在 `R = 0.3 m, T = 10 s` 下过激，因此环境暴露了显式参考整形参数：

```text
reference_velocity_gain = 0.0
pid_target_step_limit = 0.03 m
pid_xy_p_scale = 0.5
pid_xy_d_scale = 1.0
```

这组参数用于形成保守稳定的 Phase 1 基线。后续正式实验需要继续整定 PID，使其在目标周期下兼顾稳定性和跟踪精度。

### 4.2 Direct TD3

Direct TD3 作为端到端对照组，actor 输出四维归一化动作，直接映射到四个电机 RPM：

```text
rpm = hover_rpm + action * rpm_delta
```

所有 RPM 均被裁剪到合法范围。该方法用于衡量直接学习电机控制量的稳定性风险。

### 4.3 Residual TD3

Residual TD3 保留 PID 作为基础控制器。actor 输出五维残差：

```text
delta_ax, delta_ay, delta_az, delta_thrust_scale, delta_torque_scale
```

前三维被解释为加速度式参考修正，后两维用于温和缩放总推力和差分力矩。当前实现为 residual 路径使用独立 PID 控制器，避免同一个有状态 PID 在同一控制步中被调用两次。Phase 1 结果表明，当残差动作为零时，Residual TD3 与 PID 在标准环境中的输出和指标完全一致。

### 4.4 扰动感知残差 TD3

完整方法在 residual TD3 的状态中加入扰动观测：

```text
wind_x, wind_y, wind_z,
density_loss,
thermal_acc_z,
thrust_loss,
torque_loss
```

同时引入安全门控：

```text
residual = gate_disturbance * gate_saturation * residual
```

其中 `gate_disturbance` 在标准环境中接近零，使完整策略退回 PID 附近；`gate_saturation` 在电机接近上下限时抑制残差，降低饱和和异常动作风险。

### 4.5 输出与证据链

每次 rollout 输出：

- `trajectory.csv`
- `control.csv`
- `episode_summary.json`

汇总脚本输出：

- `summary_metrics.csv`
- `summary_metrics_aggregate.csv`

论文主张由 `experiments/circular_tracking/analysis/claim_evidence_ledger.csv` 绑定到具体实验、控制器、场景、随机种子和指标。

## 5 实验设计

主实验计划包含五类控制器：

1. PID
2. PID-FF，如果解析扰动前馈被完整实现
3. Direct TD3
4. Residual TD3
5. Disturbance-aware Residual TD3

主场景为：

```text
standard, wind, thermal, dust, compound
```

`unseen` 只作为泛化测试，不进入主实验均值表。每个控制器和场景至少使用 `0, 1, 2` 三个随机种子。正式论文结果必须报告 `mean ± std` 和失败率。

## 6 当前结果

当前结果分为六类：实现正确性 smoke test、早期 TD3 短训诊断、扰动力施加点修复后的全场景验收、三种子 5000 步 fixed-physics pilot、PID-FF warm-start 追加诊断、以及 warm-start retention 加 checkpoint 选模的保守改进实验。正文中的性能判断以修复后的 30 秒多种子结果为准；修复前结果只作为 bug 发现和训练链路诊断材料。

### 6.1 零残差一致性

5 秒 Phase 1 smoke test 显示，标准场景中 PID 与零动作 Residual TD3 的输出完全一致：

| 控制器 | 场景 | 时长 (s) | 位置 RMSE (m) | 最大倾角 (rad) | 是否失败 |
|---|---:|---:|---:|---:|---|
| PID | standard | 5 | 0.2905 | 0.0228 | false |
| Residual TD3，零动作 | standard | 5 | 0.2905 | 0.0228 | false |

12 秒标准环境 smoke test 同样保持一致：

| 控制器 | 场景 | 时长 (s) | 位置 RMSE (m) | 稳定段 RMSE (m) | 最大倾角 (rad) | 是否失败 |
|---|---:|---:|---:|---:|---:|---|
| PID | standard | 12 | 0.3885 | 0.3932 | 0.0290 | false |
| Residual TD3，零动作 | standard | 12 | 0.3885 | 0.3932 | 0.0290 | false |

该结果说明残差包装在零动作时没有破坏 PID 基线，是后续学习补偿实验的必要前提。

### 6.2 安全门控修正

早期实现中，完整 disturbance-aware residual TD3 只对推力和力矩缩放残差使用安全门控，加速度残差仍会在 standard 场景下生效。该问题已经修正：安全门控现在作用于全部残差。修正后，2 秒标准场景中完整方法与 PID 的指标完全一致：

| 控制器 | 场景 | 时长 (s) | 位置 RMSE (m) | 最大倾角 (rad) | 是否失败 |
|---|---:|---:|---:|---:|---|
| PID | standard | 2 | 0.1534 | 0.0213 | false |
| Disturbance-aware Residual TD3 | standard | 2 | 0.1534 | 0.0213 | false |

这验证了安全门控的一个核心设计目标：无扰动时完整方法应自动退回 PID 附近。

### 6.3 TD3 训练链路与短训诊断

三类 TD3 控制器均完成了 Stable-Baselines3 TD3 训练 smoke，并保存 `model.zip`、`monitor.csv` 和 `config.json`：

```text
experiments/circular_tracking/results/td3_residual_paper/runs/direct_td3_smoke_seed0
experiments/circular_tracking/results/td3_residual_paper/runs/residual_td3_smoke_seed0
experiments/circular_tracking/results/td3_residual_paper/runs/disturbance_aware_residual_td3_smoke_seed0
```

进一步的 1000 步 seed-0 短训在 standard 场景下得到如下诊断结果：

| 控制器 | 时长 (s) | 位置 RMSE (m) | 最大倾角 (rad) | 是否失败 | 失败原因 |
|---|---:|---:|---:|---|---|
| PID | 5 | 0.2905 | 0.0228 | false |  |
| Residual TD3，1000 步短训 | 5 | 0.1860 | 1.1128 | true | tilt_limit |
| Disturbance-aware Residual TD3，1000 步短训 | 5 | 0.2905 | 0.0228 | false |  |
| Direct TD3，1000 步短训 | 5 | 0.0503 | 1.6978 | true | tilt_limit |

Direct TD3 和普通 Residual TD3 的 RMSE 数字看似较低，但它们是在早停前的短时间窗口内计算得到，不能解释为跟踪性能更好。更重要的事实是二者都触发 `tilt_limit`，说明短训或探索阶段存在明显安全风险。完整方法在 standard 场景中保持 PID 行为，是安全门控的预期效果；它还不能说明扰动补偿已经学会，因为 standard 场景下 gate 抑制了残差动作。

![短训轨迹图](../../experiments/circular_tracking/results/td3_residual_paper/figures/short_seed0_standard/figure3_trajectory_xy_smoke.png)

![短训误差曲线](../../experiments/circular_tracking/results/td3_residual_paper/figures/short_seed0_standard/figure4_position_error_smoke.png)

![短训指标柱状图](../../experiments/circular_tracking/results/td3_residual_paper/figures/short_seed0_standard/figure5_metric_bars_smoke.png)

### 6.4 扰动力施加点修正与全场景验收

执行过程中发现一个关键物理实现问题：扰动外力使用 `WORLD_FRAME` 施加时，早期代码把 `posObj` 写成 `[0,0,0]`。在 PyBullet 中这代表世界原点而不是无人机质心，会引入非物理外力矩，导致风、热和复合扰动场景早期触发 `tilt_limit`。修正后，扰动力被施加在当前无人机 base position。

修复后的 5 秒 seed-0 全场景检查位于：

```text
experiments/circular_tracking/results/td3_residual_paper/eval_disturbance_force_point_fix_seed0_5s
```

PID、PID-FF、零动作 Residual TD3 和零动作 Disturbance-aware Residual TD3 在 `standard/wind/thermal/dust/compound/unseen` 中均不再出现早期倾角失效。这说明旧的 wind/thermal/compound 失败不能作为控制器结论，只能作为物理实现 bug 的诊断证据。

### 6.5 三种子 5000 步 fixed-physics pilot

修复外力施加点后，重新运行三种子训练与 30 秒评估：

```text
run = experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s
seeds = 0, 1, 2
TD3 train timesteps = 5000
training scenario_set = train
evaluation duration = 30 s
scenarios = standard, wind, thermal, dust, compound
```

所有 12 个 TD3 训练目录均保存了 `model.zip`、`config.json`、`monitor.csv` 和 `progress.csv`。评估目录包含 90 个 rollout 的 `trajectory.csv`、`control.csv`、`episode_summary.json`，以及 `summary_metrics.csv` 和 `summary_metrics_aggregate.csv`。

关键聚合结果如下：

| 控制器 | standard 失败率 | standard RMSE (m) | wind 失败率 | wind RMSE (m) | dust 失败率 | compound 失败率 | compound RMSE (m) |
|---|---:|---:|---:|---:|---:|---:|---:|
| PID | 0.00 | 0.3607 | 0.33 | 0.8425 | 0.00 | 0.33 | 0.8028 |
| PID-FF | 0.00 | 0.3691 | 0.00 | 0.3738 | 0.00 | 0.00 | 0.4731 |
| Direct TD3 | 1.00 | 0.0154 | 1.00 | 0.0194 | 1.00 | 1.00 | 0.0197 |
| Residual TD3 | 0.33 | 0.8569 | 0.33 | 1.3638 | 0.33 | 0.33 | 1.1803 |
| Disturbance-aware Residual TD3 | 0.00 | 0.3607 | 0.33 | 1.1501 | 0.00 | 0.67 | 0.9669 |
| No-gate DA-Residual TD3 | 0.33 | 0.6518 | 0.33 | 0.9843 | 0.00 | 0.33 | 1.0746 |

Direct TD3 在所有主场景中均以 `tilt_limit` 失败，因此其极低 RMSE 只是早停前短窗口的假象。Residual TD3 和无门控残差控制虽然保留 PID 底座，但训练后的残差仍会破坏标准场景稳定性。完整门控方法在 standard 中与 PID 完全一致，在 dust 和 thermal 中保持 0 失败率；这支持“安全门控是必要安全机制”的主张。

不过，当前 TD3 策略并未学到优于解析 PID-FF 的扰动补偿。在 wind 和 compound 中，PID-FF 同时具有更低失败率和更低 RMSE；完整方法在 compound 中失败率达到 0.67。因此，本 pilot 不支持“扰动感知残差 TD3 已经优于 PID/PID-FF”的强结论。

修复版图表位于：

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_5000td3_30s/figures
```

进一步的 gate/action 诊断来自 `diagnostic_summary_aggregate.csv`。在 standard 场景中，Disturbance-aware Residual TD3 的 actor 原始动作并非零，但 `mean_gate = 0.0`，因此残差被完全抑制，最终指标与 PID 一致。No-gate 版本在同一场景中 `action_smoothness_mean = 0.1936`，并有 1/3 seed 失败；完整门控版本在 dust 和 thermal 中也保持 0 失败率和更低动作突变。这说明安全门控的主要贡献是抑制无扰动或弱扰动下的不必要学习动作，而不是直接提升复合扰动跟踪精度。

为补齐训练验证链路，本文还在 validation seeds `100,101,102` 上评估了 5000 步 final models，并输出 `validation_summary.csv`、`validation_model_scores.csv` 和 `selected_models.json`。验证集结果与测试集一致：Direct TD3 全部失败；Residual TD3 的最佳 seed 可以降低失败率，但稳态 RMSE 仍高；Disturbance-aware Residual TD3 的最佳 seed 具有较低 RMSE，但仍有失败样本。因此，验证集选模可以减少随机种子偶然性，却不能改变当前训练预算下 TD3 不及 PID-FF 的结论。

### 6.6 PID-FF warm-start 追加实验

为了检验“TD3 是否只是初始化太差”，本文加入了一个 disturbance-aware residual actor 的 PID-FF imitation warm-start。训练脚本先从 `feedforward_residual_action()` 生成 4096 个模仿样本，进行 10 个监督 epoch，再继续 5000 步 TD3 微调。监督模仿损失从 0.05537 降至 0.00054，说明 actor 能拟合 PID-FF 启发的残差目标。

三组 30 秒测试分别评估 warm-start 后未微调模型、5000 步 TD3 final model 和 validation-selected 4000-step checkpoint：

| 控制器/模型 | wind 失败率 | wind 稳定段 RMSE (m) | compound 失败率 | compound 稳定段 RMSE (m) |
|---|---:|---:|---:|---:|
| PID | 0.33 | 0.9970 | 0.33 | 0.9537 |
| PID-FF | 0.00 | 0.3545 | 0.00 | 0.4838 |
| DA-Residual，warm-start imitation | 0.33 | 0.8983 | 0.00 | 0.5990 |
| DA-Residual，warm-start + 5000 步 TD3 final | 0.33 | 1.3744 | 0.67 | 1.1741 |
| DA-Residual，validation-selected 4000-step checkpoint | 0.33 | 1.3204 | 0.67 | 1.1197 |

结果显示，PID-FF imitation warm-start 能把复合扰动下的失败率降到 0，并相对 plain PID 降低 compound 稳定段 RMSE，但仍没有超过 PID-FF。更重要的是，随后的 TD3 微调反而破坏了 wind 和 compound 表现；即便使用 validation seeds `100,101,102` 选出的 4000-step checkpoint，测试集中仍有 1/3 wind 失败和 2/3 compound 失败。因此，后续改进不应只是延长训练，而应在 fine-tuning 阶段加入保持 warm-start 行为的正则、课程学习或更保守的残差更新策略。

### 6.7 Warm-start retention 与 checkpoint 选模

朴素 warm-start 的主要问题不是 actor 无法学习 PID-FF 残差，而是 TD3 微调很快偏离该初始化。为此，本文进一步加入三个保守设置：第一，将学习率降至 `1e-4`，将探索噪声降至 `0.02`；第二，在 TD3 微调过程中周期性对 warm-start 数据集做监督保持更新；第三，在非零扰动场景中设置 `residual_gate_min = 0.8`，避免安全门控过度压制 PID-FF 启发的补偿动作。该设置仍保留标准场景 `gate = 0`，因此无扰动时不会改变 PID 输出。

第一轮训练目录为：

```text
experiments/circular_tracking/results/td3_residual_paper/warm_start_retain_gate08_4096x10_seed0
```

在 validation seeds `100,101,102` 上同时评估 warm-start、final model 和每 1000 步 checkpoint 后，选择分数最低的是 1000-step checkpoint，而不是最终模型。该候选的 validation failure_rate 为 0，平均稳态 RMSE 为 0.5611 m；warm-start 模型本身也接近该结果，说明较晚 TD3 更新仍有退化趋势。

随后使用同一训练协议补充 training seeds `1,2`，并对三个训练种子统一进行 validation checkpoint 选模。三个训练种子的最佳候选分别为：seed0 的 1000-step checkpoint、seed1 的 warm-start 模型、seed2 的 final model。三者 validation failure_rate 均为 0，对应平均稳态 RMSE 为 0.5611 m、0.5404 m 和 0.5196 m。

三训练种子合并后的测试集 30 秒评估结果如下。DA-Residual 聚合包含 `3` 个训练种子乘以 `3` 个测试扰动种子，共 `9` 个 rollout；PID 和 PID-FF 是固定基线，仅统计 `3` 个测试扰动种子。

| 控制器/模型 | standard 失败率 | standard 稳态 RMSE (m) | wind 失败率 | wind 稳态 RMSE (m) | thermal 稳态 RMSE (m) | dust 稳态 RMSE (m) | compound 失败率 | compound 稳态 RMSE (m) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PID | 0.00 | 0.3458 | 0.33 | 0.9970 | 0.3495 | 0.3566 | 0.33 | 0.9537 |
| PID-FF | 0.00 | 0.3551 | 0.00 | 0.3545 | 0.4084 | 0.3441 | 0.00 | 0.4838 |
| DA-Residual，validation-selected multiseed | 0.00 | 0.3458 | 0.11 | 0.6914 | 0.4403 | 0.4239 | 0.11 | 0.6821 |

该结果相对前一轮负结果有实质改善：保守选模在 standard 中仍完全保持 PID，在 wind 和 compound 中把普通 PID 的 1/3 失败率降低到 1/9，并将稳态 RMSE 分别从 0.9970 m 降至 0.6914 m、从 0.9537 m 降至 0.6821 m。它也满足了“完整方法在 compound 中优于 PID 和普通 Residual TD3、failure_rate 低于 Direct TD3”的最低 pilot 验收口径。

但边界同样明确。该策略在 thermal 和 dust 中比普通 PID 更差，在所有扰动场景中仍不如 PID-FF；并且 seed2 的 selected final model 在测试集 wind 和 compound 中各出现一次失败。这说明 validation 选模不能完全消除训练种子风险。因此，这一节应解释为“保守 warm-start 选模证明了残差 TD3 路线可以平均超过普通 PID 的部分扰动场景”，而不是“TD3 已经超过解析前馈控制”。

为了进一步隔离扰动观测的作用，本文使用同一 conservative retention 协议补充训练了无扰动观测的 `residual_td3`。该消融保留 PID 底座、五维残差动作、PID-FF imitation warm-start、retention 更新、checkpoint 候选和 validation seeds，仅从策略观测中移除风、热、密度和效率损失等扰动量。三训练种子的 selected candidates 分别为 seed0 的 warm-start、seed1 的 final model 和 seed2 的 1000-step checkpoint，三者 validation failure_rate 均为 0。

Matched 消融主测试结果如下：

| 场景 | Residual TD3 失败率 | Residual TD3 稳态 RMSE (m) | DA-Residual 失败率 | DA-Residual 稳态 RMSE (m) |
|---|---:|---:|---:|---:|
| standard | 0.000 | 0.3788 | 0.000 | 0.3458 |
| wind | 0.111 | 0.7528 | 0.111 | 0.6914 |
| thermal | 0.000 | 0.3865 | 0.000 | 0.4403 |
| dust | 0.000 | 0.4293 | 0.000 | 0.4239 |
| compound | 0.111 | 0.7580 | 0.111 | 0.6821 |

该结果支持一个更窄但更干净的 C2 结论：扰动观测在主测试 wind 和 compound 中降低了稳态跟踪误差，但没有降低失败率，也没有改善所有扰动类型。Thermal 场景下 DA-Residual 反而更差，dust 场景只有很小差异。因此，扰动观测的作用应被表述为“对风/复合扰动补偿有帮助”，而不是“普遍提升抗扰性能”。

另外，`residual_gate_min = 1.0` 作为敏感性检查也跑完了完整 5 场景评估。若仍使用 1000-step checkpoint，它同样保持 0 失败率，并将 wind 稳态 RMSE 改善至 0.6438 m，但 compound、thermal 和 dust 分别变为 0.5871 m、0.5845 m 和 0.4619 m。进一步在 gate=1.0 下重新做 validation 选模后，最佳候选变成 warm-start 模型本身；其测试集 wind、thermal、dust 和 compound 稳态 RMSE 分别为 0.6125 m、0.4642 m、0.4323 m 和 0.6015 m。该结果说明 gate=1.0 更偏向直接部署 PID-FF imitation 行为，能改善 wind，但 compound 不如 gate=0.8 的 selected checkpoint。因此，主文采用 `0.8` 作为主设置，将 `1.0` 作为门控强度敏感性探针。

### 6.8 泛化 pilot

复用 5000 步模型和后续 conservative selected models，在不重新训练的情况下评估：

```text
radius = 0.4, period = 8, scenarios = compound/unseen
radius = 0.5, period = 12, scenarios = compound/unseen
```

结果目录：

```text
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_generalization_r04_t8_5000td3
experiments/circular_tracking/results/td3_residual_paper/pilot_force_point_fix_generalization_r05_t12_5000td3
```

三训练种子 conservative selected models 的泛化聚合显示：在 `R=0.4,T=8` 的 compound 中，DA-Residual failure_rate 为 0.111、稳态 RMSE 为 0.7511 m，优于普通 PID 的 0.333 和 0.9781 m，但弱于 PID-FF 的 0 和 0.5864 m；在 `R=0.5,T=12` 的 compound 中，DA-Residual failure_rate 为 0.111、稳态 RMSE 为 0.9039 m，同样优于普通 PID 但弱于 PID-FF。unseen 场景仍明显失败：两个半径/周期下 DA-Residual failure_rate 均为 0.778，稳态 RMSE 分别为 1.2079 m 和 1.3708 m，均弱于 PID-FF。该结果说明当前 TD3 模型对训练分布附近的 compound 扰动有一定迁移能力，但尚不具备可靠外推泛化能力，后续需要课程学习、扰动强度随机化或显式扰动估计器。

Matched residual_td3 泛化消融进一步确认了这一边界。在 compound 泛化中，DA-Residual 对 `R=0.4,T=8` 和 `R=0.5,T=12` 的稳态 RMSE 分别为 0.7511 m 和 0.9039 m，低于无扰动观测 residual_td3 的 0.8644 m 和 0.9580 m，失败率均同为 0.111。但在 unseen 场景中结果反向：residual_td3 的 failure_rate 为 0.667，低于 DA-Residual 的 0.778；两个半径/周期下 residual_td3 的稳态 RMSE 为 0.9992 m 和 0.9387 m，也低于 DA-Residual 的 1.2079 m 和 1.3708 m。这说明显式扰动观测在接近建模分布的复合扰动中有帮助，但当前策略会在更强外推扰动下过度依赖这些观测。

## 7 讨论

当前工作已经从“计划”推进到“可训练、可评估、可画图”的小论文原型，并完成了修复后 30 秒、三种子、多场景 pilot。结果最重要的价值不是证明 TD3 已经优于传统控制，而是把几个机制的边界暴露出来：Direct TD3 作为端到端电机控制在当前训练预算下非常不安全；普通 residual TD3 虽然保留 PID 底座，但训练后的残差仍可能破坏标准环境稳定性；安全门控能让完整方法在无扰动标准环境中退回 PID，并在 dust/thermal 中保持较好稳定性。

扰动外力施加点 bug 也说明，强化学习控制实验必须先做物理层验证。修复前 wind/thermal/compound 的早期 `tilt_limit` 失效来自非物理外力矩，而不是控制器本身。修复后，PID 和 PID-FF 可以在长时扰动评估中形成可解释基线，TD3 的失败也更有诊断意义。

最新 warm-start retention 实验把结论向前推进了一步。朴素 TD3 微调会破坏 PID-FF imitation，但较低学习率、较低探索噪声、保留监督更新、checkpoint 选模和 `residual_gate_min = 0.8` 可以保留一部分初始化收益。三训练种子合并后，选模后的策略在 wind 和 compound 中平均超过普通 PID，并降低失败率。这说明扰动感知残差 TD3 并非只能作为负结果；在合适约束下，它可以形成比固定 PID 更强的扰动补偿。

不过，PID-FF 仍是当前最强基线。它在 wind 和 compound 中的误差更低，在 thermal/dust 中也更稳。换言之，当前策略学到的是“有用但尚不充分”的残差补偿：它能改善普通 PID 的部分扰动场景，却还没有超过一个简单解析前馈规则。这个边界对论文反而很重要，因为它避免了用弱 PID 基线制造虚假优势，也说明后续训练必须以 PID-FF 为强参照。

Matched residual_td3 消融使扰动观测的作用更清楚：在同样 warm-start retention 和 validation 选模下，显式扰动观测确实降低了 wind/compound 及 compound 半径/周期迁移的稳态误差；但它没有降低失败率，也没有改善 thermal 或 unseen。一个合理解释是，当前扰动观测是仿真中的 oracle 参数，策略可以利用它拟合训练分布附近的补偿，却未学到足够稳健的外推规律。后续若要把 C2 从“主分布有效”推进到“泛化有效”，需要在训练中加入更强扰动随机化、观测噪声、课程学习或独立扰动估计器，而不是只增加观测维度。

泛化结果同样限制了结论外推。三训练种子合并后，保守选模策略在 unseen 场景下仍有 7/9 rollout 失败，且弱于 PID-FF。当前扰动观测是仿真 oracle 信息，不是机载估计器输出；未来若迁移到真实飞行，还需要加入扰动估计、传感器噪声和域随机化。因此，本文不能声称已经完成真实部署验证。

PyBullet 在 Windows 中文路径下加载 URDF 会失败，需要 ASCII 资产镜像；该问题已经在环境类中绕过。默认 DSL PID 对 `R = 0.3 m, T = 10 s` 圆轨迹仍偏保守，标准场景稳定但跟踪误差不小。后续若希望把论文从诊断型原型推进到正结果论文，应同时优化 PID/PID-FF 公平基线和 TD3 训练流程，避免用弱基线制造虚假优势。

Simulink 残差 RL-v1/RL-v2 工作可作为方法来源和背景材料，但其数值不应与 PyBullet TD3 主实验直接混表比较。两者平台、动力学实现和扰动模型不同，直接数值比较会削弱论文可信度。

## 8 结论

本文构建了面向复合扰动圆周轨迹跟踪的扰动感知残差 TD3 研究框架，并完成了 PyBullet 环境、输出 schema、证据账本、训练脚本、warm-start retention、模型加载评估脚本、validation checkpoint 选模、聚合脚本和图表脚本。修复扰动外力施加点后，三种子 5000 步 pilot 表明：零动作残差包装能够保持 PID 行为不变；安全门控使完整方法在标准环境中不劣化 PID；Direct TD3 在当前训练预算下全部早停失败；普通残差和无门控残差仍可能破坏稳定性。进一步的三训练种子 conservative retention 实验显示，validation 选模后的 DA-Residual 可以在 wind 和 compound 中平均优于普通 PID，并降低失败率；matched no-disturbance-observation 消融进一步表明，扰动观测能降低主分布 wind/compound 和 compound 迁移的稳态误差。与此同时，PID-FF 仍是当前最强扰动基线，thermal/dust 表现和 unseen 泛化仍未达标。因此，本文当前结论是有边界的：门控残差结构和保守 warm-start 选模能把 TD3 从不安全探索推进到可用的部分扰动补偿，但尚不能证明其全面优于解析 PID-FF。后续工作应围绕 matched safety-gate ablation、课程学习、更强扰动估计和更长训练继续推进。

## 参考文献草稿

1. Ma, Q., Wu, Y., Shoukat, M. U., Yan, Y., Wang, J., Yang, L., Yan, F., and Yan, L. Deep Reinforcement Learning-Based Wind Disturbance Rejection Control Strategy for UAV. Drones, 2024, 8(11), 632.
2. Liu, Y., Hao, L., Wang, S., and Wang, X. Trajectory Tracking Controller for Quadrotor by Continual Reinforcement Learning in Wind-Disturbed Environment. Sensors, 2025, 25(16), 4895.
3. Ishihara, Y., Hazama, Y., Suzuki, K., Yokono, J. J., Sabe, K., and Kawamoto, K. Improving Wind Resistance Performance of Cascaded PID Controlled Quadcopters using Residual Reinforcement Learning. arXiv:2308.01648, 2023.
4. Zhang, Y., Chai, S., Zhang, Y., Huang, D., and Ge, Q. Cascaded TD3-PID Hybrid Controller for Quadrotor Trajectory Tracking in Wind Disturbance Environments. arXiv:2604.13505, 2026.
5. Al Tasim, A., and Sun, W. Wind-Aware Reinforcement Learning Control of a Small Quadrotor Using Learned Onboard Wind Estimation in Simulated Atmospheric Turbulence. arXiv:2607.01528, 2026.
