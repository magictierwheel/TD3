"""Matched Direct and Residual TD3 training for hidden disturbances.

This entry point deliberately admits only the frozen training seed set and
protocol budgets.  Held-out, test, and unseen evaluation belong to Task 7 and
later, so they are not parser options here.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from typing import Any, Mapping, Sequence

# Set these before NumPy/Torch import so every trainer process has one BLAS/OpenMP
# worker. Torch is constrained again by ``configure_single_thread_runtime``.
for _thread_variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_thread_variable] = "1"

import gymnasium as gym
import numpy as np
import torch
from gymnasium import spaces
from stable_baselines3 import TD3
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.noise import ActionNoise

from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.environments.hidden_disturbance_td3_env import (
    HiddenDisturbanceCircularTD3Env,
)
from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.training.pid_contract import (
    load_pid_runtime_contract,
)
from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.training.tune_hidden_pid import (
    _canonical_json_hash,
    _canonical_sha256,
    protocol_hash,
)
from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.study_paths import (
    ENVIRONMENT_SOURCE_PATH,
    FROZEN_PID_PATH,
    PROTOCOL_PATH,
    REPO_ROOT,
    STUDY_ROOT,
)


SUPPORTED_MODES = ("direct_td3", "residual_td3")
TRAINING_SEEDS = frozenset(range(0, 5))
SMOKE_TOTAL_TIMESTEPS = 200
ALLOWED_TOTAL_TIMESTEPS = (SMOKE_TOTAL_TIMESTEPS, 2_000, 5_000, 20_000, 50_000, 100_000)
CHECKPOINT_STEPS = (5_000, 10_000, 20_000, 50_000, 100_000)
TRAINING_PROFILES = ("standard", "random_wind", "actuator_loss", "compound")
TRAINING_PROFILE_PROBABILITIES = (0.25, 0.25, 0.25, 0.25)
CURRICULUM_INITIAL_PROBABILITIES = (0.75, 0.25, 0.0, 0.0)
CURRICULUM_RAMP_START = 2_000
CURRICULUM_RAMP_END = 5_000
ROLLOUT_DURATION_SEC = 20.0
RESULTS_ROOT = STUDY_ROOT / "stages"
THREAD_LIMIT_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")

TD3_HYPERPARAMETERS: dict[str, Any] = {
    "policy": "MlpPolicy",
    "policy_kwargs": {"net_arch": [256, 256]},
    "learning_rate": 1e-3,
    "batch_size": 256,
    "buffer_size": 1_000_000,
    "learning_starts": 2_000,
    "gamma": 0.99,
    "tau": 0.005,
    "train_freq": 1,
    "gradient_steps": 1,
    "policy_delay": 2,
    "learning_starts": 2_000,
}

OBSERVATION_NORMALIZATION_KIND = "fixed_physical_v2"
WARMUP_ACTION_LIMIT = 0.05
WARMUP_ACTION_SLEW_LIMIT = 0.02
DIRECT_ACTOR_FINAL_WEIGHT_BOUND = 3e-3
_ACTION_SCALES_RPM: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class RunPaths:
    """Paths created for one immutable training attempt."""

    output_folder: Path
    checkpoint_folder: Path
    config_path: Path
    running_path: Path
    done_path: Path


@dataclass(frozen=True, slots=True)
class TrainingSnapshot:
    """Immutable files required to resume one TD3 run exactly."""

    model_path: Path
    replay_buffer_path: Path
    state_path: Path


class FixedObservationScaleWrapper(gym.ObservationWrapper):
    """Apply the frozen physical observation scales shared by both TD3 modes."""

    _FIELD_SCALES = (2.0, 3.0, float(np.pi), 10.0, 2.0, 3.0, 2.0, 3.0, 1.0, None)

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        base = env.unwrapped
        if not isinstance(base, HiddenDisturbanceCircularTD3Env):
            raise TypeError("fixed observation scaling requires HiddenDisturbanceCircularTD3Env")
        scales: list[np.ndarray] = []
        for width, field_scale in zip(base._HISTORY_FIELD_WIDTHS, self._FIELD_SCALES):
            scale = base.MAX_RPM if field_scale is None else field_scale
            scales.append(np.full(width * base.HISTORY_LENGTH, scale, dtype=np.float32))
        scales.append(np.full(4, base.MAX_RPM, dtype=np.float32))
        self.scales = np.concatenate(scales)
        if self.scales.shape != env.observation_space.shape:
            raise RuntimeError("fixed observation scale shape does not match the policy observation")
        self.observation_space = spaces.Box(
            low=(env.observation_space.low / self.scales).astype(np.float32),
            high=(env.observation_space.high / self.scales).astype(np.float32),
            dtype=np.float32,
        )

    def observation(self, observation: np.ndarray) -> np.ndarray:
        return (np.asarray(observation, dtype=np.float32) / self.scales).astype(np.float32)


def observation_normalization_spec() -> dict[str, object]:
    """Record the analytic, non-adaptive observation transform in run metadata."""

    return {
        "kind": OBSERVATION_NORMALIZATION_KIND,
        "learned_statistics": False,
        "field_scales": {
            "position_m": 2.0,
            "velocity_mps": 3.0,
            "attitude_rad": "pi",
            "angular_velocity_radps": 10.0,
            "reference_position_m": 2.0,
            "reference_velocity_mps": 3.0,
            "position_error_m": 2.0,
            "velocity_error_mps": 3.0,
            "last_policy_action": 1.0,
            "applied_rpm": "MAX_RPM",
            "pid_rpm": "MAX_RPM",
        },
    }


def build_action_noise_spec(mode: str) -> dict[str, float]:
    """Express behavior and target noise in normalized and actual RPM units."""

    if mode not in SUPPORTED_MODES:
        raise ValueError(f"mode must be one of {SUPPORTED_MODES}")
    direct_span, residual_limit = _physical_action_scales_rpm()
    residual_behavior = 0.10
    residual_target = 0.20
    residual_clip = 0.50
    action_scale = direct_span if mode == "direct_td3" else residual_limit
    return {
        "action_scale_rpm": action_scale,
        "behavior_sigma_normalized": residual_behavior * residual_limit / action_scale,
        "behavior_sigma_rpm": residual_behavior * residual_limit,
        "behavior_clip_normalized": WARMUP_ACTION_LIMIT if mode == "direct_td3" else WARMUP_ACTION_LIMIT,
        "behavior_clip_rpm": WARMUP_ACTION_LIMIT * action_scale,
        "target_sigma_normalized": residual_target * residual_limit / action_scale,
        "target_sigma_rpm": residual_target * residual_limit,
        "target_clip_normalized": residual_clip * residual_limit / action_scale,
        "target_clip_rpm": residual_clip * residual_limit,
    }


def _physical_action_scales_rpm() -> tuple[float, float]:
    """Read the fixed simulator RPM constants once rather than approximating them."""

    global _ACTION_SCALES_RPM
    if _ACTION_SCALES_RPM is None:
        env = HiddenDisturbanceCircularTD3Env(
            controller_mode="direct_td3", disturbance_profile="standard", rollout_duration_sec=20.0
        )
        try:
            _ACTION_SCALES_RPM = (
                float(env.MAX_RPM - env.HOVER_RPM),
                float(0.10 * env.MAX_RPM),
            )
        finally:
            env.close()
    return _ACTION_SCALES_RPM


class SafeWarmupActionGenerator:
    """Smooth bounded exploration in collective/attitude coordinates, not motor-wise jumps."""

    _MIX = np.array(
        [[1.0, 1.0, 1.0, 1.0], [1.0, -1.0, 1.0, -1.0], [1.0, 1.0, -1.0, -1.0], [1.0, -1.0, -1.0, 1.0]],
        dtype=np.float32,
    ) / 2.0

    def __init__(self, *, mode: str, seed: int) -> None:
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"mode must be one of {SUPPORTED_MODES}")
        self.mode = mode
        self._rng = np.random.default_rng(seed)
        self._latent = np.zeros(4, dtype=np.float32)
        self._last_action = np.zeros(4, dtype=np.float32)

    def sample(self) -> np.ndarray:
        if self.mode == "direct_td3":
            # A raw-RPM Direct policy has no inner attitude loop during warm-up;
            # excite collective thrust only so exploration cannot integrate torque.
            self._latent[0] = 0.85 * self._latent[0] + 0.004 * float(self._rng.normal())
            candidate = np.full(4, self._latent[0], dtype=np.float32)
        else:
            self._latent = 0.85 * self._latent + 0.004 * self._rng.normal(size=4).astype(np.float32)
            candidate = self._MIX @ self._latent
        delta = np.clip(candidate - self._last_action, -WARMUP_ACTION_SLEW_LIMIT, WARMUP_ACTION_SLEW_LIMIT)
        self._last_action = np.clip(self._last_action + delta, -WARMUP_ACTION_LIMIT, WARMUP_ACTION_LIMIT)
        return self._last_action.copy()

    def state_dict(self) -> dict[str, object]:
        return {"latent": self._latent.copy(), "last_action": self._last_action.copy(), "rng": self._rng.bit_generator.state}

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        self._latent = np.asarray(state["latent"], dtype=np.float32)
        self._last_action = np.asarray(state["last_action"], dtype=np.float32)
        self._rng.bit_generator.state = state["rng"]


class CorrelatedMotorActionNoise(ActionNoise):
    """Correlated behavior noise with per-motor physical RMS set by the protocol."""

    def __init__(self, *, sigma: float, clip: float, seed: int) -> None:
        self.sigma = float(sigma)
        self.clip = float(clip)
        self._rng = np.random.default_rng(seed)
        self._latent = np.zeros(4, dtype=np.float32)
        self._training_step = 0

    def set_training_step(self, step: int) -> None:
        self._training_step = int(step)

    def __call__(self) -> np.ndarray:
        ramp = float(np.clip((self._training_step - CURRICULUM_RAMP_START) / (CURRICULUM_RAMP_END - CURRICULUM_RAMP_START), 0.0, 1.0))
        if ramp == 0.0:
            return np.zeros(4, dtype=np.float32)
        self._latent = 0.85 * self._latent + np.sqrt(1.0 - 0.85**2) * self.sigma * self._rng.normal(size=4).astype(np.float32)
        return np.clip(ramp * (SafeWarmupActionGenerator._MIX @ self._latent), -self.clip, self.clip).astype(np.float32)

    def reset(self, **kwargs: object) -> None:
        self._latent.fill(0.0)

    def state_dict(self) -> dict[str, object]:
        return {
            "latent": self._latent.copy(),
            "rng": self._rng.bit_generator.state,
            "training_step": self._training_step,
        }

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        self._latent = np.asarray(state["latent"], dtype=np.float32)
        self._rng.bit_generator.state = state["rng"]
        self._training_step = int(state["training_step"])


class SafeWarmupTD3(TD3):
    """Keep TD3's delayed updates while replacing only unsafe warm-up actions."""

    def __init__(self, *args: object, warmup_generator: SafeWarmupActionGenerator | None = None, **kwargs: object) -> None:
        self.warmup_generator = warmup_generator or SafeWarmupActionGenerator(mode="direct_td3", seed=0)
        super().__init__(*args, **kwargs)

    def _sample_action(self, learning_starts: int, action_noise: ActionNoise | None = None, n_envs: int = 1) -> tuple[np.ndarray, np.ndarray]:
        if hasattr(self.env, "env_method"):
            self.env.env_method("set_training_step", self.num_timesteps)
        if isinstance(action_noise, CorrelatedMotorActionNoise):
            action_noise.set_training_step(self.num_timesteps)
        if self.num_timesteps < learning_starts:
            if not isinstance(self.action_space, spaces.Box):
                raise RuntimeError("safe warm-up requires a continuous action space")
            scaled_action = np.vstack([self.warmup_generator.sample() for _ in range(n_envs)])
            return self.policy.unscale_action(scaled_action), scaled_action
        return super()._sample_action(learning_starts, action_noise, n_envs)


def _repo_root() -> Path:
    return REPO_ROOT


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _package_versions() -> dict[str, str]:
    names = ("numpy", "gymnasium", "pybullet", "torch", "stable-baselines3", "control")
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = version(name)
        except PackageNotFoundError as exc:  # pragma: no cover - invalid local runtime
            raise RuntimeError(f"required package is unavailable: {name}") from exc
    return versions


def _validate_mode_seed_and_budget(mode: str, seed: int, total_timesteps: int) -> tuple[str, int, int]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"mode must be one of {SUPPORTED_MODES}, not {mode!r}")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise TypeError("training seed must be an integer")
    normalized_seed = int(seed)
    if normalized_seed not in TRAINING_SEEDS:
        raise ValueError("training seed must be in the frozen range 0-4")
    if isinstance(total_timesteps, bool) or not isinstance(total_timesteps, (int, np.integer)):
        raise TypeError("total_timesteps must be an integer")
    normalized_budget = int(total_timesteps)
    if normalized_budget not in ALLOWED_TOTAL_TIMESTEPS:
        raise ValueError(
            "total_timesteps must be one frozen protocol budget or the 200-step smoke budget"
        )
    return mode, normalized_seed, normalized_budget


def _load_inherited_frozen_pid_config() -> dict[str, Any]:
    """Load the already accepted v1 PID contract without reopening PID evidence validation."""

    payload = load_pid_runtime_contract(FROZEN_PID_PATH)
    parameters = payload["parameters"]
    return {
        **payload,
        "protocol_hash": protocol_hash(),
        "protocol_path": str(PROTOCOL_PATH.relative_to(_repo_root())).replace("\\", "/"),
        "schema_version": 4,
        "pid_payload_hash": payload["pid_payload_hash"],
    }


def _require_training_authorized() -> None:
    """Refuse all training while the active protocol is marked NO-GO."""

    try:
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("active training protocol is unavailable") from exc
    if not isinstance(protocol, Mapping) or protocol.get("training_authorized") is not True:
        raise RuntimeError("training is blocked: current protocol is not training-authorized")


def build_training_config(*, mode: str, seed: int, total_timesteps: int) -> dict[str, Any]:
    """Build the single frozen Direct/Residual training configuration.

    Only ``mode``, action interpretation, and residual-output initialization
    differ between the two TD3 variants.  This is deliberately a pure
    construction step so reviewers can compare both dictionaries directly.
    """

    normalized_mode, normalized_seed, normalized_budget = _validate_mode_seed_and_budget(
        mode, seed, total_timesteps
    )
    frozen_pid = _load_inherited_frozen_pid_config()
    pid_parameters = dict(frozen_pid["parameters"])
    action_semantics = (
        "normalized_direct_motor_rpm"
        if normalized_mode == "direct_td3"
        else "gated_normalized_pid_motor_rpm_residual"
    )
    return {
        "schema_version": 2,
        "mode": normalized_mode,
        "action_semantics": action_semantics,
        "zero_output_initialization": normalized_mode == "residual_td3",
        "seed": normalized_seed,
        "total_timesteps": normalized_budget,
        "rollout_duration_sec": ROLLOUT_DURATION_SEC,
        "training_profiles": list(TRAINING_PROFILES),
        "training_profile_probabilities": list(TRAINING_PROFILE_PROBABILITIES),
        "training_curriculum": {
            "steps_0_2000": list(CURRICULUM_INITIAL_PROBABILITIES),
            "steps_2000_5000": "linear_to_equal_four_profile_mix",
            "steps_5000_plus": list(TRAINING_PROFILE_PROBABILITIES),
        },
        "checkpoint_steps": list(CHECKPOINT_STEPS),
        "observation_normalization": observation_normalization_spec(),
        "noise_physical": build_action_noise_spec(normalized_mode),
        "td3": {
            key: (dict(value) if isinstance(value, Mapping) else value)
            for key, value in TD3_HYPERPARAMETERS.items()
        },
        "runtime": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "torch_device": "cpu",
            "threads_per_process": 1,
            "thread_environment": {name: "1" for name in THREAD_LIMIT_ENV},
        },
        "git_sha": _git_sha(),
        "protocol_path": str(PROTOCOL_PATH).replace("\\", "/"),
        "protocol_hash": protocol_hash(),
        "frozen_pid_config_path": str(FROZEN_PID_PATH).replace("\\", "/"),
        "frozen_pid_parameters": pid_parameters,
        "frozen_pid_payload_hash": frozen_pid["pid_payload_hash"],
        "frozen_pid_config_hash": _canonical_json_hash(frozen_pid),
        "frozen_pid_source_protocol_hash": frozen_pid["protocol_hash"],
        "package_versions": _package_versions(),
        "environment_schema": list(HiddenDisturbanceCircularTD3Env._SHARED_OBSERVATION_SCHEMA),
        "environment_source_sha256": _canonical_sha256(ENVIRONMENT_SOURCE_PATH),
        "interface_schema": {
            "history_length": HiddenDisturbanceCircularTD3Env.HISTORY_LENGTH,
            "action_dimension": 4,
            "normalized_action_bounds": [-1.0, 1.0],
        },
    }


class EqualTrainingProfileSampler(gym.Wrapper):
    """Sample only the four frozen training profiles with equal probability."""

    def __init__(self, env: HiddenDisturbanceCircularTD3Env, *, seed: int) -> None:
        super().__init__(env)
        self._profile_rng = np.random.default_rng(seed)
        self._training_step = 0

    def set_training_step(self, step: int) -> None:
        self._training_step = int(step)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        if seed is not None:
            self._profile_rng = np.random.default_rng(seed)
        profile_index = int(
            self._profile_rng.choice(
                len(TRAINING_PROFILES), p=training_profile_probabilities(self._training_step)
            )
        )
        self.unwrapped.disturbance_profile = TRAINING_PROFILES[profile_index]
        return self.env.reset(seed=seed, options=options)


def training_profile_probabilities(training_step: int) -> tuple[float, float, float, float]:
    """Frozen v2.1 curriculum shared by Direct and Residual TD3."""

    step = int(training_step)
    if step <= CURRICULUM_RAMP_START:
        return CURRICULUM_INITIAL_PROBABILITIES
    if step >= CURRICULUM_RAMP_END:
        return TRAINING_PROFILE_PROBABILITIES
    fraction = (step - CURRICULUM_RAMP_START) / (CURRICULUM_RAMP_END - CURRICULUM_RAMP_START)
    return tuple(
        float(start + fraction * (end - start))
        for start, end in zip(CURRICULUM_INITIAL_PROBABILITIES, TRAINING_PROFILE_PROBABILITIES)
    )


def make_training_environment(config: Mapping[str, Any]) -> EqualTrainingProfileSampler:
    """Construct the one fair hidden-disturbance environment used by both modes."""

    mode, seed, total_timesteps = _validate_mode_seed_and_budget(
        config["mode"], config["seed"], config["total_timesteps"]
    )
    if config.get("rollout_duration_sec") != ROLLOUT_DURATION_SEC:
        raise ValueError("training rollout duration must remain frozen at 20 seconds")
    pid_parameters = config.get("frozen_pid_parameters")
    if not isinstance(pid_parameters, Mapping):
        raise ValueError("missing frozen PID parameters")
    if total_timesteps != config["total_timesteps"] or seed != config["seed"]:
        raise ValueError("training configuration normalization mismatch")
    env = HiddenDisturbanceCircularTD3Env(
        controller_mode=mode,
        disturbance_profile="standard",
        rollout_duration_sec=ROLLOUT_DURATION_SEC,
        reference_velocity_gain=float(pid_parameters["reference_velocity_gain"]),
        pid_xy_p_scale=float(pid_parameters["pid_xy_p_scale"]),
        pid_xy_d_scale=float(pid_parameters["pid_xy_d_scale"]),
        pid_target_step_limit=float(pid_parameters["pid_target_step_limit"]),
        gui=False,
    )
    return FixedObservationScaleWrapper(EqualTrainingProfileSampler(env, seed=seed))


def _final_actor_linear(actor: torch.nn.Module) -> torch.nn.Linear:
    layers = [module for module in actor.mu.modules() if isinstance(module, torch.nn.Linear)]
    if not layers:  # pragma: no cover - SB3 contract guard
        raise RuntimeError("TD3 actor has no Linear output layer")
    return layers[-1]


def _zero_initialize_residual_output(model: TD3) -> None:
    """Zero only the residual actor's final linear layer and mirror its target."""

    output_layer = _final_actor_linear(model.actor)
    with torch.no_grad():
        output_layer.weight.zero_()
        output_layer.bias.zero_()
    model.actor_target.load_state_dict(model.actor.state_dict())


def _small_initialize_direct_output(model: TD3) -> None:
    """Use the DDPG small-final-layer convention around hover (action zero)."""

    output_layer = _final_actor_linear(model.actor)
    with torch.no_grad():
        output_layer.weight.uniform_(-DIRECT_ACTOR_FINAL_WEIGHT_BOUND, DIRECT_ACTOR_FINAL_WEIGHT_BOUND)
        output_layer.bias.zero_()
    model.actor_target.load_state_dict(model.actor.state_dict())


def build_td3_model(env: gym.Env, config: Mapping[str, Any]) -> SafeWarmupTD3:
    """Construct TD3 with protocol-matched nonstructural hyperparameters."""

    mode, seed, _ = _validate_mode_seed_and_budget(
        config["mode"], config["seed"], config["total_timesteps"]
    )
    td3 = config.get("td3")
    if not isinstance(td3, Mapping) or dict(td3) != TD3_HYPERPARAMETERS:
        raise ValueError("TD3 hyperparameters do not match the frozen protocol")
    action_shape = env.action_space.shape
    if action_shape is None:
        raise ValueError("training environment must have a vector action space")
    noise = config.get("noise_physical")
    if not isinstance(noise, Mapping):
        raise ValueError("missing physical noise specification")
    action_noise = CorrelatedMotorActionNoise(
        sigma=float(noise["behavior_sigma_normalized"]),
        clip=float(noise["behavior_clip_normalized"]),
        seed=seed + 10_000,
    )
    model = SafeWarmupTD3(
        td3["policy"],
        env,
        warmup_generator=SafeWarmupActionGenerator(mode=mode, seed=seed + 20_000),
        seed=seed,
        learning_rate=td3["learning_rate"],
        buffer_size=td3["buffer_size"],
        learning_starts=td3["learning_starts"],
        batch_size=td3["batch_size"],
        tau=td3["tau"],
        gamma=td3["gamma"],
        train_freq=td3["train_freq"],
        gradient_steps=td3["gradient_steps"],
        policy_delay=td3["policy_delay"],
        target_policy_noise=float(noise["target_sigma_normalized"]),
        target_noise_clip=float(noise["target_clip_normalized"]),
        action_noise=action_noise,
        policy_kwargs=dict(td3["policy_kwargs"]),
        device="cpu",
        verbose=0,
        tensorboard_log=None,
    )
    if mode == "residual_td3":
        _zero_initialize_residual_output(model)
    else:
        _small_initialize_direct_output(model)
    return model


def _write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    except FileExistsError:
        raise FileExistsError(f"refusing to replace immutable run metadata: {path}") from None


def prepare_run_directory(
    output_folder: Path,
    config: Mapping[str, Any],
    *,
    command: Sequence[str],
) -> RunPaths:
    """Create one non-overwriting run directory and initial durable metadata."""

    output_folder = Path(output_folder)
    if output_folder.exists():
        raise FileExistsError(f"refusing to overwrite existing run directory: {output_folder}")
    output_folder.mkdir(parents=True, exist_ok=False)
    checkpoint_folder = output_folder / "checkpoints"
    checkpoint_folder.mkdir()
    config_path = output_folder / "config.json"
    running_path = output_folder / "RUNNING.json"
    done_path = output_folder / "DONE.json"
    config_payload = dict(config)
    config_hash = _canonical_json_hash(config_payload)
    _write_json_once(config_path, config_payload)
    _write_json_once(
        running_path,
        {
            "schema_version": 1,
            "status": "running",
            "started_at_utc": _utc_timestamp(),
            "command": list(command),
            "config_sha256": config_hash,
            "git_sha": config_payload["git_sha"],
            "protocol_hash": config_payload["protocol_hash"],
        },
    )
    return RunPaths(
        output_folder=output_folder,
        checkpoint_folder=checkpoint_folder,
        config_path=config_path,
        running_path=running_path,
        done_path=done_path,
    )


def finalize_run(
    run_paths: RunPaths,
    *,
    status: str,
    total_timesteps: int,
    error: BaseException | None = None,
) -> None:
    """Write the sole terminal state for a completed or failed attempt."""

    if status not in {"completed", "failed"}:
        raise ValueError("run status must be completed or failed")
    running = json.loads(run_paths.running_path.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "finished_at_utc": _utc_timestamp(),
        "total_timesteps": int(total_timesteps),
        "config_sha256": running["config_sha256"],
        "git_sha": running["git_sha"],
        "protocol_hash": running["protocol_hash"],
    }
    if status == "completed":
        payload["model_path"] = "model.zip"
        payload["progress_path"] = "progress.csv"
        payload["checkpoint_folder"] = "checkpoints"
    elif error is not None:
        payload["error_type"] = type(error).__name__
        payload["error_message"] = str(error)
    _write_json_once(run_paths.done_path, payload)


class EpisodeProgressCallback(BaseCallback):
    """Write compact episode progress independently of Stable-Baselines3 logs."""

    def __init__(self, progress_path: Path) -> None:
        super().__init__()
        self._progress_path = progress_path

    def _on_training_start(self) -> None:
        with self._progress_path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["timesteps", "episode_reward", "episode_length", "time_elapsed"],
            )
            writer.writeheader()

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            episode = info.get("episode") if isinstance(info, dict) else None
            if episode is not None:
                with self._progress_path.open("a", newline="", encoding="utf-8") as handle:
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


class FrozenCheckpointCallback(BaseCallback):
    """Save models at the immutable protocol checkpoint steps only."""

    def __init__(self, checkpoint_folder: Path, checkpoint_steps: Sequence[int]) -> None:
        super().__init__()
        self._checkpoint_folder = checkpoint_folder
        self._pending_steps = {int(step) for step in checkpoint_steps}

    def _on_step(self) -> bool:
        if self.num_timesteps in self._pending_steps:
            self.model.save(self._checkpoint_folder / f"checkpoint_{self.num_timesteps:06d}")
            self._pending_steps.remove(self.num_timesteps)
        return True


def configure_single_thread_runtime() -> None:
    """Enforce CPU-only one-thread execution for a training process."""

    for name in THREAD_LIMIT_ENV:
        os.environ[name] = "1"
    torch.set_num_threads(1)


def _validate_output_folder(output_folder: Path) -> Path:
    resolved = Path(output_folder).resolve()
    allowed_root = RESULTS_ROOT.resolve()
    try:
        relative = resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"output folder must be inside the study stages namespace: {allowed_root}"
        ) from exc
    if len(relative.parts) < 3 or relative.parts[1] != "runs":
        raise ValueError("output folder must be inside studies/pid_residual_td3/stages/*/runs/")
    return resolved


def _profile_sampler(env: gym.Env) -> EqualTrainingProfileSampler:
    current: gym.Env = env
    while not isinstance(current, EqualTrainingProfileSampler):
        if not isinstance(current, gym.Wrapper):
            raise RuntimeError("training environment has no profile sampler")
        current = current.env
    return current


def save_training_snapshot(*, model: SafeWarmupTD3, env: gym.Env, output_folder: Path) -> TrainingSnapshot:
    """Persist model, optimizer, replay, fixed scaling and random state for exact continuation."""

    output = Path(output_folder)
    model_path = output / "model.zip"
    replay_buffer_path = output / "replay_buffer.pkl"
    state_path = output / "training_state.pt"
    model.save(model_path)
    model.save_replay_buffer(replay_buffer_path)
    sampler = _profile_sampler(env)
    torch.save(
        {
            "schema_version": 1,
            "num_timesteps": model.num_timesteps,
            "python_random_state": random.getstate(),
            "numpy_random_state": np.random.get_state(),
            "torch_rng_state": torch.get_rng_state(),
            "profile_rng_state": sampler._profile_rng.bit_generator.state,
            "warmup_state": model.warmup_generator.state_dict(),
            "action_noise_state": model.action_noise.state_dict() if isinstance(model.action_noise, CorrelatedMotorActionNoise) else None,
            "observation_normalization": observation_normalization_spec(),
        },
        state_path,
    )
    return TrainingSnapshot(model_path=model_path, replay_buffer_path=replay_buffer_path, state_path=state_path)


def restore_training_snapshot(*, snapshot: TrainingSnapshot, env: gym.Env) -> SafeWarmupTD3:
    """Restore every trainable and stochastic state needed by a later budget extension."""

    model = SafeWarmupTD3.load(snapshot.model_path, env=env, device="cpu")
    if not isinstance(model, SafeWarmupTD3):  # pragma: no cover - SB3 subclass guard
        raise RuntimeError("snapshot did not restore the safe TD3 class")
    model.load_replay_buffer(snapshot.replay_buffer_path)
    state = torch.load(snapshot.state_path, map_location="cpu", weights_only=False)
    if state.get("observation_normalization") != observation_normalization_spec():
        raise ValueError("snapshot observation normalization does not match protocol v2")
    model.num_timesteps = int(state["num_timesteps"])
    random.setstate(state["python_random_state"])
    np.random.set_state(state["numpy_random_state"])
    torch.set_rng_state(state["torch_rng_state"])
    _profile_sampler(env)._profile_rng.bit_generator.state = state["profile_rng_state"]
    model.warmup_generator.load_state_dict(state["warmup_state"])
    if isinstance(model.action_noise, CorrelatedMotorActionNoise) and state.get("action_noise_state") is not None:
        model.action_noise.load_state_dict(state["action_noise_state"])
    return model


def run_training(
    *,
    config: Mapping[str, Any],
    output_folder: Path,
    command: Sequence[str],
    resume_from: Path | None = None,
) -> RunPaths:
    """Run one immutable matched TD3 attempt and persist its terminal state."""

    _require_training_authorized()
    configure_single_thread_runtime()
    output_path = _validate_output_folder(output_folder)
    run_paths = prepare_run_directory(output_path, config, command=command)
    env: gym.Env | None = None
    try:
        env = make_training_environment(config)
        monitored_env = Monitor(env, filename=str(run_paths.output_folder / "monitor.csv"))
        if resume_from is None:
            model = build_td3_model(monitored_env, config)
            remaining_timesteps = int(config["total_timesteps"])
        else:
            source = Path(resume_from)
            model = restore_training_snapshot(
                snapshot=TrainingSnapshot(
                    model_path=source / "model.zip",
                    replay_buffer_path=source / "replay_buffer.pkl",
                    state_path=source / "training_state.pt",
                ),
                env=monitored_env,
            )
            remaining_timesteps = int(config["total_timesteps"]) - model.num_timesteps
            if remaining_timesteps <= 0:
                raise ValueError("resume target budget must exceed saved training steps")
        model.set_logger(configure(str(run_paths.output_folder / "logs"), ["csv"]))
        checkpoint_steps = [
            step for step in CHECKPOINT_STEPS if model.num_timesteps < step <= int(config["total_timesteps"])
        ]
        callbacks = CallbackList(
            [
                EpisodeProgressCallback(run_paths.output_folder / "progress.csv"),
                FrozenCheckpointCallback(run_paths.checkpoint_folder, checkpoint_steps),
            ]
        )
        model.learn(
            total_timesteps=remaining_timesteps,
            progress_bar=False,
            callback=callbacks,
            reset_num_timesteps=resume_from is None,
        )
        save_training_snapshot(model=model, env=monitored_env, output_folder=run_paths.output_folder)
        finalize_run(
            run_paths,
            status="completed",
            total_timesteps=int(config["total_timesteps"]),
        )
        return run_paths
    except BaseException as exc:
        if not run_paths.done_path.exists():
            finalize_run(
                run_paths,
                status="failed",
                total_timesteps=int(config["total_timesteps"]),
                error=exc,
            )
        raise
    finally:
        if env is not None:
            env.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the sole public training CLI without evaluation/test controls."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=SUPPORTED_MODES, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--total-timesteps", type=int, required=True)
    parser.add_argument("--output-folder", type=Path, required=True)
    parser.add_argument("--resume-from", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = build_training_config(
            mode=args.mode,
            seed=args.seed,
            total_timesteps=args.total_timesteps,
        )
        run_paths = run_training(
            config=config,
            output_folder=args.output_folder,
            command=[sys.executable, "-m", __name__, *(argv if argv is not None else sys.argv[1:])],
            resume_from=args.resume_from,
        )
    except (FileExistsError, RuntimeError, TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({"output_folder": str(run_paths.output_folder), "status": "completed"}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
