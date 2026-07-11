"""Summarize TD3 evaluation metrics into aggregate tables."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


GROUP_COLUMNS = ["controller", "scenario", "radius", "period", "height", "duration_sec"]
NUMERIC_METRICS = [
    "position_rmse",
    "steady_position_rmse",
    "max_position_error",
    "final_position_error",
    "max_altitude_error",
    "max_tilt_angle",
    "rotor_saturation_rate",
    "control_energy",
    "action_smoothness",
]


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def group_key(row: Dict[str, str]) -> Tuple[str, ...]:
    return tuple(row[column] for column in GROUP_COLUMNS)


def as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def mean(values: List[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return float("nan")
    return sum(finite) / len(finite)


def sample_std(values: List[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if len(finite) < 2:
        return 0.0
    mu = mean(finite)
    return math.sqrt(sum((value - mu) ** 2 for value in finite) / (len(finite) - 1))


def summarize(rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    groups: Dict[Tuple[str, ...], List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)

    aggregate_rows: List[Dict[str, object]] = []
    for key, group_rows in sorted(groups.items()):
        aggregate: Dict[str, object] = dict(zip(GROUP_COLUMNS, key))
        aggregate["num_seeds"] = len({row["seed"] for row in group_rows})
        failures = [str(row.get("failure", "")).lower() == "true" for row in group_rows]
        aggregate["failure_rate"] = sum(failures) / len(failures) if failures else float("nan")
        for metric in NUMERIC_METRICS:
            values = [as_float(row.get(metric, "")) for row in group_rows]
            aggregate[f"{metric}_mean"] = mean(values)
            aggregate[f"{metric}_std"] = sample_std(values)
        aggregate_rows.append(aggregate)
    return aggregate_rows


def write_rows(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: List[str] = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary-metrics",
        type=Path,
        required=True,
        help="Path to summary_metrics.csv.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path. Defaults to summary_metrics_aggregate.csv beside the input file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output or args.summary_metrics.with_name("summary_metrics_aggregate.csv")
    rows = read_rows(args.summary_metrics)
    write_rows(output, summarize(rows))


if __name__ == "__main__":
    main()
