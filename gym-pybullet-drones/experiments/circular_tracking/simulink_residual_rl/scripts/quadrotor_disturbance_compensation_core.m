function [accResidual, thrustScale, tauScale] = quadrotor_disturbance_compensation_core(x, env, p)
%QUADROTOR_DISTURBANCE_COMPENSATION_CORE Model-based disturbance feedforward.
%   Deterministically compensates the same environment channels that the
%   residual RL policy observes: wind drag, thermal updraft, density loss, and
%   dust-induced thrust/counter-torque efficiency loss.

accResidual = zeros(3, 1);
tauScale = ones(2, 1);
thrustScale = 1.0;

blend = min(max(p(97), 0.0), 1.0);
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
windGate = min(max(sqrt(sum(wind .* wind)) / 1.0, 0.0), 1.0);

accResidual = -blend * windGate * dragAcc;
accResidual(3) = accResidual(3) - blend * thermalZ;
for i = 1:3
    accResidual(i) = min(max(accResidual(i), -3.0), 3.0);
end

lossT = min(max((1.0 / fT) - 1.0, 0.0), 2.0);
lossQ = min(max((1.0 / fQ) - 1.0, 0.0), 2.0);

thrustScale = 1.0 + blend * lossT;
thrustScale = min(max(thrustScale, 0.75), 1.80);

tauScale(1) = 1.0 + blend * lossT;
tauScale(2) = 1.0 + blend * lossQ;
for i = 1:2
    tauScale(i) = min(max(tauScale(i), 0.80), 1.80);
end
end
