function [accResidual, thrustScale, tauScale] = quadrotor_rl_v2_policy_core(t, x, ref, env, p)
%QUADROTOR_RL_V2_POLICY_CORE Preview residual RL policy for deployment.
%   RL-v2 keeps the stabilizing cascaded controller and adds a bounded
%   residual action. It uses fixed 32->16 tanh features, trainable readout
%   slots in p(121:240), deterministic disturbance compensation, and a
%   preview-teacher residual that is gated to disturbed temperature cases.

accResidual = zeros(3, 1);
tauScale = ones(2, 1);
thrustScale = 1.0;

blend = min(max(p(122), 0.0), 1.0);
if blend <= 0.0
    return;
end

[~, hidden, tempGate, residualGate] = ...
    quadrotor_rl_v2_features_core(t, x, ref, env, p);

[ffAcc, ffThrustScale, ffTauScale] = quadrotor_disturbance_compensation_core(x, env, p);
ffBlend = min(max(p(220), 0.0), 1.50);

baseA = baseline_outer_acceleration(x, ref, p);
previewA = quadrotor_mpc_outer_core(t, x, p);
previewBlend = min(max(p(214), 0.0), 1.50);
previewResidual = tempGate * previewBlend * (previewA - baseA);

readout = readout_policy(hidden, p);

learnedBlend = min(max(p(215), 0.0), 1.50);
accScale = max(p(216), 0.0);
thrustOutScale = max(p(217), 0.0);
tauOutScale = max(p(218), 0.0);
accClamp = max(p(219), 0.5);

accResidual = blend * (ffBlend * ffAcc + previewResidual + ...
    residualGate * learnedBlend * accScale * readout(1:3));
for i = 1:3
    accResidual(i) = min(max(accResidual(i), -accClamp), accClamp);
end

thrustScale = 1.0 + ffBlend * (ffThrustScale - 1.0) + ...
    residualGate * learnedBlend * thrustOutScale * readout(4);
thrustScale = min(max(thrustScale, 0.75), 1.80);

tauScale(1) = 1.0 + ffBlend * (ffTauScale(1) - 1.0) + ...
    residualGate * learnedBlend * tauOutScale * readout(5);
tauScale(2) = 1.0 + ffBlend * (ffTauScale(2) - 1.0) + ...
    residualGate * learnedBlend * tauOutScale * readout(5);
for i = 1:2
    tauScale(i) = min(max(tauScale(i), 0.80), 1.80);
end

end

function aCmd = baseline_outer_acceleration(x, ref, p)
aCmd = ref(7:9);
errPos = ref(1:3) - x(1:3);
errVel = ref(4:6) - x(4:6);
ierr = min(max(x(13:15), -p(65)), p(65));
aCmd(1) = aCmd(1) + p(54) * errPos(1) + p(55) * errVel(1) + p(56) * ierr(1);
aCmd(2) = aCmd(2) + p(54) * errPos(2) + p(55) * errVel(2) + p(56) * ierr(2);
aCmd(3) = aCmd(3) + p(57) * errPos(3) + p(58) * errVel(3) + p(59) * ierr(3);
end

function y = readout_policy(hidden, p)
y = zeros(5, 1);
for o = 1:5
    z = p(203 + o);
    for h = 1:16
        idx = 123 + (o - 1) * 16 + h;
        z = z + p(idx) * hidden(h);
    end
    y(o) = tanh(z) * p(208 + o);
end
end
