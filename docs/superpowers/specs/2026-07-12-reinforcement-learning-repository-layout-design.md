# 《强化学习》项目仓库布局设计

日期：2026-07-12
状态：用户已确认设计，尚未开始实施

## 1. 目标

将当前分散、重复且混合了 Git worktree、历史协议、训练产物和不同仿真平台的工作区，整理成一个名称和边界明确的《强化学习》项目仓库。

最终仓库必须同时满足：

- 根目录保留 `README.md`、`AGENTS.md`、交接、状态和路线图等入口文件；
- MATLAB/Simulink 与 PyBullet 是并列的正式研究主线；
- TD3 只是 PyBullet 研究线中的算法，不再作为整个项目名称；
- 当前研究和历史协议分开；
- 当前 PyBullet 主线按预检、Stage A、Stage B、Stage C 和最终评估排列；
- 通用代码只保留一份，阶段目录不复制训练实现；
- 本地可以保留 Replay Buffer、模型、日志和原始轨迹，但 GitHub 不上传大文件；
- 删除不再需要的悬停复现和定点控制研究，并清理全部悬空引用；
- GitHub 仓库根目录对应唯一正式项目 worktree，不再镜像整个本地工作区。

## 2. 已确认的核心决策

### 2.1 项目名称

项目的逻辑名称为：

```text
强化学习
```

当前 GitHub 仓库名 `TD3` 是历史命名，不再作为目录设计依据。是否重命名 GitHub 仓库是后续独立操作，不阻塞本次文件布局整理。

### 2.2 两条正式研究主线

仅保留两条核心研究线：

1. MATLAB/Simulink 圆周抗扰与残差强化学习；
2. PyBullet 圆周跟踪与 PID-based Residual TD3。

MATLAB/Simulink 不是 PyBullet 的废弃协议，也不放入 PyBullet 的 `archive/`。两条研究线在 `experiments/circular_tracking/` 下并列。

### 2.3 双层分类

PyBullet 内容按两层分类：

1. 第一层区分当前主线和历史路线；
2. 当前主线内部再按训练阶段排列。

协议版本、训练 Gate、Smoke 和 Stage A/B/C 不再混排在同一目录层级。

### 2.4 退役研究

以下研究从正式仓库中完整移除：

```text
experiments/hover_rl_reproduction/
experiments/hover_fixed_point/
```

删除必须同时处理兼容入口、Docker 入口、可视化工具、报告生成器和文档引用，不能留下坏导入或失效路径。

## 3. 仓库与本地工作区的边界

GitHub 仓库根目录必须对应一个唯一正式 worktree，而不是本地父目录 `强化学习/` 中所有 worktree 的镜像。

本地允许采用：

```text
强化学习/
├─ project/                    # 唯一正式仓库，与 GitHub 根目录对应
├─ _worktrees/                 # impl、task 等临时 Git worktree
├─ _pytest_tmp/                # pytest --basetemp 统一出口
├─ _local_artifacts/           # 可选的集中式大文件存储
└─ research_papers/            # 本地论文库，不上传到代码仓库
```

物理目录重命名不属于第一步。迁移可以先在当前 `wt-gpd/integration` worktree 内完成，再单独决定是否将其改名为更直观的目录。

以下内容不作为仓库目录上传：

- 其他 Git worktree；
- `pytest_tmp_*`；
- `.pytest_cache`；
- 本地论文全文库；
- Git 元数据；
- 构建缓存和编辑器临时文件。

## 4. 目标根目录

```text
强化学习/
├─ README.md
├─ AGENTS.md
├─ PROJECT_HANDOFF.md
├─ STATUS.md
├─ ROADMAP.md
├─ .gitignore
├─ pyproject.toml
├─ LICENSE
├─ CITATION.cff
├─ .github/
├─ .research/
├─ gym_pybullet_drones/
├─ experiments/
├─ tests/
├─ docs/
├─ reproducibility/
└─ tools/
```

根目录不保留整个本地工作区的 `gym-pybullet-drones/`、`research_papers/` 和 `wt-gpd/` 三份镜像。仓库内容直接位于正式项目根目录。

## 5. 根目录文档职责

### 5.1 `README.md`

面向人的稳定入口，只包含：

- 项目目标；
- 两条核心研究线；
- 安装与快速开始；
- 目录导航；
- 当前状态链接。

不在 README 中手工记录容易过期的 Gate 进度和单次训练结果。

### 5.2 `AGENTS.md`

面向智能体，只包含：

- 必读顺序；
- 不可违反的实验边界；
- 状态恢复流程；
- 文件写权限；
- 当前状态的唯一来源；
- 测试和运行约束。

历史故事、详细结果和过期任务清单移出该文件。

### 5.3 `PROJECT_HANDOFF.md`

保留在根目录，作为人和智能体的交接入口。内容限制为：

- 研究脉络摘要；
- 已确认的关键决策；
- 当前主线；
- 历史材料入口；
- 接手顺序。

完整失败诊断和长篇历史迁入 `docs/project/`。

### 5.4 `STATUS.md`

给人阅读的当前状态摘要，只显示：

- 当前研究线；
- 当前阶段；
- 最新 GO/NO-GO/BLOCKED 结论；
- 唯一下一步；
- 最近更新时间和证据链接。

它必须由 `.research/execution_state.json` 受控生成或同步，不作为第二个独立状态源。

### 5.5 `ROADMAP.md`

保存稳定路线图：

- MATLAB/Simulink 研究阶段；
- PyBullet 研究阶段；
- Stage A/B/C 的定义；
- 各阶段之间的依赖和停止条件。

### 5.6 迁出根目录的长文档

```text
docs/project/
├─ repository_structure.md
├─ public_snapshot_policy.md
├─ research_history.md
└─ decisions/

docs/projects/pybullet_td3/
├─ research_plan.md
├─ implementation_plan.md
├─ parallel_runbook.md
└─ protocol_history.md
```

现有 `PROJECT_STRUCTURE.md`、`PROJECT_LAYOUT.json` 和 `RL_PAPER_EXECUTION_PLAN.md` 的有效内容迁入上述位置；迁移后根目录不保留重复副本。

## 6. 实验目录总结构

```text
experiments/
├─ README.md
└─ circular_tracking/
   ├─ README.md
   ├─ matlab_simulink/
   └─ pybullet_td3/
```

删除悬停复现和定点控制后，`experiments/` 不再列出它们。

## 7. MATLAB/Simulink 正式研究线

### 7.1 目标结构

```text
experiments/circular_tracking/matlab_simulink/
├─ README.md
├─ models/
├─ common/
├─ methods/
│  ├─ pid/
│  ├─ pid_feedforward/
│  ├─ mpc/
│  ├─ adrc/
│  ├─ residual_rl_v1/
│  └─ residual_rl_v2/
├─ studies/
│  ├─ 00_environment_models/
│  ├─ 10_controller_comparison/
│  ├─ 20_residual_rl_v1/
│  └─ 30_rl_v2_mpc_imitation/
├─ tests/
├─ evidence/
├─ artifacts/
└─ reports/
```

### 7.2 现存材料位置

完整材料目前仍存在于：

```text
E:/1-AI辅助工作/科研项目/强化学习/gym-pybullet-drones/
  experiments/circular_tracking/simulink_residual_rl/
```

该目录有 108 个文件、约 48.9 MiB，包括：

- 9 个 `.slx` 模型；
- 29 个 MATLAB 脚本；
- 8 个 `.mat` 数据或策略文件；
- CSV 指标、图表和报告。

原始独立工程仍存在于：

```text
E:/1-AI辅助工作/科研项目/干扰环境仿真/quadrotor_env_comparison/
```

它包含构建缓存和其他辅助材料，不能整目录无筛选复制。

### 7.3 权威来源规则

迁移时采用以下优先级：

1. 当前 Git HEAD 中已跟踪的 MATLAB 脚本、文档和测试作为文本源码基线；
2. 主 worktree 中缺失于 integration 的 `.slx`、最终策略、CSV 和报告作为候选补充；
3. 外部原始工程用于哈希核对和缺失恢复；
4. 若同名文件内容不同，先生成差异与哈希清单，不允许凭修改时间自动覆盖。

### 7.4 文件跟踪策略

必须跟踪：

- `models/*.slx`，因为它们是源模型；
- MATLAB `.m` 脚本；
- MATLAB 测试；
- 冻结配置；
- 小型 CSV 指标；
- Markdown 报告；
- 最终选定策略的清单和 SHA-256。

按条件跟踪：

- 最终策略 `.mat`：仅在体积合理、身份明确且有清单时跟踪或通过 Release/LFS 发布；
- 最终 PDF/DOCX：优先通过发布包保存，仓库保留 Markdown 源文档。

本地忽略：

- `slprj/`；
- Simulink 缓存；
- 自动保存文件；
- 中间训练数据；
- 大型原始 `.mat`；
- 批量生成图和临时报告。

## 8. PyBullet 正式研究线

### 8.1 目标结构

```text
experiments/circular_tracking/pybullet_td3/
├─ README.md
├─ common/
├─ studies/
│  └─ pid_residual_td3/
│     ├─ README.md
│     ├─ protocol/
│     ├─ code/
│     │  ├─ environments/
│     │  ├─ training/
│     │  ├─ evaluation/
│     │  └─ analysis/
│     └─ stages/
│        ├─ 00_foundation_and_pid/
│        ├─ 10_bootstrap_preflight/
│        ├─ 20_stage_a_20k/
│        ├─ 30_stage_b_50k/
│        ├─ 40_stage_c_100k/
│        └─ 50_final_evaluation/
└─ archive/
   ├─ 10_oracle_pid_ff_pilot/
   ├─ 20_hidden_disturbance_v1/
   ├─ 30_hidden_disturbance_v2/
   └─ 31_hidden_disturbance_v2_1/
```

### 8.2 当前代码映射

| 当前内容 | 目标位置 |
|---|---|
| 隐藏扰动环境 | `studies/pid_residual_td3/code/environments/` |
| PID 冻结配置 | `studies/pid_residual_td3/protocol/` |
| 训练脚本 | `studies/pid_residual_td3/code/training/` |
| 评估脚本 | `studies/pid_residual_td3/code/evaluation/` |
| 汇总与统计 | `studies/pid_residual_td3/code/analysis/` |
| 新方法根因预检 | `stages/10_bootstrap_preflight/` |
| 未来 20k | `stages/20_stage_a_20k/` |
| 未来 50k | `stages/30_stage_b_50k/` |
| 可选 100k | `stages/40_stage_c_100k/` |

### 8.3 历史证据映射

| 当前内容 | 目标位置 |
|---|---|
| 旧 `stage_A/`、`stage_B/` | `archive/20_hidden_disturbance_v1/` |
| `protocol_v2/` | `archive/30_hidden_disturbance_v2/` |
| `protocol_v2_1/` | `archive/31_hidden_disturbance_v2_1/` |
| 旧 Smoke | 归入产生它的协议目录 |
| Oracle/PID-FF PyBullet 路线 | `archive/10_oracle_pid_ff_pilot/` |

历史目录只读保存，不进入当前论文主表，也不根据新代码重写旧结果。

## 9. 阶段目录模板

每个当前 PyBullet 阶段使用统一结构：

```text
20_stage_a_20k/
├─ README.md
├─ config/
│  ├─ stage.json
│  └─ controller_overrides.json
├─ manifests/
│  ├─ experiment_manifest.json
│  ├─ seed_manifest.json
│  └─ model_registry.json
├─ evidence/
│  ├─ metrics.csv
│  ├─ summary.json
│  ├─ decision.json
│  └─ figures/
└─ runs/
   ├─ README.md
   ├─ pid/
   └─ residual_td3/
```

`direct_td3/` 不在当前主线中预建。只有未来协议明确恢复 Direct TD3 对照时，才在对应阶段增加该控制器目录；已有 Direct TD3 结果保留在历史协议归档中。

阶段 README 必须明确：

1. 阶段目的；
2. 入口条件；
3. 训练预算和种子；
4. 冻结配置；
5. GO、NO-GO 和立即停止条件；
6. 最终结论与证据位置。

运行路径固定为：

```text
runs/<controller>/seed_<NNN>/budget_<steps>/attempt_<NN>/
```

失败或重跑必须创建新 attempt，禁止覆盖旧 attempt。

## 10. 结果与大文件策略

### 10.1 Git 跟踪内容

- README；
- 冻结配置；
- 运行清单；
- 小型 CSV/JSON 指标；
- `decision.json`；
- 少量关键图；
- 模型身份、SHA-256 和外部位置。

### 10.2 本地内容

- Replay Buffer；
- checkpoint；
- TensorBoard；
- 原始轨迹；
- 控制日志；
- 视频；
- 临时训练状态；
- 大型 MATLAB 中间数据。

`runs/README.md` 和 `artifacts/README.md` 被 Git 跟踪，使 GitHub 能显示对应目录；不能创建伪造的同名模型或 Replay 文件。

单个 Git blob 不得超过 50 MiB。需要发布的大模型优先使用 GitHub Release、Git LFS 或独立对象存储。

## 11. 状态唯一来源

```text
.research/execution_state.json
             ↓
          STATUS.md
             ↓
阶段 README + evidence/decision.json
```

- `.research/execution_state.json` 是运行状态唯一真相源；
- `STATUS.md` 是面向人的受控摘要；
- `decision.json` 是某阶段终局决定；
- 不再维护独立且可能过期的 `stage_status.md`；删除前先把其中独有的历史结论迁入对应 archive README 或 `decision.json`；
- README 只保存稳定说明和指向状态文件的链接。

## 12. 悬停复现和定点控制的完整退役

删除目录：

```text
experiments/hover_rl_reproduction/
experiments/hover_fixed_point/
```

同时删除：

- `gym_pybullet_drones/examples/learn.py`；
- `gym_pybullet_drones/examples/play.py`；
- `gym_pybullet_drones/examples/mrac.py`；
- 仅服务悬停复现的 `reproducibility/docker/Dockerfile.repro`；
- `tools/visualization/live_progress_viewer.py`；
- PPO 悬停专用指南；
- 仅服务悬停复现的报告生成器。

同时修改：

- 混合用途报告中的悬停段落；
- README、AGENTS、HANDOFF、STRUCTURE 中的相关入口；
- 引用已删除兼容入口的测试、文档和包清单。

处理规则：

- 仅服务于退役研究的文件直接删除；
- 同时服务圆周主线的文件只删除相关段落；
- 删除后运行全仓库引用扫描；
- 不删除外部 MATLAB 工程、其他 worktree、备份和圆周跟踪训练产物。

## 13. 迁移顺序

1. 确认无活跃训练，记录当前 Git SHA 和文件清单；
2. 对 MATLAB 三处材料生成路径、大小和 SHA-256 对照表；
3. 创建新目录骨架和 README；
4. 整理根目录文档和状态唯一来源；
5. 迁入 MATLAB/Simulink 源模型、源码和小型证据；
6. 迁入 PyBullet 当前代码，归档旧协议；
7. 完整退役悬停复现和定点控制；
8. 更新所有导入、配置、文档和测试路径；
9. 更新 `.gitignore` 和公开快照说明；
10. 运行引用扫描、导入检查、重点测试和一次全量验证；
11. 以一个布局迁移提交同步 GitHub；
12. 验证 GitHub 根目录、Actions、文件大小和本地大文件保留情况。

迁移过程中不得运行新的强化学习训练，也不得修改算法、奖励、协议阈值或历史实验数值。

## 14. 非目标

本次布局整理不包括：

- 修正 Direct TD3 或 Residual TD3 算法；
- 重跑 Gate、Stage A 或 Stage B；
- 重新生成 MATLAB 仿真结果；
- 修改历史 CSV/JSON 数值；
- 删除外部原始工程或备份；
- 删除约 15.7 GiB 的本地 PyBullet 训练产物；
- 自动清理全部 worktree 和 pytest 临时目录；
- 未经单独确认重命名 GitHub 仓库。

## 15. 风险与控制

### 15.1 MATLAB 同名文件冲突

控制：先生成哈希对照表，冲突文件人工选择权威版本，不按时间戳覆盖。

### 15.2 Python 导入和配置路径失效

控制：先建立兼容导入或一次性更新所有引用，再运行 `rg` 引用扫描、导入测试和现有 pytest。

### 15.3 历史证据失去可追溯性

控制：归档时保留原相对路径映射、Git SHA、协议版本和清单；不改历史数值。

### 15.4 大文件误上传

控制：提交前检查暂存文件大小、Git blob 大小和忽略规则；任何大于 50 MiB 的文件阻止提交。

### 15.5 状态再次分叉

控制：先迁移 `stage_status.md` 的独有历史结论，再删除该文件，并规定 `.research/execution_state.json` 为唯一运行状态源。

## 16. 验收标准

设计实施完成必须同时满足：

1. 根目录直接显示 README、AGENTS、HANDOFF、STATUS 和 ROADMAP；
2. GitHub 根目录与唯一正式本地 worktree 一一对应；
3. MATLAB/Simulink 与 PyBullet 两条主线并列且入口清楚；
4. 9 个 Simulink 源模型已纳入明确的版本管理策略；
5. PyBullet 当前主线与旧协议完全分开；
6. Stage 目录均符合统一模板；
7. 不再存在 `hover_rl_reproduction` 和 `hover_fixed_point`；
8. 不存在指向已删除研究的悬空导入和文档路径；
9. 根状态、机器状态和阶段决定一致；
10. 本地 Replay、checkpoint 和 MATLAB 大型中间产物未丢失；
11. Git 中没有超过 50 MiB 的 blob；
12. `.github/workflows` 位于真正仓库根目录并能被 GitHub 识别；
13. 现有圆周跟踪重点测试和全量测试通过；
14. 工作区在提交后干净。
