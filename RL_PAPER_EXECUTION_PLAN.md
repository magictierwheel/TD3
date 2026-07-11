# RL Paper Execution Plan

> **Status: REVISED RESEARCH PLAN — 2026-07-10**
>
> 本计划已经取代旧的“oracle 扰动观测 + PID-FF imitation warm-start + gate-min”路线。
> 旧代码、旧模型和旧结果只保留为失败诊断与研究演化记录，不得进入新论文主结果表。

## 0. 接手者先读

新论文只研究三个核心控制器：

```text
1. Conventional PID
2. End-to-end Direct TD3
3. PID-based Residual TD3
```

三者只获得相同的可测飞行状态和参考轨迹，均不得获得真实风速、空气密度、热流、推力效率、力矩效率、场景名称或任何等价的扰动真值。

一句话研究问题：

> 在扰动不可直接观测时，以 PID 为稳定先验的残差 TD3，能否比端到端 TD3 更安全、更省样本，并在随机复合扰动下改善普通 PID 的圆周轨迹跟踪？

详细研究设计：

```text
.research/design_brief.md
docs/superpowers/specs/2026-07-10-hidden-disturbance-td3-paper-redesign.md
```

逐任务实现计划：

```text
docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md
```

## 1. 不可违反的研究边界

### 1.1 主实验禁止项

新方法和主实验禁止：

- 把仿真器真实扰动参数加入 policy observation。
- 把 scenario 名称、扰动强弱标签或随机种子加入 policy observation。
- 使用真实扰动幅值计算 safety gate。
- 使用 PID-FF、MPC 或其他解析扰动补偿生成 imitation targets。
- 使用旧 PID-FF warm-start 模型初始化新 actor。
- 针对每个训练 seed 分别挑选最有利 checkpoint。
- 查看测试集后继续改 gate、reward、训练预算或超参数。
- 把失败前短轨迹的低 RMSE 解读为更好的跟踪。
- 把重复使用的三个扰动 seed 当成九个独立样本。

### 1.2 PID 是否使用扰动观测器

不使用。普通 PID 只通过位置、速度、姿态和角速度反馈以及自身积分状态抵抗扰动。

若未来加入 disturbance observer、ADRC、PID-FF 或 MPC，它必须作为明确的第四个强基线，不能偷偷并入“传统 PID”。当前小论文不以击败这些方法为主张。

### 1.3 允许的信息

所有控制器可使用：

```text
reference position and velocity
position and velocity
attitude and angular velocity
tracking error
the same sensor-noise model
```

两种 TD3 使用相同长度的可测状态、误差和历史动作窗口，以便从状态变化中隐式推断未知扰动。两者还共同读取同一冻结 PID 在当前控制时刻输出的 motor command；它是上述非特权信息与普通 PID 记忆的确定函数，不是扰动真值。Direct 不得以此改变其完整 RPM 动作映射，Residual 才以它作为残差动作中心。

## 2. 为什么旧路线失败

后续智能体必须理解这些失败原因，不能只把旧结果当成“训练步数不够”。

### 2.1 终止惩罚没有进入 terminal reward

旧环境在 `_computeReward()` 中读取 `_failure_reason`，但 `BaseAviary.step()` 先计算 reward，随后才调用 `_computeTerminated()` 设置失败原因。episode 在该步结束，因此 `-50` 终止惩罚没有反馈给 TD3。

结论：旧 TD3 模型是在与论文描述不一致的奖励下训练的。任何新训练必须先通过 terminal-reward regression test。

### 2.2 训练 episode 只覆盖半圈

旧配置：

```text
episode duration = 5 s
reference period = 10 s
```

每次训练只看到圆周前半段，然后回到同一初始相位。策略没有学习完整周期、跨周期误差积累或长期稳定性。

新配置必须使用 20 秒 episode，覆盖两个完整周期；也可以在未来增加随机初始相位，但不能再次只训练半圈。

### 2.3 训练预算不是收敛实验

旧配置每个模型只有 5000 steps，其中前 1000 steps 不更新网络，总计约 20 个 episode。五种场景平均只有约四个 episode，无法支撑 TD3 critic 学习。

旧“Direct TD3 不安全”只能表述为：在旧动作映射、错误终止奖励和 5000-step 预算下全部失败。不能外推成 TD3 算法普遍不安全。

### 2.4 PID nominal baseline 没有真正跟踪圆周

旧 PID 关闭完整参考速度、限制目标步长并降低水平增益。标准场景稳态 RMSE 约 0.346 m，而圆半径仅 0.3 m。原始轨迹复核显示实际路径长度远低于三圈参考长度，并存在巨大相位滞后。

结论：Residual TD3 当时不只在补偿扰动，还在补偿一个不合格的圆周跟踪底座。新 PID 必须先通过 nominal acceptance，随后冻结。

### 2.5 “无扰动观测”消融并不 matched

旧 `disturbance_aware_residual_td3` 使用 disturbance/saturation gate，旧 `residual_td3` 固定 `gate=1.0`。二者同时改变了 policy observation 和 gate，因此不能把差异单独归因于扰动观测。

旧 C2 还存在训练种子不一致：聚合优势主要来自一个训练 seed，另外两个 seed 的方向相反。

### 2.6 Oracle 信息消除了 RL 的必要性

旧 actor 直接获得仿真器真实风、热、密度和效率损失；PID-FF 又使用同一动力学模型生成解析补偿，并作为 actor imitation teacher。TD3 实际上在有限数据下近似一个已知控制律，随后微调还破坏了该初始化。

当扰动和模型都已知时，PID-FF/MPC 本来就更合适。新论文必须让扰动保持隐藏，让 RL 学习普通反馈未能消除的未知残差。

### 2.7 测试集被反复用于开发

旧 seeds `0,1,2` 被多次用于比较 warm-start、retention、gate=0.8、gate=1.0 和 checkpoint，已经不再是未触碰测试集。

新实验固定：

```text
training seeds:   0-4
validation seeds: 100-109
test seeds:       200-219
unseen seeds:     300-319
unit-test seeds:  9000-9099
```

测试 seeds 200-219 在协议冻结前禁止打开。

所有可执行数值、公式、范围和阶段判定以
`experiments/circular_tracking/config/hidden_td3_protocol.json` 为机器可读唯一来源；
文档与 protocol 不一致时必须先停止并修正文档，不能由实现者自行解释。

### 2.8 早停指标和统计独立性处理错误

旧 `steady_position_rmse` 在 episode 不足一个周期时退化为失败前整段 RMSE，使越早失败的模型有时数字越小。旧聚合还把相同三个测试扰动在三个训练模型上的九次 rollout 当成普通独立样本。

新指标必须同时记录实际飞行时长、完成率、成功 episode RMSE 和 failure-penalized horizon error，并按 training seed 与 disturbance seed 分层统计。

### 2.9 旧图表不是论文级证据

旧主文主要包含 smoke 图；部分 combined 目录没有 trajectory，生成了空白轨迹图；柱状图缺少置信区间且混合早停 RMSE。新论文图必须从 revised result namespace 重新生成。

## 3. 新论文定位

推荐题目：

> 未知随机扰动下四旋翼圆周轨迹跟踪的残差 TD3：与 PID 和端到端 TD3 的对比研究

英文候选：

> Residual TD3 for Quadrotor Circular Tracking under Hidden Stochastic Disturbances: A Comparison with PID and End-to-End TD3

### 3.1 可证伪假设

- `H1`: PID 在未知扰动下保持一定反馈抗扰能力，但误差随扰动增强而增加。
- `H2`: 相同步数下 Direct TD3 的失败率和训练种子方差高于 Residual TD3。
- `H3`: Residual TD3 在 compound 中优于冻结 PID，并且不会破坏 standard 安全性。
- `H4`: 只依赖可测状态和执行器余量的 gate 能限制有害残差动作。
- `H5`: unseen 只用于描述外推边界，不预设泛化成功。

若 H3 在 50k 三种子阶段不成立，停止扩大训练预算，改写成负结果/诊断论文。

## 4. 三种控制器的严格定义

### 4.1 Conventional PID

```text
input  = reference + measured flight state
memory = ordinary PID integral state
output = 4 motor RPM commands
```

PID 不读取 disturbance truth，不使用 disturbance observer。PID 在 standard validation 上整定一次，达到 nominal acceptance 后冻结，RL 训练和测试期间不得再改。

### 4.2 Direct TD3

```text
input  = shared observable state/reference/error history + current frozen PID motor command
output = 4 bounded motor RPM commands
```

动作映射：

```text
rpm = clip(hover_rpm + action * direct_rpm_span, 0, max_rpm)
```

### 4.3 Residual TD3

```text
input  = shared observable history + current frozen PID motor command
output = 4 bounded motor RPM deltas
```

动作映射：

```text
rpm = clip(pid_rpm + gate * action * residual_rpm_limit, 0, max_rpm)
```

Residual actor 输出层零初始化，使训练开始时严格等于 PID。禁止 PID-FF imitation warm-start。

### 4.4 公平性要求

Direct 与 Residual TD3 必须共享：

```text
state/reference/error information
history length
network size unless action head requires a minimal difference
reward
optimizer and TD3 hyperparameters
training disturbance distribution
training steps
termination thresholds
motor bounds
validation and test disturbances
```

结构允许的差异只有：Direct 输出完整 motor command；Residual 输出 PID motor residual。两种 TD3 都读取相同的当前冻结 PID command，因此该非特权控制器派生特征不得造成 actor/critic 输入维度差异。

## 5. 观测与隐式扰动推断

不提供真实扰动后，瞬时状态可能不足以区分惯性、历史动作和持续外力。推荐给两种 TD3 相同的短历史窗口：

```text
current full measurable state
recent position/velocity tracking errors
recent applied motor commands
recent policy actions
reference phase and derivatives
current frozen PID motor command shared by both TD3 modes
```

第一版使用 4-8 个 control steps 的历史。单帧版本作为消融，不在第一阶段引入 RNN 或显式学习型扰动观测器。

## 6. Safety Gate

删除所有基于 disturbance magnitude、scenario 或 efficiency truth 的 gate。

主方法 gate 只允许依赖：

```text
tracking error
attitude and altitude safety margin
PID motor headroom
```

推荐形式：

```text
gate = error_gate * actuator_headroom_gate
```

`residual_td3_no_gate` 只作为消融。不能把 gate 本身解释为策略已经识别扰动。

## 7. 隐藏随机扰动设计

为保证论文聚焦，主实验使用四类场景：

| 场景 | 训练/主测试定义 |
|---|---|
| `standard` | 无扰动 |
| `random_wind` | 隐藏水平风，每 1-3 秒改变或使用有相关性的随机过程 |
| `actuator_loss` | 隐藏推力/力矩效率缓慢变化 |
| `compound` | random wind 与 actuator loss 同时存在 |

`unseen` 使用更大幅值或更快变化频率，只用于最终压力测试。

推荐第一版范围：

```text
train/main wind magnitude <= 1.5 m/s
train/main thrust/torque efficiency = 0.90-1.00
unseen wind magnitude <= 2.5 m/s
unseen thrust/torque efficiency = 0.80-0.90
```

扰动 truth 可以写入离线日志，但不能进入 controller observation、gate、reward 特权项或 model selection feature。

## 8. Reward 与终止

两种 TD3 使用同一 reward，只基于可测状态和实际 motor command：

```text
tracking position error
tracking velocity error
attitude/altitude safety
total motor energy
motor-command smoothness
terminal failure penalty
```

禁止对 Direct 使用 total action、对 Residual 使用 residual action 的不对称惩罚制造优势。主要能耗和平滑度应基于最终 applied RPM。

Reward 和 termination 必须调用同一个纯函数，从当前 state 计算 failure reason，保证 terminal penalty 在失败 transition 当步生效。

## 9. PID Nominal Acceptance

在任何 TD3 训练前，PID 必须在 `R=0.3 m, T=10 s, h=1.0 m` 的 standard 场景完成 30 秒评估，并满足：

```text
failure = false
steady_position_rmse < 0.10 m
path_length_ratio in [0.90, 1.10]
finite phase error and motor metrics
```

PID 只能使用 nominal validation 调参。冻结结果保存到：

```text
experiments/circular_tracking/config/hidden_pid_frozen.json
```

若 PID 未通过，本项目不得进入 TD3 训练阶段。

## 10. 分阶段训练预算

### Stage 0: 无训练验收

完成：

- terminal reward test。
- disturbance reproducibility/range test。
- observation privilege-leak test。
- PID nominal acceptance。
- zero residual equals PID test。
- Direct/Residual action bounds and common reward test。

### Stage A: 20k seed-0 go/no-go

```text
modes = direct_td3, residual_td3
training seed = 0
episode duration = 20 s
checkpoints = 5k, 10k, 20k
```

GO 条件：Residual 在 standard 中零失败且 success-only steady RMSE 不超过 PID 的 `1.10x`；并且在 validation compound 中，相对 PID 或 Direct 至少减少 1/10 次失败，或在失败数相同的情况下将 failure-penalized horizon error 降低至少 5%。否则停止，不扩大预算。

### Stage B: 50k three-seed direction pilot

```text
training seeds = 0,1,2
checkpoints = 20k, 50k
validation seeds = 100-109
```

选择一个全局 checkpoint budget，对所有 training seeds 一致使用。至少 2/3 training seeds 的 Residual 改善方向一致才通过。

“改善方向”固定表示：standard gate 通过，并且 compound 中同时相对 PID 和 Direct TD3 满足“至少少一次失败，或失败数相同且 failure-penalized error 至少降低 5%”。全局预算按 failure rate、failure-penalized horizon error、success-only RMSE、较小预算的固定词典序选择。

### Stage C: 100k five-seed paper run

只在 Stage B 通过后执行：

```text
training seeds = 0,1,2,3,4
global budget <= 100k unless validation learning curve still clearly improves
test seeds = 200-219
unseen seeds = 300-319
```

不默认执行 500k。只有 100k validation 曲线仍持续改善且机制证据一致时，才另行论证更大预算。

## 11. 评估矩阵

### 11.1 Main

```text
controllers = PID, Direct TD3, Residual TD3
scenarios = standard, random_wind, actuator_loss, compound
duration = 30 s
TD3 training seeds = 0-4
paired test disturbance seeds = 200-219
```

### 11.2 Ablation

```text
Residual TD3 gate vs no gate
single-frame vs short-history observation
zero-initial residual vs trained residual
20k vs 50k vs 100k sample efficiency
```

### 11.3 Generalization

```text
unseen stronger/faster disturbances
nominal geometry only: R=0.3,T=10
```

当前赶稿协议不运行 `R=0.4,T=8` 或 `R=0.5,T=12` 几何外推；对应 claim 必须标为 unsupported。Unseen 不参与训练、选模或超参数调整。

## 12. 指标与统计

### 12.1 Primary

```text
failure_rate
steady_position_rmse_success_only
failure_penalized_horizon_error
```

### 12.2 Secondary

```text
flight_time_sec
completion_rate
path_length_ratio
mean_phase_error
max_position_error
final_position_error
max_altitude_error
max_tilt_angle
rotor_saturation_rate
control_energy_from_applied_rpm
motor_command_smoothness
```

### 12.3 Aggregation

先在每个 training seed 内对 paired disturbance seeds 聚合，再跨 training seeds 汇总。报告：

```text
num_training_seeds
num_disturbance_seeds
num_rollouts
mean or median
standard deviation
clustered/hierarchical 95% confidence interval
seed-level paired differences
```

不能只报告 pooled `mean ± std`。

## 13. Claim Acceptance

| Claim | 最低通过条件 |
|---|---|
| Residual 比 Direct 更安全/省样本 | 相同步数下 failure 更低或 learning curve 更快，至少 4/5 training seeds 同方向 |
| Residual 改善 PID compound tracking | failure 不增加且 paired primary error 降低，clustered CI 支持实际改善 |
| Standard 不退化 | failure=0，且相对 PID 的误差增幅不超过预注册容差 |
| Gate 有安全价值 | matched gate/no-gate ablation 降低 failure、危险姿态或饱和，而非只改变 raw actor smoothness |
| Unseen generalization | 只根据未触碰 unseen test 判定；失败则明确写失败 |

任何未通过项必须标为 rejected/unsupported，不得改 acceptance rule 迁就结果。

## 14. 新文件与结果边界

新实现：

```text
experiments/circular_tracking/rl_envs/disturbance_processes.py
experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py
experiments/circular_tracking/scripts/td3/tune_hidden_pid.py
experiments/circular_tracking/scripts/td3/train_hidden_td3.py
experiments/circular_tracking/scripts/td3/evaluate_hidden_td3.py
experiments/circular_tracking/scripts/td3/summarize_hidden_td3.py
tests/circular_tracking/
```

新结果：

```text
experiments/circular_tracking/results/hidden_disturbance_td3_paper/
```

新分析：

```text
experiments/circular_tracking/analysis/hidden_td3_metric_schema.md
experiments/circular_tracking/analysis/hidden_td3_claim_evidence_ledger.csv
experiments/circular_tracking/analysis/hidden_td3_completion_audit.md
```

旧实现和结果保持不动：

```text
experiments/circular_tracking/rl_envs/circular_residual_td3_env.py
experiments/circular_tracking/results/td3_residual_paper/
experiments/circular_tracking/analysis/claim_evidence_ledger.csv
docs/paper/results.md
```

它们统一标记为 legacy oracle/PID-FF pilot。

## 15. 论文重写

新写作工作区：

```text
docs/paper/revised_outline.md
docs/paper/revised_method.md
docs/paper/revised_results.md
```

最终再覆盖 `docs/paper/manuscript.md` 和 `manuscript.docx`。在新证据完成前，当前 manuscript 是 legacy draft，不是投稿稿。

新正文按以下顺序：

1. 未知随机扰动与公平信息边界。
2. PID、Direct TD3、Residual TD3 的统一动作/观测定义。
3. PID residual prior 的机制假设。
4. hidden time-varying disturbance protocol。
5. equal-budget learning curves。
6. failure-first main results。
7. gate/history/sample-budget ablations。
8. unseen 边界与负结果。

禁止在正文继续使用“今晚、Phase 1 smoke、当前准备跑、结果目录如下”等执行日志语言。

## 16. 图表计划

- Figure 1: 三控制器与隐藏扰动信息边界。
- Figure 2: time-varying hidden disturbance examples。
- Figure 3: equal-budget learning curves with training-seed uncertainty。
- Figure 4: compound full-horizon trajectory and error-time comparison。
- Figure 5: failure rate and paired primary metrics with 95% CI。
- Figure 6: gate/history/sample-budget ablation。
- Table 1: controller information/action contract。
- Table 2: disturbance distributions and seed partitions。
- Table 3: main hierarchical metrics。
- Table 4: unseen/generalization results。

任何空白图、smoke-only 图或无误差条 pooled bar chart 均不得进入投稿稿。

## 17. 执行顺序

```text
Phase 0  Freeze design and legacy boundary
Phase 1  Write failing tests
Phase 2  Implement hidden disturbance process and fair environment
Phase 3  Fix reward and pass environment invariants
Phase 4  Tune/freeze nominal PID
Phase 5  Stage A 20k go/no-go
Phase 6  Stage B 50k three-seed pilot
Phase 7  Stage C 100k five-seed run only after GO
Phase 8  Held-out paired test and unseen evaluation
Phase 9  Hierarchical statistics and figures
Phase 10 Rewrite manuscript and audit evidence
```

每个 Phase 的测试、文件和命令详见 implementation plan。禁止跳过 Phase 1-4 直接训练。

## 18. 接手智能体的第一步

如果用户说“继续新论文实验”，执行顺序是：

1. 读本文件。
2. 读 `.research/design_brief.md`。
3. 读 `docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md`。
4. 检查 `experiments/circular_tracking/results/hidden_disturbance_td3_paper/stage_status.md`，确认当前 Phase。
5. 从第一个未完成 checkbox 开始，不重用旧模型。

如果新环境和测试尚未实现，第一项代码工作必须是 terminal reward regression test 和 hidden-information boundary test；不是启动 50k 或 100k 训练。

## 19. 最终成文判断

新论文最有希望成立的结论是：

> 在相同可测状态、相同隐藏随机扰动和相同训练预算下，PID 稳定先验是否能够让 Residual TD3 比端到端 Direct TD3 更安全、更省样本，并补偿普通 PID 未能消除的动态误差。

只有 revised evidence 通过预注册 acceptance 后才能写成正结果。若不通过，则诚实写成残差结构未产生稳定收益的诊断研究。无论结果方向如何，都不得回到 oracle disturbance、PID-FF imitation 或测试集挑选路线来制造优势。
