function setup_simulink_residual_rl_paths()
%SETUP_SIMULINK_RESIDUAL_RL_PATHS Add local Simulink RL folders to MATLAB path.

rootDir = fileparts(mfilename('fullpath'));
addpath(fullfile(rootDir, 'scripts'));
addpath(fullfile(rootDir, 'models'));
fprintf('Simulink residual-RL paths added: %s\n', rootDir);
end
