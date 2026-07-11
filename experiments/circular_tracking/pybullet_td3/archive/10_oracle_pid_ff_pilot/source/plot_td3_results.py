"""Generate paper-oriented figures from TD3 circular-tracking result folders."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CONTROLLER_LABELS = {
    "pid": "PID",
    "pid_ff": "PID-FF",
    "residual_td3": "Residual TD3",
    "disturbance_aware_residual_td3": "DA-Residual TD3",
    "disturbance_aware_residual_td3_no_gate": "DA-Residual no gate",
    "direct_td3": "Direct TD3",
}

CONTROLLER_COLORS = {
    "pid": "#2f455c",
    "pid_ff": "#5c7189",
    "residual_td3": "#3f8f70",
    "disturbance_aware_residual_td3": "#b64b4b",
    "disturbance_aware_residual_td3_no_gate": "#c77d2b",
    "direct_td3": "#7b5ea7",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_monitor_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        lines = [line for line in handle if not line.startswith("#")]
    if not lines:
        return []
    return list(csv.DictReader(lines))


def controller_label(controller: str) -> str:
    return CONTROLLER_LABELS.get(controller, controller)


def controller_color(controller: str) -> str:
    return CONTROLLER_COLORS.get(controller, "#555555")


def plot_trajectory(eval_folder: Path, controllers: Iterable[str], scenario: str, seed: int, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=160)
    for controller in controllers:
        path = eval_folder / controller / scenario / f"seed_{seed:03d}" / "trajectory.csv"
        if not path.exists():
            continue
        rows = read_csv(path)
        if not rows:
            continue
        x = [float(row["x"]) for row in rows]
        y = [float(row["y"]) for row in rows]
        ref_x = [float(row["ref_x"]) for row in rows]
        ref_y = [float(row["ref_y"]) for row in rows]
        ax.plot(x, y, label=controller_label(controller), color=controller_color(controller), linewidth=1.8)
        if controller == "pid":
            ax.plot(ref_x, ref_y, "--", label="Reference", color="#222222", linewidth=1.2)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"XY trajectory, {scenario}, seed {seed}")
    ax.axis("equal")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_position_error(eval_folder: Path, controllers: Iterable[str], scenario: str, seed: int, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=160)
    for controller in controllers:
        path = eval_folder / controller / scenario / f"seed_{seed:03d}" / "trajectory.csv"
        if not path.exists():
            continue
        rows = read_csv(path)
        if not rows:
            continue
        time = [float(row["time"]) for row in rows]
        error = [float(row["pos_error"]) for row in rows]
        ax.plot(time, error, label=controller_label(controller), color=controller_color(controller), linewidth=1.8)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("position error (m)")
    ax.set_title(f"Position error, {scenario}, seed {seed}")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_metric_bars(summary_metrics: Path, output: Path) -> None:
    rows = read_csv(summary_metrics)
    if not rows:
        return
    controllers = [row["controller"] for row in rows]
    x = range(len(controllers))
    rmse = [float(row["position_rmse"]) for row in rows]
    tilt = [float(row["max_tilt_angle"]) for row in rows]
    failures = [1.0 if row["failure"].lower() == "true" else 0.0 for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(9.5, 3.4), dpi=160)
    metrics = [
        ("Position RMSE (m)", rmse),
        ("Max tilt (rad)", tilt),
        ("Failure", failures),
    ]
    labels = [controller_label(controller) for controller in controllers]
    colors = [controller_color(controller) for controller in controllers]
    for ax, (title, values) in zip(axes, metrics):
        ax.bar(list(x), values, color=colors, width=0.68)
        ax.set_title(title)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
        ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_aggregate_metrics(
    aggregate_metrics: Path,
    controllers: Iterable[str],
    scenarios: Iterable[str],
    output: Path,
) -> None:
    rows = read_csv(aggregate_metrics)
    if not rows:
        return
    row_map = {(row["controller"], row["scenario"]): row for row in rows}
    controller_list = list(controllers)
    scenario_list = list(scenarios)
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), dpi=160)
    metrics = [
        ("position_rmse_mean", "Position RMSE mean (m)"),
        ("failure_rate", "Failure rate"),
    ]
    width = 0.8 / max(len(controller_list), 1)
    x_positions = list(range(len(scenario_list)))
    for ax, (metric, title) in zip(axes, metrics):
        for index, controller in enumerate(controller_list):
            values = [
                float(row_map.get((controller, scenario), {}).get(metric, "nan"))
                for scenario in scenario_list
            ]
            offsets = [x + (index - (len(controller_list) - 1) / 2) * width for x in x_positions]
            ax.bar(
                offsets,
                values,
                width=width,
                color=controller_color(controller),
                label=controller_label(controller),
            )
        ax.set_title(title)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(scenario_list, rotation=25, ha="right")
        ax.grid(True, axis="y", alpha=0.25)
    axes[1].set_ylim(0.0, 1.05)
    axes[0].legend(frameon=False, fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_training_rewards(runs_folder: Path, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=160)
    found = False
    for run_dir in sorted(path for path in runs_folder.iterdir() if path.is_dir()):
        monitor = run_dir / "monitor.csv"
        if not monitor.exists():
            continue
        rows = read_monitor_csv(monitor)
        if not rows:
            continue
        rewards = [float(row["r"]) for row in rows]
        episodes = list(range(1, len(rewards) + 1))
        label = run_dir.name.replace("_smoke_seed0", "").replace("_", " ")
        ax.plot(episodes, rewards, marker="o", linewidth=1.5, label=label)
        found = True
    if not found:
        plt.close(fig)
        return
    ax.set_xlabel("episode")
    ax.set_ylabel("episode reward")
    ax.set_title("TD3 smoke-training rewards")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_diagnostic_metrics(
    diagnostic_metrics: Path,
    controllers: Iterable[str],
    scenarios: Iterable[str],
    output: Path,
) -> None:
    rows = read_csv(diagnostic_metrics)
    if not rows:
        return
    row_map = {(row["controller"], row["scenario"]): row for row in rows}
    controller_list = list(controllers)
    scenario_list = list(scenarios)
    metrics = [
        ("mean_gate_mean", "Mean gate"),
        ("mean_action_norm_mean", "Mean action norm"),
        ("action_smoothness_mean", "Action smoothness"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.0), dpi=160)
    width = 0.8 / max(len(controller_list), 1)
    x_positions = list(range(len(scenario_list)))
    for ax, (metric, title) in zip(axes, metrics):
        for index, controller in enumerate(controller_list):
            values = [
                float(row_map.get((controller, scenario), {}).get(metric, "nan"))
                for scenario in scenario_list
            ]
            offsets = [x + (index - (len(controller_list) - 1) / 2) * width for x in x_positions]
            ax.bar(
                offsets,
                values,
                width=width,
                color=controller_color(controller),
                label=controller_label(controller),
            )
        ax.set_title(title)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(scenario_list, rotation=25, ha="right")
        ax.grid(True, axis="y", alpha=0.25)
    axes[0].set_ylim(0.0, 1.05)
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eval-folder",
        type=Path,
        default=Path("experiments/circular_tracking/results/td3_residual_paper/eval_td3_model_smoke_all"),
    )
    parser.add_argument(
        "--runs-folder",
        type=Path,
        default=Path("experiments/circular_tracking/results/td3_residual_paper/runs"),
    )
    parser.add_argument(
        "--aggregate-metrics",
        type=Path,
        default=None,
        help="Optional summary_metrics_aggregate.csv for multi-scenario grouped bars.",
    )
    parser.add_argument(
        "--diagnostic-metrics",
        type=Path,
        default=None,
        help="Optional diagnostic_summary_aggregate.csv for gate/action grouped bars.",
    )
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=Path("experiments/circular_tracking/results/td3_residual_paper/figures"),
    )
    parser.add_argument(
        "--controllers",
        nargs="+",
        default=["pid", "residual_td3", "disturbance_aware_residual_td3", "direct_td3"],
    )
    parser.add_argument("--scenario", default="standard")
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=["standard", "wind", "thermal", "dust", "compound"],
        help="Scenario order for aggregate figures.",
    )
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_folder.mkdir(parents=True, exist_ok=True)
    plot_trajectory(
        args.eval_folder,
        args.controllers,
        args.scenario,
        args.seed,
        args.output_folder / "figure3_trajectory_xy_smoke.png",
    )
    plot_position_error(
        args.eval_folder,
        args.controllers,
        args.scenario,
        args.seed,
        args.output_folder / "figure4_position_error_smoke.png",
    )
    plot_metric_bars(
        args.eval_folder / "summary_metrics.csv",
        args.output_folder / "figure5_metric_bars_smoke.png",
    )
    plot_training_rewards(
        args.runs_folder,
        args.output_folder / "figure6_training_smoke_rewards.png",
    )
    aggregate_path = args.aggregate_metrics or args.eval_folder / "summary_metrics_aggregate.csv"
    if aggregate_path.exists():
        plot_aggregate_metrics(
            aggregate_path,
            args.controllers,
            args.scenarios,
            args.output_folder / "figure5_aggregate_metrics.png",
        )
    diagnostic_path = args.diagnostic_metrics or args.eval_folder / "diagnostic_summary_aggregate.csv"
    if diagnostic_path.exists():
        plot_diagnostic_metrics(
            diagnostic_path,
            args.controllers,
            args.scenarios,
            args.output_folder / "figure6_gate_action_diagnostics.png",
        )


if __name__ == "__main__":
    main()
