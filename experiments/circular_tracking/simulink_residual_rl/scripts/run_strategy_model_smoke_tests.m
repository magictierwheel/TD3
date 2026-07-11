function smoke = run_strategy_model_smoke_tests()
%RUN_STRATEGY_MODEL_SMOKE_TESTS Verify strategy-specific Simulink models run.

rootDir = fileparts(fileparts(mfilename('fullpath')));
scriptsDir = fullfile(rootDir, 'scripts');
modelsDir = fullfile(rootDir, 'models');
dataDir = fullfile(rootDir, 'results', 'data');
if ~exist(dataDir, 'dir'), mkdir(dataDir); end
addpath(scriptsDir);

build_controller_strategy_models();
addpath(modelsDir);

modelNames = {'quadrotor_strategy_pid', 'quadrotor_strategy_pid_ff', ...
    'quadrotor_strategy_mpc', 'quadrotor_strategy_adrc', 'quadrotor_strategy_rl', ...
    'quadrotor_strategy_rl_v2'};
strategyLabels = {'原PID', 'PID扰动补偿', '线性MPC', 'ADRC', '强化学习策略', 'RL-v2'};
rows = {};
smoke = struct();

for i = 1:numel(modelNames)
    params = init_quadrotor_params('standard', 'circle', false);
    params.stopTime = 2.0;

    in = Simulink.SimulationInput(modelNames{i});
    in = in.setModelParameter('StopTime', num2str(params.stopTime));
    in = in.setVariable('quad_model_id', params.modelId);
    in = in.setVariable('quad_scenario_id', params.scenarioId);
    in = in.setVariable('quad_param_vec', params.paramVec);
    in = in.setVariable('quad_x0', params.x0);
    in = in.setVariable('quad_stop_time', params.stopTime);
    out = sim(in);

    parsed = parse_quad_log(out.sim_log, 'standard', 'circle');
    finalErr = parsed.posErrAbs(end);
    maxErr = max(parsed.posErrAbs);
    minRotor = min(parsed.rotorOmega(:));
    maxRotor = max(parsed.rotorOmega(:));
    finiteOk = all(isfinite(parsed.pos(:))) && all(isfinite(parsed.rotorOmega(:)));
    smoke.(modelNames{i}) = parsed;
    rows(end+1, :) = {modelNames{i}, strategyLabels{i}, finiteOk, finalErr, ...
        maxErr, minRotor, maxRotor}; %#ok<AGROW>
end

summary = cell2table(rows, 'VariableNames', {'model_name', 'strategy_label', ...
    'finite_ok', 'final_position_error_m', 'max_position_error_m', ...
    'min_rotor_speed_rad_s', 'max_rotor_speed_rad_s'});
writetable(summary, fullfile(dataDir, 'quadrotor_strategy_model_smoke_tests.csv'));
save(fullfile(dataDir, 'quadrotor_strategy_model_smoke_tests.mat'), 'smoke', 'summary');
end
