function env = quadrotor_environment_core(t, x, modelId, p)
%QUADROTOR_ENVIRONMENT_CORE Temperature and dust disturbance proxy.
%   env = [rho; deltaT; Sfire; thermalZ; wind(3); dustCd; etaT; etaQ; fT; fQ].

env = zeros(12, 1);

rho0 = p(12);
rho = rho0;
deltaT = 0;
Sfire = 0;
thermalZ = 0;
wind = zeros(3, 1);
dustCd = 0;
etaT = 1;
etaQ = 1;

unusedX = x(1); %#ok<NASGU>
stepActive = t >= 5.0;

if modelId > 0.5 && modelId < 1.5
    if stepActive
        Sfire = 1.0;
        deltaT = 55.0;
        rho = p(14) / (p(15) * (p(13) + deltaT));
        wind = p(29:31) + p(32:34);
        thermalZ = p(43);
    end
elseif modelId >= 1.5
    if stepActive
        dustCd = 0.010;
    end
    muD = dustCd / max(rho, 1.0e-6);
    fd = min(max((p(45) / p(46))^0.15, 0.25), 2.5);
    etaT = min(max(1.0 - 2.5 * (muD^0.85) * fd, 0.88), 1.0);
    etaQ = min(max(1.0 - 1.5 * (muD^0.85) * fd, 0.90), 1.0);
end

fT = max(0.25, rho / rho0 * etaT);
fQ = max(0.25, rho / rho0 * etaQ);

env(1) = rho;
env(2) = deltaT;
env(3) = Sfire;
env(4) = thermalZ;
env(5:7) = wind;
env(8) = dustCd;
env(9) = etaT;
env(10) = etaQ;
env(11) = fT;
env(12) = fQ;
end
