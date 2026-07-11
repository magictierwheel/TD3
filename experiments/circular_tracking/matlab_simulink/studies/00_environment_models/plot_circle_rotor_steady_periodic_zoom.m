function outPath = plot_circle_rotor_steady_periodic_zoom()
%PLOT_CIRCLE_ROTOR_STEADY_PERIODIC_ZOOM Magnify steady circular-flight rotor differences.

rootDir = matlab_simulink_root();
dataPath = fullfile(rootDir, 'artifacts', '00_environment_models', 'data', ...
    'quadrotor_environment_comparison_results.mat');
figDir = fullfile(rootDir, 'artifacts', '00_environment_models', 'figures');
if ~exist(figDir, 'dir')
    mkdir(figDir);
end

data = load(dataPath, 'results');
scenario = data.results.circle;

models = {'standard', 'temperature', 'dust'};
modelTitles = { ...
    zh([26631 20934 27169 22411 65306 31283 23450 27573 26059 32764 24046 21160]), ...
    zh([28201 24230 25200 21160 27169 22411 65306 31283 23450 27573 26059 32764 24046 21160]), ...
    zh([31881 23576 25200 21160 27169 22411 65306 31283 23450 27573 26059 32764 24046 21160])};
rotorLabels = {zh([26059 32764 49]), zh([26059 32764 50]), ...
    zh([26059 32764 51]), zh([26059 32764 52])};
rotorColors = [0.00 0.27 0.56; 0.78 0.20 0.16; 0.12 0.50 0.24; 0.45 0.22 0.70];

fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1180 920]);
for i = 1:numel(models)
    out = scenario.(models{i});
    idx = out.t >= 10 & out.t <= 30;
    t = out.t(idx);
    omega = out.rotorOmega(idx, :);
    omegaDiff = omega - mean(omega, 2);
    maxAbs = max(abs(omegaDiff), [], 'all');
    yLimit = max(0.01, 1.15 * maxAbs);

    subplot(3, 1, i);
    for r = 1:4
        plot(t, omegaDiff(:, r), 'Color', rotorColors(r, :), 'LineWidth', 1.5); hold on;
    end
    yline(0, 'k:', 'LineWidth', 0.8);
    xlim([10 30]);
    ylim([-yLimit yLimit]);
    grid on;
    ylabel(zh([24046 21160 36716 36895 32 47 32 114 97 100 32 115 94 123 45 49 125]));
    title(modelTitles{i});
    legend(rotorLabels, 'Location', 'best');
    if i == numel(models)
        xlabel(zh([26102 38388 32 47 32 115]));
    end
end

set_figure_title(zh([21248 36895 22278 21608 39134 34892 24037 20917 31283 23450 27573 26059 32764 36716 36895 21608 26399 24615 24046 21160 25918 22823 22270]));
annotation(fig, 'textbox', [0.12 0.01 0.78 0.04], ...
    'String', zh([22235 26059 32764 24179 22343 36716 36895 24050 25187 38500 65292 20165 26174 31034 21508 26059 32764 30456 23545 24179 22343 20540 30340 24494 23567 21608 26399 24615 24046 21160]), ...
    'EdgeColor', 'none', 'HorizontalAlignment', 'center', 'FontSize', 10);

outPath = fullfile(figDir, 'circle_rotor_steady_periodic_zoom.png');
print(fig, outPath, '-dpng', '-r220');
close(fig);
fprintf('Saved: %s\n', outPath);
end

function text = zh(codePoints)
text = char(codePoints);
end

function set_figure_title(text)
if exist('sgtitle', 'file') == 2
    sgtitle(text);
else
    axesHandles = findall(gcf, 'Type', 'axes');
    if ~isempty(axesHandles)
        title(axesHandles(end), text);
    end
end
end
