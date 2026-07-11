function aCmd = quadrotor_adrc_outer_core(x, ref, p)
%QUADROTOR_ADRC_OUTER_CORE Linear ADRC outer-loop acceleration command.
%   The outer loop treats each translational axis as a double integrator with
%   an extended disturbance state estimated by quadrotor_adrc_eso_derivative_core.

aCmd = zeros(3, 1);

g = p(2);
maxTilt = p(64);

z3 = x(26:28);
pos = x(1:3);
vel = x(4:6);

rRef = ref(1:3);
vRef = ref(4:6);
aRef = ref(7:9);

wcH = max(p(100), 0.20);
wcZ = max(p(101), 0.20);
kp = [wcH * wcH; wcH * wcH; wcZ * wcZ];
kd = [2.0 * wcH; 2.0 * wcH; 2.0 * wcZ];

distBlendH = min(max(p(102), 0.0), 1.2);
distBlendZ = min(max(p(105), 0.0), 1.2);
distLimitH = max(p(103), 0.10);
distLimitZ = max(p(104), 0.10);
distEst = z3;
distEst(1) = min(max(distEst(1), -distLimitH), distLimitH);
distEst(2) = min(max(distEst(2), -distLimitH), distLimitH);
distEst(3) = min(max(distEst(3), -distLimitZ), distLimitZ);

posErr = rRef - pos;
velErr = vRef - vel;
aCmd(1) = aRef(1) + kp(1) * posErr(1) + kd(1) * velErr(1) - distBlendH * distEst(1);
aCmd(2) = aRef(2) + kp(2) * posErr(2) + kd(2) * velErr(2) - distBlendH * distEst(2);
aCmd(3) = aRef(3) + kp(3) * posErr(3) + kd(3) * velErr(3) - distBlendZ * distEst(3);

accLimitH = min(2.80, 0.82 * g * tan(maxTilt));
accLimitZ = 3.00;
aCmd(1) = min(max(aCmd(1), -accLimitH), accLimitH);
aCmd(2) = min(max(aCmd(2), -accLimitH), accLimitH);
aCmd(3) = min(max(aCmd(3), -accLimitZ), accLimitZ);
end
