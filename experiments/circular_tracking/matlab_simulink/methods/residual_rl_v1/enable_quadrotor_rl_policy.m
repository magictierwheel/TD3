function value = enable_quadrotor_rl_policy(value, weights, blend)
%ENABLE_QUADROTOR_RL_POLICY Enable the deployed residual RL policy.
%   p = ENABLE_QUADROTOR_RL_POLICY(p) updates a parameter vector.
%   params = ENABLE_QUADROTOR_RL_POLICY(params) updates params.paramVec.

if nargin < 2 || isempty(weights)
    weights = load_default_weights();
end
if nargin < 3 || isempty(blend)
    blend = 1.0;
end

if isstruct(value)
    p = value.paramVec;
else
    p = value;
end

if numel(p) < 120
    p(120, 1) = 0;
end

weights = weights(:);
if numel(weights) < 5
    error('RL policy weight vector must contain at least five values.');
end

p(89) = 1.0;
p(91:95) = weights(1:5);
p(96) = blend;

if isstruct(value)
    value.paramVec = p;
else
    value = p;
end
end

function weights = load_default_weights()
rootDir = matlab_simulink_root();
policyPath = fullfile(rootDir, 'evidence', '20_residual_rl_v1', 'policy', ...
    'quadrotor_rl_policy.mat');
if exist(policyPath, 'file') == 2
    data = load(policyPath, 'bestWeights');
    weights = data.bestWeights(:);
else
    weights = ones(5, 1);
end
end
