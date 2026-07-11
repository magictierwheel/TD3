# 研究历史

本文是旧路线的历史叙事与失败诊断，不是当前研究状态、执行状态或结果汇总。历史数字和含义按当时记录保留；当前状态以持久化执行状态和现行协议为准。

## terminal reward bug

旧环境在 `_computeReward()` 中读取 `_failure_reason`，但 `BaseAviary.step()` 先计算 reward，随后才调用 `_computeTerminated()` 设置失败原因。episode 在该步结束，因此描述中的 `-50` terminal failure penalty 没有进入 terminal transition，旧策略没有得到正确的失控学习信号。

## half-circle training

旧训练 episode 为 5 秒，而参考周期为 10 秒。策略每次只看到前半圈和同一初始相位，不能据此证明完整圆周跟踪能力。

## oracle leakage

旧 actor 获得仿真器真实风、热、密度和效率参数。真实扰动信息进入策略后，问题不再是隐藏扰动下的控制；已知扰动和模型时，解析前馈本来就比有限数据的 TD3 更直接。

## PID-FF imitation

旧路线使用 PID-FF 解析扰动补偿生成 imitation target，并以 PID-FF imitation warm-start 初始化策略。结果由教师动作和 warm-start 主导，TD3 fine-tuning 还可能退化，因而不能作为无特权残差学习的证据。

## test leakage

旧 test seeds `0-2` 被多次用于选择 warm-start、retention、gate 和 checkpoint，后来不再是未触碰的测试集。所谓 no-disturbance-observation ablation 还同时改变了 safety gate（DA-Residual 有 gate，旧 residual_td3 固定 `gate=1`），比较并不公平。

## statistical lessons

旧 5000 steps 约等于 20 个 episode，五类场景平均只有约四个 episode，不能视为 TD3 收敛实验。early failure 可能产生偏低 RMSE；三个训练模型反复使用相同三个扰动 seed，九行数据不等于九个独立环境样本。旧 nominal PID 稳态 RMSE 与圆半径相当，实际路径长度远小于三圈参考长度，因此 residual actor 同时在补偿 PID 圆周滞后和环境扰动。上述问题属于历史诊断，不代表当前实验已经完成或当前结果。
