# 当前研究状态

更新时间：2026-07-10

## 先读这里

论文方向已经重置。新的权威入口是：

```text
RL_PAPER_EXECUTION_PLAN.md
.research/design_brief.md
docs/superpowers/specs/2026-07-10-hidden-disturbance-td3-paper-redesign.md
docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md
AGENTS.md
PROJECT_HANDOFF.md
```

## 新论文方向

比较：

```text
PID
Direct TD3
PID + Residual TD3
```

条件：

```text
hidden stochastic disturbances
same observable state information
no true disturbance parameters
no PID-FF imitation
no disturbance-magnitude gate
```

研究问题是 PID residual prior 能否改善 TD3 的训练安全性、样本效率和未知扰动跟踪，而不是让 TD3 模仿已知前馈控制。

## 当前完成度

已完成：

- 旧 oracle/PID-FF pilot 的实现、训练、评估和 draft paper。
- 对旧论文逻辑、数据、代码和图表的审稿式复核。
- 新研究问题、设计 brief、根目录主计划和 test-first implementation plan。
- README、AGENTS、项目交接与结构文档的新旧边界同步。

尚未完成：

- hidden time-varying disturbance process。
- revised three-controller environment。
- terminal reward regression test。
- information-leak test。
- valid frozen nominal PID。
- revised Direct/Residual TD3 training。
- 20k/50k/100k staged experiments。
- revised manuscript results。

## Legacy Draft

```text
docs/paper/manuscript.md
docs/paper/manuscript.docx
docs/paper/method.md
docs/paper/results.md
experiments/circular_tracking/results/td3_residual_paper/
```

这些文件仍是成型的旧方案草稿和诊断记录，但不是新的投稿稿。不要继续向其中添加 oracle/PID-FF 主实验结论。

## 旧路线失败原因

1. Terminal failure penalty 因调用顺序没有进入 reward。
2. 5 秒训练 episode 只覆盖 10 秒圆周的前半圈。
3. 5000 steps 每模型只有约 20 个 episode。
4. Nominal PID standard RMSE 与圆半径相当，未真正完成轨迹。
5. Actor 读取真实扰动，PID-FF 又提供已知答案，RL 缺少合理任务。
6. No-disturbance-observation 消融同时改变 safety gate。
7. Warm-start 收益主要来自 PID-FF imitation，TD3 fine-tuning 经常退化。
8. Test seeds 0-2 被反复用于选择方法和 checkpoint。
9. Early termination RMSE 与 pooled 统计高估了证据。
10. 最终图表仍有 smoke-only、无置信区间和空白 trajectory 问题。

## 当前禁止事项

- 不要运行旧 PID-FF warm-start 或 retention 路线。
- 不要把旧 `td3_residual_paper` 模型拿来初始化新实验。
- 不要给任何新 controller 添加 disturbance truth。
- 不要在 Stage 0 tests 和 PID acceptance 前启动训练。
- 不要使用 test seeds 200-219 调参。
- 不要默认跳到 500k。

## 下一步

从 implementation plan 的 Task 1 开始。第一批代码必须建立：

```text
tests/circular_tracking/test_hidden_disturbance_td3_env.py
experiments/circular_tracking/rl_envs/disturbance_processes.py
experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py
```

先证明 terminal reward、扰动隐藏和 zero-residual invariant 正确，再整定 PID；只有 PID 通过 30 秒 nominal circle acceptance，才能开始 Stage A 20k。
