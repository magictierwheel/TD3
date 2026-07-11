"""Stage-A validation metrics and decision tests for hidden-disturbance TD3."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.evaluation.evaluate_hidden_td3 import (
    VALIDATION_SEEDS,
    compute_metrics,
    evaluate_paired_rollouts,
    validate_validation_seeds,
)
from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.analysis.summarize_hidden_td3 import (
    evaluate_stage_a_gate,
    select_global_checkpoint,
    summarize_hierarchical,
)


def test_failed_rollout_is_not_reported_as_full_horizon_steady_rmse() -> None:
    rows = [
        {
            "time": float(time),
            "pos_error": 0.25,
            "xy_path_increment": 0.01,
            "reference_path_increment": 0.01,
            "phase_error": 0.1,
        }
        for time in np.arange(0.0, 8.0, 1.0 / 48.0)
    ]

    metrics = compute_metrics(
        trajectory_rows=rows,
        period=10.0,
        duration_sec=30.0,
        failure=True,
    )

    assert math.isnan(metrics["steady_position_rmse_success_only"])
    assert metrics["flight_time_sec"] < 10.0
    assert metrics["completion_rate"] < 1.0
    assert metrics["failure_penalized_horizon_error"] >= 2.0


def test_validation_api_rejects_test_and_unseen_seeds() -> None:
    assert validate_validation_seeds([100, 109]) == (100, 109)
    for forbidden_seed in (99, 110, 200, 300):
        with pytest.raises(ValueError, match="validation"):
            validate_validation_seeds([forbidden_seed])
    assert VALIDATION_SEEDS == tuple(range(100, 110))


def test_stage_a_evaluator_rejects_every_nonzero_training_seed() -> None:
    for training_seed in range(1, 5):
        with pytest.raises(ValueError, match="Stage A training seed"):
            evaluate_paired_rollouts(
                training_seed=training_seed,
                checkpoint=20_000,
                direct_model=Path("direct_model"),
                residual_model=Path("residual_model"),
                worker=lambda **_: [],
            )


def test_hierarchical_summary_preserves_training_and_disturbance_counts() -> None:
    rows = []
    for disturbance_seed in range(100, 103):
        rows.append(
            {
                "controller": "residual_td3",
                "scenario": "compound",
                "training_seed": 0,
                "disturbance_seed": disturbance_seed,
                "failure": False,
                "steady_position_rmse_success_only": 0.2,
                "flight_time_sec": 30.0,
                "completion_rate": 1.0,
                "path_length_ratio": 1.0,
                "mean_phase_error": 0.1,
                "failure_penalized_horizon_error": 0.2,
            }
        )

    result = summarize_hierarchical(rows)[0]

    assert result["num_training_seeds"] == 1
    assert result["num_disturbance_seeds"] == 3
    assert result["num_rollouts"] == 3
    assert result["failure_rate"] == 0.0


def test_stage_a_hierarchical_summary_rejects_every_nonzero_training_seed() -> None:
    for training_seed in range(1, 5):
        with pytest.raises(ValueError, match="Stage A training seed"):
            summarize_hierarchical(
                [
                    {
                        "controller": "residual_td3",
                        "scenario": "compound",
                        "training_seed": training_seed,
                        "disturbance_seed": 100,
                        "failure": False,
                    }
                ]
            )


def _stage_a_rows(
    *,
    residual_standard_rmse: float = 0.11,
    residual_compound_failures: int = 0,
    residual_compound_error: float = 1.9,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for scenario in ("standard", "compound"):
        for controller in ("pid", "direct_td3", "residual_td3"):
            for seed in VALIDATION_SEEDS:
                is_residual = controller == "residual_td3"
                failure = (
                    scenario == "compound"
                    and is_residual
                    and seed in VALIDATION_SEEDS[:residual_compound_failures]
                )
                rows.append(
                    {
                        "controller": controller,
                        "scenario": scenario,
                        "training_seed": 0,
                        "disturbance_seed": seed,
                        "checkpoint": 20_000 if controller != "pid" else "frozen_pid",
                        "failure": failure,
                        "steady_position_rmse_success_only": (
                            residual_standard_rmse
                            if scenario == "standard" and is_residual
                            else 0.1
                        ),
                        "failure_penalized_horizon_error": (
                            residual_compound_error
                            if scenario == "compound" and is_residual
                            else 2.0
                        ),
                    }
                )
    return rows


def test_stage_a_gate_emits_go_with_raw_evidence_at_exact_threshold() -> None:
    decision = evaluate_stage_a_gate(_stage_a_rows())

    assert decision["decision"] == "GO"
    assert decision["standard_gate"] is True
    assert decision["compound_improvement_vs_pid"] is True
    assert decision["compound_improvement_vs_direct_td3"] is True
    assert len(decision["raw_evidence"]["compound"]["residual_td3"]) == 10


def test_stage_a_gate_requires_all_ten_validation_disturbances() -> None:
    rows = _stage_a_rows()
    rows.pop()

    with pytest.raises(ValueError, match="100-109"):
        evaluate_stage_a_gate(rows)


def test_checkpoint_selection_uses_fixed_lexicographic_order() -> None:
    rows = []
    for checkpoint in (5_000, 20_000):
        for controller in ("direct_td3", "residual_td3"):
            rows.append(
                {
                    "controller": controller,
                    "checkpoint": checkpoint,
                    "training_seed": 0,
                    "failure": False,
                    "failure_penalized_horizon_error": 0.2,
                    "steady_position_rmse_success_only": 0.1,
                }
            )

    assert select_global_checkpoint(rows) == 5_000


def test_checkpoint_selection_rejects_every_nonzero_stage_a_training_seed() -> None:
    for training_seed in range(1, 5):
        with pytest.raises(ValueError, match="Stage A training seed"):
            select_global_checkpoint(
                [
                    {
                        "controller": "residual_td3",
                        "checkpoint": 20_000,
                        "training_seed": training_seed,
                        "failure": False,
                        "failure_penalized_horizon_error": 0.2,
                        "steady_position_rmse_success_only": 0.1,
                    }
                ]
            )
