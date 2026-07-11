function comparison = run_rl_circle_comparison()
%RUN_RL_CIRCLE_COMPARISON Compare baseline and RL policy on circular tracking.
%   Uses Simulink.SimulationInput for every run and writes metrics, MAT data,
%   and Chinese-titled figures under results/.

rootDir = fileparts(fileparts(mfilename('fullpath')));
scriptsDir = fullfile(rootDir, 'scripts');
modelsDir = fullfile(rootDir, 'models');
dataDir = fullfile(rootDir, 'results', 'data');
figDir = fullfile(rootDir, 'results', 'figures');
rlDir = fullfile(rootDir, 'results', 'policies', 'rl_v1');
if ~exist(dataDir, 'dir'), mkdir(dataDir); end
if ~exist(figDir, 'dir'), mkdir(figDir); end
if ~exist(rlDir, 'dir'), mkdir(rlDir); end
addpath(scriptsDir);

policyPath = fullfile(rlDir, 'quadrotor_rl_policy.mat');
if exist(policyPath, 'file') ~= 2
    train_quadrotor_rl_policy();
end
policyData = load(policyPath, 'bestWeights');
weights = policyData.bestWeights(:);

build_quadrotor_models();
addpath(modelsDir);

modelTypes = {'standard', 'temperature', 'dust'};
modelNames = {'quadrotor_standard', 'quadrotor_temperature', 'quadrotor_dust'};
modelLabels = {'标准模型', '温度扰动模型', '粉尘扰动模型'};
controllerTypes = {'baseline', 'rl'};
controllerLabels = {'原控制器', '强化学习策略'};

comparison = struct();
metricsRows = {};
for m = 1:numel(modelTypes)
    modelType = modelTypes{m};
    modelName = modelNames{m};
    modelResult = struct();
    for c = 1:numel(controllerTypes)
        controller = controllerTypes{c};
        fprintf('Running circle comparison: %s / %s\n', modelType, controller);
        params = init_quadrotor_params(modelType, 'circle', false);
        if strcmp(controller, 'rl')
            params = enable_quadrotor_rl_policy(params, weights, 1.0);
        end

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

        metric = compute_rl_metrics(parsed);
        metricsRows(end+1, :) = {modelType, modelLabels{m}, controller, controllerLabels{c}, ...
            metric.rmsPosErr, metric.steadyRmsPosErr, metric.maxPosErr, metric.finalPosErr, metric.maxAltitudeErr, ...
            metric.meanOmega, metric.maxTiltCommand, metric.meanControlEffort, ...
            metric.minRho, metric.maxDeltaT, metric.maxWind, metric.maxDustCd, metric.minEtaT}; %#ok<AGROW>
    end
    comparison.(modelType) = modelResult;
end

metrics = cell2table(metricsRows, 'VariableNames', { ...
    'model_type', 'model_label', 'controller_type', 'controller_label', ...
    'rms_position_error_m', 'steady_rms_position_error_m', 'max_position_error_m', 'final_position_error_m', ...
    'max_altitude_error_m', 'mean_rotor_speed_rad_s', 'max_tilt_command_rad', ...
    'mean_control_effort_rad_s', 'min_air_density_kg_m3', 'max_temperature_rise_K', ...
    'max_wind_speed_m_s', 'max_dust_concentration_kg_m3', 'min_eta_T'});

save(fullfile(dataDir, 'quadrotor_rl_circle_comparison_results.mat'), ...
    'comparison', 'metrics', 'weights');
writetable(metrics, fullfile(dataDir, 'quadrotor_rl_circle_comparison_metrics.csv'));
write_rl_metrics_markdown(metrics, fullfile(dataDir, 'quadrotor_rl_circle_comparison_metrics.md'));
plot_rl_figures(comparison, modelTypes, modelLabels, figDir);

fprintf('RL comparison finished. Metrics: %s\n', ...
    fullfile(dataDir, 'quadrotor_rl_circle_comparison_metrics.csv'));
end

function metric = compute_rl_metrics(out)
altitudeErr = out.pos(:, 3) - out.refPos(:, 3);
rotorMean = mean(out.rotorOmega, 2);
rotorDelta = out.omegaCmd - out.rotorOmega;
windSpeed = sqrt(sum(out.wind .* out.wind, 2));
metric = struct();
metric.rmsPosErr = sqrt(mean(out.posErrAbs .^ 2));
steadyMask = out.t >= 8.0;
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
end

function plot_rl_figures(comparison, modelTypes, modelLabels, figDir)
colors = [0.78 0.20 0.16; 0.00 0.27 0.56];

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1220 820]);
plot3(comparison.standard.baseline.refPos(:,1), comparison.standard.baseline.refPos(:,2), ...
    comparison.standard.baseline.refPos(:,3), 'k--', 'LineWidth', 1.4); hold on;
for m = 1:numel(modelTypes)
    baseOut = comparison.(modelTypes{m}).baseline;
    rlOut = comparison.(modelTypes{m}).rl;
    plot3(baseOut.pos(:,1), baseOut.pos(:,2), baseOut.pos(:,3), ':', ...
        'Color', [0.65 0.65 0.65], 'LineWidth', 1.1);
    plot3(rlOut.pos(:,1), rlOut.pos(:,2), rlOut.pos(:,3), 'LineWidth', 1.8);
end
grid on; axis equal; view(36, 24);
xlabel('x / m'); ylabel('y / m'); zlabel('z / m');
title('匀速圆周轨迹：原控制器与强化学习策略对比');
legend({'参考轨迹', '原控制器轨迹', '强化学习策略轨迹'}, 'Location', 'best');
print(fig, fullfile(figDir, 'rl_circle_trajectory_3d.png'), '-dpng', '-r220');
close(fig);

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1180 900]);
for m = 1:numel(modelTypes)
    subplot(3, 1, m);
    baseOut = comparison.(modelTypes{m}).baseline;
    rlOut = comparison.(modelTypes{m}).rl;
    plot(baseOut.t, baseOut.posErrAbs, 'Color', colors(1, :), 'LineWidth', 1.4); hold on;
    plot(rlOut.t, rlOut.posErrAbs, 'Color', colors(2, :), 'LineWidth', 1.4);
    grid on; ylabel('||e_r|| / m');
    title([modelLabels{m} '圆周位置误差对比']);
    legend({'原控制器', '强化学习策略'}, 'Location', 'best');
    if m == numel(modelTypes)
        xlabel('时间 / s');
    end
end
print(fig, fullfile(figDir, 'rl_circle_position_error.png'), '-dpng', '-r220');
close(fig);

rmsVals = zeros(numel(modelTypes), 2);
maxVals = zeros(numel(modelTypes), 2);
for m = 1:numel(modelTypes)
    rmsVals(m, 1) = sqrt(mean(comparison.(modelTypes{m}).baseline.posErrAbs .^ 2));
    rmsVals(m, 2) = sqrt(mean(comparison.(modelTypes{m}).rl.posErrAbs .^ 2));
    maxVals(m, 1) = max(comparison.(modelTypes{m}).baseline.posErrAbs);
    maxVals(m, 2) = max(comparison.(modelTypes{m}).rl.posErrAbs);
end

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1080 760]);
subplot(2, 1, 1);
bar(categorical(modelLabels), rmsVals);
grid on; ylabel('RMS 误差 / m');
title('匀速圆周抗扰 RMS 误差对比');
legend({'原控制器', '强化学习策略'}, 'Location', 'best');
subplot(2, 1, 2);
bar(categorical(modelLabels), maxVals);
grid on; ylabel('最大误差 / m');
xlabel('扰动条件');
title('匀速圆周抗扰最大误差对比');
legend({'原控制器', '强化学习策略'}, 'Location', 'best');
print(fig, fullfile(figDir, 'rl_circle_metric_improvement.png'), '-dpng', '-r220');
close(fig);
end

function write_rl_metrics_markdown(metrics, outPath)
fid = fopen(outPath, 'w');
if fid < 0
    error('Cannot write %s', outPath);
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '# RL Circle Tracking Comparison Metrics\n\n');
fprintf(fid, '| Model | Controller | RMS error (m) | Steady RMS 8s+ (m) | Max error (m) | Final error (m) | Max z error (m) | Mean omega | Max tilt | min rho | max dT | max cd | min etaT |\n');
fprintf(fid, '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n');
for i = 1:height(metrics)
    fprintf(fid, '| %s | %s | %.4f | %.4f | %.4f | %.4f | %.4f | %.2f | %.4f | %.4f | %.2f | %.5f | %.4f |\n', ...
        metrics.model_label{i}, metrics.controller_label{i}, ...
        metrics.rms_position_error_m(i), metrics.steady_rms_position_error_m(i), ...
        metrics.max_position_error_m(i), ...
        metrics.final_position_error_m(i), metrics.max_altitude_error_m(i), ...
        metrics.mean_rotor_speed_rad_s(i), metrics.max_tilt_command_rad(i), ...
        metrics.min_air_density_kg_m3(i), metrics.max_temperature_rise_K(i), ...
        metrics.max_dust_concentration_kg_m3(i), metrics.min_eta_T(i));
end
end
