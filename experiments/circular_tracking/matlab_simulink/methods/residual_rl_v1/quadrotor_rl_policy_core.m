function [accResidual, thrustScale, tauScale] = quadrotor_rl_policy_core(t, x, ref, env, p)
%QUADROTOR_RL_POLICY_CORE Compact residual RL policy for Simulink deployment.
%   The policy follows the PPO-style residual-control idea used in the local
%   gym-pybullet-drones project: keep a stabilizing low-level controller, then
%   learn a small state-dependent residual action under domain-randomized
%   disturbances. The trained weights live in p(91:96).

accResidual = zeros(3, 1);
tauScale = ones(2, 1);
thrustScale = 1.0;

blend = min(max(p(96), 0.0), 1.0);
if blend <= 0.0
    return;
end

mass = p(1);
rho = env(1);
thermalZ = env(4);
wind = env(5:7);
fT = max(env(11), 0.25);
fQ = max(env(12), 0.25);
CDA = p(16);

vel = x(4:6);
vrel = vel - wind;
vrelNorm = sqrt(sum(vrel .* vrel));
dragAcc = -0.5 * rho * CDA * vrelNorm * vrel / mass;

lossT = min(max((1.0 / fT) - 1.0, 0.0), 2.0);
lossQ = min(max((1.0 / fQ) - 1.0, 0.0), 2.0);
windGate = min(max(sqrt(sum(wind .* wind)) / 1.0, 0.0), 1.0);

accResidual = -blend * p(91) * windGate * dragAcc;
accResidual(3) = accResidual(3) - blend * p(92) * thermalZ;
for i = 1:3
    accResidual(i) = min(max(accResidual(i), -3.0), 3.0);
end

thrustScale = 1.0 + blend * p(93) * lossT;
thrustScale = min(max(thrustScale, 0.75), 1.80);

tauScale(1) = 1.0 + blend * p(94) * lossT;
tauScale(2) = 1.0 + blend * p(95) * lossQ;
for i = 1:2
    tauScale(i) = min(max(tauScale(i), 0.80), 1.80);
end

unusedT = t; %#ok<NASGU>
unusedRef = ref(1); %#ok<NASGU>
end
