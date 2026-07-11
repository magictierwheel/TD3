# 强化学习项目路线图

## MATLAB/Simulink圆周抗扰

环境模型 → 多控制器比较 → Residual RL-v1 → RL-v2/MPC imitation

## PyBullet圆周跟踪

基础环境与PID → Bootstrap Preflight → Stage A 20k → Stage B 50k → 可选Stage C 100k → 最终评估

## 停止规则

任何前置阶段NO-GO时，后续阶段保持未开始；不得通过换种子、修改阈值或扩大预算绕过。
