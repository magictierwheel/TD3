function tests = test_quadrotor_rl_v2_imitation
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
rootDir = fileparts(fileparts(mfilename('fullpath')));
addpath(fullfile(rootDir, 'scripts'));
testCase.TestData.rootDir = rootDir;
end

function testSavedPolicyHasTrainedReadout(testCase)
data = load(fullfile(testCase.TestData.rootDir, 'results', 'policies', 'rl_v2', ...
    'quadrotor_rl_v2_policy.mat'), 'bestPolicySlots');
weights = data.bestPolicySlots(4:83);

verifyGreaterThanOrEqual(testCase, nnz(abs(weights) > 1e-10), 60);
verifyTrue(testCase, all(isfinite(weights)));
end

function testReadoutFitBeatsZeroBaseline(testCase)
rng(17);
sampleCount = 320;
hidden = 0.65 * randn(sampleCount, 16);
trueWeights = 0.18 * randn(16, 5);
trueBias = [0.08, -0.06, 0.04, 0.03, -0.02];
trueScales = [0.9, 0.8, 0.7, 0.25, 0.20];
gates = 0.20 + 0.80 * rand(sampleCount, 1);
targets = gates .* (tanh(hidden * trueWeights + trueBias) .* trueScales);

[slots, stats] = fit_quadrotor_rl_v2_readout(hidden, targets, gates, 1e-4);

verifyGreaterThanOrEqual(testCase, nnz(abs(slots(4:83)) > 1e-10), 60);
verifyTrue(testCase, all(isfinite(slots)));
verifyLessThan(testCase, stats.rmse, 0.35 * stats.zeroBaselineRmse);
end

function testSharedFeatureMapIsFiniteAndBounded(testCase)
params = init_quadrotor_params('temperature', 'circle', false);
p = params.paramVec;
p(88) = params.scenarioId;
p(90) = params.modelId;
t = 2.5;
x = params.x0;
ref = quadrotor_reference_core(t, params.scenarioId, p);
env = quadrotor_environment_core(t, x, params.modelId, p);

[features, hidden, tempGate, residualGate] = ...
    quadrotor_rl_v2_features_core(t, x, ref, env, p);

verifySize(testCase, features, [32, 1]);
verifySize(testCase, hidden, [16, 1]);
verifyTrue(testCase, all(isfinite(features)));
verifyTrue(testCase, all(isfinite(hidden)));
verifyGreaterThanOrEqual(testCase, tempGate, 0);
verifyLessThanOrEqual(testCase, tempGate, 1);
verifyGreaterThanOrEqual(testCase, residualGate, 0);
verifyLessThanOrEqual(testCase, residualGate, 1);
end

function testImitationDatasetContainsTrainableSamples(testCase)
imitation = create_quadrotor_rl_v2_imitation_dataset( ...
    {'standard', 'temperature', 'dust'});

verifySize(testCase, imitation.hidden, [size(imitation.hidden, 1), 16]);
verifySize(testCase, imitation.targets, [size(imitation.hidden, 1), 5]);
verifySize(testCase, imitation.gates, [size(imitation.hidden, 1), 1]);
verifyTrue(testCase, all(isfinite(imitation.hidden), 'all'));
verifyTrue(testCase, all(isfinite(imitation.targets), 'all'));
verifyTrue(testCase, all(isfinite(imitation.gates)));
verifyGreaterThanOrEqual(testCase, nnz(imitation.gates > 0.05), 100);
end
