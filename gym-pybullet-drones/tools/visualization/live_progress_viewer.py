"""Live matplotlib viewer for experiments/hover_rl_reproduction/scripts/reproduce_hover_short.py progress.csv."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import matplotlib.pyplot as plt


def read_rows(csv_path: Path) -> list[dict[str, float]]:
    if not csv_path.exists():
        return []

    rows: list[dict[str, float]] = []
    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            try:
                rows.append(
                    {
                        "timesteps": float(row["timesteps"]),
                        "total_timesteps": float(row["total_timesteps"]),
                        "mean_reward": float(row["mean_reward"]),
                        "std_reward": float(row["std_reward"]),
                        "target_reward": float(row["target_reward"]),
                        "reward_gap": float(row["reward_gap"]),
                        "target_percent": float(row["target_percent"]),
                        "elapsed_sec": float(row["elapsed_sec"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
    return rows


def format_elapsed(seconds: float) -> str:
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {sec:02d}s"
    return f"{minutes:d}m {sec:02d}s"


def update_plot(ax: plt.Axes, csv_path: Path, target_reward: float) -> None:
    rows = read_rows(csv_path)
    ax.clear()
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("Training steps")
    ax.set_ylabel("Mean reward")
    ax.set_title("PPO hover training progress")

    if not rows:
        ax.text(
            0.5,
            0.5,
            f"Waiting for progress data...\n{csv_path}",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return

    steps = [row["timesteps"] for row in rows]
    rewards = [row["mean_reward"] for row in rows]
    target = target_reward if target_reward > 0 else rows[-1]["target_reward"]
    total_steps = rows[-1]["total_timesteps"]
    latest = rows[-1]

    ax.plot(steps, rewards, marker="o", linewidth=2, label="Mean reward")
    ax.axhline(target, color="tab:red", linestyle="--", linewidth=1.5, label="Target")
    ax.set_xlim(0, max(total_steps, max(steps)))

    y_values = rewards + [target]
    y_min = min(y_values)
    y_max = max(y_values)
    y_pad = max(5.0, (y_max - y_min) * 0.15)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)

    train_percent = 100.0 * latest["timesteps"] / total_steps if total_steps else 0.0
    status = (
        f"steps: {int(latest['timesteps'])}/{int(total_steps)} ({train_percent:.1f}%)\n"
        f"mean reward: {latest['mean_reward']:.2f} +/- {latest['std_reward']:.2f}\n"
        f"target: {target:.2f} | gap: {latest['reward_gap']:.2f}\n"
        f"target progress: {latest['target_percent']:.1f}%\n"
        f"elapsed: {format_elapsed(latest['elapsed_sec'])}"
    )
    ax.text(
        0.02,
        0.98,
        status,
        ha="left",
        va="top",
        transform=ax.transAxes,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.85},
    )
    ax.legend(loc="lower right")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show live training progress.")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--target-reward", type=float, default=474.0)
    parser.add_argument("--refresh-sec", type=float, default=5.0)
    args = parser.parse_args()

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.canvas.manager.set_window_title("Training progress")

    while plt.fignum_exists(fig.number):
        update_plot(ax, args.csv, args.target_reward)
        fig.tight_layout()
        fig.canvas.draw_idle()
        plt.pause(args.refresh_sec)
        time.sleep(0.05)


if __name__ == "__main__":
    main()
