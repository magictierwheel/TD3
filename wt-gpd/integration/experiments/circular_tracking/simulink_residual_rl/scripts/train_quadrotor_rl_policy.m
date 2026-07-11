function training = train_quadrotor_rl_policy()
%TRAIN_QUADROTOR_RL_POLICY Train compact residual policy weights.
%   This script uses direct policy search over a residual actor deployed by
%   quadrotor_rl_policy_core. It follows the local gym-pybullet-drones RL
%   workflow at a Simulink-friendly scale: rollout -> reward/cost -> policy
%   update -> save best actor weights.

rootDir = fileparts(fileparts(mfilename('fullpath')));
scriptsDir = fullfile(rootDir, 'scripts');
rlDir = fullfile(rootDir, 'results', 'policies', 'rl_v1');
dataDir = fullfile(rootDir, 'results', 'data');
if ~exist(rlDir, 'dir'), mkdir(rlDir); end
if ~exist(dataDir, 'dir'), mkdir(dataDir); end
addpath(scriptsDir);

rng(20260622);
startWallClock = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
trainingTimer = tic;
modelTypes = {'standard', 'temperature', 'dust'};
modelWeights = [0.35, 1.00, 0.65];

popSize = 14;
eliteCount = 5;
numIterations = 4;
lower = zeros(1, 5);
upper = 1.6 * ones(1, 5);
mu = [0.80, 0.90, 0.95, 0.90, 0.90];
sigma = [0.35, 0.35, 0.30, 0.30, 0.30];

bestWeights = ones(1, 5);
bestCost = inf;
logRows = {};
iterationWallSeconds = zeros(numIterations, 1);

for iter = 1:numIterations
    iterationTimer = tic;
    candidates = zeros(popSize, 5);
    candidates(1, :) = mu;
    candidates(2, :) = ones(1, 5);
    candidates(3, :) = zeros(1, 5);
    for k = 4:popSize
        candidates(k, :) = mu + sigma .* randn(1, 5);
    end
    candidates = min(max(candidates, lower), upper);

    costs = zeros(popSize, 1);
    rmsByModel = zeros(popSize, numel(modelTypes));
    maxByModel = zeros(popSize, numel(modelTypes));
    for k = 1:popSize
        candidateTimer = tic;
        [costs(k), rmsByModel(k, :), maxByModel(k, :)] = evaluate_candidate( ...
            candidates(k, :), modelTypes, modelWeights);
        candidateElapsed = toc(candidateTimer);
        logRows(end+1, :) = {iter, k, candidates(k, 1), candidates(k, 2), ...
            candidates(k, 3), candidates(k, 4), candidates(k, 5), candidateElapsed, costs(k), ...
            rmsByModel(k, 1), rmsByModel(k, 2), rmsByModel(k, 3), ...
            maxByModel(k, 1), maxByModel(k, 2), maxByModel(k, 3)}; %#ok<AGROW>
    end

    [sortedCosts, order] = sort(costs, 'ascend');
    elites = candidates(order(1:eliteCount), :);
    mu = mean(elites, 1);
    sigma = max(std(elites, 0, 1), 0.04);

    if sortedCosts(1) < bestCost
        bestCost = sortedCosts(1);
        bestWeights = candidates(order(1), :);
    end

    fprintf('RL policy search iter %d/%d best cost %.5f weights [%s]\n', ...
        iter, numIterations, bestCost, sprintf(' %.3f', bestWeights));
    iterationWallSeconds(iter) = toc(iterationTimer);
end

elapsedWallSeconds = toc(trainingTimer);
endWallClock = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');

training = struct();
training.algorithm = 'CEM direct policy search';
training.seed = 20260622;
training.bestWeights = bestWeights;
training.bestCost = bestCost;
training.modelTypes = modelTypes;
training.startWallClock = char(startWallClock);
training.endWallClock = char(endWallClock);
training.elapsedWallSeconds = elapsedWallSeconds;
training.iterationWallSeconds = iterationWallSeconds;
training.description = ['Residual actor trained on circle tracking under ', ...
    'standard, temperature, and dust disturbances.'];

logTable = cell2table(logRows, 'VariableNames', { ...
    'iteration', 'candidate', 'w_drag', 'w_thermal', 'w_thrust', 'w_tau_xy', ...
    'w_tau_yaw', 'candidate_wall_seconds', 'cost', 'rms_standard_m', 'rms_temperature_m', 'rms_dust_m', ...
    'max_standard_m', 'max_temperature_m', 'max_dust_m'});
writetable(logTable, fullfile(dataDir, 'quadrotor_rl_training_log.csv'));

save(fullfile(rlDir, 'quadrotor_rl_policy.mat'), 'bestWeights', 'bestCost', 'training');
write_policy_summary(rootDir, bestWeights, bestCost, logTable, training);
end

function [cost, rmsByModel, maxByModel] = evaluate_candidate(weights, modelTypes, modelWeights)
rmsByModel = zeros(1, numel(modelTypes));
maxByModel = zeros(1, numel(modelTypes));
cost = 0;
for i = 1:numel(modelTypes)
    metric = rollout_metric(modelTypes{i}, weights);
    rmsByModel(i) = metric.rmsError;
    maxByModel(i) = metric.maxError;
    cost = cost + modelWeights(i) * metric.cost;
end
end

function metric = rollout_metric(modelType, weights)
params = init_quadrotor_params(modelType, 'circle', false);
p = enable_quadrotor_rl_policy(params.paramVec, weights, 1.0);
modelId = params.modelId;
scenarioId = params.scenarioId;
dt = 0.02;
n = round(params.stopTime / dt);
x = params.x0;
err = zeros(n + 1, 1);
tilt = zeros(n + 1, 1);
omegaMean = zeros(n + 1, 1);
unstablePenalty = 0;

for k = 1:n+1
    t = (k - 1) * dt;
    ref = quadrotor_reference_core(t, scenarioId, p);
    [omegaCmd, ctrlDbg] = quadrotor_controller_core(t, x, ref, p);
    posErr = x(1:3) - ref(1:3);
    err(k) = sqrt(sum(posErr .* posErr));
    tilt(k) = sqrt(x(7) * x(7) + x(8) * x(8));
    omegaMean(k) = mean(omegaCmd);
    if any(~isfinite(x)) || abs(x(3)) > 8 || tilt(k) > 0.85
        unstablePenalty = unstablePenalty + 50;
        break;
    end
    if k <= n
        x = rk4_step(t, x, dt, scenarioId, modelId, p);
    end
    unusedCtrl = ctrlDbg(1); %#ok<NASGU>
end

valid = err > 0 | (1:numel(err)).' == 1;
err = err(valid);
tilt = tilt(valid);
omegaMean = omegaMean(valid);
metric = struct();
metric.rmsError = sqrt(mean(err .* err));
metric.maxError = max(err);
metric.finalError = err(end);
metric.meanTilt = mean(tilt);
metric.cost = metric.rmsError + 0.25 * metric.maxError + 0.35 * metric.finalError + ...
    0.02 * mean(abs(diff(omegaMean))) + 0.15 * metric.meanTilt + unstablePenalty;
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

function write_policy_summary(rootDir, bestWeights, bestCost, logTable, training)
summaryPath = fullfile(rootDir, 'results', 'policies', 'rl_v1', 'quadrotor_rl_policy_summary.md');
fid = fopen(summaryPath, 'w');
if fid < 0
    error('Cannot write %s', summaryPath);
end
cleanup = onCleanup(@() fclose(fid));

fprintf(fid, '# Quadrotor RL Residual Policy Summary\n\n');
fprintf(fid, 'Generated: %s\n\n', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')));
fprintf(fid, 'Algorithm: cross-entropy direct policy search over a compact residual actor.\n\n');
fprintf(fid, 'Wall-clock start: %s\n\n', training.startWallClock);
fprintf(fid, 'Wall-clock end: %s\n\n', training.endWallClock);
fprintf(fid, 'Wall-clock elapsed: %.2f s (%.2f min)\n\n', ...
    training.elapsedWallSeconds, training.elapsedWallSeconds / 60.0);
fprintf(fid, 'Best cost: %.6f\n\n', bestCost);
fprintf(fid, 'Best weights:\n\n');
fprintf(fid, '| weight | value | meaning |\n');
fprintf(fid, '|---|---:|---|\n');
names = {'w_drag', 'w_thermal', 'w_thrust', 'w_tau_xy', 'w_tau_yaw'};
meanings = {'cancel drag acceleration from wind-relative motion', ...
    'cancel vertical thermal updraft', ...
    'compensate rotor thrust loss f_T', ...
    'compensate roll/pitch torque loss', ...
    'compensate yaw torque loss f_Q'};
for i = 1:numel(names)
    fprintf(fid, '| %s | %.6f | %s |\n', names{i}, bestWeights(i), meanings{i});
end
fprintf(fid, '\nTraining evaluations: %d candidates.\n', height(logTable));
end
