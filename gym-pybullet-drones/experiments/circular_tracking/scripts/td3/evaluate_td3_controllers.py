"""Evaluate Phase-1 circular tracking controllers and export traceable outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

from experiments.circular_tracking.rl_envs import CircularResidualTD3Env


TRAJECTORY_COLUMNS = [
    "time",
    "x",
    "y",
    "z",
    "vx",
    "vy",
    "vz",
    "roll",
    "pitch",
    "yaw",
    "ref_x",
    "ref_y",
    "ref_z",
    "ref_vx",
    "ref_vy",
    "ref_vz",
    "pos_error",
    "xy_error",
    "z_error",
]

CONTROL_COLUMNS = [
    "time",
    "rpm_0",
    "rpm_1",
    "rpm_2",
    "rpm_3",
    "action_0",
    "action_1",
    "action_2",
    "action_3",
    "action_4",
    "gate",
    "saturation_fraction",
    "control_energy",
    "action_delta",
]

SUMMARY_COLUMNS = [
    "controller",
    "scenario",
    "seed",
    "radius",
    "period",
    "height",
    "duration_sec",
    "position_rmse",
    "steady_position_rmse",
    "max_position_error",
    "final_position_error",
    "max_altitude_error",
    "max_tilt_angle",
    "rotor_saturation_rate",
    "control_energy",
    "action_smoothness",
    "failure",
    "failure_reason",
]


def run_rollout(
    controller: str,
    scenario: str,
    seed: int,
    duration_sec: float,
    output_folder: Path,
    model_path: Path | None = None,
    radius: float = 0.3,
    period: float = 10.0,
    height: float = 1.0,
    residual_gate_min: float = 0.0,
) -> Dict[str, object]:
    env = CircularResidualTD3Env(
        controller_mode=controller,
        scenario=scenario,
        duration_sec=duration_sec,
        radius=radius,
        period=period,
        height=height,
        residual_gate_min=residual_gate_min,
        gui=False,
        record=False,
    )
    try:
        env.reset(seed=seed)
        model = load_td3_model(model_path) if model_path else None
        trajectory_rows: List[Dict[str, float]] = []
        control_rows: List[Dict[str, float]] = []
        terminated = False
        truncated = False
        info: Dict[str, object] = {}
        obs = env._computeObs()

        while not (terminated or truncated):
            if model is None:
                action = np.zeros(env.action_space.shape, dtype=np.float32)
            else:
                action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            state = env._getDroneStateVector(0)
            ref = info["reference"]
            ref_pos = np.asarray(ref["pos"], dtype=float)
            ref_vel = np.asarray(ref["vel"], dtype=float)
            pos = state[0:3]
            vel = state[10:13]
            rpy = state[7:10]
            pos_error_vec = pos - ref_pos
            action_values = np.asarray(info["policy_action"], dtype=float).reshape(-1)
            action_padded = np.zeros(5, dtype=float)
            action_padded[: min(5, action_values.size)] = action_values[:5]
            rpm = np.asarray(info["rpm"], dtype=float).reshape(4)

            trajectory_rows.append(
                {
                    "time": float(info["time"]),
                    "x": float(pos[0]),
                    "y": float(pos[1]),
                    "z": float(pos[2]),
                    "vx": float(vel[0]),
                    "vy": float(vel[1]),
                    "vz": float(vel[2]),
                    "roll": float(rpy[0]),
                    "pitch": float(rpy[1]),
                    "yaw": float(rpy[2]),
                    "ref_x": float(ref_pos[0]),
                    "ref_y": float(ref_pos[1]),
                    "ref_z": float(ref_pos[2]),
                    "ref_vx": float(ref_vel[0]),
                    "ref_vy": float(ref_vel[1]),
                    "ref_vz": float(ref_vel[2]),
                    "pos_error": float(np.linalg.norm(pos_error_vec)),
                    "xy_error": float(np.linalg.norm(pos_error_vec[0:2])),
                    "z_error": float(pos_error_vec[2]),
                }
            )
            control_rows.append(
                {
                    "time": float(info["time"]),
                    "rpm_0": float(rpm[0]),
                    "rpm_1": float(rpm[1]),
                    "rpm_2": float(rpm[2]),
                    "rpm_3": float(rpm[3]),
                    "action_0": float(action_padded[0]),
                    "action_1": float(action_padded[1]),
                    "action_2": float(action_padded[2]),
                    "action_3": float(action_padded[3]),
                    "action_4": float(action_padded[4]),
                    "gate": float(info["gate"]),
                    "saturation_fraction": float(info["saturation_fraction"]),
                    "control_energy": float(info["control_energy"]),
                    "action_delta": float(info["action_delta"]),
                }
            )

        metrics = compute_metrics(trajectory_rows, control_rows, env.period)
        metrics["failure"] = bool(terminated)
        metrics["failure_reason"] = str(info.get("failure_reason", "")) if terminated else ""
        summary = {
            "controller": controller,
            "scenario": scenario,
            "seed": seed,
            "radius": env.radius,
            "period": env.period,
            "height": env.height,
            "duration_sec": duration_sec,
            "disturbance": info.get("disturbance", {}),
            "metrics": metrics,
        }

        rollout_dir = output_folder / controller / scenario / f"seed_{seed:03d}"
        rollout_dir.mkdir(parents=True, exist_ok=True)
        write_csv(rollout_dir / "trajectory.csv", TRAJECTORY_COLUMNS, trajectory_rows)
        write_csv(rollout_dir / "control.csv", CONTROL_COLUMNS, control_rows)
        (rollout_dir / "episode_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            "controller": controller,
            "scenario": scenario,
            "seed": seed,
            "radius": env.radius,
            "period": env.period,
            "height": env.height,
            "duration_sec": duration_sec,
            **metrics,
        }
    finally:
        env.close()


def compute_metrics(
    trajectory_rows: List[Dict[str, float]],
    control_rows: List[Dict[str, float]],
    period: float,
) -> Dict[str, object]:
    if not trajectory_rows:
        return {
            "position_rmse": float("nan"),
            "steady_position_rmse": float("nan"),
            "max_position_error": float("nan"),
            "final_position_error": float("nan"),
            "max_altitude_error": float("nan"),
            "max_tilt_angle": float("nan"),
            "rotor_saturation_rate": float("nan"),
            "control_energy": float("nan"),
            "action_smoothness": float("nan"),
        }

    pos_error = np.array([row["pos_error"] for row in trajectory_rows], dtype=float)
    z_error = np.array([row["z_error"] for row in trajectory_rows], dtype=float)
    time = np.array([row["time"] for row in trajectory_rows], dtype=float)
    tilt = np.array(
        [np.hypot(row["roll"], row["pitch"]) for row in trajectory_rows],
        dtype=float,
    )
    steady_mask = time >= period
    steady_error = pos_error[steady_mask] if np.any(steady_mask) else pos_error
    saturation = np.array([row["saturation_fraction"] for row in control_rows], dtype=float)
    energy = np.array([row["control_energy"] for row in control_rows], dtype=float)
    action_delta = np.array([row["action_delta"] for row in control_rows], dtype=float)
    return {
        "position_rmse": float(np.sqrt(np.mean(pos_error**2))),
        "steady_position_rmse": float(np.sqrt(np.mean(steady_error**2))),
        "max_position_error": float(np.max(pos_error)),
        "final_position_error": float(pos_error[-1]),
        "max_altitude_error": float(np.max(np.abs(z_error))),
        "max_tilt_angle": float(np.max(tilt)),
        "rotor_saturation_rate": float(np.mean(saturation)) if saturation.size else float("nan"),
        "control_energy": float(np.mean(energy)) if energy.size else float("nan"),
        "action_smoothness": float(np.mean(action_delta)) if action_delta.size else float("nan"),
    }


def write_csv(path: Path, columns: Iterable[str], rows: List[Dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def load_td3_model(model_path: Path):
    if not model_path.exists():
        raise FileNotFoundError(f"TD3 model path does not exist: {model_path}")
    from stable_baselines3 import TD3

    return TD3.load(model_path, device="cpu")


def model_path_for_controller(args: argparse.Namespace, controller: str) -> Path | None:
    paths = {
        "direct_td3": args.direct_td3_model,
        "residual_td3": args.residual_td3_model,
        "disturbance_aware_residual_td3": args.disturbance_aware_residual_td3_model,
        "disturbance_aware_residual_td3_no_gate": args.disturbance_aware_residual_td3_no_gate_model,
    }
    return paths.get(controller)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controllers", nargs="+", default=["pid", "residual_td3"])
    parser.add_argument("--scenarios", nargs="+", default=["standard", "wind"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--duration-sec", type=float, default=12.0)
    parser.add_argument("--radius", type=float, default=0.3)
    parser.add_argument("--period", type=float, default=10.0)
    parser.add_argument("--height", type=float, default=1.0)
    parser.add_argument("--residual-gate-min", type=float, default=0.0)
    parser.add_argument("--direct-td3-model", type=Path, default=None)
    parser.add_argument("--residual-td3-model", type=Path, default=None)
    parser.add_argument("--disturbance-aware-residual-td3-model", type=Path, default=None)
    parser.add_argument("--disturbance-aware-residual-td3-no-gate-model", type=Path, default=None)
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=Path("experiments/circular_tracking/results/td3_residual_paper/eval_phase1"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_folder.mkdir(parents=True, exist_ok=True)
    config = {
        "controllers": args.controllers,
        "scenarios": args.scenarios,
        "seeds": args.seeds,
        "duration_sec": args.duration_sec,
        "radius": args.radius,
        "period": args.period,
        "height": args.height,
        "residual_gate_min": args.residual_gate_min,
        "output_folder": str(args.output_folder),
        "model_paths": {
            "direct_td3": str(args.direct_td3_model) if args.direct_td3_model else None,
            "residual_td3": str(args.residual_td3_model) if args.residual_td3_model else None,
            "disturbance_aware_residual_td3": (
                str(args.disturbance_aware_residual_td3_model)
                if args.disturbance_aware_residual_td3_model
                else None
            ),
            "disturbance_aware_residual_td3_no_gate": (
                str(args.disturbance_aware_residual_td3_no_gate_model)
                if args.disturbance_aware_residual_td3_no_gate_model
                else None
            ),
        },
        "note": "If a TD3 model path is omitted for a TD3 controller, zero actions are used.",
    }
    (args.output_folder / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_rows: List[Dict[str, object]] = []
    for controller in args.controllers:
        for scenario in args.scenarios:
            for seed in args.seeds:
                model_path = model_path_for_controller(args, controller)
                summary_rows.append(
                    run_rollout(
                        controller=controller,
                        scenario=scenario,
                        seed=seed,
                        duration_sec=args.duration_sec,
                        output_folder=args.output_folder,
                        model_path=model_path,
                        radius=args.radius,
                        period=args.period,
                        height=args.height,
                        residual_gate_min=args.residual_gate_min,
                    )
                )
    write_csv(args.output_folder / "summary_metrics.csv", SUMMARY_COLUMNS, summary_rows)


if __name__ == "__main__":
    main()
