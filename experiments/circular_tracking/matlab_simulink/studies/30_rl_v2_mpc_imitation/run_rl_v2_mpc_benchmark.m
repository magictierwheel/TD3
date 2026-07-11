function comparison = run_rl_v2_mpc_benchmark(profile)
%RUN_RL_V2_MPC_BENCHMARK Compare PID/PID-FF/MPC/ADRC/RL-v1/RL-v2.

if nargin < 1 || isempty(profile)
    profile = 'smoke';
end

rootDir = matlab_simulink_root();
commonDir = fullfile(rootDir, 'common');
modelsDir = fullfile(rootDir, 'models');
evidenceDir = fullfile(rootDir, 'evidence', '30_rl_v2_mpc_imitation');
figDir = fullfile(evidenceDir, 'figures');
artifactDataDir = fullfile(rootDir, 'artifacts', '30_rl_v2_mpc_imitation', 'data');
rlDir = fullfile(rootDir, 'evidence', '20_residual_rl_v1', 'policy');
rlV2Dir = fullfile(evidenceDir, 'policy');
if ~exist(evidenceDir, 'dir'), mkdir(evidenceDir); end
if ~exist(figDir, 'dir'), mkdir(figDir); end
if ~exist(artifactDataDir, 'dir'), mkdir(artifactDataDir); end
addpath(commonDir);

policyPath = fullfile(rlDir, 'quadrotor_rl_policy.mat');
if exist(policyPath, 'file') ~= 2
    error('Missing tracked RL-v1 policy evidence: %s', policyPath);
end
policyData = load(policyPath, 'bestWeights');
rlV1Weights = policyData.bestWeights(:);

policyV2Path = fullfile(rlV2Dir, 'quadrotor_rl_v2_policy.mat');
if exist(policyV2Path, 'file') ~= 2
    error('Missing tracked RL-v2 policy evidence: %s', policyV2Path);
end
policyV2Data = load(policyV2Path, 'bestPolicySlots');
rlV2Slots = policyV2Data.bestPolicySlots(:);

build_quadrotor_models();
addpath(modelsDir);

modelTypes = {'standard', 'temperature', 'dust'};
modelNames = {'quadrotor_standard', 'quadrotor_temperature', 'quadrotor_dust'};
modelLabels = {'标准模型', '温度扰动模型', '粉尘扰动模型'};
controllerTypes = {'baseline', 'pid_ff', 'mpc', 'adrc', 'rl', 'rl_v2'};
controllerLabels = {'原PID', 'PID扰动补偿', '线性MPC', 'ADRC', 'RL-v1', 'RL-v2'};

comparison = struct();
metricsRows = {};
for m = 1:numel(modelTypes)
    modelType = modelTypes{m};
    modelName = modelNames{m};
    modelResult = struct();
    for c = 1:numel(controllerTypes)
        controller = controllerTypes{c};
        fprintf('Running RL-v2 benchmark: %s / %s\n', modelType, controller);
        params = init_quadrotor_params(modelType, 'circle', false);
        params = configure_controller(params, controller, rlV1Weights, rlV2Slots);

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

        metric = compute_benchmark_metrics(parsed, params);
        metricsRows(end+1, :) = {modelType, modelLabels{m}, controller, controllerLabels{c}, ...
            metric.rmsPosErr, metric.steadyRmsPosErr, metric.maxPosErr, ...
            metric.finalPosErr, metric.maxAltitudeErr, metric.meanOmega, ...
            metric.maxTiltCommand, metric.meanControlEffort, metric.minRho, ...
            metric.maxDeltaT, metric.maxWind, metric.maxDustCd, metric.minEtaT, ...
            metric.minRotorSpeed, metric.maxRotorSpeed, metric.rotorSaturationRate, ...
            metric.compositeCost}; %#ok<AGROW>
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
    'max_rotor_speed_rad_s', 'rotor_saturation_rate', 'composite_cost'});

save(fullfile(artifactDataDir, 'quadrotor_rl_v2_mpc_benchmark_results.mat'), ...
    'comparison', 'metrics', 'rlV1Weights', 'rlV2Slots');
writetable(metrics, fullfile(evidenceDir, 'quadrotor_rl_v2_mpc_benchmark_metrics.csv'));
write_benchmark_metrics_markdown(metrics, fullfile(evidenceDir, 'quadrotor_rl_v2_mpc_benchmark_metrics.md'));
plot_benchmark_figures(comparison, modelTypes, modelLabels, controllerTypes, controllerLabels, figDir);

fprintf('RL-v2 benchmark finished. Metrics: %s\n', ...
    fullfile(evidenceDir, 'quadrotor_rl_v2_mpc_benchmark_metrics.csv'));
end

function params = configure_controller(params, controller, rlV1Weights, rlV2Slots)
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
        p = enable_quadrotor_rl_policy(p, rlV1Weights, 1.0);
    case 'rl_v2'
        p = enable_quadrotor_rl_v2_policy(p, rlV2Slots, 1.0);
    otherwise
        error('Unknown controller: %s', controller);
end
params.paramVec = p;
end

function metric = compute_benchmark_metrics(out, params)
altitudeErr = out.pos(:, 3) - out.refPos(:, 3);
rotorMean = mean(out.rotorOmega, 2);
rotorDelta = out.omegaCmd - out.rotorOmega;
windSpeed = sqrt(sum(out.wind .* out.wind, 2));
steadyMask = out.t >= 8.0;
omegaMax = params.paramVec(11);
omegaMin = params.paramVec(10);
satMask = any(out.omegaCmd >= 0.995 * omegaMax | out.omegaCmd <= 1.005 * omegaMin, 2);
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
metric.rotorSaturationRate = mean(satMask);
metric.compositeCost = 1.2 * metric.rmsPosErr + 1.5 * metric.steadyRmsPosErr + ...
    0.8 * metric.finalPosErr + 0.6 * metric.maxAltitudeErr + ...
    0.15 * metric.meanControlEffort + 25.0 * max(0.0, metric.maxTiltCommand - 0.35) + ...
    40.0 * metric.rotorSaturationRate;
end

function plot_benchmark_figures(comparison, modelTypes, modelLabels, controllerTypes, controllerLabels, figDir)
colors = [0.78 0.20 0.16; 0.12 0.50 0.24; 0.45 0.22 0.70; ...
    0.88 0.48 0.10; 0.00 0.27 0.56; 0.10 0.58 0.66];

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1420 650]);
for m = 1:numel(modelTypes)
    subplot(1, 3, m);
    ref = comparison.(modelTypes{m}).baseline.refPos;
    plot3(ref(:,1), ref(:,2), ref(:,3), 'k--', 'LineWidth', 1.2); hold on;
    for c = 1:numel(controllerTypes)
        out = comparison.(modelTypes{m}).(controllerTypes{c});
        plot3(out.pos(:,1), out.pos(:,2), out.pos(:,3), ...
            'Color', colors(c,:), 'LineWidth', 1.35);
    end
    grid on; axis equal; view(36, 24);
    xlabel('x / m'); ylabel('y / m'); zlabel('z / m');
    title([modelLabels{m} '圆周轨迹']);
    if m == 1
        legend([{ '参考轨迹' }, controllerLabels], 'Location', 'best');
    end
end
sgtitle('RL-v2 与 MPC 六控制器三维轨迹对比');
print(fig, fullfile(figDir, 'rl_v2_benchmark_trajectory_3d.png'), '-dpng', '-r220');
close(fig);

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1220 920]);
for m = 1:numel(modelTypes)
    subplot(3, 1, m);
    for c = 1:numel(controllerTypes)
        out = comparison.(modelTypes{m}).(controllerTypes{c});
        plot(out.t, out.posErrAbs, 'Color', colors(c,:), 'LineWidth', 1.2); hold on;
    end
    grid on; ylabel('||e_r|| / m');
    title([modelLabels{m} '圆周位置误差']);
    legend(controllerLabels, 'Location', 'best');
    if m == numel(modelTypes)
        xlabel('时间 / s');
    end
end
print(fig, fullfile(figDir, 'rl_v2_benchmark_position_error.png'), '-dpng', '-r220');
close(fig);

[rmsVals, steadyVals, finalVals, effortVals, tiltVals, satVals] = collect_metric_matrices( ...
    comparison, modelTypes, controllerTypes);

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1280 940]);
subplot(3, 1, 1);
bar(categorical(modelLabels), rmsVals); grid on;
ylabel('全程RMS / m'); title('全程 RMS 误差');
legend(controllerLabels, 'Location', 'best');
subplot(3, 1, 2);
bar(categorical(modelLabels), steadyVals); grid on;
ylabel('稳定段RMS / m'); title('8s 后稳定段 RMS');
legend(controllerLabels, 'Location', 'best');
subplot(3, 1, 3);
bar(categorical(modelLabels), finalVals); grid on;
ylabel('终端误差 / m'); xlabel('扰动条件'); title('终端误差');
legend(controllerLabels, 'Location', 'best');
print(fig, fullfile(figDir, 'rl_v2_benchmark_metric_bars.png'), '-dpng', '-r220');
close(fig);

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1250 900]);
subplot(3, 1, 1);
bar(categorical(modelLabels), effortVals); grid on;
ylabel('控制努力'); title('控制努力对比');
legend(controllerLabels, 'Location', 'best');
subplot(3, 1, 2);
bar(categorical(modelLabels), tiltVals); grid on;
ylabel('最大倾角 / rad'); title('最大倾角命令');
legend(controllerLabels, 'Location', 'best');
subplot(3, 1, 3);
bar(categorical(modelLabels), satVals); grid on;
ylabel('饱和率'); xlabel('扰动条件'); title('旋翼命令饱和率');
legend(controllerLabels, 'Location', 'best');
print(fig, fullfile(figDir, 'rl_v2_benchmark_effort_feasibility.png'), '-dpng', '-r220');
close(fig);
end

function [rmsVals, steadyVals, finalVals, effortVals, tiltVals, satVals] = collect_metric_matrices(comparison, modelTypes, controllerTypes)
rmsVals = zeros(numel(modelTypes), numel(controllerTypes));
steadyVals = zeros(numel(modelTypes), numel(controllerTypes));
finalVals = zeros(numel(modelTypes), numel(controllerTypes));
effortVals = zeros(numel(modelTypes), numel(controllerTypes));
tiltVals = zeros(numel(modelTypes), numel(controllerTypes));
satVals = zeros(numel(modelTypes), numel(controllerTypes));
for m = 1:numel(modelTypes)
    for c = 1:numel(controllerTypes)
        out = comparison.(modelTypes{m}).(controllerTypes{c});
        rotorDelta = out.omegaCmd - out.rotorOmega;
        steadyMask = out.t >= 8.0;
        omegaMax = out.params.paramVec(11);
        omegaMin = out.params.paramVec(10);
        satMask = any(out.omegaCmd >= 0.995 * omegaMax | out.omegaCmd <= 1.005 * omegaMin, 2);
        rmsVals(m, c) = sqrt(mean(out.posErrAbs .^ 2));
        steadyVals(m, c) = sqrt(mean(out.posErrAbs(steadyMask) .^ 2));
        finalVals(m, c) = out.posErrAbs(end);
        effortVals(m, c) = mean(sqrt(sum(rotorDelta .* rotorDelta, 2)));
        tiltVals(m, c) = max(out.tiltCmdNorm);
        satVals(m, c) = mean(satMask);
    end
end
end

function write_benchmark_metrics_markdown(metrics, outPath)
fid = fopen(outPath, 'w');
if fid < 0
    error('Cannot write %s', outPath);
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '# RL-v2 vs MPC Benchmark Metrics\n\n');
fprintf(fid, '| Model | Controller | RMS | Steady RMS | Final | Max z | Effort | Max tilt | Saturation | Composite |\n');
fprintf(fid, '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n');
for i = 1:height(metrics)
    fprintf(fid, '| %s | %s | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f |\n', ...
        metrics.model_label{i}, metrics.controller_label{i}, ...
        metrics.rms_position_error_m(i), metrics.steady_rms_position_error_m(i), ...
        metrics.final_position_error_m(i), metrics.max_altitude_error_m(i), ...
        metrics.mean_control_effort_rad_s(i), metrics.max_tilt_command_rad(i), ...
        metrics.rotor_saturation_rate(i), metrics.composite_cost(i));
end
end
