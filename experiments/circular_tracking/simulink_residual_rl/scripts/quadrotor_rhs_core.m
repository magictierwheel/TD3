function [dx, dbg] = quadrotor_rhs_core(x, ref, omegaCmd, env, p)
%QUADROTOR_RHS_CORE Rigid-body dynamics with environment-corrected rotors.

dx = zeros(28, 1);
dbg = zeros(10, 1);

mass = p(1);
g = p(2);
arm = p(6);
kf = p(7);
kq = p(8);
Tm = p(9);
CDA = p(16);
rC = p(17:19);
J = reshape(p(20:28), 3, 3).';

pos = x(1:3);
vel = x(4:6);
eul = x(7:9);
omegaBody = x(10:12);
omegaRotor = x(16:19);

rho = env(1);
thermal = [0; 0; env(4)];
wind = env(5:7);
fT = env(11);
fQ = env(12);

phi = eul(1);
theta = eul(2);
psi = eul(3);
cphi = cos(phi); sphi = sin(phi);
cth = cos(theta); sth = sin(theta);
cpsi = cos(psi); spsi = sin(psi);

Rbw = [ cpsi*cth, cpsi*sth*sphi - spsi*cphi, cpsi*sth*cphi + spsi*sphi; ...
        spsi*cth, spsi*sth*sphi + cpsi*cphi, spsi*sth*cphi - cpsi*sphi; ...
        -sth,     cth*sphi,                    cth*cphi ];

omegaSq = omegaRotor .* omegaRotor;
Ti = kf * fT * omegaSq;
thrust = sum(Ti);
tauRotor = [arm * (Ti(2) - Ti(4)); ...
            arm * (Ti(3) - Ti(1)); ...
            kq * fQ * (-omegaSq(1) + omegaSq(2) - omegaSq(3) + omegaSq(4))];
tauCom = -cross(rC, [0; 0; thrust]);
tauTotal = tauRotor + tauCom;

vrel = vel - wind;
vrelNorm = sqrt(sum(vrel .* vrel));
dragForce = -0.5 * rho * CDA * vrelNorm * vrel;
acc = (Rbw * [0; 0; thrust]) / mass - [0; 0; g] + dragForce / mass + thermal;

tanTheta = sin(theta) / max(0.15, cos(theta));
E = [1, sphi * tanTheta, cphi * tanTheta; ...
     0, cphi,           -sphi; ...
     0, sphi / max(0.15, cos(theta)), cphi / max(0.15, cos(theta))];
eulDot = E * omegaBody;

omegaDot = J \ (tauTotal - cross(omegaBody, J * omegaBody));

dx(1:3) = vel;
dx(4:6) = acc;
dx(7:9) = eulDot;
dx(10:12) = omegaDot;
dx(13:15) = ref(1:3) - pos;
dx(16:19) = (omegaCmd - omegaRotor) / Tm;
if round(p(89)) == 4
    dx(20:28) = quadrotor_adrc_eso_derivative_core(x, ref, p);
end

dbg(1) = thrust;
dbg(2:4) = tauRotor;
dbg(5:7) = dragForce;
dbg(8:10) = acc;
end
