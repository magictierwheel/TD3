"""Train Direct TD3 on the circular tracking environment."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from stable_baselines3 import TD3
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.noise import NormalActionNoise

from experiments.circular_tracking.rl_envs import CircularResidualTD3Env


class EpisodeProgressCallback(BaseCallback):
    """Write a small episode-level progress CSV independent of SB3 log dumps."""

    def __init__(self, progress_path: Path) -> None:
        super().__init__()
        self.progress_path = progress_path

    def _on_training_start(self) -> None:
        with self.progress_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timesteps", "episode_reward", "episode_length", "time_elapsed"])
            writer.writeheader()

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            episode = info.get("episode") if isinstance(info, dict) else None
            if episode:
                with self.progress_path.open("a", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["timesteps", "episode_reward", "episode_length", "time_elapsed"],
                    )
                    writer.writerow(
                        {
                            "timesteps": self.num_timesteps,
                            "episode_reward": episode.get("r", ""),
                            "episode_length": episode.get("l", ""),
                            "time_elapsed": episode.get("t", ""),
                        }
                    )
        return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="standard")
    parser.add_argument(
        "--scenario-set",
        choices=["train", "validation", "test", "unseen"],
        default=None,
        help="Optional per-episode scenario sampler. Overrides fixed --scenario during reset.",
    )
    parser.add_argument("--total-timesteps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--duration-sec", type=float, default=12.0)
    parser.add_argument("--radius", type=float, default=0.3)
    parser.add_argument("--period", type=float, default=10.0)
    parser.add_argument("--height", type=float, default=1.0)
    parser.add_argument("--residual-gate-min", type=float, default=0.0)
    parser.add_argument(
        "--checkpoint-freq",
        type=int,
        default=0,
        help="Save model checkpoints every N environment steps. Disabled when 0.",
    )
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=Path("experiments/circular_tracking/results/td3_residual_paper/runs/direct_td3_seed0"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_folder.mkdir(parents=True, exist_ok=True)
    env = CircularResidualTD3Env(
        controller_mode="direct_td3",
        scenario=args.scenario,
        scenario_set=args.scenario_set,
        duration_sec=args.duration_sec,
        radius=args.radius,
        period=args.period,
        height=args.height,
        residual_gate_min=args.residual_gate_min,
    )
    monitored_env = Monitor(env, filename=str(args.output_folder / "monitor.csv"))
    action_noise = NormalActionNoise(
        mean=0.0 * monitored_env.action_space.low,
        sigma=0.1 * (monitored_env.action_space.high - monitored_env.action_space.low),
    )
    config = {
        "controller_mode": "direct_td3",
        "scenario": args.scenario,
        "scenario_set": args.scenario_set,
        "total_timesteps": args.total_timesteps,
        "seed": args.seed,
        "duration_sec": args.duration_sec,
        "radius": args.radius,
        "period": args.period,
        "height": args.height,
        "residual_gate_min": args.residual_gate_min,
        "algorithm": "TD3",
        "learning_rate": 1e-3,
        "buffer_size": 300000,
        "learning_starts": min(5000, max(100, args.total_timesteps // 10)),
        "batch_size": 256,
        "tau": 0.005,
        "gamma": 0.99,
        "train_freq": 1,
        "gradient_steps": 1,
        "policy_delay": 2,
        "target_policy_noise": 0.2,
        "target_noise_clip": 0.5,
        "tensorboard_log": None,
        "progress_csv": str(args.output_folder / "progress.csv"),
        "checkpoint_freq": args.checkpoint_freq,
        "checkpoint_folder": str(args.output_folder / "checkpoints"),
    }
    (args.output_folder / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    model = TD3(
        "MlpPolicy",
        monitored_env,
        seed=args.seed,
        learning_rate=config["learning_rate"],
        buffer_size=config["buffer_size"],
        learning_starts=config["learning_starts"],
        batch_size=config["batch_size"],
        tau=config["tau"],
        gamma=config["gamma"],
        train_freq=config["train_freq"],
        gradient_steps=config["gradient_steps"],
        policy_delay=config["policy_delay"],
        target_policy_noise=config["target_policy_noise"],
        target_noise_clip=config["target_noise_clip"],
        action_noise=action_noise,
        verbose=1,
        tensorboard_log=config["tensorboard_log"],
    )
    model.set_logger(configure(str(args.output_folder / "logs"), ["stdout", "csv"]))
    callbacks = [EpisodeProgressCallback(args.output_folder / "progress.csv")]
    if args.checkpoint_freq > 0:
        callbacks.append(
            CheckpointCallback(
                save_freq=args.checkpoint_freq,
                save_path=str(args.output_folder / "checkpoints"),
                name_prefix="model",
                save_replay_buffer=False,
                save_vecnormalize=False,
            )
        )
    model.learn(
        total_timesteps=args.total_timesteps,
        progress_bar=False,
        callback=CallbackList(callbacks),
    )
    model.save(args.output_folder / "model")
    monitored_env.close()


if __name__ == "__main__":
    main()
