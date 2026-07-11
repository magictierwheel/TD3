function aCmd = quadrotor_mpc_outer_core(t, x, p)
%QUADROTOR_MPC_OUTER_CORE Fixed-size linear MPC outer loop.
%   Uses a discrete double-integrator model over a finite horizon and returns
%   the first inertial-frame acceleration command. Constraints are enforced as
%   hard acceleration clipping before the existing attitude/thrust limits.

aCmd = zeros(3, 1);

Ts = 0.08;
horizon = 18;
scenarioId = p(88);
if scenarioId < 0.5
    scenarioId = 2.0;
end

refPos = zeros(horizon, 3);
refVel = zeros(horizon, 3);
for k = 1:horizon
    ref = quadrotor_reference_core(t + k * Ts, scenarioId, p);
    refPos(k, :) = ref(1:3).';
    refVel(k, :) = ref(4:6).';
end

for axis = 1:3
    stateAxis = [x(axis); x(axis + 3)];
    if axis < 3
        qPos = 16.0;
        qVel = 5.0;
        rAcc = 3.8;
        accLimit = min(2.30, 0.70 * p(2) * tan(p(64)));
    else
        qPos = 24.0;
        qVel = 6.0;
        rAcc = 2.5;
        accLimit = 2.6;
    end
    aCmd(axis) = solve_axis_mpc(stateAxis, refPos(:, axis), refVel(:, axis), ...
        Ts, qPos, qVel, rAcc, accLimit);
end
end

function u0 = solve_axis_mpc(x0, refPos, refVel, Ts, qPos, qVel, rAcc, accLimit)
N = 18;
H = zeros(N, N);
f = zeros(N, 1);

for step = 1:N
    basePos = x0(1) + step * Ts * x0(2);
    baseVel = x0(2);
    posErr0 = basePos - refPos(step);
    velErr0 = baseVel - refVel(step);
    for j = 1:step
        velCoeffJ = Ts;
        posCoeffJ = (step - j + 0.5) * Ts * Ts;
        f(j) = f(j) + qPos * posCoeffJ * posErr0 + qVel * velCoeffJ * velErr0;
        for l = 1:step
            velCoeffL = Ts;
            posCoeffL = (step - l + 0.5) * Ts * Ts;
            H(j, l) = H(j, l) + qPos * posCoeffJ * posCoeffL + qVel * velCoeffJ * velCoeffL;
        end
    end
end

for j = 1:N
    H(j, j) = H(j, j) + rAcc;
end

uSeq = -(H \ f);
u0 = min(max(uSeq(1), -accLimit), accLimit);
end
