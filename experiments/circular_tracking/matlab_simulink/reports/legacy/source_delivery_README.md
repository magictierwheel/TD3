# 四旋翼环境扰动仿真对比交付说明

本目录是独立交付包，未在参考工程目录中写入任何文件。

## 主要交付物

- `models/quadrotor_standard.slx`：标准四旋翼模型。
- `models/quadrotor_temperature.slx`：考虑温度、空气密度、风场和热上升扰动的四旋翼模型。
- `models/quadrotor_dust.slx`：考虑粉尘浓度导致推力/反扭矩效率折减的四旋翼模型。
- `models/quadrotor_strategy_pid.slx`：原 PID 控制策略专用模型。
- `models/quadrotor_strategy_pid_ff.slx`：PID 扰动补偿控制策略专用模型。
- `models/quadrotor_strategy_mpc.slx`：线性 MPC 控制策略专用模型。
- `models/quadrotor_strategy_adrc.slx`：ADRC 扩张状态观测器抗扰控制策略专用模型。
- `models/quadrotor_strategy_rl.slx`：强化学习残差控制策略专用模型。
- `scripts/init_quadrotor_params.m`：统一参数、工况和模型类型入口。
- `scripts/build_quadrotor_models.m`：重新生成三份 Simulink 模型。
- `scripts/run_all_simulations.m`：运行悬停、匀速圆周、点到点三类工况的 9 组仿真并导出图和数据。
- `scripts/train_quadrotor_rl_policy.m`：训练适合 Simulink 部署的强化学习残差策略权重。
- `scripts/run_rl_circle_comparison.m`：运行匀速圆周工况下“原控制器 vs 强化学习策略”的 6 组对比仿真。
- `scripts/run_strategy_circle_comparison.m`：运行原 PID、PID 扰动补偿、线性 MPC、ADRC、强化学习策略的 15 组圆周抗扰对比仿真。
- `scripts/build_controller_strategy_models.m`：生成五个控制策略专用 Simulink 模型。
- `scripts/run_strategy_model_smoke_tests.m`：快速验证五个策略专用模型都能运行并导出日志。
- `results/figures/*.png`：轨迹、误差、环境输入、各旋翼转速变化和模型顶层结构截图。
- `results/data/quadrotor_environment_comparison_results.mat`：完整仿真数据。
- `results/data/quadrotor_environment_comparison_metrics.csv`：指标汇总表。
- `results/policies/rl_v1/quadrotor_rl_policy.mat`：已训练的强化学习残差策略权重。
- `results/data/quadrotor_rl_circle_comparison_metrics.csv`：强化学习圆周抗扰对比指标。
- `results/data/quadrotor_strategy_circle_comparison_metrics.csv`：多控制策略圆周抗扰对比指标。
- `reports/四旋翼无人机环境扰动仿真对比最终报告.docx`：最终总结报告。
- `reports/强化学习圆周抗扰控制对比报告.docx`：强化学习策略部署与优越性对比报告。
- `reports/多控制策略圆周抗扰对比报告.docx`：原 PID、PID 扰动补偿、MPC 与强化学习策略对比报告。
- `reports/quadrotor_environment_comparison_detailed_formula_report.docx`：详细公式说明报告。
- `audit/*.csv`、`audit/*.txt`、`audit/delivery_audit_summary.md`：参考目录哈希证明和交付审核结果。

## 出图规定

`results/figures` 文件夹中由本项目脚本生成的所有图片，图表标题必须使用中文。新增或修改绘图脚本时，应把中文标题直接固化在脚本中，并通过 `audit_delivery` 检查保留该规则。

## 复现命令

在 MATLAB 中运行：

```matlab
projectRoot = 'E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl';
addpath(projectRoot);
setup_simulink_residual_rl_paths;
build_quadrotor_models;
run_all_simulations;
audit_delivery;
```

训练并复现强化学习圆周抗扰对比：

```matlab
projectRoot = 'E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl';
addpath(projectRoot);
setup_simulink_residual_rl_paths;
train_quadrotor_rl_policy;
run_rl_circle_comparison;
```

运行五种控制策略圆周抗扰对比：

```matlab
projectRoot = 'E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl';
addpath(projectRoot);
setup_simulink_residual_rl_paths;
run_strategy_circle_comparison;
```

生成并快速验证五个策略专用 Simulink 模型：

```matlab
projectRoot = 'E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl';
addpath(projectRoot);
setup_simulink_residual_rl_paths;
build_controller_strategy_models;
run_strategy_model_smoke_tests;
```

重新生成强化学习对比报告：

```powershell
python "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\scripts\reporting\generate_rl_comparison_report.py"
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\scripts\reporting\export_docx_pdf.ps1" -DocxPath "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\reports\rl_v1\强化学习圆周抗扰控制对比报告.docx" -PdfPath "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\reports\rl_v1\强化学习圆周抗扰控制对比报告.pdf"
```

重新生成多控制策略对比报告：

```powershell
python "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\scripts\reporting\generate_strategy_comparison_report.py"
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\scripts\reporting\export_docx_pdf.ps1" -DocxPath "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\reports\strategy_comparison\多控制策略圆周抗扰对比报告.docx" -PdfPath "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\reports\strategy_comparison\多控制策略圆周抗扰对比报告.pdf"
```

当前副本中可重新生成的报告脚本：

```powershell
python "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\scripts\reporting\generate_beginner_control_strategy_report.py"
python "E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\scripts\reporting\generate_rl_v2_mpc_report.py"
```

## 参考资料只读证明

参考路径：

- `C:\Users\audib\Desktop\UAV\UAV_MATLAB`
- `C:\Users\audib\Desktop\ForestFire_Quadrotor_Iterative_CoSim_V2\reports\汇报`

哈希比对结果见：

- `audit/reference_integrity_before.csv`
- `audit/reference_integrity_after.csv`
- `audit/reference_integrity_compare.txt`

当前结果为：`PASS: reference directories unchanged. Files checked: 196`

