function params = init_quadrotor_params(modelType, scenarioName, assignToBase)
%INIT_QUADROTOR_PARAMS Prepare base-workspace variables for one comparison run.
%   The generated Simulink models read only named variables produced here:
%   quad_param_vec, quad_model_id, quad_scenario_id, quad_x0, quad_stop_time.
%
%   params = INIT_QUADROTOR_PARAMS(modelType, scenarioName, false) returns the
%   same parameter struct without writing variables to the base workspace. This
%   mode is used by run_all_simulations through Simulink.SimulationInput.

if nargin < 1 || isempty(modelType)
    modelType = 'standard';
end
if nargin < 2 || isempty(scenarioName)
    scenarioName = 'hover';
end
if nargin < 3 || isempty(assignToBase)
    assignToBase = true;
end

modelType = lower(strtrim(modelType));
scenarioName = lower(strtrim(scenarioName));

switch modelType
    case {'standard','base'}
        modelId = 0;
        modelName = 'quadrotor_standard';
        modelLabel = 'Standard';
    case {'temperature','temp'}
        modelId = 1;
        modelName = 'quadrotor_temperature';
        modelLabel = 'Temperature';
    case {'dust','particle'}
        modelId = 2;
        modelName = 'quadrotor_dust';
        modelLabel = 'Dust';
    otherwise
        error('Unknown modelType: %s', modelType);
end

switch scenarioName
    case {'hover','hovering'}
        scenarioId = 1;
        scenarioLabel = 'Hover';
        stopTime = 20;
    case {'circle','circular','uniform_circle'}
        scenarioId = 2;
        scenarioLabel = 'UniformCircle';
        stopTime = 30;
    case {'point_to_point','point','p2p'}
        scenarioId = 3;
        scenarioLabel = 'PointToPoint';
        stopTime = 25;
    otherwise
        error('Unknown scenarioName: %s', scenarioName);
end

p = zeros(240, 1);

% Core quadrotor parameters. The controller structure and baseline inertia
% follow the supplied UAV_INPUT/UAV_input.m reference, while the aerodynamic
% thrust/dust coefficients follow the supplied formula-derivation document.
p(1)  = 1.0;          % mass, kg
p(2)  = 9.81;         % gravity, m/s^2
p(3)  = 0.0095;       % Ixx, kg*m^2
p(4)  = 0.0095;       % Iyy, kg*m^2
p(5)  = 0.0186;       % Izz, kg*m^2
p(6)  = 0.23;         % arm length, m
p(7)  = 8.0e-6;       % baseline thrust coefficient kf0
p(8)  = 1.7e-7;       % baseline counter-torque coefficient kq0
p(9)  = 0.076;        % motor first-order time constant, s
p(10) = 120;          % minimum rotor speed, rad/s
p(11) = 1150;         % maximum rotor speed, rad/s
p(12) = 1.225;        % sea-level air density, kg/m^3
p(13) = 288.15;       % ISA ambient temperature, K
p(14) = p(12) * 287.05 * p(13); % pressure chosen so rho=rho0 at ISA
p(15) = 287.05;       % dry-air gas constant, J/(kg*K)
p(16) = 0.075;        % combined drag coefficient and reference area

% Standard comparison keeps the same mass properties across the three
% environmental models so that the isolated disturbance path is visible.
p(17:19) = [0; 0; 0]; % center-of-mass offset, m
J = diag([p(3), p(4), p(5)]);
p(20:28) = reshape(J.', 9, 1);

% Fire-temperature proxy, density reduction, induced wind and thermal updraft.
p(29:31) = [1.40; 0.25; 0.00]; % base wind used by temperature model, m/s
p(32:34) = [0.80; 0.25; 0.45]; % fire-induced wind coefficient, m/s
p(35) = 2.0;          % fire center x, m
p(36) = 1.5;          % fire center y, m
p(37) = 2.4;          % fire sigma x, m
p(38) = 2.0;          % fire sigma y, m
p(39) = 82.0;         % peak temperature rise, K
p(40) = 0.82;         % fire temporal base
p(41) = 0.18;         % fire temporal amplitude
p(42) = 0.18;         % fire temporal angular rate, rad/s
p(43) = 1.15;         % thermal updraft peak proxy, m/s^2

% Dust-concentration proxy. Peak concentration is kept moderate but visible;
% eta_T,d and eta_Q,d still use the clipped equations from the formula note.
p(44) = 0.0040;       % peak dust concentration, kg/m^3
p(45) = 50e-6;        % particle diameter, m
p(46) = 50e-6;        % reference particle diameter, m
p(47) = 3.0;          % dust cloud center x, m
p(48) = 2.0;          % dust cloud center y, m
p(49) = 3.5;          % dust sigma x, m
p(50) = 3.0;          % dust sigma y, m
p(51) = 5.0;          % dust pulse start, s
p(52) = 18.0;         % dust pulse end, s
p(53) = 0.8;          % dust pulse transition time, s

% Unified controller gains. These remain unchanged for all model comparisons.
p(54) = 0.85;         % horizontal position Kp
p(55) = 1.55;         % horizontal velocity Kd
p(56) = 0.025;        % horizontal integral Ki
p(57) = 4.20;         % vertical position Kp
p(58) = 3.20;         % vertical velocity Kd
p(59) = 0.080;        % vertical integral Ki
p(60) = 10.0;         % roll/pitch attitude Kp
p(61) = 3.40;         % roll/pitch rate Kd
p(62) = 4.50;         % yaw Kp
p(63) = 1.80;         % yaw-rate Kd
p(64) = 0.48;         % maximum commanded roll/pitch angle, rad
p(65) = 1.50;         % integral-state clamp used by controller, m*s

% Scenario parameters.
p(70) = 2.0;          % hover altitude, m
p(71) = 2.0;          % circle radius, m
p(72) = 0.32;         % circle angular rate, rad/s
p(73) = 2.4;          % circle altitude, m
p(74) = 18.0;         % point-to-point transition time, s
p(75:77) = [0.0; 0.0; 1.6]; % point-to-point start, m
p(78:80) = [5.0; 4.0; 2.6]; % point-to-point goal, m

% Reinforcement-learning residual policy deployment slots.
% p(89) selects the controller:
%   0 original cascaded PID, 1 RL residual policy,
%   2 PID with deterministic disturbance feedforward,
%   3 linear MPC outer loop with deterministic disturbance feedforward,
%   4 ADRC outer loop with linear extended-state observer,
%   5 RL-v2 preview residual policy.
p(88) = scenarioId;   % scenario identity visible inside controller/MPC
p(89) = 0;            % controller mode
p(90) = modelId;      % model identity visible inside the controller
p(91) = 1.0;          % RL weight: drag acceleration cancellation
p(92) = 1.0;          % RL weight: thermal-updraft cancellation
p(93) = 1.0;          % RL weight: thrust loss compensation
p(94) = 1.0;          % RL weight: roll/pitch torque loss compensation
p(95) = 1.0;          % RL weight: yaw torque loss compensation
p(96) = 1.0;          % RL safety blend, 0 disables residual action
p(97) = 1.0;          % deterministic feedforward blend
p(98) = 5.0;          % ADRC ESO horizontal bandwidth, rad/s
p(99) = 6.0;          % ADRC ESO vertical bandwidth, rad/s
p(100) = 1.00;        % ADRC horizontal tracking bandwidth, rad/s
p(101) = 2.00;        % ADRC vertical tracking bandwidth, rad/s
p(102) = 0.04;        % ADRC disturbance-estimate compensation blend
p(103) = 2.20;        % ADRC horizontal disturbance estimate clamp, m/s^2
p(104) = 2.80;        % ADRC vertical disturbance estimate clamp, m/s^2
p(105) = 0.95;        % ADRC vertical disturbance-estimate compensation blend

% RL-v2 preview residual policy slots. p(121:240) are intentionally kept
% fixed-size for Simulink deployment. The deployed network uses deterministic
% 32->16 hidden features and trains the output/readout parameters here.
p(121) = 2.0;         % RL-v2 policy version marker
p(122) = 1.0;         % RL-v2 safety blend
p(209:213) = [0.20; 0.20; 0.16; 0.08; 0.06]; % output channel scales
p(214) = 1.0;         % preview-teacher blend
p(215) = 0.0;         % learned readout blend
p(216) = 0.25;        % learned acceleration residual scale, m/s^2
p(217) = 0.08;        % learned thrust-scale residual
p(218) = 0.06;        % learned torque-scale residual
p(219) = 3.0;         % RL-v2 acceleration residual clamp, m/s^2
p(220) = 1.0;         % deterministic disturbance feedforward blend

ref0 = quadrotor_reference_core(0.0, scenarioId, p);
hoverOmega = sqrt(p(1) * p(2) / (4.0 * p(7)));
x0 = zeros(28, 1);
x0(1:3) = ref0(1:3);
x0(16:19) = hoverOmega * ones(4, 1);
x0(20:22) = x0(1:3);
x0(23:25) = x0(4:6);

params = struct();
params.modelType = modelType;
params.modelId = modelId;
params.modelName = modelName;
params.modelLabel = modelLabel;
params.scenarioName = scenarioName;
params.scenarioId = scenarioId;
params.scenarioLabel = scenarioLabel;
params.stopTime = stopTime;
params.paramVec = p;
params.x0 = x0;
params.hoverOmega = hoverOmega;

if assignToBase
    assignin('base', 'quad_model_id', modelId);
    assignin('base', 'quad_scenario_id', scenarioId);
    assignin('base', 'quad_param_vec', p);
    assignin('base', 'quad_x0', x0);
    assignin('base', 'quad_stop_time', stopTime);
    assignin('base', 'quad_model_label', modelLabel);
    assignin('base', 'quad_scenario_label', scenarioLabel);
end
end
