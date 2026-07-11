function setup_matlab_simulink_paths()
%SETUP_MATLAB_SIMULINK_PATHS Add only active source folders to MATLAB path.
rootDir = fileparts(mfilename('fullpath'));
folders = {
    rootDir
    fullfile(rootDir, 'common')
    fullfile(rootDir, 'methods', 'pid')
    fullfile(rootDir, 'methods', 'pid_feedforward')
    fullfile(rootDir, 'methods', 'mpc')
    fullfile(rootDir, 'methods', 'adrc')
    fullfile(rootDir, 'methods', 'residual_rl_v1')
    fullfile(rootDir, 'methods', 'residual_rl_v2')
    fullfile(rootDir, 'studies', '00_environment_models')
    fullfile(rootDir, 'studies', '10_controller_comparison')
    fullfile(rootDir, 'studies', '20_residual_rl_v1')
    fullfile(rootDir, 'studies', '30_rl_v2_mpc_imitation')
    };
for idx = 1:numel(folders)
    addpath(folders{idx});
end
fprintf('MATLAB/Simulink study paths added: %s\n', rootDir);
end
