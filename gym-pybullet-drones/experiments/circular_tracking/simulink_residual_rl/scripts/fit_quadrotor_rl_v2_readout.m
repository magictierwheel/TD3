function [slots, stats] = fit_quadrotor_rl_v2_readout(hidden, targets, gates, ridge)
%FIT_QUADROTOR_RL_V2_READOUT Fit the fixed-feature 16-to-5 policy readout.
%   TARGETS are the already-gated physical residual commands. The fitted
%   network predicts the corresponding ungated command and deployment
%   reapplies GATES through the policy's residual gate.

if nargin < 4 || isempty(ridge)
    ridge = 1e-4;
end
if size(hidden, 2) ~= 16
    error('RLV2:InvalidHiddenSize', 'hidden must have 16 columns.');
end
if size(targets, 2) ~= 5 || size(targets, 1) ~= size(hidden, 1)
    error('RLV2:InvalidTargetSize', ...
        'targets must be N-by-5 with the same row count as hidden.');
end
gates = gates(:);
if numel(gates) ~= size(hidden, 1)
    error('RLV2:InvalidGateSize', 'gates must contain one value per sample.');
end
if any(~isfinite(hidden(:))) || any(~isfinite(targets(:))) || ...
        any(~isfinite(gates)) || ~isfinite(ridge) || ridge < 0
    error('RLV2:NonFiniteFitData', ...
        'Fit inputs and ridge must be finite, with a nonnegative ridge.');
end

valid = gates > 0.05;
if nnz(valid) < 20
    error('RLV2:InsufficientGatedSamples', ...
        'At least 20 gated samples are required; received %d.', nnz(valid));
end

effectiveTargets = targets(valid, :) ./ gates(valid);
outputScales = max(1.25 * max(abs(effectiveTargets), [], 1), 1e-3);
normalizedTargets = effectiveTargets ./ outputScales;
activationTargets = atanh(min(max(normalizedTargets, -0.95), 0.95));

design = [hidden(valid, :), ones(nnz(valid), 1)];
ridgePenalty = diag([ones(16, 1); 0]);
coeff = (design.' * design + ridge * ridgePenalty) \ ...
    (design.' * activationTargets);

slots = zeros(120, 1);
slots(1) = 2.0;
slots(2) = 1.0;
for outputIndex = 1:5
    first = 4 + (outputIndex - 1) * 16;
    slots(first:first+15) = coeff(1:16, outputIndex);
end
slots(84:88) = coeff(17, :).';
slots(89:93) = outputScales(:);
slots(94) = 0.05;
slots(95) = 1.0;
slots(96:98) = 1.0;
slots(99) = 3.0;
slots(100) = 0.05;

effectivePrediction = tanh(design * coeff) .* outputScales;
prediction = gates(valid) .* effectivePrediction;
fitError = prediction - targets(valid, :);
zeroError = targets(valid, :);

stats = struct();
stats.sampleCount = size(hidden, 1);
stats.validSampleCount = nnz(valid);
stats.nonzeroWeightCount = nnz(abs(slots(4:83)) > 1e-10);
stats.rmse = sqrt(mean(fitError(:) .^ 2));
stats.zeroBaselineRmse = sqrt(mean(zeroError(:) .^ 2));
stats.outputScales = outputScales;
end
