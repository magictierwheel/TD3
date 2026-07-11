"""Hierarchical Stage-A summaries and the frozen GO/NO-GO decision rule."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from numbers import Real
from pathlib import Path
from typing import Mapping, Sequence

from experiments.circular_tracking.scripts.td3.evaluate_hidden_td3 import (
    VALIDATION_SEEDS,
    validate_stage_a_training_seed,
    validate_validation_seeds,
)


ROLL_OUT_METRICS = (
    "flight_time_sec",
    "completion_rate",
    "path_length_ratio",
    "mean_phase_error",
    "steady_position_rmse_success_only",
    "failure_penalized_horizon_error",
)
_STAGE_A_CONTROLLERS = ("pid", "direct_td3", "residual_td3")
_STAGE_A_SCENARIOS = ("standard", "compound")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        return float("nan")
    normalized = float(value)
    return normalized if math.isfinite(normalized) else float("nan")


def _mean(values: Sequence[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float("nan") if not finite else sum(finite) / len(finite)


def _sample_std(values: Sequence[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if len(finite) < 2:
        return 0.0
    average = _mean(finite)
    return math.sqrt(sum((value - average) ** 2 for value in finite) / (len(finite) - 1))


def _checkpoint_key(value: object) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def _group_key(row: Mapping[str, object]) -> tuple[str, str, object]:
    return (
        str(row["controller"]),
        str(row["scenario"]),
        row.get("checkpoint", ""),
    )


def _within_training_seed_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {
        "training_seed": int(rows[0]["training_seed"]),
        "num_rollouts": len(rows),
        "num_disturbance_seeds": len({int(row["disturbance_seed"]) for row in rows}),
        "failure_count": sum(_as_bool(row.get("failure", False)) for row in rows),
    }
    summary["failure_rate"] = summary["failure_count"] / len(rows) if rows else float("nan")
    for metric in ROLL_OUT_METRICS:
        summary[metric] = _mean([_as_float(row.get(metric)) for row in rows])
    return summary


def summarize_hierarchical(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Aggregate within training seed before comparing training seeds.

    Disturbance seed repetitions are retained as paired rollouts within a
    training seed.  The returned mean and standard deviation therefore use
    training seeds as the top-level replication unit, not a fictitious pooled
    rollout count.
    """

    grouped: dict[tuple[str, str, object], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        validate_stage_a_training_seed(row["training_seed"])
        grouped[_group_key(row)].append(row)

    result: list[dict[str, object]] = []
    for (controller, scenario, checkpoint), group_rows in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1], _checkpoint_key(item[0][2]))
    ):
        by_training_seed: dict[int, list[Mapping[str, object]]] = defaultdict(list)
        for row in group_rows:
            by_training_seed[int(row["training_seed"])].append(row)
        per_training_seed = [
            _within_training_seed_summary(seed_rows)
            for _, seed_rows in sorted(by_training_seed.items())
        ]
        aggregate: dict[str, object] = {
            "controller": controller,
            "scenario": scenario,
            "checkpoint": checkpoint,
            "analysis_unit": "training_seed",
            "num_training_seeds": len(per_training_seed),
            "num_disturbance_seeds": len(
                {int(row["disturbance_seed"]) for row in group_rows}
            ),
            "num_rollouts": len(group_rows),
            "failure_count": sum(
                int(summary["failure_count"]) for summary in per_training_seed
            ),
            "failure_rate": _mean(
                [_as_float(summary["failure_rate"]) for summary in per_training_seed]
            ),
            "per_training_seed": per_training_seed,
        }
        for metric in ROLL_OUT_METRICS:
            values = [_as_float(summary[metric]) for summary in per_training_seed]
            aggregate[f"{metric}_mean"] = _mean(values)
            aggregate[f"{metric}_training_seed_std"] = _sample_std(values)
        result.append(aggregate)
    return result


def select_global_checkpoint(rows: Sequence[Mapping[str, object]]) -> object:
    """Choose one checkpoint with the protocol's fixed lexicographic order."""

    candidates: dict[object, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        validate_stage_a_training_seed(row["training_seed"])
        if str(row.get("controller")) in {"direct_td3", "residual_td3"}:
            candidates[row.get("checkpoint", "")].append(row)
    if not candidates:
        raise ValueError("checkpoint selection requires Direct or Residual TD3 rows")

    def score(item: tuple[object, list[Mapping[str, object]]]) -> tuple[float, float, float, tuple[int, int | str]]:
        checkpoint, candidate_rows = item
        failure_rate = sum(_as_bool(row.get("failure", False)) for row in candidate_rows) / len(candidate_rows)
        horizon_error = _mean(
            [_as_float(row.get("failure_penalized_horizon_error")) for row in candidate_rows]
        )
        steady_rmse = _mean(
            [_as_float(row.get("steady_position_rmse_success_only")) for row in candidate_rows]
        )
        return (
            failure_rate,
            horizon_error if math.isfinite(horizon_error) else math.inf,
            steady_rmse if math.isfinite(steady_rmse) else math.inf,
            _checkpoint_key(checkpoint),
        )

    return min(candidates.items(), key=score)[0]


def _selected_stage_a_rows(rows: Sequence[Mapping[str, object]]) -> tuple[object, list[Mapping[str, object]]]:
    selected_checkpoint = select_global_checkpoint(rows)
    selected: list[Mapping[str, object]] = []
    for row in rows:
        controller = str(row.get("controller"))
        if controller == "pid" or row.get("checkpoint", "") == selected_checkpoint:
            selected.append(row)
    return selected_checkpoint, selected


def _require_stage_a_coverage(
    rows: Sequence[Mapping[str, object]],
    controller: str,
    scenario: str,
) -> list[Mapping[str, object]]:
    selected = [
        row
        for row in rows
        if str(row.get("controller")) == controller and str(row.get("scenario")) == scenario
    ]
    actual_seeds = tuple(sorted(int(row["disturbance_seed"]) for row in selected))
    if actual_seeds != VALIDATION_SEEDS:
        raise ValueError(
            f"Stage A requires exactly one paired row for every validation seed 100-109; "
            f"{controller}/{scenario} has {actual_seeds}"
        )
    validate_validation_seeds(actual_seeds)
    training_seeds = {int(row["training_seed"]) for row in selected}
    if len(training_seeds) != 1:
        raise ValueError("Stage A gate accepts one training seed at a time")
    return selected


def _gate_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    failures = sum(_as_bool(row.get("failure", False)) for row in rows)
    success_only_rmse = _mean(
        [_as_float(row.get("steady_position_rmse_success_only")) for row in rows]
    )
    horizon_error = _mean(
        [_as_float(row.get("failure_penalized_horizon_error")) for row in rows]
    )
    return {
        "failure_count": failures,
        "success_only_steady_position_rmse": success_only_rmse,
        "failure_penalized_horizon_error": horizon_error,
    }


def _compound_improvement(
    residual: Mapping[str, object], comparator: Mapping[str, object]
) -> tuple[bool, str]:
    residual_failures = int(residual["failure_count"])
    comparator_failures = int(comparator["failure_count"])
    if residual_failures <= comparator_failures - 1:
        return True, "at_least_one_fewer_failure"
    residual_error = _as_float(residual["failure_penalized_horizon_error"])
    comparator_error = _as_float(comparator["failure_penalized_horizon_error"])
    if (
        residual_failures == comparator_failures
        and math.isfinite(residual_error)
        and math.isfinite(comparator_error)
        and comparator_error > 0.0
        and residual_error <= 0.95 * comparator_error + 1e-12
    ):
        return True, "equal_failures_and_horizon_error_at_least_5_percent_lower"
    return False, "no_required_compound_improvement"


def evaluate_stage_a_gate(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Apply the frozen Stage-A rule and preserve the raw paired evidence."""

    for row in rows:
        validate_stage_a_training_seed(row["training_seed"])
    selected_checkpoint, selected_rows = _selected_stage_a_rows(rows)
    raw_evidence: dict[str, dict[str, list[Mapping[str, object]]]] = {}
    summaries: dict[str, dict[str, dict[str, object]]] = {}
    for scenario in _STAGE_A_SCENARIOS:
        raw_evidence[scenario] = {}
        summaries[scenario] = {}
        for controller in _STAGE_A_CONTROLLERS:
            coverage = _require_stage_a_coverage(selected_rows, controller, scenario)
            raw_evidence[scenario][controller] = coverage
            summaries[scenario][controller] = _gate_summary(coverage)

    residual_standard = summaries["standard"]["residual_td3"]
    pid_standard = summaries["standard"]["pid"]
    residual_rmse = _as_float(residual_standard["success_only_steady_position_rmse"])
    pid_rmse = _as_float(pid_standard["success_only_steady_position_rmse"])
    standard_gate = bool(
        residual_standard["failure_count"] == 0
        and math.isfinite(residual_rmse)
        and math.isfinite(pid_rmse)
        and residual_rmse <= 1.10 * pid_rmse + 1e-12
    )

    residual_compound = summaries["compound"]["residual_td3"]
    pid_compound = summaries["compound"]["pid"]
    direct_compound = summaries["compound"]["direct_td3"]
    vs_pid, pid_rule = _compound_improvement(residual_compound, pid_compound)
    vs_direct, direct_rule = _compound_improvement(residual_compound, direct_compound)
    decision = "GO" if standard_gate and (vs_pid or vs_direct) else "NO-GO"
    return {
        "decision": decision,
        "selected_checkpoint": selected_checkpoint,
        "standard_gate": standard_gate,
        "compound_improvement_vs_pid": vs_pid,
        "compound_improvement_vs_direct_td3": vs_direct,
        "rules": {
            "standard": "zero residual failures and success-only RMSE <= 1.10 * PID",
            "compound": "at least one fewer failure of 10, or equal failures with failure-penalized horizon error <= 0.95 * comparator",
            "vs_pid": pid_rule,
            "vs_direct_td3": direct_rule,
        },
        "summaries": summaries,
        "raw_evidence": raw_evidence,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollouts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    rows = json.loads(args.rollouts.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("rollouts JSON must contain a list")
    payload = {
        "hierarchical_summary": summarize_hierarchical(rows),
        "stage_a_decision": evaluate_stage_a_gate(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"decision": payload["stage_a_decision"]["decision"]}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
