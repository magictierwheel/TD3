function rootDir = matlab_simulink_root()
%MATLAB_SIMULINK_ROOT Return the canonical MATLAB/Simulink study root.
rootDir = fileparts(fileparts(mfilename('fullpath')));
end
