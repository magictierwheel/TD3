"""Compute diagnostic summaries for TD3 circular-tracking rollouts."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


DIAGNOSTIC_COLUMNS = [
    "controller",
    "scenario",
    "seed",
    "flight_time",
    "failure",
    "failure_reason",
    "position_rmse",
    "steady_position_rmse",
    "max_position_error",
    "final_position_error",
    "max_tilt_angle",
    "rotor_saturation_rate",
    "control_energy",
    "action_smoothness",
    "mean_gate",
    "max_gate",
    "active_gate_rate",
    "mean_abs_action",
    "max_abs_action",
    "mean_action_norm",
    "max_action_norm",
]

GROUP_COLUMNS = ["controller", "scenario"]
AGGREGATE_METRICS = [
    "flight_time",
    "position_rmse",
    "steady_position_rmse",
    "max_position_error",
    "final_position_error",
    "max_tilt_angle",
    "rotor_saturation_rate",
    "control_energy",
    "action_smoothness",
    "mean_gate",
    "max_gate",
    "active_gate_rate",
    "mean_abs_action",
    "max_abs_action",
    "mean_action_norm",
    "max_action_norm",
]


def read_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fieldnames: Iterable[str], rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: object, default: float = float("nan")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def finite(values: Iterable[float]) -> List[float]:
    return [value for value in values if math.isfinite(value)]


def mean(values: Iterable[float]) -> float:
    clean = finite(values)
    if not clean:
        return float("nan")
    return sum(clean) / len(clean)


def sample_std(values: Iterable[float]) -> float:
    clean = finite(values)
    if len(clean) < 2:
        return 0.0
    mu = mean(clean)
    return math.sqrt(sum((value - mu) ** 2 for value in clean) / (len(clean) - 1))


def action_values(row: Dict[str, str]) -> List[float]:
    values = []
    for index in range(5):
        value = row.get(f"action_{index}", "")
        if value == "":
            continue
        values.append(as_float(value))
    return values


def diagnostic_row(
    summary: Dict[str, str],
    trajectory_rows: List[Dict[str, str]],
    control_rows: List[Dict[str, str]],
) -> Dict[str, object]:
    times = [as_float(row.get("time")) for row in trajectory_rows]
    flight_time = max(finite(times), default=0.0)
    gate = [as_float(row.get("gate")) for row in control_rows]
    actions = [action_values(row) for row in control_rows]
    action_abs = [abs(value) for row_values in actions for value in row_values]
    action_norms = [math.sqrt(sum(value * value for value in row_values)) for row_values in actions if row_values]

    return {
        "controller": summary["controller"],
        "scenario": summary["scenario"],
        "seed": summary["seed"],
        "flight_time": flight_time,
        "failure": summary.get("failure", ""),
        "failure_reason": summary.get("failure_reason", ""),
        "position_rmse": as_float(summary.get("position_rmse")),
        "steady_position_rmse": as_float(summary.get("steady_position_rmse")),
        "max_position_error": as_float(summary.get("max_position_error")),
        "final_position_error": as_float(summary.get("final_position_error")),
        "max_tilt_angle": as_float(summary.get("max_tilt_angle")),
        "rotor_saturation_rate": as_float(summary.get("rotor_saturation_rate")),
        "control_energy": as_float(summary.get("control_energy")),
        "action_smoothness": as_float(summary.get("action_smoothness")),
        "mean_gate": mean(gate),
        "max_gate": max(finite(gate), default=float("nan")),
        "active_gate_rate": mean([1.0 if value > 1e-3 else 0.0 for value in finite(gate)]),
        "mean_abs_action": mean(action_abs),
        "max_abs_action": max(finite(action_abs), default=float("nan")),
        "mean_action_norm": mean(action_norms),
        "max_action_norm": max(finite(action_norms), default=float("nan")),
    }


def aggregate_rows(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    groups: Dict[Tuple[str, str], List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["controller"]), str(row["scenario"]))].append(row)

    aggregate: List[Dict[str, object]] = []
    for (controller, scenario), group_rows in sorted(groups.items()):
        out: Dict[str, object] = {
            "controller": controller,
            "scenario": scenario,
            "num_seeds": len({str(row["seed"]) for row in group_rows}),
            "failure_rate": mean(
                [1.0 if str(row.get("failure", "")).lower() == "true" else 0.0 for row in group_rows]
            ),
        }
        for metric in AGGREGATE_METRICS:
            values = [as_float(row.get(metric)) for row in group_rows]
            out[f"{metric}_mean"] = mean(values)
            out[f"{metric}_std"] = sample_std(values)
        aggregate.append(out)
    return aggregate


def build_diagnostics(eval_folder: Path) -> List[Dict[str, object]]:
    summary_path = eval_folder / "summary_metrics.csv"
    summary_rows = read_rows(summary_path)
    diagnostics: List[Dict[str, object]] = []
    for summary in summary_rows:
        seed = int(as_float(summary["seed"], 0.0))
        rollout_dir = eval_folder / summary["controller"] / summary["scenario"] / f"seed_{seed:03d}"
        diagnostics.append(
            diagnostic_row(
                summary,
                read_rows(rollout_dir / "trajectory.csv"),
                read_rows(rollout_dir / "control.csv"),
            )
        )
    return diagnostics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-folder", type=Path, required=True)
    parser.add_argument("--output-folder", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_folder = args.output_folder or args.eval_folder
    diagnostics = build_diagnostics(args.eval_folder)
    write_rows(output_folder / "diagnostic_summary.csv", DIAGNOSTIC_COLUMNS, diagnostics)

    aggregate = aggregate_rows(diagnostics)
    aggregate_columns = list(aggregate[0].keys()) if aggregate else ["controller", "scenario"]
    write_rows(output_folder / "diagnostic_summary_aggregate.csv", aggregate_columns, aggregate)


if __name__ == "__main__":
    main()
