"""Train residual TD3 variants on the circular tracking environment."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
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


class WarmStartRetentionCallback(BaseCallback):
    """Periodically pull the actor back toward the PID-FF imitation target."""

    def __init__(
        self,
        observations: np.ndarray,
        actions: np.ndarray,
        frequency: int,
        updates_per_call: int,
        batch_size: int,
        start_timesteps: int,
        loss_path: Path,
    ) -> None:
        super().__init__()
        self.observations = observations
        self.actions = actions
        self.frequency = max(1, int(frequency))
        self.updates_per_call = max(1, int(updates_per_call))
        self.batch_size = max(1, int(batch_size))
        self.start_timesteps = max(0, int(start_timesteps))
        self.loss_path = loss_path
        self.rng = np.random.default_rng(1)

    def _on_training_start(self) -> None:
        with self.loss_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timesteps", "updates", "mse_loss"])
            writer.writeheader()

    def _on_step(self) -> bool:
        if self.num_timesteps < self.start_timesteps:
            return True
        if self.num_timesteps % self.frequency != 0:
            return True
        if self.observations.size == 0 or self.actions.size == 0:
            return True

        device = self.model.device
        actor = self.model.actor
        optimizer = actor.optimizer
        obs_tensor = torch.as_tensor(self.observations, device=device)
        action_tensor = torch.as_tensor(self.actions, device=device)
        losses = []
        for _ in range(self.updates_per_call):
            batch_indices = self.rng.choice(
                len(self.observations),
                size=min(self.batch_size, len(self.observations)),
                replace=False,
            )
            predicted = actor(obs_tensor[batch_indices])
            loss = torch.nn.functional.mse_loss(predicted, action_tensor[batch_indices])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu().item()))
        self.model.actor_target.load_state_dict(self.model.actor.state_dict())

        with self.loss_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timesteps", "updates", "mse_loss"])
            writer.writerow(
                {
                    "timesteps": self.num_timesteps,
                    "updates": self.updates_per_call,
                    "mse_loss": float(np.mean(losses)),
                }
            )
        return True


def collect_warm_start_dataset(args: argparse.Namespace) -> tuple[np.ndarray, np.ndarray]:
    env = CircularResidualTD3Env(
        controller_mode=args.mode,
        scenario=args.scenario,
        scenario_set=args.warm_start_scenario_set or args.scenario_set,
        duration_sec=args.duration_sec,
        radius=args.radius,
        period=args.period,
        height=args.height,
        residual_gate_min=args.residual_gate_min,
    )
    observations = []
    actions = []
    try:
        seed = args.seed
        obs, _ = env.reset(seed=seed)
        while len(observations) < args.warm_start_samples:
            target_action = env.feedforward_residual_action()
            observations.append(obs.copy())
            actions.append(target_action.copy())
            obs, _, terminated, truncated, _ = env.step(target_action)
            if terminated or truncated:
                seed += 1
                obs, _ = env.reset(seed=seed)
    finally:
        env.close()
    return np.asarray(observations, dtype=np.float32), np.asarray(actions, dtype=np.float32)


def warm_start_actor(
    model: TD3,
    observations: np.ndarray,
    actions: np.ndarray,
    epochs: int,
    batch_size: int,
    output_folder: Path,
) -> None:
    if observations.size == 0 or actions.size == 0 or epochs <= 0:
        return

    device = model.device
    actor = model.actor
    optimizer = actor.optimizer
    losses = []
    generator = np.random.default_rng(0)
    obs_tensor = torch.as_tensor(observations, device=device)
    action_tensor = torch.as_tensor(actions, device=device)
    for epoch in range(epochs):
        indices = generator.permutation(len(observations))
        epoch_losses = []
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            predicted = actor(obs_tensor[batch_indices])
            loss = torch.nn.functional.mse_loss(predicted, action_tensor[batch_indices])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu().item()))
        losses.append({"epoch": epoch + 1, "mse_loss": float(np.mean(epoch_losses))})
    model.actor_target.load_state_dict(model.actor.state_dict())

    with (output_folder / "warm_start_loss.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["epoch", "mse_loss"])
        writer.writeheader()
        writer.writerows(losses)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=[
            "residual_td3",
            "disturbance_aware_residual_td3",
            "disturbance_aware_residual_td3_no_gate",
        ],
        default="residual_td3",
    )
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
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument(
        "--learning-starts",
        type=int,
        default=None,
        help="Number of environment steps before TD3 gradient updates. Defaults to the original heuristic.",
    )
    parser.add_argument(
        "--action-noise-sigma",
        type=float,
        default=0.1,
        help="Multiplier for the normalized action-space width used by NormalActionNoise.",
    )
    parser.add_argument(
        "--residual-gate-min",
        type=float,
        default=0.0,
        help="Minimum gate for nonzero-disturbance residual control. Default preserves old behavior.",
    )
    parser.add_argument(
        "--checkpoint-freq",
        type=int,
        default=0,
        help="Save model checkpoints every N environment steps. Disabled when 0.",
    )
    parser.add_argument("--warm-start-samples", type=int, default=0)
    parser.add_argument("--warm-start-epochs", type=int, default=0)
    parser.add_argument("--warm-start-batch-size", type=int, default=256)
    parser.add_argument(
        "--warm-start-scenario-set",
        choices=["train", "validation", "test", "unseen"],
        default="train",
        help="Scenario sampler used to collect PID-FF imitation samples.",
    )
    parser.add_argument(
        "--warm-start-retain-freq",
        type=int,
        default=0,
        help="Every N TD3 steps, run supervised actor updates on the warm-start dataset. Disabled when 0.",
    )
    parser.add_argument("--warm-start-retain-updates", type=int, default=1)
    parser.add_argument("--warm-start-retain-batch-size", type=int, default=256)
    parser.add_argument("--warm-start-retain-start", type=int, default=0)
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=Path("experiments/circular_tracking/results/td3_residual_paper/runs/residual_td3_seed0"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_folder.mkdir(parents=True, exist_ok=True)
    env = CircularResidualTD3Env(
        controller_mode=args.mode,
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
        sigma=args.action_noise_sigma * (monitored_env.action_space.high - monitored_env.action_space.low),
    )
    learning_starts = (
        args.learning_starts
        if args.learning_starts is not None
        else min(5000, max(100, args.total_timesteps // 10))
    )
    config = {
        "controller_mode": args.mode,
        "scenario": args.scenario,
        "scenario_set": args.scenario_set,
        "total_timesteps": args.total_timesteps,
        "seed": args.seed,
        "duration_sec": args.duration_sec,
        "radius": args.radius,
        "period": args.period,
        "height": args.height,
        "algorithm": "TD3",
        "learning_rate": args.learning_rate,
        "buffer_size": 300000,
        "learning_starts": learning_starts,
        "batch_size": 256,
        "tau": 0.005,
        "gamma": 0.99,
        "train_freq": 1,
        "gradient_steps": 1,
        "policy_delay": 2,
        "target_policy_noise": 0.2,
        "target_noise_clip": 0.5,
        "tensorboard_log": None,
        "action_noise_sigma": args.action_noise_sigma,
        "residual_gate_min": args.residual_gate_min,
        "progress_csv": str(args.output_folder / "progress.csv"),
        "checkpoint_freq": args.checkpoint_freq,
        "checkpoint_folder": str(args.output_folder / "checkpoints"),
        "warm_start_samples": args.warm_start_samples,
        "warm_start_epochs": args.warm_start_epochs,
        "warm_start_batch_size": args.warm_start_batch_size,
        "warm_start_scenario_set": args.warm_start_scenario_set,
        "warm_start_retain_freq": args.warm_start_retain_freq,
        "warm_start_retain_updates": args.warm_start_retain_updates,
        "warm_start_retain_batch_size": args.warm_start_retain_batch_size,
        "warm_start_retain_start": args.warm_start_retain_start,
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
    observations = np.empty((0, monitored_env.observation_space.shape[0]), dtype=np.float32)
    actions = np.empty((0, monitored_env.action_space.shape[0]), dtype=np.float32)
    if args.warm_start_samples > 0 and args.warm_start_epochs > 0:
        observations, actions = collect_warm_start_dataset(args)
        np.savez_compressed(
            args.output_folder / "warm_start_dataset.npz",
            observations=observations,
            actions=actions,
        )
        warm_start_actor(
            model=model,
            observations=observations,
            actions=actions,
            epochs=args.warm_start_epochs,
            batch_size=args.warm_start_batch_size,
            output_folder=args.output_folder,
        )
        model.save(args.output_folder / "warm_start_model")
    callbacks = [EpisodeProgressCallback(args.output_folder / "progress.csv")]
    if args.warm_start_retain_freq > 0:
        if observations.size == 0 or actions.size == 0:
            raise ValueError("--warm-start-retain-freq requires a warm-start dataset")
        callbacks.append(
            WarmStartRetentionCallback(
                observations=observations,
                actions=actions,
                frequency=args.warm_start_retain_freq,
                updates_per_call=args.warm_start_retain_updates,
                batch_size=args.warm_start_retain_batch_size,
                start_timesteps=args.warm_start_retain_start,
                loss_path=args.output_folder / "warm_start_retention_loss.csv",
            )
        )
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
