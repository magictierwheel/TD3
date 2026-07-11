"""Run paired, validation-only Stage-A rollouts for the hidden TD3 study.

Every controller in one paired worker is reset with the same validation seed.
The environment therefore regenerates the same deterministic hidden-disturbance
realization for PID, Direct TD3, and Residual TD3.  Policies receive only the
environment observation; disturbance truth is copied to offline metadata only
after the action has been selected.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

import numpy as np


VALIDATION_SEEDS = tuple(range(100, 110))
STAGE_A_TRAINING_SEED = 0
STAGE_A_SCENARIOS = ("standard", "random_wind", "actuator_loss", "compound")
CONTROLLERS = ("pid", "direct_td3", "residual_td3")
EVALUATION_DURATION_SEC = 30.0
REFERENCE_PERIOD_SEC = 10.0
FAILURE_HORIZON_ERROR_M = 3.0

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROTOCOL_PATH = Path("experiments/circular_tracking/config/hidden_td3_protocol.json")
_PID_CONFIG_PATH = Path("experiments/circular_tracking/config/hidden_pid_frozen.json")
_ENVIRONMENT_SOURCE_PATH = Path(
    "experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py"
)


def validate_validation_seeds(seeds: Sequence[int]) -> tuple[int, ...]:
    """Normalize validation seeds and reject every training/test/unseen value."""

    normalized: list[int] = []
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, Integral):
            raise TypeError("validation seeds must be integers in the frozen range 100-109")
        value = int(seed)
        if value not in VALIDATION_SEEDS:
            raise ValueError("evaluation accepts validation seeds 100-109 only")
        normalized.append(value)
    if not normalized:
        raise ValueError("at least one validation seed in 100-109 is required")
    if len(set(normalized)) != len(normalized):
        raise ValueError("validation seeds must be unique")
    return tuple(normalized)


def validate_stage_a_training_seed(seed: int) -> int:
    """Stage A is the frozen seed-0 diagnostic and admits no other replicate."""

    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise TypeError("Stage A training seed must be the integer 0")
    normalized = int(seed)
    if normalized != STAGE_A_TRAINING_SEED:
        raise ValueError("Stage A training seed must be 0")
    return normalized


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field} must be a finite real number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field} must be a finite real number")
    return normalized


def _mean(values: Sequence[float]) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return float("nan") if not finite else sum(finite) / len(finite)


def compute_metrics(
    *,
    trajectory_rows: Sequence[Mapping[str, object]],
    period: float,
    duration_sec: float,
    failure: bool,
) -> dict[str, float | bool]:
    """Compute failure-first metrics from one control-step trajectory.

    A failed rollout has no success-only steady-state RMSE.  Its horizon error
    replaces the unflown fraction with ``FAILURE_HORIZON_ERROR_M`` so that a
    short, low-error prefix cannot outrank a completed trajectory.
    """

    normalized_period = _finite_float(period, "period")
    normalized_duration = _finite_float(duration_sec, "duration_sec")
    if normalized_period <= 0.0 or normalized_duration <= 0.0:
        raise ValueError("period and duration_sec must be positive")
    if not trajectory_rows:
        raise ValueError("trajectory_rows must contain at least one control-step row")

    rows = sorted(trajectory_rows, key=lambda row: _finite_float(row["time"], "time"))
    times = [_finite_float(row["time"], "time") for row in rows]
    errors = [_finite_float(row["pos_error"], "pos_error") for row in rows]
    path_increments = [
        _finite_float(row.get("xy_path_increment", 0.0), "xy_path_increment")
        for row in rows
    ]
    reference_increments = [
        _finite_float(
            row.get("reference_path_increment", 0.0),
            "reference_path_increment",
        )
        for row in rows
    ]
    phase_errors = [
        _finite_float(row.get("phase_error", 0.0), "phase_error")
        for row in rows
    ]

    flight_time_sec = min(normalized_duration, max(0.0, times[-1]))
    completion_rate = min(1.0, flight_time_sec / normalized_duration)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    if failure:
        steady_position_rmse_success_only = float("nan")
    else:
        steady_errors = [
            error for time, error in zip(times, errors) if time >= normalized_period
        ]
        steady_position_rmse_success_only = (
            math.sqrt(sum(error * error for error in steady_errors) / len(steady_errors))
            if steady_errors
            else float("nan")
        )

    reference_path_length = sum(reference_increments)
    path_length_ratio = (
        sum(path_increments) / reference_path_length
        if reference_path_length > 0.0
        else float("nan")
    )
    unflown_fraction = 1.0 - completion_rate if failure else 0.0
    failure_penalized_horizon_error = (
        completion_rate * rmse + unflown_fraction * FAILURE_HORIZON_ERROR_M
    )
    return {
        "flight_time_sec": flight_time_sec,
        "failure": bool(failure),
        "completion_rate": completion_rate,
        "path_length_ratio": path_length_ratio,
        "mean_phase_error": _mean(phase_errors),
        "steady_position_rmse_success_only": steady_position_rmse_success_only,
        "failure_penalized_horizon_error": failure_penalized_horizon_error,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _model_file(model_path: Path) -> Path:
    path = Path(model_path)
    return path if path.is_file() else path.with_suffix(".zip")


def _rollout_identity(controller: str, model_path: Path | None) -> dict[str, object]:
    protocol_file = _REPO_ROOT / _PROTOCOL_PATH
    pid_file = _REPO_ROOT / _PID_CONFIG_PATH
    pid_payload = json.loads(pid_file.read_text(encoding="utf-8"))
    model_file = _model_file(model_path) if model_path is not None else None
    if model_file is not None and not model_file.is_file():
        raise FileNotFoundError(f"model file does not exist: {model_file}")
    return {
        "controller": controller,
        "model_path": str(model_file.resolve()) if model_file is not None else "frozen_pid",
        "model_sha256": _sha256(model_file) if model_file is not None else None,
        "source_git_sha": _git_sha(),
        "evaluation_source_sha256": _sha256(Path(__file__).resolve()),
        "environment_source_sha256": _sha256(_REPO_ROOT / _ENVIRONMENT_SOURCE_PATH),
        "protocol_path": str(_PROTOCOL_PATH).replace("\\", "/"),
        "protocol_sha256": _sha256(protocol_file),
        "pid_config_path": str(_PID_CONFIG_PATH).replace("\\", "/"),
        "pid_config_sha256": _sha256(pid_file),
        "pid_config_payload_hash": pid_payload.get("pid_payload_hash"),
    }


def _phase_error(position: np.ndarray, reference_position: np.ndarray) -> float:
    actual_phase = math.atan2(float(position[1]), float(position[0]))
    reference_phase = math.atan2(float(reference_position[1]), float(reference_position[0]))
    return math.atan2(
        math.sin(actual_phase - reference_phase),
        math.cos(actual_phase - reference_phase),
    )


def _truth_metadata(info: Mapping[str, object]) -> dict[str, float] | None:
    truth = info.get("disturbance_truth")
    if truth is None:
        return None
    names = ("wind_x", "wind_y", "thrust_efficiency", "torque_efficiency")
    return {name: float(getattr(truth, name)) for name in names}


def make_evaluation_environment(
    controller: str,
    scenario: str,
    parameters: Mapping[str, object],
):
    """Build the evaluation environment with the exact protocol-v2 policy transform."""

    from experiments.circular_tracking.rl_envs.hidden_disturbance_td3_env import (
        HiddenDisturbanceCircularTD3Env,
    )
    from experiments.circular_tracking.scripts.td3.train_hidden_td3 import (
        FixedObservationScaleWrapper,
    )

    raw_env = HiddenDisturbanceCircularTD3Env(
        controller_mode=controller,
        disturbance_profile=scenario,
        rollout_duration_sec=EVALUATION_DURATION_SEC,
        reference_velocity_gain=float(parameters["reference_velocity_gain"]),
        pid_xy_p_scale=float(parameters["pid_xy_p_scale"]),
        pid_xy_d_scale=float(parameters["pid_xy_d_scale"]),
        pid_target_step_limit=float(parameters["pid_target_step_limit"]),
        gui=False,
    )
    return FixedObservationScaleWrapper(raw_env) if controller != "pid" else raw_env


def rollout_controller(
    *,
    controller: str,
    scenario: str,
    training_seed: int,
    disturbance_seed: int,
    checkpoint: int,
    model_path: Path | None,
) -> dict[str, object]:
    """Evaluate one controller without exposing simulator truth to its policy."""

    if controller not in CONTROLLERS:
        raise ValueError(f"controller must be one of {CONTROLLERS}")
    validate_stage_a_training_seed(training_seed)
    validate_validation_seeds([disturbance_seed])
    if scenario not in STAGE_A_SCENARIOS:
        raise ValueError(f"scenario must be one of {STAGE_A_SCENARIOS}")

    # Imports are intentionally deferred: metric-only tests do not need a
    # PyBullet runtime, while real rollouts retain the actual environment/model.
    from stable_baselines3 import TD3

    from experiments.circular_tracking.scripts.td3.train_hidden_td3 import (
        observation_normalization_spec,
    )

    pid_payload = json.loads((_REPO_ROOT / _PID_CONFIG_PATH).read_text(encoding="utf-8"))
    parameters = pid_payload["parameters"]
    env = make_evaluation_environment(controller, scenario, parameters)
    model = None if controller == "pid" else TD3.load(str(_model_file(Path(model_path))))
    trajectory_rows: list[dict[str, float]] = []
    disturbance_truth_metadata: list[dict[str, object]] = []
    failure_reason = ""
    try:
        observation, info = env.reset(seed=disturbance_seed)
        reference_position = np.asarray(info["reference_position"], dtype=float)
        position = reference_position - np.asarray(info["position_error"], dtype=float)
        previous_position = position.copy()
        previous_reference_position = reference_position.copy()
        while True:
            # The model is given only the shared observable policy observation.
            action = (
                np.zeros(1, dtype=np.float32)
                if model is None
                else np.asarray(model.predict(observation, deterministic=True)[0], dtype=np.float32)
            )
            observation, _, terminated, truncated, info = env.step(action)
            reference_position = np.asarray(info["reference_position"], dtype=float)
            position = reference_position - np.asarray(info["position_error"], dtype=float)
            trajectory_rows.append(
                {
                    "time": float(info["time_sec"]),
                    "pos_error": float(np.linalg.norm(info["position_error"])),
                    "xy_path_increment": float(
                        np.linalg.norm(position[:2] - previous_position[:2])
                    ),
                    "reference_path_increment": float(
                        np.linalg.norm(
                            reference_position[:2] - previous_reference_position[:2]
                        )
                    ),
                    "phase_error": _phase_error(position, reference_position),
                }
            )
            truth = _truth_metadata(info)
            if truth is not None:
                disturbance_truth_metadata.append({"time_sec": info["time_sec"], **truth})
            previous_position = position
            previous_reference_position = reference_position
            failure_reason = str(info.get("failure_reason", ""))
            if terminated or truncated:
                metrics = compute_metrics(
                    trajectory_rows=trajectory_rows,
                    period=REFERENCE_PERIOD_SEC,
                    duration_sec=EVALUATION_DURATION_SEC,
                    failure=bool(terminated),
                )
                break
    finally:
        env.close()

    identity = _rollout_identity(controller, model_path)
    return {
        **identity,
        "observation_normalization": observation_normalization_spec() if controller != "pid" else None,
        **metrics,
        "scenario": scenario,
        "training_seed": int(training_seed),
        "disturbance_seed": int(disturbance_seed),
        "checkpoint": "frozen_pid" if controller == "pid" else int(checkpoint),
        "failure_reason": failure_reason,
        "rollout_metadata": {"disturbance_truth": disturbance_truth_metadata},
    }


def run_paired_validation_worker(
    *,
    training_seed: int,
    scenario: str,
    validation_seed: int,
    checkpoint: int,
    direct_model: Path,
    residual_model: Path,
    rollout: Callable[..., dict[str, object]] = rollout_controller,
) -> list[dict[str, object]]:
    """Run one seed's PID/Direct/Residual pair in one local worker.

    Each reset receives the identical seed and scenario.  The environment uses
    this seed only to construct its private deterministic disturbance process.
    """

    validate_stage_a_training_seed(training_seed)
    validate_validation_seeds([validation_seed])
    model_paths: dict[str, Path | None] = {
        "pid": None,
        "direct_td3": Path(direct_model),
        "residual_td3": Path(residual_model),
    }
    return [
        rollout(
            controller=controller,
            scenario=scenario,
            training_seed=training_seed,
            disturbance_seed=validation_seed,
            checkpoint=checkpoint,
            model_path=model_paths[controller],
        )
        for controller in CONTROLLERS
    ]


def evaluate_paired_rollouts(
    *,
    training_seed: int,
    checkpoint: int,
    direct_model: Path,
    residual_model: Path,
    scenarios: Sequence[str] = STAGE_A_SCENARIOS,
    validation_seeds: Sequence[int] = VALIDATION_SEEDS,
    worker: Callable[..., list[dict[str, object]]] = run_paired_validation_worker,
) -> list[dict[str, object]]:
    """Evaluate only the frozen validation set with paired controller resets."""

    validate_stage_a_training_seed(training_seed)
    seeds = validate_validation_seeds(validation_seeds)
    if set(scenarios) - set(STAGE_A_SCENARIOS):
        raise ValueError(f"scenarios must be drawn from {STAGE_A_SCENARIOS}")
    rows: list[dict[str, object]] = []
    for scenario in scenarios:
        for seed in seeds:
            rows.extend(
                worker(
                    training_seed=training_seed,
                    scenario=scenario,
                    validation_seed=seed,
                    checkpoint=checkpoint,
                    direct_model=Path(direct_model),
                    residual_model=Path(residual_model),
                )
            )
    return rows


def write_rollout_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """Write raw evidence as JSON; nested rollout metadata remains intact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(rows), indent=2, sort_keys=True), encoding="utf-8")


def write_rollout_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """Write a compact flat companion table for inspection outside Python."""

    fieldnames = sorted({key for row in rows for key in row if key != "rollout_metadata"})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the validation-only Stage-A CLI (no test or unseen seed options)."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-seed", type=int, required=True, choices=(STAGE_A_TRAINING_SEED,))
    parser.add_argument("--direct-model", type=Path, required=True)
    parser.add_argument("--residual-model", type=Path, required=True)
    parser.add_argument("--output-folder", type=Path, required=True)
    parser.add_argument("--checkpoint", type=int, default=20_000, choices=(5_000, 10_000, 20_000))
    parser.add_argument("--scenarios", nargs="+", choices=STAGE_A_SCENARIOS, default=STAGE_A_SCENARIOS)
    parser.add_argument("--validation-seeds", nargs="+", type=int, default=VALIDATION_SEEDS)
    args = parser.parse_args(argv)
    try:
        args.validation_seeds = validate_validation_seeds(args.validation_seeds)
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    if args.validation_seeds != VALIDATION_SEEDS:
        parser.error("Stage A requires the complete frozen validation set 100-109")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    rows = evaluate_paired_rollouts(
        training_seed=args.training_seed,
        checkpoint=args.checkpoint,
        direct_model=args.direct_model,
        residual_model=args.residual_model,
        scenarios=args.scenarios,
    )
    output_folder = Path(args.output_folder)
    write_rollout_rows(output_folder / "stage_a_rollouts.json", rows)
    write_rollout_csv(output_folder / "stage_a_rollouts.csv", rows)

    from experiments.circular_tracking.scripts.td3.summarize_hidden_td3 import (
        evaluate_stage_a_gate,
        summarize_hierarchical,
    )

    summary = summarize_hierarchical(rows)
    (output_folder / "stage_a_hierarchical_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    decision = evaluate_stage_a_gate(rows)
    (output_folder / "stage_a_decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"decision": decision["decision"], "rows": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
