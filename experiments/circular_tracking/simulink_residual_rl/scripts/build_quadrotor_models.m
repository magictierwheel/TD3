function build_quadrotor_models()
%BUILD_QUADROTOR_MODELS Generate three clean Simulink models for comparison.
%   The models are written only under the current delivery directory.

rootDir = fileparts(fileparts(mfilename('fullpath')));
modelsDir = fullfile(rootDir, 'models');
if ~exist(modelsDir, 'dir')
    mkdir(modelsDir);
end

addpath(fullfile(rootDir, 'scripts'));
modelPathWasPresent = is_path_member(modelsDir);
if modelPathWasPresent
    rmpath(modelsDir);
end
restoreModelPath = onCleanup(@() restore_path(modelsDir, modelPathWasPresent)); %#ok<NASGU>

modelSpecs = { ...
    'quadrotor_standard',     0, '标准四旋翼基线模型：不引入温度、风场、热上升或粉尘扰动，用于环境扰动对照。'; ...
    'quadrotor_temperature',  1, '温度扰动四旋翼模型：考虑火场温升导致的空气密度变化，并引入诱导风和竖直热上升扰动。'; ...
    'quadrotor_dust',         2, '粉尘浓度扰动四旋翼模型：通过 eta_T 和 eta_Q 折减旋翼推力及反扭矩效率，体现粉尘对动力输出的影响。'};

for i = 1:size(modelSpecs, 1)
    create_one_model(modelSpecs{i, 1}, modelSpecs{i, 2}, modelSpecs{i, 3}, modelsDir);
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

function create_one_model(modelName, defaultModelId, modelDescription, modelsDir)
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

% Put model identity in model workspace as a default for interactive runs.
mw = get_param(modelName, 'ModelWorkspace');
assignin(mw, 'quad_model_id_default', defaultModelId);

add_block('simulink/Sources/Clock', [modelName '/仿真时钟'], ...
    'Position', [35 108 65 132]);
add_block('simulink/Continuous/Integrator', [modelName '/状态积分器'], ...
    'InitialCondition', 'quad_x0', ...
    'Position', [790 102 835 148]);
add_block('simulink/Sources/Constant', [modelName '/模型编号'], ...
    'Value', 'quad_model_id', ...
    'Position', [35 205 110 235]);
add_block('simulink/Sources/Constant', [modelName '/工况编号'], ...
    'Value', 'quad_scenario_id', ...
    'Position', [35 260 110 290]);
add_block('simulink/Sources/Constant', [modelName '/参数向量'], ...
    'Value', 'quad_param_vec', ...
    'Position', [35 320 125 350]);
add_block('simulink/Sinks/To Workspace', [modelName '/仿真日志'], ...
    'VariableName', 'sim_log', ...
    'SaveFormat', 'Array', ...
    'MaxDataPoints', 'inf', ...
    'Position', [1060 362 1145 392]);

make_matlab_subsystem(modelName, '参考轨迹调度', ...
    {'时间', '工况编号', '参数向量'}, {'参考信号'}, reference_script(), [190 60 365 150]);
make_matlab_subsystem(modelName, '环境扰动', ...
    {'时间', '状态向量', '模型编号', '参数向量'}, {'环境量'}, environment_script(), [190 205 365 320]);
make_matlab_subsystem(modelName, '统一控制器', ...
    {'时间', '状态向量', '参考信号', '参数向量'}, {'转速指令', '控制调试'}, controller_script(), [470 60 655 160]);
make_matlab_subsystem(modelName, '四旋翼动力学', ...
    {'状态向量', '参考信号', '转速指令', '环境量', '参数向量'}, {'状态导数', '动力学调试'}, dynamics_script(), [470 235 655 360]);
make_matlab_subsystem(modelName, '信号记录', ...
    {'时间', '状态向量', '参考信号', '环境量', '转速指令', '控制调试', '动力学调试'}, {'记录输出'}, logging_script(), [800 318 975 430]);

% Main signal path, intentionally laid left-to-right to keep the drawing tidy.
add_line(modelName, '仿真时钟/1', '参考轨迹调度/1', 'autorouting', 'on');
add_line(modelName, '工况编号/1', '参考轨迹调度/2', 'autorouting', 'on');
add_line(modelName, '参数向量/1', '参考轨迹调度/3', 'autorouting', 'on');

add_line(modelName, '仿真时钟/1', '环境扰动/1', 'autorouting', 'on');
add_line(modelName, '状态积分器/1', '环境扰动/2', 'autorouting', 'on');
add_line(modelName, '模型编号/1', '环境扰动/3', 'autorouting', 'on');
add_line(modelName, '参数向量/1', '环境扰动/4', 'autorouting', 'on');

add_line(modelName, '仿真时钟/1', '统一控制器/1', 'autorouting', 'on');
add_line(modelName, '状态积分器/1', '统一控制器/2', 'autorouting', 'on');
add_line(modelName, '参考轨迹调度/1', '统一控制器/3', 'autorouting', 'on');
add_line(modelName, '参数向量/1', '统一控制器/4', 'autorouting', 'on');

add_line(modelName, '状态积分器/1', '四旋翼动力学/1', 'autorouting', 'on');
add_line(modelName, '参考轨迹调度/1', '四旋翼动力学/2', 'autorouting', 'on');
add_line(modelName, '统一控制器/1', '四旋翼动力学/3', 'autorouting', 'on');
add_line(modelName, '环境扰动/1', '四旋翼动力学/4', 'autorouting', 'on');
add_line(modelName, '参数向量/1', '四旋翼动力学/5', 'autorouting', 'on');
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
