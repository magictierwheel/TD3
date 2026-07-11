"""Acceptance and reproducibility tests for the frozen nominal PID tuner."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import zipfile

import pytest

from experiments.circular_tracking.scripts.td3 import tune_hidden_pid as tuner
from experiments.circular_tracking.scripts.td3.tune_hidden_pid import (
    CANDIDATE_PARAMETER_ORDER,
    CANDIDATE_VALUES,
    enumerate_pid_candidates,
    evaluate_pid_config,
    load_frozen_pid_config,
    main,
    rank_candidates,
    split_candidate_shards,
    tune_and_freeze,
)


def test_candidate_grid_and_four_shard_round_trip() -> None:
    candidates = enumerate_pid_candidates()
    assert len(candidates) == 81
    assert tuple(candidates[0]) == (0.5, 0.5, 0.75, 0.0)
    assert tuple(candidates[-1]) == (1.0, 1.0, 1.25, 0.10)
    assert [len(shard) for shard in split_candidate_shards(candidates, 4)] == [21, 20, 20, 20]
    assert sorted(index for shard in split_candidate_shards(candidates, 4) for index, _ in shard) == list(range(81))


def test_candidate_sharding_rejects_noncanonical_grid_or_nonfour_worker_plan() -> None:
    candidates = enumerate_pid_candidates()
    with pytest.raises(ValueError, match="exactly four"):
        split_candidate_shards(candidates, 3)
    noncanonical = list(candidates)
    noncanonical[-1] = noncanonical[0]
    with pytest.raises(ValueError, match="canonical"):
        split_candidate_shards(noncanonical, 4)


def test_ranking_is_failure_first_and_deterministic() -> None:
    rows = [
        {"candidate_index": 2, "failure": False, "completed_steps": 1440, "steady_position_rmse": 0.05, "mean_phase_error": 0.2, "path_length_ratio": 1.02, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
        {"candidate_index": 1, "failure": False, "completed_steps": 1440, "steady_position_rmse": 0.05, "mean_phase_error": 0.2, "path_length_ratio": 0.98, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
        {"candidate_index": 0, "failure": True, "completed_steps": 1440, "steady_position_rmse": 0.0, "mean_phase_error": 0.0, "path_length_ratio": 1.0, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
    ]
    assert rank_candidates(rows)[0]["candidate_index"] == 1
    assert rank_candidates(rows)[1]["candidate_index"] == 2
    assert len(rank_candidates(rows)) == 2


def test_ranking_recomputes_acceptance_instead_of_trusting_record_flag() -> None:
    rows = [
        {"candidate_index": 0, "accepted": True, "failure": True, "completed_steps": 1440, "steady_position_rmse": 0.01, "mean_phase_error": 0.01, "path_length_ratio": 1.0, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
        {"candidate_index": 1, "accepted": True, "failure": False, "completed_steps": 1439, "steady_position_rmse": 0.01, "mean_phase_error": 0.01, "path_length_ratio": 1.0, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
        {"candidate_index": 2, "accepted": True, "failure": False, "completed_steps": 1440, "steady_position_rmse": 0.10, "mean_phase_error": 0.01, "path_length_ratio": 1.0, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
        {"candidate_index": 3, "accepted": False, "failure": False, "completed_steps": 1440, "steady_position_rmse": 0.02, "mean_phase_error": 0.01, "path_length_ratio": 1.0, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
        {"candidate_index": 4, "accepted": True, "failure": False, "completed_steps": "not-an-int", "steady_position_rmse": 0.01, "mean_phase_error": 0.01, "path_length_ratio": 1.0, "rotor_saturation_rate": 0.0, "control_energy": 0.2},
    ]
    assert [row["candidate_index"] for row in rank_candidates(rows)] == [3]


@pytest.mark.parametrize("completed_steps", [1440.1, 1440.9, "1440", None, True])
def test_ranking_requires_exact_numeric_integral_completed_step_count(
    completed_steps: object,
) -> None:
    row = {
        "candidate_index": 0,
        "accepted": True,
        "failure": False,
        "completed_steps": completed_steps,
        "steady_position_rmse": 0.01,
        "mean_phase_error": 0.01,
        "path_length_ratio": 1.0,
        "rotor_saturation_rate": 0.0,
        "control_energy": 0.2,
    }
    assert rank_candidates([row]) == []


def test_ranking_accepts_exact_integral_numeric_completed_step_count() -> None:
    row = {
        "candidate_index": 0,
        "accepted": False,
        "failure": False,
        "completed_steps": 1440.0,
        "steady_position_rmse": 0.01,
        "mean_phase_error": 0.01,
        "path_length_ratio": 1.0,
        "rotor_saturation_rate": 0.0,
        "control_energy": 0.2,
    }
    assert [item["candidate_index"] for item in rank_candidates([row])] == [0]


@pytest.mark.parametrize(
    "duration_sec, seed",
    [(20.0, 100), (30.0, 99), (30.0, 101), (30.0, 200)],
)
def test_evaluate_pid_config_rejects_nonvalidation_scope_before_simulation(
    duration_sec: float,
    seed: int,
) -> None:
    with pytest.raises(ValueError, match="validation"):
        evaluate_pid_config(
            duration_sec=duration_sec,
            seed=seed,
        )


def test_tune_api_and_cli_reject_nonvalidation_scope_before_enumerating_grid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def grid_must_not_start() -> list[tuple[float, float, float, float]]:
        raise AssertionError("grid construction must not start outside validation scope")

    monkeypatch.setattr(tuner, "enumerate_pid_candidates", grid_must_not_start)
    with pytest.raises(ValueError, match="validation"):
        tune_and_freeze(
            tmp_path / "frozen.json",
            seed=0,
            attempt_root=tmp_path / "external_attempt",
        )
    with pytest.raises(ValueError, match="validation"):
        tune_and_freeze(
            tmp_path / "frozen-seed-101.json",
            seed=101,
            attempt_root=tmp_path / "external_attempt_seed_101",
        )
    with pytest.raises(SystemExit) as exc_info:
        main(["--duration-sec", "20"])
    assert exc_info.value.code == 2


def test_tune_requires_explicit_external_attempt_root_before_grid_or_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def grid_must_not_start() -> list[tuple[float, float, float, float]]:
        raise AssertionError("candidate grid must not start without an external attempt root")

    repo_local_attempt = Path(
        "experiments/circular_tracking/results/hidden_disturbance_td3_paper/"
        "pid_tuning/rejected_attempt"
    )
    assert not repo_local_attempt.exists()
    monkeypatch.setattr(tuner, "enumerate_pid_candidates", grid_must_not_start)
    with pytest.raises(ValueError, match="external"):
        tune_and_freeze(tmp_path / "local-reject.json", attempt_root=repo_local_attempt)
    with pytest.raises(ValueError, match="external"):
        tune_and_freeze(tmp_path / "missing-reject.json")
    assert not repo_local_attempt.exists()


def test_cli_requires_an_explicit_external_attempt_root(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2
    assert "--attempt-root" in capsys.readouterr().err


def test_tune_attempt_writes_and_resumes_immutable_four_shard_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[float, float, float, float]] = []
    fail_once = {"value": True}

    def synthetic_evaluation(
        config: dict[str, float],
        duration_sec: float,
        seed: int,
    ) -> dict[str, float | bool | int | str]:
        candidate = tuple(config[name] for name in CANDIDATE_PARAMETER_ORDER)
        calls.append(candidate)
        if fail_once["value"] and len(calls) == 22:
            raise RuntimeError("simulated infrastructure interruption")
        assert duration_sec == 30.0
        assert seed == 100
        assert {os.environ[name] for name in tuner.THREAD_LIMIT_ENV} == {"1"}
        return {
            "failure": False,
            "failure_reason": "",
            "completed_steps": 1440,
            "duration_sec": duration_sec,
            "seed": seed,
            "steady_position_rmse": 0.01,
            "path_length_ratio": 1.0,
            "mean_phase_error": 0.01,
            "rotor_saturation_rate": 0.0,
            "control_energy": 0.2,
        }

    def synthetic_row(
        task: tuple[int, tuple[float, float, float, float], float, int],
    ) -> dict[str, object]:
        index, candidate, duration_sec, seed = task
        result = synthetic_evaluation(
            tuner.candidate_to_config(candidate),
            duration_sec,
            seed,
        )
        return {**result, "candidate_index": index, "candidate": list(candidate)}

    def synthetic_shards(
        _archive: Path,
        _archive_hash: str,
        pending_shards: object,
    ) -> object:
        assert isinstance(pending_shards, list)
        for shard in pending_shards:
            assert isinstance(shard, list)
            yield [synthetic_row(task) for task in shard]

    def synthetic_worker(
        _archive: Path,
        _archive_hash: str,
        request: dict[str, object],
        **_: object,
    ) -> dict[str, object]:
        assert request["kind"] == "shard"
        raw_task = request["tasks"][0]
        assert isinstance(raw_task, list)
        return {
            "rows": [
                synthetic_row(
                    (
                        int(raw_task[0]),
                        tuple(float(value) for value in raw_task[1]),
                        float(raw_task[2]),
                        int(raw_task[3]),
                    )
                )
            ]
        }

    monkeypatch.setattr(tuner, "_run_snapshot_shards", synthetic_shards)
    monkeypatch.setattr(tuner, "_run_snapshot_worker_process", synthetic_worker)
    attempt_root = tmp_path / "attempt_01"
    output = tmp_path / "frozen.json"
    with pytest.raises(RuntimeError, match="infrastructure"):
        tune_and_freeze(output, attempt_root=attempt_root, command=["unit-test"])
    assert (attempt_root / "RUNNING.json").is_file()
    assert (attempt_root / "candidate_manifest.json").is_file()
    assert len(list((attempt_root / "candidates").glob("candidate_*.json"))) == 21
    assert not (attempt_root / "DONE.json").exists()

    fail_once["value"] = False
    payload = tune_and_freeze(output, attempt_root=attempt_root, command=["unit-test"])
    assert payload is not None
    assert payload["winner_index"] == 0
    assert load_frozen_pid_config(output) == payload
    evidence = payload["attempt_evidence"]
    assert evidence["schema_version"] == 2
    assert Path(evidence["attempt_root"]) == attempt_root.resolve()
    assert set(evidence) == {
        "schema_version",
        "attempt_root",
        "evidence_index",
        "config_payload_sha256",
    }
    assert len(evidence["config_payload_sha256"]) == 64
    assert Path(evidence["evidence_index"]["path"]).is_file()
    indexed = tuner._read_immutable_json(Path(evidence["evidence_index"]["path"]))
    assert set(indexed["records"]) == {
        "running",
        "source_snapshot",
        "candidate_manifest",
        "candidates",
        "shards",
        "coverage",
        "ranking",
        "winner_recheck",
        "done",
    }
    assert len(indexed["records"]["candidates"]) == 81
    assert len(indexed["records"]["shards"]) == 4
    for name in ("RUNNING.json", "candidate_manifest.json", "coverage.json", "ranking.json", "winner_recheck.json", "DONE.json", "evidence_index.json"):
        assert (attempt_root / name).is_file()
    assert len(list((attempt_root / "candidates").glob("candidate_*.json"))) == 81
    assert len(list((attempt_root / "shards").glob("shard_*.json"))) == 4
    assert json.loads((attempt_root / "coverage.json").read_text(encoding="utf-8"))["complete"] is True
    assert json.loads((attempt_root / "DONE.json").read_text(encoding="utf-8"))["decision"] == "GO"
    with pytest.raises(FileExistsError, match="complete"):
        tune_and_freeze(output, attempt_root=attempt_root, command=["unit-test"])

    # A recovery procedure can find the frozen config after the DONE sentinel
    # was lost. It must verify the identical immutable payload and finish the
    # attempt, never overwrite the config or start a new grid.
    frozen_before_recovery = output.read_bytes()
    (attempt_root / "DONE.json").unlink()
    recovered = tune_and_freeze(output, attempt_root=attempt_root, command=["unit-test"])
    assert recovered is not None
    assert output.read_bytes() == frozen_before_recovery
    assert json.loads((attempt_root / "DONE.json").read_text(encoding="utf-8"))["decision"] == "GO"


def test_frozen_pid_tracks_three_nominal_circles() -> None:
    if tuner._is_known_repository_stale_pid_config():
        pytest.xfail(
            "repository nominal PID evidence is stale schema-2 history; regenerate current schema-4 evidence"
        )
    try:
        config = load_frozen_pid_config()
    except ValueError as exc:
        raise
    metrics = evaluate_pid_config(
        config=config,
        duration_sec=30.0,
        seed=100,
    )
    assert not metrics["failure"]
    assert metrics["completed_steps"] == 1440
    assert metrics["steady_position_rmse"] < 0.1
    assert 0.9 <= metrics["path_length_ratio"] <= 1.1
    for field in ("mean_phase_error", "rotor_saturation_rate", "control_energy"):
        assert math.isfinite(float(metrics[field]))


def test_load_frozen_config_rejects_protocol_tamper(tmp_path: Path) -> None:
    frozen_path, _ = _write_synthetic_complete_evidence_chain(tmp_path)
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    payload["protocol_hash"] = "tampered"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="protocol"):
        load_frozen_pid_config(tampered)


def _frozen_payload_copy(tmp_path: Path) -> dict[str, object]:
    frozen_path, _ = _write_synthetic_complete_evidence_chain(tmp_path)
    return json.loads(frozen_path.read_text(encoding="utf-8"))


def _set_nested(payload: dict[str, object], path: tuple[str, ...], value: object) -> None:
    target: dict[str, object] = payload
    for key in path[:-1]:
        child = target.get(key)
        if not isinstance(child, dict):
            child = {}
            target[key] = child
        target = child
    target[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("evaluation_seed",), 0, "validation"),
        (("evaluation_duration_sec",), 20.0, "validation"),
        (("geometry", "radius_m"), 0.4, "geometry"),
        (("simulation",), {"physics_frequency_hz": 1}, "simulation"),
        (("environment_schema",), [], "schema"),
        (("winner_metrics", "completed_steps"), 1439, "winner"),
        (("acceptance", "required_completed_steps"), 1439, "acceptance"),
        (("ranking_hash",), "tampered", "ranking"),
        (("attempt_evidence", "config_payload_sha256"), "tampered", "provenance"),
    ],
)
def test_load_frozen_config_rejects_tampered_contract_and_provenance(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    payload = _frozen_payload_copy(tmp_path)
    _set_nested(payload, path, value)
    if path == ("ranking_hash",):
        payload["attempt_evidence"]["config_payload_sha256"] = tuner._frozen_config_payload_hash(payload)
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_frozen_pid_config(tampered)


def test_load_frozen_config_requires_complete_attempt_provenance_schema(
    tmp_path: Path,
) -> None:
    payload = _frozen_payload_copy(tmp_path)
    payload["attempt_evidence"] = {"schema_version": 2}
    tampered = tmp_path / "incomplete-provenance.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        load_frozen_pid_config(tampered)


def _synthetic_pid_result(
    index: int,
    candidate: tuple[float, float, float, float],
) -> dict[str, float | int | bool | str]:
    """A deliberately non-simulated accepted result for evidence-only tests."""

    return {
        "failure": False,
        "failure_reason": "",
        "completed_steps": 1440,
        "duration_sec": 30.0,
        "seed": 100,
        "steady_position_rmse": 0.01 + index / 100_000.0,
        "path_length_ratio": 1.0,
        "mean_phase_error": 0.01,
        "rotor_saturation_rate": 0.0,
        "control_energy": 0.2,
        **tuner.candidate_to_config(candidate),
    }


def _immutable_rewrite(path: Path, payload: dict[str, object]) -> dict[str, object]:
    core = dict(payload)
    core.pop("content_sha256", None)
    stored = tuner._immutable_stored_payload(core)
    tuner._write_atomic_json(path, stored)
    return stored


def _synthetic_entry(path: Path, **metadata: object) -> dict[str, object]:
    return {
        **metadata,
        **tuner._artifact_provenance_entry(path),
    }


def _write_synthetic_complete_evidence_chain(tmp_path: Path) -> tuple[Path, Path]:
    """Create the complete evidence-v2 graph without calling a PID rollout."""

    attempt_root = tmp_path / "external_evidence"
    attempt_root.mkdir()
    candidates = enumerate_pid_candidates()
    shards = split_candidate_shards(candidates, 4)
    command = ["synthetic-evidence-test", "--validation-only"]
    manifest = tuner._attempt_manifest(candidates, duration_sec=30.0, seed=100)
    stored_manifest = tuner._write_immutable_json(
        attempt_root / "candidate_manifest.json", manifest
    )
    source_snapshot = tuner._write_source_snapshot(attempt_root, tuner._git_sha())
    tuner._write_immutable_json(
        attempt_root / "RUNNING.json",
        {
            "schema_version": 2,
            "attempt_name": attempt_root.name,
            "protocol_hash": tuner.protocol_hash(),
            "candidate_manifest_sha256": stored_manifest["content_sha256"],
            "evaluation_git_sha": tuner._git_sha(),
            "source_snapshot_sha256": source_snapshot["content_sha256"],
            "command": command,
            "thread_limits": {name: "1" for name in tuner.THREAD_LIMIT_ENV},
            "worker_count": 4,
            "started_at_utc": "2026-07-11T00:00:00+00:00",
        },
    )

    rows: dict[int, dict[str, object]] = {}
    for index, candidate in enumerate(candidates):
        record_path = tuner._candidate_record_path(attempt_root, index)
        record = tuner._write_immutable_json(
            record_path,
            {
                "schema_version": 2,
                "protocol_hash": tuner.protocol_hash(),
                "candidate_index": index,
                "candidate": list(candidate),
                "parameters": tuner.candidate_to_config(candidate),
                "evaluation_duration_sec": 30.0,
                "evaluation_seed": 100,
                "result": _synthetic_pid_result(index, candidate),
            },
        )
        rows[index] = tuner._result_from_candidate_record(
            record,
            index=index,
            candidate=candidate,
            duration_sec=30.0,
            seed=100,
        )
    for shard_index, shard in enumerate(shards):
        shard_path = attempt_root / "shards" / f"shard_{shard_index:02d}.json"
        tuner._write_immutable_json(
            shard_path,
            {
                "schema_version": 2,
                "shard_index": shard_index,
                "candidate_indices": [index for index, _ in shard],
                "candidate_record_hashes": [
                    tuner._read_immutable_json(
                        tuner._candidate_record_path(attempt_root, index)
                    )["content_sha256"]
                    for index, _ in shard
                ],
            },
        )

    coverage_path = attempt_root / "coverage.json"
    coverage = tuner._write_immutable_json(
        coverage_path,
        {
            "schema_version": 2,
            "expected_candidate_indices": list(range(81)),
            "actual_candidate_indices": list(range(81)),
            "missing_candidate_indices": [],
            "duplicate_candidate_indices": [],
            "shard_sizes": [21, 20, 20, 20],
            "complete": True,
        },
    )
    ranking = rank_candidates(rows[index] for index in range(81))
    ranking_path = attempt_root / "ranking.json"
    stored_ranking = tuner._write_immutable_json(
        ranking_path,
        {
            "schema_version": 2,
            "candidate_manifest_sha256": stored_manifest["content_sha256"],
            "coverage_sha256": coverage["content_sha256"],
            "accepted_candidate_indices": [row["candidate_index"] for row in ranking],
            "ranking": ranking,
        },
    )
    winner = ranking[0]
    original_result = dict(rows[int(winner["candidate_index"])])
    original_result.pop("candidate_index")
    original_result.pop("candidate")
    recheck_path = attempt_root / "winner_recheck.json"
    winner_recheck = tuner._write_immutable_json(
        recheck_path,
        {
            "schema_version": 2,
            "decision": "GO",
            "winner_index": winner["candidate_index"],
            "candidate": winner["candidate"],
            "original_result": original_result,
            "recheck_result": original_result,
            "ranking_sha256": stored_ranking["content_sha256"],
        },
    )
    done_path = attempt_root / "DONE.json"
    tuner._write_immutable_json(
        done_path,
        {
            "schema_version": 2,
            "decision": "GO",
            "candidate_manifest_sha256": stored_manifest["content_sha256"],
            "coverage_sha256": coverage["content_sha256"],
            "ranking_sha256": stored_ranking["content_sha256"],
            "winner_recheck_sha256": winner_recheck["content_sha256"],
        },
    )

    evidence_index_path = attempt_root / "evidence_index.json"
    tuner._write_evidence_index(
        attempt_root,
        duration_sec=30.0,
        seed=100,
        command=command,
    )
    frozen_path = tmp_path / "frozen-evidence-v2.json"
    payload = tuner.build_frozen_payload(
        winner,
        command=command,
        duration_sec=30.0,
        seed=100,
        ranking=ranking,
        attempt_evidence={
            "schema_version": 2,
            "attempt_root": str(attempt_root.resolve()),
            "evidence_index": _synthetic_entry(evidence_index_path),
        },
    )
    payload["schema_version"] = 4
    payload["attempt_evidence"]["schema_version"] = 2
    payload["attempt_evidence"]["config_payload_sha256"] = tuner._frozen_config_payload_hash(payload)
    tuner._write_new_frozen_payload(frozen_path, payload)
    return frozen_path, evidence_index_path


def _rebind_synthetic_index(frozen_path: Path, index_path: Path) -> None:
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    payload["attempt_evidence"]["evidence_index"] = _synthetic_entry(index_path)
    payload["attempt_evidence"]["config_payload_sha256"] = tuner._frozen_config_payload_hash(payload)
    frozen_path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_frozen_config_verifies_complete_evidence_v2_chain_without_rollouts(
    tmp_path: Path,
) -> None:
    frozen_path, _ = _write_synthetic_complete_evidence_chain(tmp_path)

    payload = load_frozen_pid_config(frozen_path)

    assert payload["schema_version"] == 4
    assert payload["attempt_evidence"]["schema_version"] == 2


def test_complete_evidence_v2_rejects_indexed_sha_rebased_to_another_commit(
    tmp_path: Path,
) -> None:
    frozen_path, index_path = _write_synthetic_complete_evidence_chain(tmp_path)
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    other_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD^"],
        cwd=tuner._repo_root(),
        text=True,
    ).strip()
    assert other_sha != payload["evaluation_git_sha"]

    index = tuner._read_immutable_json(index_path)
    index["evaluation_git_sha"] = other_sha
    _immutable_rewrite(index_path, index)
    payload["evaluation_git_sha"] = other_sha
    frozen_path.write_text(json.dumps(payload), encoding="utf-8")
    _rebind_synthetic_index(frozen_path, index_path)

    with pytest.raises(ValueError, match="(source identity|working-tree source)"):
        load_frozen_pid_config(frozen_path)


def _dirty_environment_source_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Make the environment's working-tree digest differ from its Git blob."""

    clean_hash = tuner._canonical_sha256
    environment_path = tuner._resolve_repo_path(tuner.ENV_SOURCE_PATH).resolve()

    def dirty_hash(path: Path) -> str:
        if tuner._resolve_repo_path(path).resolve() == environment_path:
            return "0" * 64
        return clean_hash(path)

    monkeypatch.setattr(tuner, "_canonical_sha256", dirty_hash)


def test_tune_rejects_dirty_working_tree_source_before_starting_grid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dirty_environment_source_hash(monkeypatch)

    def grid_must_not_start() -> list[tuple[float, float, float, float]]:
        raise AssertionError("source preflight must run before candidate enumeration")

    monkeypatch.setattr(tuner, "enumerate_pid_candidates", grid_must_not_start)
    with pytest.raises(ValueError, match="working-tree source"):
        tune_and_freeze(
            tmp_path / "frozen.json",
            attempt_root=tmp_path / "external_attempt",
            command=["unit-test"],
        )


def test_load_frozen_config_rejects_dirty_working_tree_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_path, _ = _write_synthetic_complete_evidence_chain(tmp_path)
    _dirty_environment_source_hash(monkeypatch)

    with pytest.raises(ValueError, match="working-tree source"):
        load_frozen_pid_config(frozen_path)


def test_tune_recovers_post_done_pre_config_without_rerunning_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_path, index_path = _write_synthetic_complete_evidence_chain(tmp_path)
    frozen_before_recovery = frozen_path.read_bytes()
    frozen_path.unlink()

    def candidate_pool_must_not_start(*_: object, **__: object) -> object:
        raise AssertionError("recovery must not rerun candidates")

    monkeypatch.setattr(tuner, "ProcessPoolExecutor", candidate_pool_must_not_start)
    recovered = tune_and_freeze(
        frozen_path,
        attempt_root=index_path.parent,
        command=["ignored-on-recovery"],
    )

    assert recovered is not None
    assert frozen_path.read_bytes() == frozen_before_recovery
    assert load_frozen_pid_config(frozen_path) == recovered


@pytest.mark.parametrize(
    "tamper_target",
    [
        "running",
        "source_snapshot",
        "candidate",
        "shard",
        "index",
        "source",
        "ranking",
        "winner_metric",
        "done",
    ],
)
def test_complete_evidence_v2_rejects_every_bound_tamper(
    tmp_path: Path,
    tamper_target: str,
) -> None:
    frozen_path, index_path = _write_synthetic_complete_evidence_chain(tmp_path)
    index = tuner._read_immutable_json(index_path)
    records = index["records"]

    if tamper_target == "candidate":
        candidate_path = Path(records["candidates"][0]["path"])
        candidate = tuner._read_immutable_json(candidate_path)
        candidate["result"]["steady_position_rmse"] = 0.02
        _immutable_rewrite(candidate_path, candidate)
        records["candidates"][0] = _synthetic_entry(candidate_path, candidate_index=0)
        # The candidate and outer index are internally rehashed; the shard
        # and ranking still bind the original candidate result and must fail
        # graph reconstruction rather than a shallow immutable-file check.
        _immutable_rewrite(index_path, index)
        _rebind_synthetic_index(frozen_path, index_path)
    elif tamper_target == "winner_metric":
        payload = json.loads(frozen_path.read_text(encoding="utf-8"))
        payload["winner_metrics"]["control_energy"] = 0.3
        payload["attempt_evidence"]["config_payload_sha256"] = tuner._frozen_config_payload_hash(payload)
        frozen_path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        if tamper_target == "running":
            target_path = Path(records["running"]["path"])
            target = tuner._read_immutable_json(target_path)
            target["command"] = ["tampered"]
            records["running"] = _synthetic_entry(target_path)
        elif tamper_target == "source_snapshot":
            target_path = Path(records["source_snapshot"]["path"])
            target = tuner._read_immutable_json(target_path)
            target["archive_sha256"] = "0" * 64
            records["source_snapshot"] = _synthetic_entry(target_path)
        elif tamper_target == "shard":
            target_path = Path(records["shards"][0]["path"])
            target = tuner._read_immutable_json(target_path)
            target["candidate_record_hashes"][0] = "0" * 64
            records["shards"][0] = _synthetic_entry(target_path)
        elif tamper_target == "index":
            index["scope"]["candidate_count"] = 80
            target = None
        elif tamper_target == "source":
            index["source_identities"]["tuner"]["working_tree_sha256"] = "0" * 64
            target = None
        elif tamper_target == "ranking":
            target_path = Path(records["ranking"]["path"])
            target = tuner._read_immutable_json(target_path)
            target["ranking"] = list(reversed(target["ranking"]))
            records["ranking"] = _synthetic_entry(target_path)
        else:
            target_path = Path(records["done"]["path"])
            target = tuner._read_immutable_json(target_path)
            target["winner_recheck_sha256"] = "0" * 64
            records["done"] = _synthetic_entry(target_path)
        if target is not None:
            _immutable_rewrite(target_path, target)
            if tamper_target in {"running", "source_snapshot", "shard", "ranking", "done"}:
                # Rebind the index entry after changing the record: the loader
                # must reject the record graph, not merely a stale outer digest.
                if tamper_target == "running":
                    records["running"] = _synthetic_entry(target_path)
                elif tamper_target == "source_snapshot":
                    records["source_snapshot"] = _synthetic_entry(target_path)
                elif tamper_target == "shard":
                    records["shards"][0] = _synthetic_entry(target_path)
                elif tamper_target == "ranking":
                    records["ranking"] = _synthetic_entry(target_path)
                else:
                    records["done"] = _synthetic_entry(target_path)
        _immutable_rewrite(index_path, index)
        _rebind_synthetic_index(frozen_path, index_path)

    with pytest.raises(ValueError, match="(evidence|provenance|ranking|winner|DONE|source|scope|RUNNING)"):
        load_frozen_pid_config(frozen_path)


def test_repository_frozen_pid_config_is_explicitly_unsupported_stale_schema() -> None:
    with pytest.raises(ValueError, match="schema version is unsupported"):
        load_frozen_pid_config()


def test_immutable_evidence_concurrent_conflicting_writers_never_overwrite(
    tmp_path: Path,
) -> None:
    """A concurrent conflicting record write must have one immutable winner."""

    path = tmp_path / "record.json"
    barrier = threading.Barrier(2)
    payloads = [{"writer": "left"}, {"writer": "right"}]

    def write(payload: dict[str, str]) -> tuple[str, dict[str, object] | str]:
        barrier.wait(timeout=5)
        try:
            return "ok", tuner._write_immutable_json(path, payload)
        except ValueError as exc:
            return "rejected", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, payloads))

    winners = [stored for status, stored in results if status == "ok"]
    assert len(winners) == 1
    assert sum(status == "rejected" for status, _ in results) == 1
    assert tuner._read_immutable_json(path) == winners[0]


def test_concurrent_conflicting_frozen_config_writers_never_overwrite(
    tmp_path: Path,
) -> None:
    """A frozen config uses the same no-overwrite commit primitive as evidence."""

    path = tmp_path / "frozen.json"
    barrier = threading.Barrier(2)
    payloads = [{"writer": "left"}, {"writer": "right"}]

    def write(payload: dict[str, str]) -> tuple[str, str | None]:
        barrier.wait(timeout=5)
        try:
            tuner._write_new_frozen_payload(path, payload)
            return "ok", None
        except FileExistsError as exc:
            return "rejected", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, payloads))

    assert sum(status == "ok" for status, _ in results) == 1
    assert sum(status == "rejected" for status, _ in results) == 1
    assert json.loads(path.read_text(encoding="utf-8")) in payloads


def test_attempt_lock_rejects_a_second_concurrent_writer(tmp_path: Path) -> None:
    """A second caller cannot mutate the same evidence attempt while it is live."""

    attempt_root = tmp_path / "attempt_01"
    with tuner._exclusive_attempt_lock(attempt_root):
        with pytest.raises(RuntimeError, match="already locked"):
            with tuner._exclusive_attempt_lock(attempt_root):
                pytest.fail("second attempt writer unexpectedly acquired the lock")


def test_worker_uses_verified_snapshot_evaluator_not_mutable_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dirty live evaluator is never invoked after an immutable snapshot is selected."""

    archive = tmp_path / "snapshot.zip"
    archive.write_bytes(b"immutable evaluation source")
    archive_hash = tuner._canonical_sha256(archive)
    calls: list[str] = []

    def snapshot_evaluator(
        config: dict[str, float], duration_sec: float, seed: int
    ) -> dict[str, object]:
        calls.append("snapshot")
        return _synthetic_pid_result(0, tuple(config[name] for name in CANDIDATE_PARAMETER_ORDER))

    def mutable_worktree_evaluator(*_: object, **__: object) -> dict[str, object]:
        calls.append("worktree")
        raise AssertionError("mutable worktree evaluator must not execute")

    monkeypatch.setattr(tuner, "_load_snapshot_evaluator", lambda path, digest: snapshot_evaluator)
    monkeypatch.setattr(tuner, "evaluate_pid_config", mutable_worktree_evaluator)
    monkeypatch.setattr(tuner, "_WORKER_EVALUATOR", None)
    tuner._configure_worker_threads(archive, archive_hash)

    result = tuner._evaluate_index((0, enumerate_pid_candidates()[0], 30.0, 100))

    assert calls == ["snapshot"]
    assert result["candidate_index"] == 0


def _rewrite_snapshot_archive(
    archive_path: Path,
    *,
    mutation: str,
) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        entries = [
            (member.filename, archive.read(member))
            for member in archive.infolist()
        ]
    if mutation == "missing":
        entries = [entry for entry in entries if entry[0] != "experiments/__init__.py"]
    elif mutation == "extra":
        entries.append(("extra_snapshot_member.py", b"extra = True\n"))
    elif mutation == "duplicate":
        duplicate = next(entry for entry in entries if entry[0] == "experiments/__init__.py")
        entries.append(duplicate)
    elif mutation == "altered":
        entries = [
            (
                name,
                b"altered = True\n"
                if name == "experiments/circular_tracking/scripts/td3/__init__.py"
                else content,
            )
            for name, content in entries
        ]
    elif mutation == "placeholder":
        entries = [
            entry
            for entry in entries
            if entry[0] == "experiments/circular_tracking/scripts/td3/tune_hidden_pid.py"
        ]
    else:  # pragma: no cover - parametrized below
        raise AssertionError(f"unknown archive mutation: {mutation}")
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        for name, content in entries:
            archive.writestr(name, content)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "altered", "placeholder"])
def test_snapshot_loader_rejects_nonexact_git_blob_member_set(
    tmp_path: Path,
    mutation: str,
) -> None:
    """The snapshot archive itself is evidence and must exactly equal Git blobs."""

    attempt_root = tmp_path / "external_attempt"
    attempt_root.mkdir()
    evaluation_git_sha = tuner._git_sha()
    snapshot = tuner._write_source_snapshot(attempt_root, evaluation_git_sha)
    archive_path, _ = tuner._source_snapshot_record(
        attempt_root,
        snapshot,
        evaluation_git_sha,
    )
    _rewrite_snapshot_archive(archive_path, mutation=mutation)

    with pytest.raises(ValueError, match="source snapshot archive members"):
        tuner._load_snapshot_evaluator(archive_path, tuner._raw_sha256(archive_path))


def test_relative_attempt_root_is_rejected_before_any_resolution_or_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``..\\external`` cannot escape the repository-root resolver."""

    def must_not_resolve(_: Path) -> Path:
        raise AssertionError("relative attempt root must be rejected before resolution")

    monkeypatch.setattr(tuner, "_resolve_repo_path", must_not_resolve)
    with pytest.raises(ValueError, match="absolute"):
        tune_and_freeze(
            tmp_path / "frozen.json",
            attempt_root=Path("..") / "external_attempt",
        )


def test_incomplete_output_is_rejected_before_snapshot_or_worker_pool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An output beside RUNNING evidence cannot be mistaken for recovery state."""

    attempt_root = tmp_path / "external_attempt"
    attempt_root.mkdir()
    (attempt_root / "RUNNING.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "incomplete.json"
    output.write_text("{}", encoding="utf-8")

    def must_not_start(*_: object, **__: object) -> object:
        raise AssertionError("incomplete output must be rejected before snapshot or pool startup")

    monkeypatch.setattr(tuner, "_write_source_snapshot", must_not_start)
    monkeypatch.setattr(tuner, "ProcessPoolExecutor", must_not_start)
    with pytest.raises(FileExistsError, match="incomplete"):
        tune_and_freeze(output, attempt_root=attempt_root, command=["unit-test"])


def test_real_spawned_snapshot_worker_uses_snapshot_for_initial_and_deferred_imports(
    tmp_path: Path,
) -> None:
    """A Windows-style fresh Python worker must never touch a poisoned live package."""

    attempt_root = tmp_path / "external_attempt"
    attempt_root.mkdir()
    evaluation_git_sha = tuner._git_sha()
    snapshot = tuner._write_source_snapshot(attempt_root, evaluation_git_sha)
    archive_path, archive_hash = tuner._source_snapshot_record(
        attempt_root,
        snapshot,
        evaluation_git_sha,
    )
    poison_root = tmp_path / "poison"
    poison_init = poison_root / "experiments" / "__init__.py"
    poison_init.parent.mkdir(parents=True)
    poison_init.write_text(
        "raise RuntimeError('external-live-package-poison-imported')\n",
        encoding="utf-8",
    )
    repository_init = tuner._repo_root() / "experiments" / "__init__.py"
    repository_bytes_before = repository_init.read_bytes()

    evidence = tuner._run_snapshot_worker_probe(
        archive_path,
        archive_hash,
        poison_root=poison_root,
    )

    assert repository_init.read_bytes() == repository_bytes_before
    for key in ("tuner_module", "environment_module", "deferred_environment_module"):
        assert str(tuner._repo_root()) not in evidence[key]
        assert "hidden_pid_snapshot_" in evidence[key]


def test_main_records_effective_argv_without_starting_a_rollout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Programmatic CLI invocation must persist its supplied argv, not pytest argv."""

    captured: dict[str, object] = {}

    def no_rollout(
        output: Path,
        *,
        duration_sec: float,
        seed: int,
        workers: int,
        command: list[str],
        attempt_root: Path,
    ) -> dict[str, object]:
        captured.update(
            output=output,
            duration_sec=duration_sec,
            seed=seed,
            workers=workers,
            command=command,
            attempt_root=attempt_root,
        )
        return {"synthetic": True}

    monkeypatch.setattr(tuner, "tune_and_freeze", no_rollout)
    argv = [
        "--output",
        str(tmp_path / "metadata-only.json"),
        "--attempt-root",
        str(tmp_path / "external_attempt"),
    ]

    assert main(argv) == 0
    assert captured["command"] == [
        os.sys.executable,
        "-m",
        "experiments.circular_tracking.scripts.td3.tune_hidden_pid",
        *argv,
    ]


def test_source_snapshot_reuses_one_git_blob_batch_for_repeated_same_sha_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated evidence checks for one SHA must not restart Git per archive member."""

    evaluation_git_sha = tuner._git_sha()
    tuner._GIT_SNAPSHOT_CACHE.clear()
    real_run = tuner.subprocess.run
    git_calls: list[tuple[str, ...]] = []

    def counting_run(command: object, *args: object, **kwargs: object) -> object:
        if isinstance(command, list) and command and command[0] == "git":
            git_calls.append(tuple(str(part) for part in command))
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(tuner.subprocess, "run", counting_run)
    first_root = tmp_path / "first_attempt"
    second_root = tmp_path / "second_attempt"
    first_root.mkdir()
    second_root.mkdir()
    first = tuner._write_source_snapshot(first_root, evaluation_git_sha)
    tuner._source_snapshot_record(first_root, first, evaluation_git_sha)
    calls_after_first = list(git_calls)
    second = tuner._write_source_snapshot(second_root, evaluation_git_sha)
    tuner._source_snapshot_record(second_root, second, evaluation_git_sha)

    assert len(calls_after_first) <= 3
    assert git_calls == calls_after_first


def test_snapshot_loader_and_real_worker_cleanup_controlled_temp_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither parent loader nor isolated worker may leak snapshot extraction folders."""

    attempt_root = tmp_path / "external_attempt"
    attempt_root.mkdir()
    evaluation_git_sha = tuner._git_sha()
    snapshot = tuner._write_source_snapshot(attempt_root, evaluation_git_sha)
    archive_path, archive_hash = tuner._source_snapshot_record(
        attempt_root,
        snapshot,
        evaluation_git_sha,
    )
    controlled_temp = tmp_path / "controlled_temp"
    controlled_temp.mkdir()
    monkeypatch.setenv("TEMP", str(controlled_temp))
    monkeypatch.setenv("TMP", str(controlled_temp))

    evaluator = tuner._load_snapshot_evaluator(archive_path, archive_hash)
    assert callable(evaluator)
    tuner._run_snapshot_worker_probe(archive_path, archive_hash)

    assert not list(controlled_temp.glob("hidden_pid_snapshot_*"))


def test_snapshot_worker_deadline_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hung isolated worker must never be mistaken for a successful shard."""

    archive_path = tmp_path / "snapshot.zip"
    archive_path.write_bytes(b"deadline-test")

    def timed_out(*_: object, **kwargs: object) -> object:
        assert "timeout" in kwargs
        raise subprocess.TimeoutExpired(cmd="snapshot-worker", timeout=0.01)

    monkeypatch.setattr(tuner.subprocess, "run", timed_out)
    with pytest.raises(RuntimeError, match="deadline"):
        tuner._run_snapshot_worker_process(
            archive_path,
            tuner._raw_sha256(archive_path),
            {"kind": "probe"},
        )


def test_existing_frozen_output_recovers_only_a_strictly_bound_missing_done(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 18: recover the indexed DONE sentinel without touching source/grid/worker."""

    frozen_path, index_path = _write_synthetic_complete_evidence_chain(tmp_path)
    frozen_before = frozen_path.read_bytes()
    attempt_root = index_path.parent
    (attempt_root / "DONE.json").unlink()

    def must_not_start(*_: object, **__: object) -> object:
        raise AssertionError("strict missing-DONE recovery must precede snapshot/grid/worker startup")

    monkeypatch.setattr(tuner, "_write_source_snapshot", must_not_start)
    monkeypatch.setattr(tuner, "enumerate_pid_candidates", must_not_start)
    monkeypatch.setattr(tuner, "_run_snapshot_shards", must_not_start)
    recovered = tune_and_freeze(frozen_path, attempt_root=attempt_root, command=["ignored"])

    assert recovered == json.loads(frozen_path.read_text(encoding="utf-8"))
    assert frozen_path.read_bytes() == frozen_before
    assert (attempt_root / "DONE.json").is_file()


def test_missing_done_with_mismatched_frozen_payload_is_rejected_before_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 18 refuses recovery when the retained frozen bytes are not graph-bound."""

    frozen_path, index_path = _write_synthetic_complete_evidence_chain(tmp_path)
    attempt_root = index_path.parent
    (attempt_root / "DONE.json").unlink()
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    payload["winner_index"] = 1
    frozen_path.write_text(json.dumps(payload), encoding="utf-8")

    def must_not_start(*_: object, **__: object) -> object:
        raise AssertionError("mismatched missing-DONE recovery must never start work")

    monkeypatch.setattr(tuner, "_write_source_snapshot", must_not_start)
    monkeypatch.setattr(tuner, "enumerate_pid_candidates", must_not_start)
    monkeypatch.setattr(tuner, "_run_snapshot_shards", must_not_start)
    with pytest.raises(FileExistsError, match="incomplete"):
        tune_and_freeze(frozen_path, attempt_root=attempt_root, command=["ignored"])


@pytest.mark.parametrize("damage", ["candidate", "shard", "index"])
def test_recovery_validates_complete_graph_before_output_or_pool_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    """Bad completed evidence is rejected in memory instead of producing a config."""

    frozen_path, index_path = _write_synthetic_complete_evidence_chain(tmp_path)
    frozen_path.unlink()
    attempt_root = index_path.parent
    index = tuner._read_immutable_json(index_path)
    if damage == "candidate":
        Path(index["records"]["candidates"][0]["path"]).unlink()
    elif damage == "shard":
        Path(index["records"]["shards"][0]["path"]).unlink()
    else:
        index["scope"]["candidate_count"] = 80
        _immutable_rewrite(index_path, index)

    def pool_must_not_start(*_: object, **__: object) -> object:
        raise AssertionError("malformed completed evidence must not start a worker pool")

    def output_must_not_be_written(*_: object, **__: object) -> None:
        raise AssertionError("malformed completed evidence must not create an output config")

    monkeypatch.setattr(tuner, "ProcessPoolExecutor", pool_must_not_start)
    monkeypatch.setattr(tuner, "_write_new_frozen_payload", output_must_not_be_written)
    with pytest.raises(ValueError):
        tune_and_freeze(frozen_path, attempt_root=attempt_root, command=["unit-test"])
    assert not frozen_path.exists()


def test_only_known_repository_schema_two_is_classified_as_stale(tmp_path: Path) -> None:
    """A current schema-4 config must run acceptance rather than receive a stale xfail."""

    assert tuner._is_known_repository_stale_pid_config(tuner.DEFAULT_FROZEN_PATH)
    frozen_path, _ = _write_synthetic_complete_evidence_chain(tmp_path)
    assert not tuner._is_known_repository_stale_pid_config(frozen_path)


def test_evaluate_pid_config_converts_constructor_failure_to_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ConstructorFailure:
        CONTROL_FREQ_HZ = 48

        def __init__(self, **_: object) -> None:
            raise RuntimeError("constructor boom")

    monkeypatch.setattr(tuner, "HiddenDisturbanceCircularTD3Env", ConstructorFailure)
    metrics = evaluate_pid_config(config=dict(zip(CANDIDATE_PARAMETER_ORDER, enumerate_pid_candidates()[0])))
    assert metrics["failure"] is True
    assert metrics["accepted"] is False
    assert metrics["failure_reason"] == "exception:RuntimeError"


def test_evaluate_pid_config_close_error_does_not_obscure_primary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CloseFailureEnv:
        CONTROL_FREQ_HZ = 48
        MAX_RPM = 1000.0

        def __init__(self, **_: object) -> None:
            self.pos = [[0.3, 0.0, 1.0]]

        def reset(self, *, seed: int) -> tuple[object, dict[str, object]]:
            assert seed == 100
            return object(), {"reference_position": [0.3, 0.0, 1.0]}

        def step(self, _: object) -> tuple[object, float, bool, bool, dict[str, object]]:
            return object(), 0.0, True, False, {
                "reference_position": [0.3, 0.0, 1.0],
                "rpm": [500.0, 500.0, 500.0, 500.0],
                "failure_reason": "primary_failure",
            }

        def close(self) -> None:
            raise RuntimeError("close boom")

    monkeypatch.setattr(tuner, "HiddenDisturbanceCircularTD3Env", CloseFailureEnv)
    metrics = evaluate_pid_config(config=dict(zip(CANDIDATE_PARAMETER_ORDER, enumerate_pid_candidates()[0])))
    assert metrics["failure"] is True
    assert metrics["failure_reason"] == "primary_failure"
