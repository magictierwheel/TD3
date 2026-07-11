function comparison = run_strategy_circle_comparison()
%RUN_STRATEGY_CIRCLE_COMPARISON Compare PID, PID+FF, MPC, ADRC, and RL.
%   Runs 3 environment models x 5 controllers using Simulink.SimulationInput.

rootDir = matlab_simulink_root();
commonDir = fullfile(rootDir, 'common');
modelsDir = fullfile(rootDir, 'models');
evidenceDir = fullfile(rootDir, 'evidence', '10_controller_comparison');
figDir = fullfile(evidenceDir, 'figures');
artifactDataDir = fullfile(rootDir, 'artifacts', '10_controller_comparison', 'data');
policyDir = fullfile(rootDir, 'evidence', '20_residual_rl_v1', 'policy');
if ~exist(evidenceDir, 'dir'), mkdir(evidenceDir); end
if ~exist(figDir, 'dir'), mkdir(figDir); end
if ~exist(artifactDataDir, 'dir'), mkdir(artifactDataDir); end
addpath(commonDir);

policyPath = fullfile(policyDir, 'quadrotor_rl_policy.mat');
if exist(policyPath, 'file') ~= 2
    error('Missing tracked RL-v1 policy evidence: %s', policyPath);
end
policyData = load(policyPath, 'bestWeights');
weights = policyData.bestWeights(:);

build_quadrotor_models();
addpath(modelsDir);

modelTypes = {'standard', 'temperature', 'dust'};
modelNames = {'quadrotor_standard', 'quadrotor_temperature', 'quadrotor_dust'};
modelLabels = {'标准模型', '温度扰动模型', '粉尘扰动模型'};
controllerTypes = {'baseline', 'pid_ff', 'mpc', 'adrc', 'rl'};
controllerLabels = {'原PID', 'PID扰动补偿', '线性MPC', 'ADRC', '强化学习策略'};

comparison = struct();
metricsRows = {};
for m = 1:numel(modelTypes)
    modelType = modelTypes{m};
    modelName = modelNames{m};
    modelResult = struct();
    for c = 1:numel(controllerTypes)
        controller = controllerTypes{c};
        fprintf('Running strategy comparison: %s / %s\n', modelType, controller);
        params = init_quadrotor_params(modelType, 'circle', false);
        params = configure_controller(params, controller, weights);

        in = Simulink.SimulationInput(modelName);
        in = in.setModelParameter('StopTime', num2str(params.stopTime));
        in = in.setVariable('quad_model_id', params.modelId);
        in = in.setVariable('quad_scenario_id', params.scenarioId);
        in = in.setVariable('quad_param_vec', params.paramVec);
        in = in.setVariable('quad_x0', params.x0);
        in = in.setVariable('quad_stop_time', params.stopTime);
        in = in.setVariable('quad_model_label', params.modelLabel);
        in = in.setVariable('quad_scenario_label', params.scenarioLabel);
        out = sim(in);

        parsed = parse_quad_log(out.sim_log, modelType, 'circle');
        parsed.modelLabel = modelLabels{m};
        parsed.controllerType = controller;
        parsed.controllerLabel = controllerLabels{c};
        parsed.params = params;
        modelResult.(controller) = parsed;

        metric = compute_strategy_metrics(parsed);
        metricsRows(end+1, :) = {modelType, modelLabels{m}, controller, controllerLabels{c}, ...
            metric.rmsPosErr, metric.steadyRmsPosErr, metric.maxPosErr, ...
            metric.finalPosErr, metric.maxAltitudeErr, metric.meanOmega, ...
            metric.maxTiltCommand, metric.meanControlEffort, metric.minRho, ...
            metric.maxDeltaT, metric.maxWind, metric.maxDustCd, metric.minEtaT, ...
            metric.minRotorSpeed, metric.maxRotorSpeed}; %#ok<AGROW>
    end
    comparison.(modelType) = modelResult;
end

metrics = cell2table(metricsRows, 'VariableNames', { ...
    'model_type', 'model_label', 'controller_type', 'controller_label', ...
    'rms_position_error_m', 'steady_rms_position_error_m', ...
    'max_position_error_m', 'final_position_error_m', 'max_altitude_error_m', ...
    'mean_rotor_speed_rad_s', 'max_tilt_command_rad', 'mean_control_effort_rad_s', ...
    'min_air_density_kg_m3', 'max_temperature_rise_K', 'max_wind_speed_m_s', ...
    'max_dust_concentration_kg_m3', 'min_eta_T', 'min_rotor_speed_rad_s', ...
    'max_rotor_speed_rad_s'});

save(fullfile(artifactDataDir, 'quadrotor_strategy_circle_comparison_results.mat'), ...
    'comparison', 'metrics', 'weights');
writetable(metrics, fullfile(evidenceDir, 'quadrotor_strategy_circle_comparison_metrics.csv'));
write_strategy_metrics_markdown(metrics, fullfile(evidenceDir, 'quadrotor_strategy_circle_comparison_metrics.md'));
plot_strategy_figures(comparison, modelTypes, modelLabels, controllerTypes, controllerLabels, figDir);

fprintf('Strategy comparison finished. Metrics: %s\n', ...
    fullfile(evidenceDir, 'quadrotor_strategy_circle_comparison_metrics.csv'));
end

function params = configure_controller(params, controller, weights)
p = params.paramVec;
p(88) = params.scenarioId;
p(90) = params.modelId;
p(97) = 1.0;
switch controller
    case 'baseline'
        p(89) = 0;
    case 'pid_ff'
        p(89) = 2;
    case 'mpc'
        p(89) = 3;
    case 'adrc'
        p(89) = 4;
    case 'rl'
        p = enable_quadrotor_rl_policy(p, weights, 1.0);
    otherwise
        error('Unknown controller: %s', controller);
end
params.paramVec = p;
end

function metric = compute_strategy_metrics(out)
altitudeErr = out.pos(:, 3) - out.refPos(:, 3);
rotorMean = mean(out.rotorOmega, 2);
rotorDelta = out.omegaCmd - out.rotorOmega;
windSpeed = sqrt(sum(out.wind .* out.wind, 2));
steadyMask = out.t >= 8.0;
metric = struct();
metric.rmsPosErr = sqrt(mean(out.posErrAbs .^ 2));
metric.steadyRmsPosErr = sqrt(mean(out.posErrAbs(steadyMask) .^ 2));
metric.maxPosErr = max(out.posErrAbs);
metric.finalPosErr = out.posErrAbs(end);
metric.maxAltitudeErr = max(abs(altitudeErr));
metric.meanOmega = mean(rotorMean);
metric.maxTiltCommand = max(out.tiltCmdNorm);
metric.meanControlEffort = mean(sqrt(sum(rotorDelta .* rotorDelta, 2)));
metric.minRho = min(out.rho);
metric.maxDeltaT = max(out.deltaT);
metric.maxWind = max(windSpeed);
metric.maxDustCd = max(out.dustCd);
metric.minEtaT = min(out.etaT);
metric.minRotorSpeed = min(out.rotorOmega(:));
metric.maxRotorSpeed = max(out.rotorOmega(:));
end

function plot_strategy_figures(comparison, modelTypes, modelLabels, controllerTypes, controllerLabels, figDir)
colors = [0.78 0.20 0.16; 0.12 0.50 0.24; 0.45 0.22 0.70; ...
    0.88 0.48 0.10; 0.00 0.27 0.56];
lineStyles = {'-', '-', '-', '-', '-'};

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1380 620]);
for m = 1:numel(modelTypes)
    subplot(1, 3, m);
    ref = comparison.(modelTypes{m}).baseline.refPos;
    plot3(ref(:,1), ref(:,2), ref(:,3), 'k--', 'LineWidth', 1.2); hold on;
    for c = 1:numel(controllerTypes)
        out = comparison.(modelTypes{m}).(controllerTypes{c});
        plot3(out.pos(:,1), out.pos(:,2), out.pos(:,3), ...
            'Color', colors(c,:), 'LineStyle', lineStyles{c}, 'LineWidth', 1.4);
    end
    grid on; axis equal; view(36, 24);
    xlabel('x / m'); ylabel('y / m'); zlabel('z / m');
    title([modelLabels{m} '圆周轨迹']);
    if m == 1
        legend([{ '参考轨迹' }, controllerLabels], 'Location', 'best');
    end
end
set_figure_title('多控制策略匀速圆周三维轨迹对比');
print(fig, fullfile(figDir, 'strategy_circle_trajectory_3d.png'), '-dpng', '-r220');
close(fig);

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1180 900]);
for m = 1:numel(modelTypes)
    subplot(3, 1, m);
    for c = 1:numel(controllerTypes)
        out = comparison.(modelTypes{m}).(controllerTypes{c});
        plot(out.t, out.posErrAbs, 'Color', colors(c,:), 'LineWidth', 1.3); hold on;
    end
    grid on; ylabel('||e_r|| / m');
    title([modelLabels{m} '圆周位置误差对比']);
    legend(controllerLabels, 'Location', 'best');
    if m == numel(modelTypes)
        xlabel('时间 / s');
    end
end
print(fig, fullfile(figDir, 'strategy_circle_position_error.png'), '-dpng', '-r220');
close(fig);

[rmsVals, steadyVals, finalVals, altitudeVals, effortVals] = collect_metric_matrices( ...
    comparison, modelTypes, controllerTypes);

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1280 920]);
subplot(3, 1, 1);
bar(categorical(modelLabels), rmsVals);
grid on; ylabel('全程RMS / m'); title('匀速圆周全程 RMS 误差对比');
legend(controllerLabels, 'Location', 'best');
subplot(3, 1, 2);
bar(categorical(modelLabels), steadyVals);
grid on; ylabel('稳定段RMS / m'); title('匀速圆周 8 s 后稳定段 RMS 误差对比');
legend(controllerLabels, 'Location', 'best');
subplot(3, 1, 3);
bar(categorical(modelLabels), finalVals);
grid on; ylabel('终端误差 / m'); xlabel('扰动条件');
title('匀速圆周终端误差对比');
legend(controllerLabels, 'Location', 'best');
print(fig, fullfile(figDir, 'strategy_circle_metric_bars.png'), '-dpng', '-r220');
close(fig);

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1180 780]);
subplot(2, 1, 1);
bar(categorical(modelLabels), effortVals);
grid on; ylabel('平均控制努力 / rad s^{-1}');
title('匀速圆周控制努力对比');
legend(controllerLabels, 'Location', 'best');
subplot(2, 1, 2);
bar(categorical(modelLabels), altitudeVals);
grid on; ylabel('最大高度误差 / m'); xlabel('扰动条件');
title('匀速圆周最大高度误差对比');
legend(controllerLabels, 'Location', 'best');
print(fig, fullfile(figDir, 'strategy_circle_effort_altitude.png'), '-dpng', '-r220');
close(fig);
end

function [rmsVals, steadyVals, finalVals, altitudeVals, effortVals] = collect_metric_matrices(comparison, modelTypes, controllerTypes)
rmsVals = zeros(numel(modelTypes), numel(controllerTypes));
steadyVals = zeros(numel(modelTypes), numel(controllerTypes));
finalVals = zeros(numel(modelTypes), numel(controllerTypes));
altitudeVals = zeros(numel(modelTypes), numel(controllerTypes));
effortVals = zeros(numel(modelTypes), numel(controllerTypes));
for m = 1:numel(modelTypes)
    for c = 1:numel(controllerTypes)
        out = comparison.(modelTypes{m}).(controllerTypes{c});
        altitudeErr = out.pos(:, 3) - out.refPos(:, 3);
        rotorDelta = out.omegaCmd - out.rotorOmega;
        steadyMask = out.t >= 8.0;
        rmsVals(m, c) = sqrt(mean(out.posErrAbs .^ 2));
        steadyVals(m, c) = sqrt(mean(out.posErrAbs(steadyMask) .^ 2));
        finalVals(m, c) = out.posErrAbs(end);
        altitudeVals(m, c) = max(abs(altitudeErr));
        effortVals(m, c) = mean(sqrt(sum(rotorDelta .* rotorDelta, 2)));
    end
end
end

function write_strategy_metrics_markdown(metrics, outPath)
fid = fopen(outPath, 'w');
if fid < 0
    error('Cannot write %s', outPath);
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '# Multi-Controller Circle Tracking Comparison Metrics\n\n');
fprintf(fid, '| Model | Controller | RMS error (m) | Steady RMS 8s+ (m) | Max error (m) | Final error (m) | Max z error (m) | Mean omega | Max tilt | Effort | min rho | max dT | max cd | min etaT |\n');
fprintf(fid, '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n');
for i = 1:height(metrics)
    fprintf(fid, '| %s | %s | %.4f | %.4f | %.4f | %.4f | %.4f | %.2f | %.4f | %.4f | %.4f | %.2f | %.5f | %.4f |\n', ...
        metrics.model_label{i}, metrics.controller_label{i}, ...
        metrics.rms_position_error_m(i), metrics.steady_rms_position_error_m(i), ...
        metrics.max_position_error_m(i), metrics.final_position_error_m(i), ...
        metrics.max_altitude_error_m(i), metrics.mean_rotor_speed_rad_s(i), ...
        metrics.max_tilt_command_rad(i), metrics.mean_control_effort_rad_s(i), ...
        metrics.min_air_density_kg_m3(i), metrics.max_temperature_rise_K(i), ...
        metrics.max_dust_concentration_kg_m3(i), metrics.min_eta_T(i));
end
end

function set_figure_title(text)
if exist('sgtitle', 'file') == 2
    sgtitle(text);
else
    axesHandles = findall(gcf, 'Type', 'axes');
    if ~isempty(axesHandles)
        title(axesHandles(end), text);
    end
end
end
