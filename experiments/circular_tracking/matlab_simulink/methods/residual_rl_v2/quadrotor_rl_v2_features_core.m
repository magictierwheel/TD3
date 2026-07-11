function [features, hidden, tempGate, residualGate] = ...
    quadrotor_rl_v2_features_core(t, x, ref, env, p)
%QUADROTOR_RL_V2_FEATURES_CORE Shared RL-v2 feature and hidden mapping.
%   This function is used by both behavior-cloning training and deployed
%   inference so the 32-dimensional feature definition cannot drift.

rho0 = p(12);
rho = env(1);
thermalZ = env(4);
wind = env(5:7);
fT = max(env(11), 0.25);
fQ = max(env(12), 0.25);

lossT = min(max((1.0 / fT) - 1.0, 0.0), 2.0);
lossQ = min(max((1.0 / fQ) - 1.0, 0.0), 2.0);
densityLoss = min(max(1.0 - rho / max(rho0, 0.1), 0.0), 0.5);
windNorm = sqrt(sum(wind .* wind));

tempGate = min(max(0.45 * windNorm / 1.5 + ...
    0.35 * abs(thermalZ) / 0.8 + ...
    0.40 * densityLoss / 0.15, 0.0), 1.0);
if round(p(90)) == 1
    tempGate = 1.0;
end
dustGate = min(max(lossT / 0.05, 0.0), 1.0);
residualGate = max(tempGate, dustGate);

features = zeros(32, 1);
errPos = ref(1:3) - x(1:3);
errVel = ref(4:6) - x(4:6);
rotorOmega = x(16:19);
omegaMin = p(10);
omegaMax = p(11);
rotorLow = min(rotorOmega - omegaMin);
rotorHigh = min(omegaMax - rotorOmega);
rotorMargin = min(max(min(rotorLow, rotorHigh) / ...
    max(omegaMax - omegaMin, 1.0), 0.0), 1.0);

features(1:3) = clip_vec(errPos / 3.0, -1.0, 1.0);
features(4:6) = clip_vec(errVel / 2.0, -1.0, 1.0);
features(7:9) = clip_vec(ref(7:9) / 3.0, -1.0, 1.0);
features(10) = min(max(densityLoss / 0.20, 0.0), 1.0);
features(11) = min(max(thermalZ / 1.20, -1.0), 1.0);
features(12:14) = clip_vec(wind / 3.0, -1.0, 1.0);
features(15) = min(max(lossT / 0.10, 0.0), 1.0);
features(16) = min(max(lossQ / 0.10, 0.0), 1.0);
features(17) = min(max(sqrt(x(7) * x(7) + x(8) * x(8)) / ...
    max(p(64), 0.1), 0.0), 1.5);
features(18) = rotorMargin;
features(19) = min(max(errPos(3) / 1.0, -1.0), 1.0);
features(20) = min(max(sqrt(sum(x(4:6) .* x(4:6))) / 3.0, 0.0), 1.0);

previewTimes = [0.08, 0.16, 0.32, 0.64];
offset = 21;
scenarioId = p(88);
if scenarioId < 0.5
    scenarioId = 2.0;
end
for k = 1:4
    refFuture = quadrotor_reference_core(t + previewTimes(k), scenarioId, p);
    futureErr = refFuture(1:3) - x(1:3);
    features(offset:offset+2) = clip_vec(futureErr / 4.0, -1.0, 1.0);
    offset = offset + 3;
end

hidden = zeros(16, 1);
for h = 1:16
    z = 0.05 * sin(0.31 * h);
    for j = 1:32
        w = 0.22 * sin(0.17 * h * j) + ...
            0.13 * cos(0.11 * (h + 2 * j));
        z = z + w * features(j);
    end
    hidden(h) = tanh(z);
end
end

function y = clip_vec(x, lo, hi)
y = zeros(size(x));
for i = 1:numel(x)
    y(i) = min(max(x(i), lo), hi);
end
end
