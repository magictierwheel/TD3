function out = parse_quad_log(rawLog, modelType, scenarioName)
%PARSE_QUAD_LOG Convert the 66-column To Workspace array into named fields.

if isa(rawLog, 'timeseries')
    rawLog = rawLog.Data;
end
if isstruct(rawLog) && isfield(rawLog, 'signals')
    rawLog = rawLog.signals.values;
end

if ndims(rawLog) == 3
    rawLog = squeeze(rawLog);
end
if size(rawLog, 2) == 66
    data = rawLog;
elseif size(rawLog, 1) == 66
    data = rawLog.';
else
    error('Unexpected sim_log dimensions: %s', mat2str(size(rawLog)));
end

out = struct();
out.modelType = modelType;
out.scenarioName = scenarioName;
out.t = data(:, 1);
out.x = data(:, 2:20);
out.pos = data(:, 2:4);
out.vel = data(:, 5:7);
out.euler = data(:, 8:10);
out.bodyRate = data(:, 11:13);
out.integralError = data(:, 14:16);
out.rotorOmega = data(:, 17:20);
out.ref = data(:, 21:30);
out.refPos = data(:, 21:23);
out.refVel = data(:, 24:26);
out.refAcc = data(:, 27:29);
out.refYaw = data(:, 30);
out.env = data(:, 31:42);
out.rho = data(:, 31);
out.deltaT = data(:, 32);
out.fireShape = data(:, 33);
out.thermalZ = data(:, 34);
out.wind = data(:, 35:37);
out.dustCd = data(:, 38);
out.etaT = data(:, 39);
out.etaQ = data(:, 40);
out.fT = data(:, 41);
out.fQ = data(:, 42);
out.omegaCmd = data(:, 43:46);
out.ctrlDbg = data(:, 47:56);
out.thrustCmd = data(:, 47);
out.tauCmd = data(:, 48:50);
out.attDes = data(:, 51:53);
out.posErrNorm = data(:, 54);
out.zErr = data(:, 55);
out.tiltCmdNorm = data(:, 56);
out.plantDbg = data(:, 57:66);
out.thrustActual = data(:, 57);
out.tauRotor = data(:, 58:60);
out.dragForce = data(:, 61:63);
out.acc = data(:, 64:66);
out.posErr = out.pos - out.refPos;
out.posErrAbs = sqrt(sum(out.posErr .* out.posErr, 2));
end
