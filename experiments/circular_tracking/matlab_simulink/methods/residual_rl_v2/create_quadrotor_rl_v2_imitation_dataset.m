function imitation = create_quadrotor_rl_v2_imitation_dataset(modelTypes)
%CREATE_QUADROTOR_RL_V2_IMITATION_DATASET Collect MPC teacher samples.
%   The teacher combines disturbance feedforward with the temperature-gated
%   difference between the MPC and baseline outer-loop acceleration.

if nargin < 1 || isempty(modelTypes)
    modelTypes = {'standard', 'temperature', 'dust'};
end

hiddenRows = zeros(0, 16);
targetRows = zeros(0, 5);
gateRows = zeros(0, 1);
modelRows = strings(0, 1);
rollouts = struct();

for modelIndex = 1:numel(modelTypes)
    modelType = char(modelTypes{modelIndex});
    params = init_quadrotor_params(modelType, 'circle', false);
    pBase = params.paramVec;
    pBase(88) = params.scenarioId;
    pBase(90) = params.modelId;
    pMpc = pBase;
    pMpc(89) = 3;
    pMpc(97) = 1.0;

    dt = 0.10;
    sampleCount = round(params.stopTime / dt) + 1;
    x = params.x0;
    compactRows = zeros(sampleCount, 13);
    modelHidden = zeros(sampleCount, 16);
    modelTargets = zeros(sampleCount, 5);
    modelGates = zeros(sampleCount, 1);

    for sampleIndex = 1:sampleCount
        t = (sampleIndex - 1) * dt;
        ref = quadrotor_reference_core(t, params.scenarioId, pBase);
        env = quadrotor_environment_core(t, x, params.modelId, pBase);
        baseA = baseline_outer_acceleration(x, ref, pBase);
        mpcA = quadrotor_mpc_outer_core(t, x, pMpc);
        [ffA, ffThrustScale, ffTauScale] = ...
            quadrotor_disturbance_compensation_core(x, env, pBase);
        [~, hidden, tempGate, residualGate] = ...
            quadrotor_rl_v2_features_core(t, x, ref, env, pBase);

        accelerationTeacher = ffA + tempGate * (mpcA - baseA);
        torqueTeacher = mean(ffTauScale - 1.0);
        teacher = [accelerationTeacher; ...
            ffThrustScale - 1.0; torqueTeacher];

        compactRows(sampleIndex, :) = [t, x(1:3).', ref(1:3).', ...
            teacher(1:3).', ffThrustScale, ffTauScale.'];
        modelHidden(sampleIndex, :) = hidden.';
        modelTargets(sampleIndex, :) = teacher.';
        modelGates(sampleIndex) = residualGate;

        if sampleIndex < sampleCount
            x = rk4_step(t, x, dt, params.scenarioId, params.modelId, pMpc);
        end
    end

    rollouts.(modelType) = compactRows;
    hiddenRows = [hiddenRows; modelHidden]; %#ok<AGROW>
    targetRows = [targetRows; modelTargets]; %#ok<AGROW>
    gateRows = [gateRows; modelGates]; %#ok<AGROW>
    modelRows = [modelRows; repmat(string(modelType), sampleCount, 1)]; %#ok<AGROW>
end

if any(~isfinite(hiddenRows(:))) || any(~isfinite(targetRows(:))) || ...
        any(~isfinite(gateRows))
    error('RLV2:NonFiniteImitationData', ...
        'MPC imitation data contains NaN or Inf values.');
end

imitation = rollouts;
imitation.hidden = hiddenRows;
imitation.targets = targetRows;
imitation.gates = gateRows;
imitation.modelType = modelRows;
imitation.sampleCount = size(hiddenRows, 1);
imitation.gatedSampleCount = nnz(gateRows > 0.05);
end

function aCmd = baseline_outer_acceleration(x, ref, p)
aCmd = ref(7:9);
errPos = ref(1:3) - x(1:3);
errVel = ref(4:6) - x(4:6);
ierr = min(max(x(13:15), -p(65)), p(65));
aCmd(1) = aCmd(1) + p(54) * errPos(1) + ...
    p(55) * errVel(1) + p(56) * ierr(1);
aCmd(2) = aCmd(2) + p(54) * errPos(2) + ...
    p(55) * errVel(2) + p(56) * ierr(2);
aCmd(3) = aCmd(3) + p(57) * errPos(3) + ...
    p(58) * errVel(3) + p(59) * ierr(3);
end

function xNext = rk4_step(t, x, dt, scenarioId, modelId, p)
k1 = closed_loop_rhs(t, x, scenarioId, modelId, p);
k2 = closed_loop_rhs(t + 0.5 * dt, x + 0.5 * dt * k1, ...
    scenarioId, modelId, p);
k3 = closed_loop_rhs(t + 0.5 * dt, x + 0.5 * dt * k2, ...
    scenarioId, modelId, p);
k4 = closed_loop_rhs(t + dt, x + dt * k3, scenarioId, modelId, p);
xNext = x + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6;
end

function dx = closed_loop_rhs(t, x, scenarioId, modelId, p)
ref = quadrotor_reference_core(t, scenarioId, p);
env = quadrotor_environment_core(t, x, modelId, p);
[omegaCmd, ~] = quadrotor_controller_core(t, x, ref, p);
[dx, ~] = quadrotor_rhs_core(x, ref, omegaCmd, env, p);
end
