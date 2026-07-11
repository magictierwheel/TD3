function build_controller_strategy_models()
%BUILD_CONTROLLER_STRATEGY_MODELS Generate strategy-specific Simulink models.
%   The five models fix p(89) internally so each .slx represents one
%   controller strategy. The environment model remains selectable through
%   quad_model_id, so each strategy model can be run under standard,
%   temperature, or dust disturbances.

rootDir = fileparts(fileparts(mfilename('fullpath')));
modelsDir = fullfile(rootDir, 'models');
if ~exist(modelsDir, 'dir')
    mkdir(modelsDir);
end

addpath(fullfile(rootDir, 'scripts'));
rlWeights = load_rl_weights(rootDir);
rlV2Slots = load_rl_v2_slots(rootDir);
modelPathWasPresent = is_path_member(modelsDir);
if modelPathWasPresent
    rmpath(modelsDir);
end
restoreModelPath = onCleanup(@() restore_path(modelsDir, modelPathWasPresent));

strategySpecs = { ...
    'quadrotor_strategy_pid',     0, '原PID策略模型：固定使用串级 PID/PD 控制器，不启用环境扰动补偿。'; ...
    'quadrotor_strategy_pid_ff',  2, 'PID扰动补偿策略模型：原PID叠加风阻、热上升、密度和粉尘效率补偿。'; ...
    'quadrotor_strategy_mpc',     3, '线性MPC策略模型：MPC外环生成加速度指令，并叠加环境扰动补偿。'; ...
    'quadrotor_strategy_adrc',    4, 'ADRC策略模型：ESO估计总扰动，外环按估计扰动进行主动补偿。'; ...
    'quadrotor_strategy_rl',      1, '强化学习策略模型：固定使用已训练残差强化学习补偿策略。'; ...
    'quadrotor_strategy_rl_v2',   5, 'RL-v2策略模型：固定使用前瞻残差强化学习补偿策略。'};

for i = 1:size(strategySpecs, 1)
    create_one_strategy_model(strategySpecs{i, 1}, strategySpecs{i, 2}, ...
        strategySpecs{i, 3}, modelsDir, rlWeights, rlV2Slots);
end
end

function tf = is_path_member(folder)
pathParts = strsplit(path, pathsep);
tf = any(strcmpi(pathParts, folder));
end

function restore_path(folder, shouldRestore)
if shouldRestore && ~is_path_member(folder)
    addpath(folder);
end
end

function weights = load_rl_weights(rootDir)
weights = ones(5, 1);
policyPath = fullfile(rootDir, 'results', 'policies', 'rl_v1', 'quadrotor_rl_policy.mat');
if exist(policyPath, 'file') == 2
    data = load(policyPath, 'bestWeights');
    weights = data.bestWeights(:);
end
end

function slots = load_rl_v2_slots(rootDir)
slots = zeros(120, 1);
slots(1) = 2.0;
slots(2) = 1.0;
slots(89:93) = [0.20; 0.20; 0.16; 0.08; 0.06];
slots(94) = 1.0;
slots(95) = 0.0;
slots(96) = 0.25;
slots(97) = 0.08;
slots(98) = 0.06;
slots(99) = 3.0;
slots(100) = 1.0;
policyPath = fullfile(rootDir, 'results', 'policies', 'rl_v2', 'quadrotor_rl_v2_policy.mat');
if exist(policyPath, 'file') == 2
    data = load(policyPath, 'bestPolicySlots');
    slots = data.bestPolicySlots(:);
end
end

function create_one_strategy_model(modelName, controllerMode, modelDescription, modelsDir, rlWeights, rlV2Slots)
if bdIsLoaded(modelName)
    close_system(modelName, 0);
end

new_system(modelName);
load_system(modelName);

set_param(modelName, ...
    'Solver', 'ode4', ...
    'SolverType', 'Fixed-step', ...
    'FixedStep', '0.02', ...
    'StopTime', 'quad_stop_time', ...
    'SaveOutput', 'off', ...
    'SaveTime', 'on', ...
    'ReturnWorkspaceOutputs', 'on', ...
    'Description', modelDescription);

add_block('simulink/Sources/Clock', [modelName '/仿真时钟'], ...
    'Position', [35 108 65 132]);
add_block('simulink/Continuous/Integrator', [modelName '/状态积分器'], ...
    'InitialCondition', 'quad_x0', ...
    'Position', [880 102 925 148]);
add_block('simulink/Sources/Constant', [modelName '/模型编号'], ...
    'Value', 'quad_model_id', ...
    'Position', [35 205 110 235]);
add_block('simulink/Sources/Constant', [modelName '/工况编号'], ...
    'Value', 'quad_scenario_id', ...
    'Position', [35 260 110 290]);
add_block('simulink/Sources/Constant', [modelName '/参数向量'], ...
    'Value', 'quad_param_vec', ...
    'Position', [35 320 125 350]);
add_block('simulink/Sources/Constant', [modelName '/控制策略编号'], ...
    'Value', num2str(controllerMode), ...
    'Position', [35 380 125 410]);
add_block('simulink/Sinks/To Workspace', [modelName '/仿真日志'], ...
    'VariableName', 'sim_log', ...
    'SaveFormat', 'Array', ...
    'MaxDataPoints', 'inf', ...
    'Position', [1160 362 1245 392]);

make_matlab_subsystem(modelName, '控制策略参数', ...
    {'参数向量', '控制策略编号', '模型编号', '工况编号'}, {'策略参数'}, ...
    strategy_param_script(controllerMode, rlWeights, rlV2Slots), [190 300 365 430]);
make_matlab_subsystem(modelName, '参考轨迹调度', ...
    {'时间', '工况编号', '策略参数'}, {'参考信号'}, reference_script(), [450 60 625 150]);
make_matlab_subsystem(modelName, '环境扰动', ...
    {'时间', '状态向量', '模型编号', '策略参数'}, {'环境量'}, environment_script(), [450 205 625 320]);
make_matlab_subsystem(modelName, '统一控制器', ...
    {'时间', '状态向量', '参考信号', '策略参数'}, {'转速指令', '控制调试'}, controller_script(), [720 60 905 160]);
make_matlab_subsystem(modelName, '四旋翼动力学', ...
    {'状态向量', '参考信号', '转速指令', '环境量', '策略参数'}, {'状态导数', '动力学调试'}, dynamics_script(), [720 235 905 360]);
make_matlab_subsystem(modelName, '信号记录', ...
    {'时间', '状态向量', '参考信号', '环境量', '转速指令', '控制调试', '动力学调试'}, {'记录输出'}, logging_script(), [900 318 1075 430]);

add_line(modelName, '参数向量/1', '控制策略参数/1', 'autorouting', 'on');
add_line(modelName, '控制策略编号/1', '控制策略参数/2', 'autorouting', 'on');
add_line(modelName, '模型编号/1', '控制策略参数/3', 'autorouting', 'on');
add_line(modelName, '工况编号/1', '控制策略参数/4', 'autorouting', 'on');

add_line(modelName, '仿真时钟/1', '参考轨迹调度/1', 'autorouting', 'on');
add_line(modelName, '工况编号/1', '参考轨迹调度/2', 'autorouting', 'on');
add_line(modelName, '控制策略参数/1', '参考轨迹调度/3', 'autorouting', 'on');

add_line(modelName, '仿真时钟/1', '环境扰动/1', 'autorouting', 'on');
add_line(modelName, '状态积分器/1', '环境扰动/2', 'autorouting', 'on');
add_line(modelName, '模型编号/1', '环境扰动/3', 'autorouting', 'on');
add_line(modelName, '控制策略参数/1', '环境扰动/4', 'autorouting', 'on');

add_line(modelName, '仿真时钟/1', '统一控制器/1', 'autorouting', 'on');
add_line(modelName, '状态积分器/1', '统一控制器/2', 'autorouting', 'on');
add_line(modelName, '参考轨迹调度/1', '统一控制器/3', 'autorouting', 'on');
add_line(modelName, '控制策略参数/1', '统一控制器/4', 'autorouting', 'on');

add_line(modelName, '状态积分器/1', '四旋翼动力学/1', 'autorouting', 'on');
add_line(modelName, '参考轨迹调度/1', '四旋翼动力学/2', 'autorouting', 'on');
add_line(modelName, '统一控制器/1', '四旋翼动力学/3', 'autorouting', 'on');
add_line(modelName, '环境扰动/1', '四旋翼动力学/4', 'autorouting', 'on');
add_line(modelName, '控制策略参数/1', '四旋翼动力学/5', 'autorouting', 'on');
add_line(modelName, '四旋翼动力学/1', '状态积分器/1', 'autorouting', 'on');

add_line(modelName, '仿真时钟/1', '信号记录/1', 'autorouting', 'on');
add_line(modelName, '状态积分器/1', '信号记录/2', 'autorouting', 'on');
add_line(modelName, '参考轨迹调度/1', '信号记录/3', 'autorouting', 'on');
add_line(modelName, '环境扰动/1', '信号记录/4', 'autorouting', 'on');
add_line(modelName, '统一控制器/1', '信号记录/5', 'autorouting', 'on');
add_line(modelName, '统一控制器/2', '信号记录/6', 'autorouting', 'on');
add_line(modelName, '四旋翼动力学/2', '信号记录/7', 'autorouting', 'on');
add_line(modelName, '信号记录/1', '仿真日志/1', 'autorouting', 'on');

Simulink.BlockDiagram.arrangeSystem(modelName);
save_system(modelName, fullfile(modelsDir, [modelName '.slx']));
close_system(modelName, 0);
end

function make_matlab_subsystem(modelName, name, inports, outports, scriptText, pos)
subsys = [modelName '/' name];
add_block('simulink/Ports & Subsystems/Subsystem', subsys, 'Position', pos);

delete_default_lines(subsys);

chartPath = [subsys '/核心公式'];
add_block('simulink/User-Defined Functions/MATLAB Function', chartPath, ...
    'Position', [175 70 315 125]);

rt = sfroot;
chart = rt.find('-isa', 'Stateflow.EMChart', 'Path', chartPath);
chart.Script = scriptText;

for i = 1:numel(inports)
    blockPath = [subsys '/' inports{i}];
    add_block('simulink/Sources/In1', blockPath, ...
        'Position', [35 35 + (i-1)*45 65 49 + (i-1)*45]);
    add_line(subsys, [inports{i} '/1'], ['核心公式/' num2str(i)], 'autorouting', 'on');
end

for i = 1:numel(outports)
    blockPath = [subsys '/' outports{i}];
    add_block('simulink/Sinks/Out1', blockPath, ...
        'Position', [420 52 + (i-1)*55 450 66 + (i-1)*55]);
    add_line(subsys, ['核心公式/' num2str(i)], [outports{i} '/1'], 'autorouting', 'on');
end
end

function delete_default_lines(subsys)
try
    delete_line(subsys, 'In1/1', 'Out1/1');
catch
end
try
    delete_block([subsys '/In1']);
catch
end
try
    delete_block([subsys '/Out1']);
catch
end
end

function s = strategy_param_script(controllerMode, rlWeights, rlV2Slots)
if controllerMode == 1
    weightLines = sprintf([ ...
        'p_out(91) = %.15g;\n', ...
        'p_out(92) = %.15g;\n', ...
        'p_out(93) = %.15g;\n', ...
        'p_out(94) = %.15g;\n', ...
        'p_out(95) = %.15g;\n'], ...
        rlWeights(1), rlWeights(2), rlWeights(3), rlWeights(4), rlWeights(5));
else
    weightLines = '';
end
if controllerMode == 5
    slotLines = '';
    for i = 1:120
        slotLines = sprintf('%sp_out(%d) = %.15g;\n', slotLines, 120 + i, rlV2Slots(i));
    end
else
    slotLines = '';
end
s = sprintf([ ...
    'function p_out = fcn(p_in, controller_mode, model_id, scenario_id)\n', ...
    '%%#codegen\n', ...
    'p_out = p_in;\n', ...
    'p_out(88) = scenario_id;\n', ...
    'p_out(89) = controller_mode;\n', ...
    'p_out(90) = model_id;\n', ...
    'p_out(97) = 1.0;\n', ...
    '%s', ...
    '%s', ...
    'end\n'], weightLines, slotLines);
end

function s = reference_script()
s = sprintf([ ...
    'function ref = fcn(t, scenario_id, p)\n', ...
    '%%#codegen\n', ...
    'ref = quadrotor_reference_core(t, scenario_id, p);\n', ...
    'end\n']);
end

function s = environment_script()
s = sprintf([ ...
    'function env = fcn(t, x, model_id, p)\n', ...
    '%%#codegen\n', ...
    'env = quadrotor_environment_core(t, x, model_id, p);\n', ...
    'end\n']);
end

function s = controller_script()
s = sprintf([ ...
    'function [omega_cmd, ctrl_dbg] = fcn(t, x, ref, p)\n', ...
    '%%#codegen\n', ...
    '[omega_cmd, ctrl_dbg] = quadrotor_controller_core(t, x, ref, p);\n', ...
    'end\n']);
end

function s = dynamics_script()
s = sprintf([ ...
    'function [dx, plant_dbg] = fcn(x, ref, omega_cmd, env, p)\n', ...
    '%%#codegen\n', ...
    '[dx, plant_dbg] = quadrotor_rhs_core(x, ref, omega_cmd, env, p);\n', ...
    'end\n']);
end

function s = logging_script()
s = sprintf([ ...
    'function log = fcn(t, x, ref, env, omega_cmd, ctrl_dbg, plant_dbg)\n', ...
    '%%#codegen\n', ...
    'log = quadrotor_pack_log_core(t, x, ref, env, omega_cmd, ctrl_dbg, plant_dbg);\n', ...
    'end\n']);
end
