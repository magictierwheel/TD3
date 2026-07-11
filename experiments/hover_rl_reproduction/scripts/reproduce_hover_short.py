"""Short PPO reproduction for the single-drone hover task.

This script keeps the original project code untouched and provides a quick,
headless reproduction path that works well in Docker. It trains a PPO policy
for a small number of steps, saves the model, evaluates it, and writes a short
rollout CSV for inspection.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.evaluation import evaluate_policy

from gym_pybullet_drones.tasks.hover.envs.HoverAviary import HoverAviary
from gym_pybullet_drones.utils.enums import ActionType, ObservationType


OBS_TYPE = ObservationType.KIN
ACT_TYPE = ActionType.ONE_D_RPM
DEFAULT_TARGET_REWARD = 474.0


def build_env(gui: bool = False) -> HoverAviary:
    return HoverAviary(gui=gui, obs=OBS_TYPE, act=ACT_TYPE)


class TrainingProgressCallback(BaseCallback):
    """Print and save periodic evaluation progress during training."""

    def __init__(
        self,
        eval_env: HoverAviary,
        total_timesteps: int,
        target_reward: float,
        eval_freq: int,
        eval_episodes: int,
        output_csv: Path,
    ) -> None:
        super().__init__()
        self.eval_env = eval_env
        self.total_timesteps = total_timesteps
        self.target_reward = target_reward
        self.eval_freq = eval_freq
        self.eval_episodes = eval_episodes
        self.output_csv = output_csv
        self.last_eval_step = 0
        self.eval_index = 0
        self.final_eval_done = False
        self.started_at = 0.0
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with self.output_csv.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "eval_index",
                    "timesteps",
                    "total_timesteps",
                    "elapsed_sec",
                    "mean_reward",
                    "std_reward",
                    "target_reward",
                    "reward_gap",
                    "target_percent",
                ],
            )
            writer.writeheader()

    def _on_training_start(self) -> None:
        self.started_at = time.time()
        print(
            "\n[TRAINING PROGRESS] "
            f"target_reward={self.target_reward:.2f}, "
            f"eval_freq={self.eval_freq} steps, "
            f"eval_episodes={self.eval_episodes}, "
            f"log={self.output_csv}"
        )

    def _on_step(self) -> bool:
        if self.eval_freq <= 0:
            return True

        due = self.num_timesteps - self.last_eval_step >= self.eval_freq
        finished = self.num_timesteps >= self.total_timesteps
        if finished and self.final_eval_done:
            return True
        if not due and not finished:
            return True

        self.last_eval_step = self.num_timesteps
        if finished:
            self.final_eval_done = True
        self.eval_index += 1
        mean_reward, std_reward = evaluate_policy(
            self.model,
            self.eval_env,
            n_eval_episodes=self.eval_episodes,
            deterministic=True,
            warn=False,
        )

        elapsed = time.time() - self.started_at
        reward_gap = self.target_reward - float(mean_reward)
        target_percent = (
            100.0 * max(0.0, float(mean_reward)) / self.target_reward
            if self.target_reward > 0
            else float("nan")
        )
        train_percent = 100.0 * self.num_timesteps / self.total_timesteps
        print(
            "[PROGRESS] "
            f"eval={self.eval_index} | "
            f"steps={self.num_timesteps}/{self.total_timesteps} "
            f"({train_percent:.1f}%) | "
            f"mean_reward={mean_reward:.2f} +/- {std_reward:.2f} | "
            f"target={self.target_reward:.2f} | "
            f"gap={reward_gap:.2f} | "
            f"target_progress={target_percent:.1f}%"
        )

        with self.output_csv.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "eval_index",
                    "timesteps",
                    "total_timesteps",
                    "elapsed_sec",
                    "mean_reward",
                    "std_reward",
                    "target_reward",
                    "reward_gap",
                    "target_percent",
                ],
            )
            writer.writerow(
                {
                    "eval_index": self.eval_index,
                    "timesteps": self.num_timesteps,
                    "total_timesteps": self.total_timesteps,
                    "elapsed_sec": elapsed,
                    "mean_reward": float(mean_reward),
                    "std_reward": float(std_reward),
                    "target_reward": self.target_reward,
                    "reward_gap": reward_gap,
                    "target_percent": target_percent,
                }
            )

        return True


def run_rollout(model: PPO, output_csv: Path, steps: int) -> dict[str, float]:
    env = build_env(gui=False)
    obs, _ = env.reset(seed=123, options={})
    rows = []
    rewards = []

    for step in range(steps):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(action)

        obs_flat = np.asarray(obs, dtype=float).reshape(-1)
        action_flat = np.asarray(action, dtype=float).reshape(-1)
        reward_value = float(np.asarray(reward).reshape(-1)[0])
        rewards.append(reward_value)

        rows.append(
            {
                "step": step,
                "x": obs_flat[0],
                "y": obs_flat[1],
                "z": obs_flat[2],
                "action": action_flat[0],
                "reward": reward_value,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )

        if terminated or truncated:
            break

    env.close()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "step",
                "x",
                "y",
                "z",
                "action",
                "reward",
                "terminated",
                "truncated",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return {
        "rollout_steps": float(len(rows)),
        "rollout_reward_sum": float(np.sum(rewards)),
        "final_z": float(rows[-1]["z"]) if rows else float("nan"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate PPO on gym-pybullet-drones HoverAviary."
    )
    parser.add_argument("--timesteps", type=int, default=2048)
    parser.add_argument("--eval-episodes", type=int, default=3)
    parser.add_argument("--rollout-steps", type=int, default=240)
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=Path("experiments/hover_rl_reproduction/results/repro_hover_short"),
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--verbose", type=int, default=0)
    parser.add_argument("--target-reward", type=float, default=DEFAULT_TARGET_REWARD)
    parser.add_argument("--progress-eval-freq", type=int, default=1000)
    parser.add_argument("--progress-eval-episodes", type=int, default=3)
    args = parser.parse_args()

    torch.set_num_threads(1)
    args.output_folder.mkdir(parents=True, exist_ok=True)

    train_env = make_vec_env(
        HoverAviary,
        env_kwargs={"gui": False, "obs": OBS_TYPE, "act": ACT_TYPE},
        n_envs=1,
        seed=args.seed,
    )
    eval_env = build_env(gui=False)

    model = PPO(
        "MlpPolicy",
        train_env,
        n_steps=64,
        batch_size=64,
        n_epochs=4,
        learning_rate=3e-4,
        gamma=0.99,
        seed=args.seed,
        verbose=args.verbose,
    )
    progress_callback = TrainingProgressCallback(
        eval_env=eval_env,
        total_timesteps=args.timesteps,
        target_reward=args.target_reward,
        eval_freq=args.progress_eval_freq,
        eval_episodes=args.progress_eval_episodes,
        output_csv=args.output_folder / "progress.csv",
    )
    model.learn(
        total_timesteps=args.timesteps,
        callback=progress_callback,
        progress_bar=False,
    )

    model_path = args.output_folder / "ppo_hover_short.zip"
    model.save(model_path)

    mean_reward, std_reward = evaluate_policy(
        model,
        eval_env,
        n_eval_episodes=args.eval_episodes,
        deterministic=True,
    )
    eval_env.close()
    train_env.close()

    rollout_summary = run_rollout(
        model=model,
        output_csv=args.output_folder / "rollout.csv",
        steps=args.rollout_steps,
    )

    summary = {
        "task": "single_drone_hover",
        "algorithm": "PPO",
        "observation": OBS_TYPE.value,
        "action": ACT_TYPE.value,
        "timesteps": args.timesteps,
        "eval_episodes": args.eval_episodes,
        "target_reward": args.target_reward,
        "progress_csv": str(args.output_folder / "progress.csv"),
        "mean_reward": float(mean_reward),
        "std_reward": float(std_reward),
        "model_path": str(model_path),
        "rollout_csv": str(args.output_folder / "rollout.csv"),
        **rollout_summary,
    }
    summary_path = args.output_folder / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n[REPRODUCTION COMPLETE]")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
