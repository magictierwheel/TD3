"""Evaluate TD3 model candidates on validation scenarios and select checkpoints."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from experiments.circular_tracking.scripts.td3.evaluate_td3_controllers import run_rollout


VALIDATION_COLUMNS = [
    "controller",
    "training_seed",
    "candidate",
    "model_path",
    "scenario",
    "validation_seed",
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

SCORE_COLUMNS = [
    "controller",
    "training_seed",
    "candidate",
    "model_path",
    "num_rollouts",
    "failure_rate",
    "mean_steady_position_rmse",
    "mean_position_rmse",
    "mean_action_smoothness",
    "selection_score",
]


def write_csv(path: Path, columns: Iterable[str], rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def finite(values: Iterable[float]) -> List[float]:
    return [value for value in values if math.isfinite(value)]


def mean(values: Iterable[float]) -> float:
    clean = finite(values)
    if not clean:
        return float("nan")
    return sum(clean) / len(clean)


def candidate_models(run_dir: Path, include_checkpoints: bool, include_warm_start: bool) -> List[Tuple[str, Path]]:
    candidates: List[Tuple[str, Path]] = []
    warm_start_model = run_dir / "warm_start_model.zip"
    if include_warm_start and warm_start_model.exists():
        candidates.append(("warm_start", warm_start_model))
    final_model = run_dir / "model.zip"
    if final_model.exists():
        candidates.append(("final", final_model))
    if include_checkpoints:
        checkpoint_dir = run_dir / "checkpoints"
        for checkpoint in sorted(checkpoint_dir.glob("*.zip")):
            candidates.append((checkpoint.stem, checkpoint))
    return candidates


def score_rows(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    groups: Dict[Tuple[str, int, str, str], List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[
            (
                str(row["controller"]),
                int(row["training_seed"]),
                str(row["candidate"]),
                str(row["model_path"]),
            )
        ].append(row)

    scores: List[Dict[str, object]] = []
    for (controller, training_seed, candidate, model_path), group in sorted(groups.items()):
        failures = [str(row["failure"]).lower() == "true" for row in group]
        failure_rate = sum(failures) / len(failures) if failures else float("nan")
        steady_rmse = mean(as_float(row["steady_position_rmse"]) for row in group)
        position_rmse = mean(as_float(row["position_rmse"]) for row in group)
        smoothness = mean(as_float(row["action_smoothness"]) for row in group)
        scores.append(
            {
                "controller": controller,
                "training_seed": training_seed,
                "candidate": candidate,
                "model_path": model_path,
                "num_rollouts": len(group),
                "failure_rate": failure_rate,
                "mean_steady_position_rmse": steady_rmse,
                "mean_position_rmse": position_rmse,
                "mean_action_smoothness": smoothness,
                "selection_score": 100.0 * failure_rate + steady_rmse + 0.1 * smoothness,
            }
        )
    return scores


def selected_models(scores: List[Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    selected: Dict[str, Dict[str, object]] = {}
    groups: Dict[Tuple[str, int], List[Dict[str, object]]] = defaultdict(list)
    for row in scores:
        groups[(str(row["controller"]), int(row["training_seed"]))].append(row)
    for (controller, training_seed), rows in sorted(groups.items()):
        best = min(rows, key=lambda row: as_float(row["selection_score"]))
        selected[f"{controller}_seed{training_seed}"] = best
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-folder", type=Path, required=True)
    parser.add_argument("--output-folder", type=Path, required=True)
    parser.add_argument(
        "--controllers",
        nargs="+",
        default=[
            "direct_td3",
            "residual_td3",
            "disturbance_aware_residual_td3",
            "disturbance_aware_residual_td3_no_gate",
        ],
    )
    parser.add_argument("--training-seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--validation-seeds", nargs="+", type=int, default=[100, 101, 102])
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=["standard", "wind", "thermal", "dust", "compound"],
    )
    parser.add_argument("--duration-sec", type=float, default=30.0)
    parser.add_argument("--radius", type=float, default=0.3)
    parser.add_argument("--period", type=float, default=10.0)
    parser.add_argument("--height", type=float, default=1.0)
    parser.add_argument("--residual-gate-min", type=float, default=0.0)
    parser.add_argument("--include-checkpoints", action="store_true")
    parser.add_argument("--include-warm-start", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_folder.mkdir(parents=True, exist_ok=True)
    config = vars(args).copy()
    config["runs_folder"] = str(args.runs_folder)
    config["output_folder"] = str(args.output_folder)
    (args.output_folder / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    rows: List[Dict[str, object]] = []
    for controller in args.controllers:
        for training_seed in args.training_seeds:
            run_dir = args.runs_folder / f"{controller}_seed{training_seed}"
            for candidate, model_path in candidate_models(
                run_dir,
                include_checkpoints=args.include_checkpoints,
                include_warm_start=args.include_warm_start,
            ):
                candidate_output = args.output_folder / "rollouts" / f"{controller}_seed{training_seed}" / candidate
                for scenario in args.scenarios:
                    for validation_seed in args.validation_seeds:
                        result = run_rollout(
                            controller=controller,
                            scenario=scenario,
                            seed=validation_seed,
                            duration_sec=args.duration_sec,
                            output_folder=candidate_output,
                            model_path=model_path,
                            radius=args.radius,
                            period=args.period,
                            height=args.height,
                            residual_gate_min=args.residual_gate_min,
                        )
                        rows.append(
                            {
                                "controller": controller,
                                "training_seed": training_seed,
                                "candidate": candidate,
                                "model_path": str(model_path),
                                "scenario": scenario,
                                "validation_seed": validation_seed,
                                "duration_sec": args.duration_sec,
                                "position_rmse": result["position_rmse"],
                                "steady_position_rmse": result["steady_position_rmse"],
                                "max_position_error": result["max_position_error"],
                                "final_position_error": result["final_position_error"],
                                "max_altitude_error": result["max_altitude_error"],
                                "max_tilt_angle": result["max_tilt_angle"],
                                "rotor_saturation_rate": result["rotor_saturation_rate"],
                                "control_energy": result["control_energy"],
                                "action_smoothness": result["action_smoothness"],
                                "failure": result["failure"],
                                "failure_reason": result["failure_reason"],
                            }
                        )

    write_csv(args.output_folder / "validation_summary.csv", VALIDATION_COLUMNS, rows)
    scores = score_rows(rows)
    write_csv(args.output_folder / "validation_model_scores.csv", SCORE_COLUMNS, scores)
    (args.output_folder / "selected_models.json").write_text(
        json.dumps(selected_models(scores), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
