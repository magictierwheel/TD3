function training = train_quadrotor_rl_v2_policy(trainProfile)
%TRAIN_QUADROTOR_RL_V2_POLICY Train the preview residual RL-v2 policy.
%   TRAIN_QUADROTOR_RL_V2_POLICY('official') runs the 40x40 candidate plan.
%   The default 'quick' profile is intended for development and verification.

if nargin < 1
    trainProfile = 'quick';
end
if isempty(trainProfile)
    trainProfile = 'quick';
end
trainProfile = lower(strtrim(trainProfile));

rootDir = fileparts(fileparts(mfilename('fullpath')));
scriptsDir = fullfile(rootDir, 'scripts');
rlDir = fullfile(rootDir, 'results', 'policies', 'rl_v2');
dataDir = fullfile(rootDir, 'results', 'data');
if ~exist(rlDir, 'dir'), mkdir(rlDir); end
if ~exist(dataDir, 'dir'), mkdir(dataDir); end
addpath(scriptsDir);

rng(20260627);
startWallClock = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
trainingTimer = tic;

switch trainProfile
    case 'smoke'
        numIterations = 2;
        popSize = 8;
        eliteCount = 3;
    case 'quick'
        numIterations = 20;
        popSize = 30;
        eliteCount = 8;
    case 'official'
        numIterations = 40;
        popSize = 40;
        eliteCount = 10;
    otherwise
        error('Unknown RL-v2 training profile: %s', trainProfile);
end

modelTypes = {'standard', 'temperature', 'dust'};
modelWeights = [0.50, 1.40, 0.85];
mpcMetrics = benchmark_mpc(modelTypes);
imitation = create_quadrotor_rl_v2_imitation_dataset(modelTypes);
[imitationSlots, imitationFit] = fit_quadrotor_rl_v2_readout( ...
    imitation.hidden, imitation.targets, imitation.gates, 1e-4);
if imitationFit.nonzeroWeightCount < 60
    error('RLV2:UntrainedReadout', ...
        'Behavior cloning produced only %d nonzero readout weights.', ...
        imitationFit.nonzeroWeightCount);
end
progressFig = init_progress_figure(trainProfile, modelTypes, mpcMetrics);

lowerBounds = [0.00, 0.00, 0.75, -0.25, -0.25, -0.25, -0.25, -0.25, 0.70, 0.70, 0.70];
upperBounds = [0.25, 0.25, 1.25,  0.25,  0.25,  0.25,  0.25,  0.25, 1.30, 1.30, 1.30];
mu = [0.05, 0.05, 1.00, 0.00, 0.00, 0.00, 0.00, 0.00, 1.00, 1.00, 1.00];
sigma = [0.05, 0.05, 0.10, 0.05, 0.05, 0.05, 0.04, 0.04, 0.08, 0.08, 0.08];

bestCost = inf;
bestGenes = mu;
bestPolicySlots = materialize_genes(imitationSlots, mu);
iterationWallSeconds = zeros(numIterations, 1);
logRows = {};

for iter = 1:numIterations
    iterTimer = tic;
    candidates = zeros(popSize, numel(mu));
    candidates(1, :) = mu;
    candidates(2, :) = [0.00, 0.00, 1.00, 0, 0, 0, 0, 0, 1.00, 1.00, 1.00];
    candidates(3, :) = [0.10, 0.05, 0.95, 0, 0, 0, 0, 0, 1.00, 1.00, 1.00];
    candidates(4, :) = [0.05, 0.10, 1.05, 0, 0, 0, 0, 0, 1.00, 1.00, 1.00];
    for k = 5:popSize
        candidates(k, :) = mu + sigma .* randn(1, numel(mu));
    end
    candidates = min(max(candidates, lowerBounds), upperBounds);

    costs = zeros(popSize, 1);
    rmsByModel = zeros(popSize, numel(modelTypes));
    steadyByModel = zeros(popSize, numel(modelTypes));
    effortByModel = zeros(popSize, numel(modelTypes));

    for k = 1:popSize
        candidateTimer = tic;
        slots = materialize_genes(imitationSlots, candidates(k, :));
        [costs(k), metrics] = evaluate_candidate(slots, modelTypes, modelWeights, mpcMetrics);
        candidateElapsed = toc(candidateTimer);
        for m = 1:numel(modelTypes)
            rmsByModel(k, m) = metrics(m).rmsError;
            steadyByModel(k, m) = metrics(m).steadyRmsError;
            effortByModel(k, m) = metrics(m).controlEffort;
        end
        update_progress_figure(progressFig, trainProfile, iter, numIterations, k, popSize, ...
            costs(k), bestCost, metrics, mpcMetrics, toc(trainingTimer));
        logRows(end+1, :) = {iter, k, candidateElapsed, costs(k), ...
            candidates(k, 1), candidates(k, 2), candidates(k, 3), ...
            candidates(k, 4), candidates(k, 5), candidates(k, 6), ...
            candidates(k, 7), candidates(k, 8), candidates(k, 9), ...
            candidates(k, 10), candidates(k, 11), ...
            rmsByModel(k, 1), rmsByModel(k, 2), rmsByModel(k, 3), ...
            steadyByModel(k, 1), steadyByModel(k, 2), steadyByModel(k, 3), ...
            effortByModel(k, 1), effortByModel(k, 2), effortByModel(k, 3)}; %#ok<AGROW>
    end

    [sortedCosts, order] = sort(costs, 'ascend');
    elites = candidates(order(1:eliteCount), :);
    mu = mean(elites, 1);
    sigma = max(std(elites, 0, 1), 0.015);

    if sortedCosts(1) < bestCost
        bestCost = sortedCosts(1);
        bestGenes = candidates(order(1), :);
        bestPolicySlots = materialize_genes(imitationSlots, bestGenes);
    end
    update_progress_figure(progressFig, trainProfile, iter, numIterations, popSize, popSize, ...
        sortedCosts(1), bestCost, evaluate_policy_metrics(bestPolicySlots, modelTypes), ...
        mpcMetrics, toc(trainingTimer));

    fprintf('RL-v2 %s iter %d/%d best cost %.6f genes [%s]\n', ...
        trainProfile, iter, numIterations, bestCost, sprintf(' %.3f', bestGenes));
    iterationWallSeconds(iter) = toc(iterTimer);
end

endWallClock = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
elapsedWallSeconds = toc(trainingTimer);
bestMetrics = evaluate_policy_metrics(bestPolicySlots, modelTypes);

training = struct();
training.algorithm = 'MPC-imitation-initialized CEM direct policy search';
training.profile = trainProfile;
training.seed = 20260627;
training.bestCost = bestCost;
training.bestGenes = bestGenes;
training.bestPolicySlots = bestPolicySlots;
training.modelTypes = modelTypes;
training.modelWeights = modelWeights;
training.mpcMetrics = mpcMetrics;
training.bestMetrics = bestMetrics;
training.imitationFit = imitationFit;
training.startWallClock = char(startWallClock);
training.endWallClock = char(endWallClock);
training.elapsedWallSeconds = elapsedWallSeconds;
training.iterationWallSeconds = iterationWallSeconds;

logTable = cell2table(logRows, 'VariableNames', { ...
    'iteration', 'candidate', 'candidate_wall_seconds', 'cost', ...
    'preview_blend', 'feedforward_blend', 'learned_blend', ...
    'bias_ax', 'bias_ay', 'bias_az', 'bias_thrust', 'bias_tau', ...
    'acc_scale', 'thrust_scale', 'tau_scale', ...
    'rms_standard_m', 'rms_temperature_m', 'rms_dust_m', ...
    'steady_standard_m', 'steady_temperature_m', 'steady_dust_m', ...
    'effort_standard', 'effort_temperature', 'effort_dust'});

save(fullfile(rlDir, 'quadrotor_rl_v2_policy.mat'), ...
    'bestPolicySlots', 'bestGenes', 'bestCost', 'training');
save(fullfile(dataDir, 'quadrotor_rl_v2_mpc_imitation_data.mat'), 'imitation');
writetable(logTable, fullfile(dataDir, 'quadrotor_rl_v2_training_log.csv'));
write_summary(rootDir, training, logTable);
end

function [cost, metrics] = evaluate_candidate(policySlots, modelTypes, modelWeights, mpcMetrics)
metrics = evaluate_policy_metrics(policySlots, modelTypes);
cost = 0;
for i = 1:numel(modelTypes)
    m = metrics(i);
    b = mpcMetrics(i);
    baseCost = 1.2 * m.rmsError + 1.5 * m.steadyRmsError + ...
        0.8 * m.finalError + 0.6 * m.maxAltitudeError + ...
        0.15 * m.controlEffort + m.saturationPenalty + m.tiltPenalty + ...
        m.unstablePenalty;
    worsePenalty = 22.0 * max(0.0, m.rmsError - b.rmsError) + ...
        18.0 * max(0.0, m.steadyRmsError - b.steadyRmsError) + ...
        8.0 * max(0.0, m.finalError - 1.10 * b.finalError) + ...
        3.0 * max(0.0, m.controlEffort - 1.20 * b.controlEffort);
    if strcmp(modelTypes{i}, 'temperature')
        worsePenalty = worsePenalty + 35.0 * max(0.0, m.rmsError - 0.0877);
    end
    cost = cost + modelWeights(i) * (baseCost + worsePenalty);
end
end

function metrics = evaluate_policy_metrics(policySlots, modelTypes)
metrics = repmat(empty_metric(), 1, numel(modelTypes));
for i = 1:numel(modelTypes)
    metrics(i) = rollout_metric(modelTypes{i}, 'rl_v2', policySlots);
end
end

function metrics = benchmark_mpc(modelTypes)
metrics = repmat(empty_metric(), 1, numel(modelTypes));
for i = 1:numel(modelTypes)
    metrics(i) = rollout_metric(modelTypes{i}, 'mpc', []);
end
end

function metric = rollout_metric(modelType, controller, policySlots)
params = init_quadrotor_params(modelType, 'circle', false);
p = params.paramVec;
p(88) = params.scenarioId;
p(90) = params.modelId;
p(97) = 1.0;
switch controller
    case 'mpc'
        p(89) = 3;
    case 'rl_v2'
        p = enable_quadrotor_rl_v2_policy(p, policySlots, 1.0);
    otherwise
        error('Unknown controller: %s', controller);
end

dt = 0.02;
n = round(params.stopTime / dt);
x = params.x0;
err = zeros(n + 1, 1);
altErr = zeros(n + 1, 1);
tiltCmd = zeros(n + 1, 1);
omegaCmdLog = zeros(n + 1, 4);
rotorLog = zeros(n + 1, 4);
unstablePenalty = 0;

for k = 1:n+1
    t = (k - 1) * dt;
    ref = quadrotor_reference_core(t, params.scenarioId, p);
    [omegaCmd, ctrlDbg] = quadrotor_controller_core(t, x, ref, p);
    posErr = x(1:3) - ref(1:3);
    err(k) = sqrt(sum(posErr .* posErr));
    altErr(k) = posErr(3);
    tiltCmd(k) = ctrlDbg(10);
    omegaCmdLog(k, :) = omegaCmd.';
    rotorLog(k, :) = x(16:19).';
    if any(~isfinite(x)) || any(~isfinite(omegaCmd)) || abs(x(3)) > 8.0 || ...
            sqrt(x(7) * x(7) + x(8) * x(8)) > 0.85
        unstablePenalty = unstablePenalty + 50.0;
        err = err(1:k);
        altErr = altErr(1:k);
        tiltCmd = tiltCmd(1:k);
        omegaCmdLog = omegaCmdLog(1:k, :);
        rotorLog = rotorLog(1:k, :);
        break;
    end
    if k <= n
        x = rk4_step(t, x, dt, params.scenarioId, params.modelId, p);
    end
end

steadyMask = ((0:numel(err)-1).' * dt) >= 8.0;
if ~any(steadyMask)
    steadyMask = true(size(err));
end
rotorDelta = omegaCmdLog - rotorLog;
omegaMin = p(10);
omegaMax = p(11);
satHigh = max(omegaCmdLog - 0.995 * omegaMax, 0.0) / omegaMax;
satLow = max(1.005 * omegaMin - omegaCmdLog, 0.0) / omegaMax;

metric = empty_metric();
metric.rmsError = sqrt(mean(err .* err));
metric.steadyRmsError = sqrt(mean(err(steadyMask) .* err(steadyMask)));
metric.maxError = max(err);
metric.finalError = err(end);
metric.maxAltitudeError = max(abs(altErr));
metric.maxTiltCommand = max(tiltCmd);
metric.controlEffort = mean(sqrt(sum(rotorDelta .* rotorDelta, 2)));
metric.minRotorSpeed = min(rotorLog(:));
metric.maxRotorSpeed = max(rotorLog(:));
metric.saturationPenalty = 40.0 * mean(satHigh(:) + satLow(:));
metric.tiltPenalty = 25.0 * max(0.0, metric.maxTiltCommand - 0.35);
metric.unstablePenalty = unstablePenalty;
end

function metric = empty_metric()
metric = struct('rmsError', 0, 'steadyRmsError', 0, 'maxError', 0, ...
    'finalError', 0, 'maxAltitudeError', 0, 'maxTiltCommand', 0, ...
    'controlEffort', 0, 'minRotorSpeed', 0, 'maxRotorSpeed', 0, ...
    'saturationPenalty', 0, 'tiltPenalty', 0, 'unstablePenalty', 0);
end

function slots = materialize_genes(baseSlots, genes)
slots = baseSlots(:);
slots(94) = genes(1);
slots(100) = genes(2);
slots(95) = genes(3);
slots(84:88) = baseSlots(84:88) + genes(4:8).';
slots(96) = genes(9);
slots(97) = genes(10);
slots(98) = genes(11);
end

function progress = init_progress_figure(profile, modelTypes, mpcMetrics)
progress = struct('fig', [], 'axCost', [], 'axRms', [], 'axSteady', [], 'axInfo', []);
try
    fig = figure('Name', 'RL-v2 Training Progress', 'NumberTitle', 'off', ...
        'Color', 'w', 'Visible', 'on', 'Position', [120 120 1180 760]);
    layout = tiledlayout(fig, 2, 2, 'Padding', 'compact', 'TileSpacing', 'compact');
    progress.fig = fig;
    progress.axCost = nexttile(layout, 1);
    progress.axRms = nexttile(layout, 2);
    progress.axSteady = nexttile(layout, 3);
    progress.axInfo = nexttile(layout, 4);
    setappdata(fig, 'bestCostHistory', []);
    setappdata(fig, 'modelTypes', modelTypes);
    setappdata(fig, 'mpcRms', [mpcMetrics.rmsError]);
    setappdata(fig, 'mpcSteady', [mpcMetrics.steadyRmsError]);
    setappdata(fig, 'profile', profile);
    axis(progress.axInfo, 'off');
    text(progress.axInfo, 0.03, 0.90, sprintf('RL-v2 training profile: %s', profile), ...
        'FontWeight', 'bold', 'FontSize', 12, 'Interpreter', 'none');
    text(progress.axInfo, 0.03, 0.78, '等待第一个候选策略评估完成...', ...
        'FontSize', 11, 'Interpreter', 'none');
    drawnow;
catch
    progress = struct('fig', [], 'axCost', [], 'axRms', [], 'axSteady', [], 'axInfo', []);
end
end

function update_progress_figure(progress, profile, iter, numIterations, candidate, popSize, ...
    candidateCost, bestCost, metrics, mpcMetrics, elapsedSeconds)
try
    if isempty(progress.fig) || ~isgraphics(progress.fig)
        return;
    end
    displayBest = min(candidateCost, bestCost);
    if ~isfinite(displayBest)
        displayBest = candidateCost;
    end
    history = getappdata(progress.fig, 'bestCostHistory');
    history(end+1) = displayBest;
    setappdata(progress.fig, 'bestCostHistory', history);

    modelTypes = getappdata(progress.fig, 'modelTypes');
    x = 1:numel(modelTypes);
    labels = modelTypes;
    rlRms = [metrics.rmsError];
    rlSteady = [metrics.steadyRmsError];
    rlEffort = [metrics.controlEffort];
    mpcRms = [mpcMetrics.rmsError];
    mpcSteady = [mpcMetrics.steadyRmsError];
    mpcEffort = [mpcMetrics.controlEffort];

    cla(progress.axCost);
    plot(progress.axCost, history, 'LineWidth', 1.6, 'Color', [0.00 0.27 0.56]);
    grid(progress.axCost, 'on');
    title(progress.axCost, 'Best cost progress');
    xlabel(progress.axCost, 'candidate update');
    ylabel(progress.axCost, 'cost');

    cla(progress.axRms);
    bar(progress.axRms, x - 0.18, rlRms, 0.35, 'FaceColor', [0.00 0.27 0.56]); hold(progress.axRms, 'on');
    bar(progress.axRms, x + 0.18, mpcRms, 0.35, 'FaceColor', [0.45 0.22 0.70]);
    hold(progress.axRms, 'off');
    grid(progress.axRms, 'on');
    set(progress.axRms, 'XTick', x, 'XTickLabel', labels);
    ylabel(progress.axRms, 'RMS / m');
    title(progress.axRms, 'RL-v2 vs MPC RMS');
    legend(progress.axRms, {'RL-v2', 'MPC'}, 'Location', 'best');

    cla(progress.axSteady);
    bar(progress.axSteady, x - 0.18, rlSteady, 0.35, 'FaceColor', [0.12 0.50 0.24]); hold(progress.axSteady, 'on');
    bar(progress.axSteady, x + 0.18, mpcSteady, 0.35, 'FaceColor', [0.88 0.48 0.10]);
    hold(progress.axSteady, 'off');
    grid(progress.axSteady, 'on');
    set(progress.axSteady, 'XTick', x, 'XTickLabel', labels);
    ylabel(progress.axSteady, 'steady RMS / m');
    title(progress.axSteady, '8s+ steady RMS');
    legend(progress.axSteady, {'RL-v2', 'MPC'}, 'Location', 'best');

    cla(progress.axInfo);
    axis(progress.axInfo, 'off');
    statusLines = {
        sprintf('Profile: %s', profile)
        sprintf('Iteration: %d / %d', iter, numIterations)
        sprintf('Candidate: %d / %d', candidate, popSize)
        sprintf('Candidate cost: %.6f', candidateCost)
        sprintf('Best cost shown: %.6f', displayBest)
        sprintf('Elapsed wall time: %.1f s (%.2f min)', elapsedSeconds, elapsedSeconds / 60.0)
        sprintf('RL-v2 effort: [%.3f %.3f %.3f]', rlEffort(1), rlEffort(2), rlEffort(3))
        sprintf('MPC effort:   [%.3f %.3f %.3f]', mpcEffort(1), mpcEffort(2), mpcEffort(3))
        };
    text(progress.axInfo, 0.03, 0.92, 'RL-v2 Training Monitor', ...
        'FontWeight', 'bold', 'FontSize', 13, 'Interpreter', 'none');
    for i = 1:numel(statusLines)
        text(progress.axInfo, 0.03, 0.92 - 0.09 * i, statusLines{i}, ...
            'FontSize', 10.5, 'Interpreter', 'none');
    end
    drawnow limitrate;
catch
end
end

function xNext = rk4_step(t, x, dt, scenarioId, modelId, p)
k1 = closed_loop_rhs(t, x, scenarioId, modelId, p);
k2 = closed_loop_rhs(t + 0.5 * dt, x + 0.5 * dt * k1, scenarioId, modelId, p);
k3 = closed_loop_rhs(t + 0.5 * dt, x + 0.5 * dt * k2, scenarioId, modelId, p);
k4 = closed_loop_rhs(t + dt, x + dt * k3, scenarioId, modelId, p);
xNext = x + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6;
end

function dx = closed_loop_rhs(t, x, scenarioId, modelId, p)
ref = quadrotor_reference_core(t, scenarioId, p);
env = quadrotor_environment_core(t, x, modelId, p);
[omegaCmd, ~] = quadrotor_controller_core(t, x, ref, p);
[dx, ~] = quadrotor_rhs_core(x, ref, omegaCmd, env, p);
end

function write_summary(rootDir, training, logTable)
summaryPath = fullfile(rootDir, 'results', 'policies', 'rl_v2', 'quadrotor_rl_v2_policy_summary.md');
fid = fopen(summaryPath, 'w');
if fid < 0
    error('Cannot write %s', summaryPath);
end
cleanup = onCleanup(@() fclose(fid));

fprintf(fid, '# Quadrotor RL-v2 Preview Residual Policy Summary\n\n');
fprintf(fid, 'Generated: %s\n\n', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')));
fprintf(fid, 'Profile: %s\n\n', training.profile);
fprintf(fid, 'Algorithm: %s\n\n', training.algorithm);
fprintf(fid, 'Wall-clock start: %s\n\n', training.startWallClock);
fprintf(fid, 'Wall-clock end: %s\n\n', training.endWallClock);
fprintf(fid, 'Wall-clock elapsed: %.2f s (%.2f min)\n\n', ...
    training.elapsedWallSeconds, training.elapsedWallSeconds / 60.0);
fprintf(fid, 'Best cost: %.6f\n\n', training.bestCost);
fprintf(fid, 'Behavior-cloning samples: %d (%d gated)\n\n', ...
    training.imitationFit.sampleCount, training.imitationFit.validSampleCount);
fprintf(fid, 'Nonzero readout weights: %d / 80\n\n', ...
    training.imitationFit.nonzeroWeightCount);
fprintf(fid, 'Imitation RMSE: %.8f (zero baseline %.8f)\n\n', ...
    training.imitationFit.rmse, training.imitationFit.zeroBaselineRmse);
fprintf(fid, 'Best compact genes:\n\n');
fprintf(fid, '| gene | value |\n');
fprintf(fid, '|---|---:|\n');
names = {'preview_blend', 'feedforward_blend', 'learned_blend', ...
    'bias_ax', 'bias_ay', 'bias_az', 'bias_thrust', 'bias_tau', ...
    'acc_scale', 'thrust_scale', 'tau_scale'};
for i = 1:numel(names)
    fprintf(fid, '| %s | %.6f |\n', names{i}, training.bestGenes(i));
end
fprintf(fid, '\nTraining evaluations: %d candidates.\n', height(logTable));
end
