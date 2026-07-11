# Agent Handoff Guide

本文件面向之后接手本仓库的智能体。当前论文方向已在 2026-07-10 发生研究重置；不要根据旧 manuscript 或旧 TD3 result folder 猜测下一步。

## Durable Recovery Protocol

聊天上下文、自动摘要和智能体记忆都不是执行状态的来源。任何开始、恢复或接手本项目的主智能体必须：

1. 阅读本文件、`RL_PAPER_EXECUTION_PLAN.md`、parallel runbook 和 implementation plan。
2. 读取 `experiments/circular_tracking/config/hidden_td3_protocol.json`。
3. 读取 `.research/execution_state.json`、当前 `.research/task_reports/task_N.md` 和 `.research/execution_journal.jsonl` 最后 20 条记录。
4. 核对 Git SHA、分支、worktree、dirty state、活跃智能体和 `active_runs`。
5. 重新运行 `last_verification` 中当前阶段要求的命令。
6. 只执行 `execution_state.json` 中的 `next_action`，不得根据聊天摘要猜测下一步。
7. 每次状态改变均递增 `state_revision`，并向 journal 追加一条 JSON 记录。

共享执行状态只允许主智能体写入。子智能体不得修改：

```text
.research/execution_state.json
.research/execution_journal.jsonl
experiments/circular_tracking/config/hidden_td3_protocol.json
docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md
experiments/circular_tracking/results/hidden_disturbance_td3_paper/stage_status.md
docs/paper/manuscript.md
任何全局 summary
```

详细并发与恢复规则见：

```text
docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-parallel-runbook.md
```

## Read First

严格按顺序阅读：

1. `RL_PAPER_EXECUTION_PLAN.md`
   - 新论文唯一主计划。
   - 定义三个控制器、信息边界、失败根因、训练阶段和 GO/NO-GO 门槛。
2. `.research/design_brief.md`
   - 可证伪研究问题、机制、可识别性、验证方案和风险登记。
3. `docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md`
   - 逐文件、逐测试、逐实验的实现清单。
4. `PROJECT_HANDOFF.md`
   - 项目历史、legacy 边界和当前接手状态。
5. `PROJECT_STRUCTURE.md`
   - 新旧目录用途。

## Current Research Direction

```text
Hidden stochastic disturbances
        ↓
PID vs Direct TD3 vs PID + Residual TD3
        ↓
same observable state, no true disturbance information
```

推荐论文题目：

```text
未知随机扰动下四旋翼圆周轨迹跟踪的残差 TD3：
与 PID 和端到端 TD3 的对比研究
```

核心问题不是“TD3 是否模仿已知前馈”，而是“PID 稳定先验是否在未知扰动下改善 TD3 的安全性、样本效率和抗扰跟踪”。

## Current Phase

当前只完成了研究设计和文档重置。新 hidden-disturbance environment、新测试和新训练尚未实现。

第一项代码工作必须是：

```text
1. terminal reward regression test
2. hidden-information boundary test
3. zero residual equals PID test
4. nominal PID circular-tracking acceptance
```

在上述测试通过前，不得启动 20k、50k、100k 或更长训练。

## Non-Negotiable Rules

- 主实验只有 `pid`、`direct_td3`、`residual_td3` 三个核心控制器。
- 所有控制器不得读取风、密度、热流、推力/力矩效率、场景标签或扰动 seed。
- 普通 PID 有正常反馈和积分记忆，但没有 disturbance observer。
- PID-FF、MPC、ADRC、DOB 若未来加入，必须作为明确的第四基线，不得作为 actor teacher。
- 禁止 PID-FF imitation warm-start；Residual actor 使用零输出初始化。
- Direct 与 Residual TD3 使用相同状态信息、历史长度、reward、训练分布、预算、终止阈值和 motor bounds。
- Safety gate 只能依赖可测 tracking error、姿态/高度余量和 motor headroom。
- 训练 episode 至少 20 秒，不能再次只覆盖 10 秒圆周的前半圈。
- PID 必须先在 standard 中真正完成圆周并通过 acceptance，再冻结并训练 RL。
- 验证 seeds 为 100-109；测试 seeds 为 200-219；unseen seeds 为 300-319。
- 不能针对不同 training seed 挑不同的有利 checkpoint；选一个全局预算。
- failure rate 优先于 RMSE；早停轨迹必须报告 flight time 和 failure-penalized metric。
- 所有论文数字必须追溯到 revised CSV/JSON，不能从图中读数。

## Legacy Boundary

以下属于旧 oracle/PID-FF pilot：

```text
experiments/circular_tracking/rl_envs/circular_residual_td3_env.py
experiments/circular_tracking/results/td3_residual_paper/
experiments/circular_tracking/analysis/claim_evidence_ledger.csv
docs/paper/manuscript.md
docs/paper/results.md
docs/paper/method.md
```

这些材料不得删除，因为它们记录了重要失败：

- 扰动力施加点曾错误使用世界原点。
- terminal failure penalty 没有进入 reward。
- 5 秒 episode 只训练半圈。
- 5000 steps 只有约 20 个 episode。
- nominal PID 跟踪质量不合格。
- oracle disturbance 让 RL 的必要性消失。
- PID-FF imitation 主导结果且 TD3 fine-tuning 退化。
- “无扰动观测”消融同时改变 gate，不是 matched ablation。
- 旧 test seeds 被反复用于调参。
- pooled 统计和早停 RMSE 高估了证据。

旧结果只能写入 revised paper 的研究动机/失败诊断，不能进入新主表或支持新 claim。

## New File Namespace

新代码按计划放到：

```text
experiments/circular_tracking/rl_envs/disturbance_processes.py
experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py
experiments/circular_tracking/scripts/td3/train_hidden_td3.py
experiments/circular_tracking/scripts/td3/evaluate_hidden_td3.py
experiments/circular_tracking/scripts/td3/summarize_hidden_td3.py
tests/circular_tracking/
```

新结果只能放到：

```text
experiments/circular_tracking/results/hidden_disturbance_td3_paper/
```

不要覆盖或混用 `td3_residual_paper/`。

## Training Gates

```text
Stage A: seed 0, 20k, diagnostic GO/NO-GO
Stage B: seeds 0-2, 50k, direction pilot
Stage C: seeds 0-4, up to 100k, only after Stage B GO
```

如果 Stage B 中 Residual 改善方向未在至少 2/3 training seeds 中一致，停止扩大预算，转为负结果/诊断论文。不要通过延长训练或重新打开测试集寻找有利结果。

## Runtime And Verification

本地实验使用：

```powershell
py -3.11
```

每个实现任务完成后运行对应 pytest。正式训练前至少执行：

```powershell
py -3.11 -m pytest tests/circular_tracking -v
py -3.11 -m compileall experiments/circular_tracking/rl_envs experiments/circular_tracking/scripts/td3
```

## Do Not Confuse These Lines

- `experiments/circular_tracking/`: 当前圆周跟踪研究主线。
- `experiments/circular_tracking/simulink_residual_rl/`: 旧 Simulink 方法来源和背景，不与新 PyBullet 数值混表。
- `experiments/hover_rl_reproduction/`: PPO 悬停链路复现，不是圆周跟踪证据。
- `experiments/hover_fixed_point/`: 定点控制，不是圆周跟踪主实验。

## Default Next Action

仅当 `.research/execution_state.json` 不存在时，才打开 implementation plan 并从第一个未完成 checkbox 开始。执行状态存在时，唯一合法的下一步是其中记录的 `next_action`；不得使用本段覆盖持久状态。
