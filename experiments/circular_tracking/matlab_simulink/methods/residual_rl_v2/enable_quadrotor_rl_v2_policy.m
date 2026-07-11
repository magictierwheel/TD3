function value = enable_quadrotor_rl_v2_policy(value, policySlots, blend)
%ENABLE_QUADROTOR_RL_V2_POLICY Enable the preview residual RL-v2 policy.
%   p = ENABLE_QUADROTOR_RL_V2_POLICY(p) updates a parameter vector.
%   params = ENABLE_QUADROTOR_RL_V2_POLICY(params) updates params.paramVec.

if nargin < 2 || isempty(policySlots)
    policySlots = load_default_policy_slots();
end
if nargin < 3 || isempty(blend)
    blend = 1.0;
end

if isstruct(value)
    p = value.paramVec;
else
    p = value;
end

if numel(p) < 240
    p(240, 1) = 0;
end

policySlots = policySlots(:);
if numel(policySlots) < 120
    padded = zeros(120, 1);
    padded(1:numel(policySlots)) = policySlots;
    policySlots = padded;
else
    policySlots = policySlots(1:120);
end

p(89) = 5.0;
p(121:240) = policySlots;
p(122) = min(max(blend, 0.0), 1.0);
p(121) = 2.0;

if isstruct(value)
    value.paramVec = p;
else
    value = p;
end
end

function policySlots = load_default_policy_slots()
rootDir = matlab_simulink_root();
policyPath = fullfile(rootDir, 'evidence', '30_rl_v2_mpc_imitation', 'policy', ...
    'quadrotor_rl_v2_policy.mat');
if exist(policyPath, 'file') == 2
    data = load(policyPath, 'bestPolicySlots');
    policySlots = data.bestPolicySlots(:);
else
    policySlots = default_policy_slots();
end
end

function policySlots = default_policy_slots()
policySlots = zeros(120, 1);
policySlots(1) = 2.0;   % p(121): version
policySlots(2) = 1.0;   % p(122): blend
policySlots(89:93) = [0.20; 0.20; 0.16; 0.08; 0.06]; % p(209:213)
policySlots(94) = 1.0;  % p(214): preview-teacher blend
policySlots(95) = 0.0;  % p(215): learned readout blend
policySlots(96) = 0.25; % p(216): acceleration residual scale
policySlots(97) = 0.08; % p(217): thrust residual scale
policySlots(98) = 0.06; % p(218): torque residual scale
policySlots(99) = 3.0;  % p(219): acceleration clamp
policySlots(100) = 1.0; % p(220): disturbance feedforward blend
end
