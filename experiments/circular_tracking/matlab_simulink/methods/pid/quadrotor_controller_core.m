function [omegaCmd, dbg] = quadrotor_controller_core(t, x, ref, p)
%QUADROTOR_CONTROLLER_CORE Shared controller for all environmental models.

omegaCmd = zeros(4, 1);
dbg = zeros(10, 1);

mass = p(1);
g = p(2);
arm = p(6);
kf = p(7);
kq = p(8);
omegaMin = p(10);
omegaMax = p(11);
J = reshape(p(20:28), 3, 3).';

pos = x(1:3);
vel = x(4:6);
eul = x(7:9);
omega = x(10:12);
ierr = x(13:15);

rRef = ref(1:3);
vRef = ref(4:6);
aRef = ref(7:9);
yawRef = ref(10);

errPos = rRef - pos;
errVel = vRef - vel;
ierr = min(max(ierr, -p(65)), p(65));

aCmd = aRef;
aCmd(1) = aCmd(1) + p(54) * errPos(1) + p(55) * errVel(1) + p(56) * ierr(1);
aCmd(2) = aCmd(2) + p(54) * errPos(2) + p(55) * errVel(2) + p(56) * ierr(2);
aCmd(3) = aCmd(3) + p(57) * errPos(3) + p(58) * errVel(3) + p(59) * ierr(3);

controllerMode = round(p(89));
useRlPolicy = controllerMode == 1;
useRlV2Policy = controllerMode == 5;
useFeedforward = controllerMode == 2 || controllerMode == 3;
useAdrc = controllerMode == 4;
thrustScale = 1.0;
tauScale = ones(2, 1);
if useAdrc
    env = quadrotor_environment_core(t, x, p(90), p);
    [~, thrustScale, tauScale] = quadrotor_disturbance_compensation_core(x, env, p);
    aCmd = quadrotor_adrc_outer_core(x, ref, p);
elseif useRlPolicy
    env = quadrotor_environment_core(t, x, p(90), p);
    [accResidual, thrustScale, tauScale] = quadrotor_rl_policy_core(t, x, ref, env, p);
    aCmd = aCmd + accResidual;
elseif useRlV2Policy
    env = quadrotor_environment_core(t, x, p(90), p);
    [accResidual, thrustScale, tauScale] = quadrotor_rl_v2_policy_core(t, x, ref, env, p);
    aCmd = aCmd + accResidual;
elseif useFeedforward
    env = quadrotor_environment_core(t, x, p(90), p);
    if controllerMode == 3
        aCmd = quadrotor_mpc_outer_core(t, x, p);
    end
    [accResidual, thrustScale, tauScale] = quadrotor_disturbance_compensation_core(x, env, p);
    aCmd = aCmd + accResidual;
end

maxTilt = p(64);
phiDes = (aCmd(1) * sin(yawRef) - aCmd(2) * cos(yawRef)) / g;
thetaDes = (aCmd(1) * cos(yawRef) + aCmd(2) * sin(yawRef)) / g;
phiDes = min(max(phiDes, -maxTilt), maxTilt);
thetaDes = min(max(thetaDes, -maxTilt), maxTilt);
psiDes = yawRef;

den = cos(eul(1)) * cos(eul(2));
den = max(0.35, den);
thrustCmd = mass * (g + aCmd(3)) / den;
if useRlPolicy || useRlV2Policy || useFeedforward || useAdrc
    thrustCmd = thrustCmd * thrustScale;
end
maxThrust = 4.0 * kf * omegaMax * omegaMax;
thrustCmd = min(max(thrustCmd, 0.05 * mass * g), 0.92 * maxThrust);

attErr = [phiDes; thetaDes; psiDes] - eul;
attErr(3) = atan2(sin(attErr(3)), cos(attErr(3)));

rateCmd = zeros(3, 1);
kpAtt = [p(60); p(60); p(62)];
kdAtt = [p(61); p(61); p(63)];
tauCmd = J * (kpAtt .* attErr + kdAtt .* (rateCmd - omega));
if useRlPolicy || useRlV2Policy || useFeedforward || useAdrc
    tauCmd(1) = tauCmd(1) * tauScale(1);
    tauCmd(2) = tauCmd(2) * tauScale(1);
    tauCmd(3) = tauCmd(3) * tauScale(2);
end
tauCmd(1) = min(max(tauCmd(1), -2.0), 2.0);
tauCmd(2) = min(max(tauCmd(2), -2.0), 2.0);
tauCmd(3) = min(max(tauCmd(3), -0.8), 0.8);

alloc = [ kf,       kf,       kf,       kf; ...
          0,        arm*kf,   0,       -arm*kf; ...
         -arm*kf,   0,        arm*kf,  0; ...
         -kq,       kq,      -kq,      kq ];
omegaSq = alloc \ [thrustCmd; tauCmd];

for i = 1:4
    omegaSq(i) = min(max(omegaSq(i), omegaMin * omegaMin), omegaMax * omegaMax);
    omegaCmd(i) = sqrt(omegaSq(i));
end

dbg(1) = thrustCmd;
dbg(2:4) = tauCmd;
dbg(5) = phiDes;
dbg(6) = thetaDes;
dbg(7) = psiDes;
dbg(8) = sqrt(sum(errPos .* errPos));
dbg(9) = errPos(3);
dbg(10) = sqrt(phiDes * phiDes + thetaDes * thetaDes) + 0.0 * t;
end
