"""Validation-only nominal PID grid search for the hidden-disturbance study.

The tuner deliberately contains no training code.  Candidates are evaluated in
fresh environments, while the parent process is the only writer of the frozen
configuration and performs deterministic ranking.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import types
from typing import Any, Callable, Iterable, Mapping, Sequence
import uuid
import zipfile

import numpy as np

from experiments.circular_tracking.rl_envs.hidden_disturbance_td3_env import (
    HiddenDisturbanceCircularTD3Env,
)


PROTOCOL_PATH = Path("experiments/circular_tracking/config/hidden_td3_protocol.json")
DEFAULT_FROZEN_PATH = Path("experiments/circular_tracking/config/hidden_pid_frozen.json")
ENV_SOURCE_PATH = Path(
    "experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py"
)
CANDIDATE_PARAMETER_ORDER = (
    "reference_velocity_gain",
    "pid_xy_p_scale",
    "pid_xy_d_scale",
    "pid_target_step_limit",
)
CANDIDATE_VALUES = {
    "reference_velocity_gain": (0.5, 0.75, 1.0),
    "pid_xy_p_scale": (0.5, 0.75, 1.0),
    "pid_xy_d_scale": (0.75, 1.0, 1.25),
    "pid_target_step_limit": (0.0, 0.05, 0.10),
}
EXPECTED_CANDIDATE_COUNT = 81
EVALUATION_DURATION_SEC = 30.0
EVALUATION_SEED = 100
VALIDATION_SEEDS = frozenset((EVALUATION_SEED,))
REQUIRED_COMPLETED_STEPS = 1440
WORKER_COUNT = 4
THREAD_LIMIT_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
ATTEMPT_SCHEMA_VERSION = 2
EVIDENCE_INDEX_SCHEMA_VERSION = 3
FROZEN_CONFIG_SCHEMA_VERSION = 4
PHYSICS_FREQUENCY_HZ = 240
PHYSICS_MODE = "PYB"
REFERENCE_PERIOD_SEC = 10.0
REFERENCE_RADIUS_M = 0.3
PHASE_RADIUS_EPS = 1e-9
FROZEN_GEOMETRY = {
    "radius_m": REFERENCE_RADIUS_M,
    "period_sec": REFERENCE_PERIOD_SEC,
    "height_m": 1.0,
}
FROZEN_SIMULATION = {
    "physics_mode": PHYSICS_MODE,
    "physics_frequency_hz": PHYSICS_FREQUENCY_HZ,
    "control_frequency_hz": HiddenDisturbanceCircularTD3Env.CONTROL_FREQ_HZ,
    "physics_substeps_per_control_step": 5,
}
FROZEN_CONTROL = {
    "controller_mode": "pid",
    "action_shape": [1],
    "action_bounds": [-1.0, 1.0],
    "disturbance_profile": "standard",
}
FROZEN_ACCEPTANCE = {
    "failure": False,
    "steady_position_rmse_strict_max_m": 0.10,
    "path_length_ratio_inclusive": [0.90, 1.10],
    "required_completed_steps": REQUIRED_COMPLETED_STEPS,
}
EVIDENCE_INDEX_FILENAME = "evidence_index.json"
SOURCE_SNAPSHOT_ARCHIVE_FILENAME = "evaluation_source_snapshot.zip"
SOURCE_SNAPSHOT_RECORD_FILENAME = "source_snapshot.json"
_ATTEMPT_LOCKS: set[Path] = set()
_WORKER_EVALUATOR: Callable[[Mapping[str, Any], float, int], dict[str, Any]] | None = None
_WORKER_SNAPSHOT_ROOT: Path | None = None
WORKER_DEADLINE_SEC = 900.0
_GIT_SNAPSHOT_CACHE: dict[str, tuple[tuple[str, ...], dict[str, bytes]]] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else _repo_root() / path


def _canonical_sha256(path: Path) -> str:
    data = _resolve_repo_path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _canonical_json_hash(payload: Any) -> str:
    data = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _canonical_json_file_hash(payload: Mapping[str, Any]) -> str:
    data = (
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _json_safe(value: Any) -> Any:
    """Convert NumPy values and nonfinite metrics into strict JSON values."""

    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _frozen_config_payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash the frozen payload while excluding its non-recursive self-hash."""

    normalized = _json_safe(payload)
    if not isinstance(normalized, dict):  # pragma: no cover - guarded by callers
        raise TypeError("frozen PID payload must be a mapping")
    copied = json.loads(json.dumps(normalized, ensure_ascii=False))
    evidence = copied.get("attempt_evidence")
    if isinstance(evidence, dict):
        evidence.pop("config_payload_sha256", None)
    return _canonical_json_hash(copied)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_repo_root()).as_posix()
    except ValueError:
        return str(resolved)


def _write_atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _serialized_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _commit_new_file(path: Path, content: bytes) -> bool:
    """Atomically create ``path`` without ever replacing an existing file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False
        return True
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive_attempt_lock(attempt_root: Path) -> Iterable[None]:
    """Serialize all evidence/config mutations for one external attempt root."""

    resolved = attempt_root.resolve()
    if resolved in _ATTEMPT_LOCKS:
        raise RuntimeError(f"PID attempt is already locked by this process: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    lock_path = resolved / ".pid_attempt.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(f"PID attempt is already locked: {resolved}") from exc
            unlock = lambda: msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover - Windows is the supported execution platform
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(f"PID attempt is already locked: {resolved}") from exc
            unlock = lambda: fcntl.flock(descriptor, fcntl.LOCK_UN)
        _ATTEMPT_LOCKS.add(resolved)
        try:
            yield
        finally:
            _ATTEMPT_LOCKS.remove(resolved)
            unlock()
    finally:
        os.close(descriptor)


def _immutable_stored_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    core = _json_safe(payload)
    if not isinstance(core, dict):  # pragma: no cover - guarded by call sites
        raise TypeError("immutable evidence payload must be a mapping")
    return {**core, "content_sha256": _canonical_json_hash(core)}


def _read_immutable_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"immutable evidence is not a JSON object: {path}")
    expected_hash = payload.pop("content_sha256", None)
    if not isinstance(expected_hash, str) or expected_hash != _canonical_json_hash(payload):
        raise ValueError(f"immutable evidence hash mismatch: {path}")
    payload["content_sha256"] = expected_hash
    return payload


def _write_immutable_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    stored = _immutable_stored_payload(payload)
    if not _commit_new_file(path, _serialized_json_bytes(stored)):
        existing = _read_immutable_json(path)
        if existing != stored:
            raise ValueError(f"refusing to overwrite immutable evidence: {path}")
        return existing
    return stored


def protocol_hash() -> str:
    """Return the LF-normalized hash of the frozen protocol."""

    return _canonical_sha256(PROTOCOL_PATH)


def _validate_validation_scope(duration_sec: float, seed: int) -> tuple[float, int]:
    """Reject all PID-tuning inputs outside the frozen validation protocol."""

    try:
        duration = float(duration_sec)
    except (TypeError, ValueError) as exc:
        raise ValueError("validation-only PID tuning requires a 30.0-second duration") from exc
    if not math.isfinite(duration) or duration != EVALUATION_DURATION_SEC:
        raise ValueError(
            "validation-only PID tuning requires a 30.0-second/1440-step duration"
        )
    if (
        isinstance(seed, bool)
        or not isinstance(seed, (int, np.integer))
        or int(seed) not in VALIDATION_SEEDS
    ):
        raise ValueError(
            "validation-only PID tuning requires the frozen seed 100"
        )
    expected_steps = int(round(duration * HiddenDisturbanceCircularTD3Env.CONTROL_FREQ_HZ))
    if expected_steps != REQUIRED_COMPLETED_STEPS:  # pragma: no cover - constant invariant
        raise RuntimeError("frozen PID duration does not equal 1440 control steps")
    return duration, int(seed)


def _validate_worker_count(workers: int) -> int:
    if isinstance(workers, bool) or not isinstance(workers, int) or workers != WORKER_COUNT:
        raise ValueError("the frozen PID tuner requires exactly four workers/shards")
    return WORKER_COUNT


def enumerate_pid_candidates() -> list[tuple[float, float, float, float]]:
    """Enumerate exactly 81 candidates, with the final dimension fastest."""

    values = [CANDIDATE_VALUES[name] for name in CANDIDATE_PARAMETER_ORDER]
    candidates = [tuple(float(value) for value in item) for item in itertools.product(*values)]
    if len(candidates) != EXPECTED_CANDIDATE_COUNT or len(set(candidates)) != EXPECTED_CANDIDATE_COUNT:
        raise RuntimeError("PID candidate grid is not the frozen 81-point grid")
    return candidates


def candidate_to_config(candidate: Sequence[float]) -> dict[str, float]:
    if len(candidate) != len(CANDIDATE_PARAMETER_ORDER):
        raise ValueError("candidate has the wrong number of parameters")
    return {
        name: float(value)
        for name, value in zip(CANDIDATE_PARAMETER_ORDER, candidate)
    }


def candidate_from_index(index: int) -> tuple[float, float, float, float]:
    if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
        raise TypeError("candidate index must be an integer")
    candidates = enumerate_pid_candidates()
    if index < 0 or index >= len(candidates):
        raise IndexError("candidate index is outside the frozen grid")
    return candidates[int(index)]


def candidate_index(candidate: Sequence[float]) -> int:
    normalized = tuple(float(value) for value in candidate)
    try:
        return enumerate_pid_candidates().index(normalized)
    except ValueError as exc:
        raise ValueError("candidate is not in the frozen grid") from exc


def split_candidate_shards(
    candidates: Sequence[Sequence[float]] | None = None,
    shard_count: int = 4,
) -> list[list[tuple[int, tuple[float, float, float, float]]]]:
    """Partition the one canonical 81-point grid into four fixed shards."""

    _validate_worker_count(shard_count)
    source = [tuple(float(value) for value in candidate) for candidate in (
        candidates if candidates is not None else enumerate_pid_candidates()
    )]
    canonical = enumerate_pid_candidates()
    if source != canonical:
        raise ValueError("the frozen tuner accepts only the canonical ordered 81-point grid")
    shards: list[list[tuple[int, tuple[float, float, float, float]]]] = [
        [] for _ in range(WORKER_COUNT)
    ]
    for index, candidate in enumerate(source):
        shards[index % WORKER_COUNT].append((index, candidate))
    if [len(shard) for shard in shards] != [21, 20, 20, 20]:  # pragma: no cover - grid invariant
        raise RuntimeError("canonical PID grid did not partition into 21/20/20/20")
    return shards


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def acceptance_passes(metrics: Mapping[str, Any]) -> bool:
    """Return whether a rollout satisfies every pre-registered criterion."""

    if bool(metrics.get("failure", True)):
        return False
    completed_steps = metrics.get("completed_steps")
    if isinstance(completed_steps, (bool, np.bool_)):
        return False
    if isinstance(completed_steps, (int, np.integer)):
        completed_is_exact = int(completed_steps) == REQUIRED_COMPLETED_STEPS
    elif isinstance(completed_steps, (float, np.floating)):
        completed_is_exact = (
            math.isfinite(float(completed_steps))
            and float(completed_steps) == float(REQUIRED_COMPLETED_STEPS)
        )
    else:
        completed_is_exact = False
    if not completed_is_exact:
        return False
    if not _finite(metrics.get("steady_position_rmse")):
        return False
    if not float(metrics["steady_position_rmse"]) < 0.10:
        return False
    path_ratio = metrics.get("path_length_ratio")
    if not _finite(path_ratio) or not 0.90 <= float(path_ratio) <= 1.10:
        return False
    for field in ("mean_phase_error", "rotor_saturation_rate", "control_energy"):
        if not _finite(metrics.get(field)):
            return False
    return True


def _wrapped_phase_error(actual: float, reference: float) -> float:
    return abs((actual - reference + math.pi) % (2.0 * math.pi) - math.pi)


def _extract_parameters(config: Mapping[str, Any]) -> dict[str, float]:
    source = config.get("parameters", config)
    if not isinstance(source, Mapping):
        raise TypeError("PID config parameters must be a mapping")
    missing = [name for name in CANDIDATE_PARAMETER_ORDER if name not in source]
    if missing:
        raise ValueError(f"PID config is missing parameters: {missing}")
    return {name: float(source[name]) for name in CANDIDATE_PARAMETER_ORDER}


def evaluate_pid_config(
    config: Mapping[str, Any] | None = None,
    duration_sec: float = EVALUATION_DURATION_SEC,
    seed: int = EVALUATION_SEED,
) -> dict[str, Any]:
    """Evaluate one PID candidate on the nominal validation profile.

    The environment is constructed and closed inside this call.  The PID
    controller is therefore fresh for every candidate and the environment's
    single cached PID update is used by each control step.
    """

    duration, validation_seed = _validate_validation_scope(duration_sec, seed)
    parameters = _extract_parameters(
        load_frozen_pid_config() if config is None else config
    )
    expected_steps = REQUIRED_COMPLETED_STEPS
    metrics: dict[str, Any] = {
        "failure": True,
        "failure_reason": "not_started",
        "completed_steps": 0,
        "duration_sec": duration,
        "seed": validation_seed,
        **parameters,
    }
    positions: list[np.ndarray] = []
    references: list[np.ndarray] = []
    phase_errors: list[float] = []
    rpms: list[np.ndarray] = []
    env: Any | None = None
    try:
        env = HiddenDisturbanceCircularTD3Env(
            controller_mode="pid",
            disturbance_profile="standard",
            rollout_duration_sec=duration,
            **parameters,
            gui=False,
        )
        _, reset_info = env.reset(seed=validation_seed)
        positions.append(np.asarray(env.pos[0], dtype=np.float64).copy())
        references.append(np.asarray(reset_info["reference_position"], dtype=np.float64).copy())
        terminated = truncated = False
        while not (terminated or truncated):
            _, _, terminated, truncated, info = env.step(np.zeros(1, dtype=np.float32))
            positions.append(np.asarray(env.pos[0], dtype=np.float64).copy())
            references.append(np.asarray(info["reference_position"], dtype=np.float64).copy())
            rpm = np.asarray(info["rpm"], dtype=np.float64).reshape(-1)
            rpms.append(rpm.copy())
            if rpm.size != 4 or not np.all(np.isfinite(rpm)) or np.any(rpm < 0.0) or np.any(rpm > env.MAX_RPM):
                metrics["failure_reason"] = "motor_metric_invalid"
                terminated = True
                break
            actual = positions[-1]
            reference = references[-1]
            actual_radius = float(np.linalg.norm(actual[:2]))
            reference_radius = float(np.linalg.norm(reference[:2]))
            if not math.isfinite(actual_radius) or actual_radius <= PHASE_RADIUS_EPS:
                metrics["failure_reason"] = "invalid_phase_radius"
                terminated = True
                break
            if reference_radius <= PHASE_RADIUS_EPS:
                metrics["failure_reason"] = "invalid_reference_phase_radius"
                terminated = True
                break
            phase_errors.append(
                _wrapped_phase_error(
                    math.atan2(float(actual[1]), float(actual[0])),
                    math.atan2(float(reference[1]), float(reference[0])),
                )
            )
            metrics["completed_steps"] = int(metrics["completed_steps"]) + 1

        metrics["completed_steps"] = len(rpms)
        metrics["terminated"] = bool(terminated)
        metrics["truncated"] = bool(truncated)
        if terminated:
            metrics["failure_reason"] = str(info.get("failure_reason", metrics["failure_reason"]))
        elif len(rpms) != expected_steps or not truncated:
            metrics["failure_reason"] = "incomplete_horizon"
        else:
            metrics["failure"] = False
            metrics["failure_reason"] = ""

        position_array = np.asarray(positions, dtype=np.float64)
        reference_array = np.asarray(references, dtype=np.float64)
        if position_array.shape != reference_array.shape or not np.all(np.isfinite(position_array)) or not np.all(np.isfinite(reference_array)):
            metrics["failure"] = True
            metrics["failure_reason"] = "nonfinite_trajectory"
        error = position_array - reference_array
        times = np.arange(position_array.shape[0], dtype=np.float64) / float(env.CONTROL_FREQ_HZ)
        steady_mask = times >= REFERENCE_PERIOD_SEC
        # A failed or incomplete rollout never receives a steady-window
        # fallback metric.  This keeps an early termination from appearing
        # artificially good merely because its prefix is short.
        if metrics.get("failure", True) or len(rpms) != expected_steps or not np.any(steady_mask):
            metrics["steady_position_rmse"] = float("nan")
        else:
            steady_error = error[steady_mask]
            metrics["steady_position_rmse"] = float(np.sqrt(np.mean(np.sum(steady_error * steady_error, axis=1), dtype=np.float64)))

        xy_positions = position_array[:, :2]
        if len(xy_positions) >= 2:
            segments = np.linalg.norm(np.diff(xy_positions, axis=0), axis=1)
            actual_path = math.fsum(float(item) for item in segments)
        else:
            actual_path = float("nan")
        expected_path = 2.0 * math.pi * REFERENCE_RADIUS_M * duration / REFERENCE_PERIOD_SEC
        metrics["path_length_m"] = float(actual_path)
        metrics["path_length_ratio"] = float(actual_path / expected_path) if math.isfinite(actual_path) else float("nan")
        metrics["mean_phase_error"] = float(math.fsum(phase_errors) / len(phase_errors)) if phase_errors else float("nan")
        rpm_array = np.asarray(rpms, dtype=np.float64)
        if rpm_array.size:
            metrics["rotor_saturation_rate"] = float(np.mean((rpm_array <= 0.0) | (rpm_array >= env.MAX_RPM)))
            metrics["control_energy"] = float(np.mean((rpm_array / env.MAX_RPM) ** 2))
            metrics["max_rpm"] = float(np.max(rpm_array))
        else:
            metrics["rotor_saturation_rate"] = float("nan")
            metrics["control_energy"] = float("nan")
            metrics["max_rpm"] = float("nan")
        if not acceptance_passes(metrics):
            metrics["failure"] = True
            if not metrics["failure_reason"]:
                metrics["failure_reason"] = "acceptance_failed"
        metrics["accepted"] = acceptance_passes(metrics)
        return metrics
    except Exception as exc:
        metrics["failure"] = True
        metrics["accepted"] = False
        metrics["failure_reason"] = f"exception:{type(exc).__name__}"
        return metrics
    finally:
        if env is not None:
            try:
                env.close()
            except Exception as exc:
                # Cleanup must neither leak nor conceal a prior rollout error.
                if not metrics.get("failure", True):
                    metrics["failure"] = True
                    metrics["accepted"] = False
                    metrics["failure_reason"] = f"exception:close:{type(exc).__name__}"


def rank_candidates(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return the deterministic ranking of the accepted candidate pool.

    Failed, nonfinite, incomplete, or otherwise rejected rows are deliberately
    excluded rather than allowed to influence the winner or its tie-break.
    """

    normalized: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        # Candidate records are evidence, not authority: acceptance is always
        # recomputed from the frozen failure/finite/1440-step/strict metrics.
        accepted = acceptance_passes(copied)
        copied["accepted"] = accepted
        if accepted:
            normalized.append(copied)

    def key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            float(row["steady_position_rmse"]),
            abs(float(row["mean_phase_error"])),
            abs(float(row["path_length_ratio"]) - 1.0),
            int(row["candidate_index"]),
        )

    return sorted(normalized, key=key)


def _evaluate_index(task: tuple[int, tuple[float, float, float, float], float, int]) -> dict[str, Any]:
    index, candidate, duration, seed = task
    evaluator = _WORKER_EVALUATOR or evaluate_pid_config
    result = evaluator(
        config=candidate_to_config(candidate),
        duration_sec=duration,
        seed=seed,
    )
    result["candidate_index"] = index
    result["candidate"] = list(candidate)
    return result


def _evaluate_shard(
    tasks: Sequence[tuple[int, tuple[float, float, float, float], float, int]],
) -> list[dict[str, Any]]:
    """Evaluate one fixed shard without writing shared attempt state."""

    return [_evaluate_index(task) for task in tasks]


@contextmanager
def _single_thread_worker_environment() -> Iterable[None]:
    """Give every spawned PID worker the frozen one-thread BLAS environment."""

    previous = {name: os.environ.get(name) for name in THREAD_LIMIT_ENV}
    for name in THREAD_LIMIT_ENV:
        os.environ[name] = "1"
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _configure_worker_threads(
    snapshot_archive: Path | None = None,
    snapshot_archive_sha256: str | None = None,
) -> None:
    """Defend the thread cap and bind each worker to one immutable source archive."""

    global _WORKER_EVALUATOR, _WORKER_SNAPSHOT_ROOT
    for name in THREAD_LIMIT_ENV:
        os.environ[name] = "1"
    if snapshot_archive is None and snapshot_archive_sha256 is None:
        _WORKER_EVALUATOR = None
        _WORKER_SNAPSHOT_ROOT = None
        return
    if snapshot_archive is None or not isinstance(snapshot_archive_sha256, str):
        raise ValueError("PID worker requires a complete immutable source snapshot")
    _WORKER_EVALUATOR = _load_snapshot_evaluator(snapshot_archive, snapshot_archive_sha256)
    _WORKER_SNAPSHOT_ROOT = snapshot_archive.parent


def _attempt_manifest(
    candidates: Sequence[tuple[float, float, float, float]],
    *,
    duration_sec: float,
    seed: int,
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "controller": "pid",
        "profile": "standard",
        "protocol_hash": protocol_hash(),
        "evaluation_duration_sec": duration_sec,
        "evaluation_seed": seed,
        "worker_count": WORKER_COUNT,
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "candidate_parameter_order": list(CANDIDATE_PARAMETER_ORDER),
        "candidate_values": {name: list(values) for name, values in CANDIDATE_VALUES.items()},
        "candidates": [
            {
                "candidate_index": index,
                "candidate": list(candidate),
                "parameters": candidate_to_config(candidate),
                "shard_index": index % WORKER_COUNT,
            }
            for index, candidate in enumerate(candidates)
        ],
    }


def _prepare_attempt(
    attempt_root: Path,
    manifest: Mapping[str, Any],
    *,
    command: Sequence[str],
    evaluation_git_sha: str,
    source_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Create or validate an interrupted immutable attempt directory."""

    attempt_root.mkdir(parents=True, exist_ok=True)
    done_path = attempt_root / "DONE.json"
    if done_path.exists():
        _read_immutable_json(done_path)
        raise FileExistsError(
            f"PID tuning attempt is complete: {attempt_root}; use a new attempt only for infrastructure recovery"
        )

    running_path = attempt_root / "RUNNING.json"
    if not isinstance(source_snapshot.get("content_sha256"), str):
        raise ValueError("PID source snapshot record has no immutable content hash")
    expected_running = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "attempt_name": attempt_root.name,
        "protocol_hash": manifest["protocol_hash"],
        "candidate_manifest_sha256": _canonical_json_hash(manifest),
        "evaluation_git_sha": evaluation_git_sha,
        "source_snapshot_sha256": source_snapshot["content_sha256"],
        "command": list(command),
        "thread_limits": {name: "1" for name in THREAD_LIMIT_ENV},
        "worker_count": WORKER_COUNT,
    }
    if running_path.exists():
        running = _read_immutable_json(running_path)
        for key, expected_value in expected_running.items():
            if running.get(key) != expected_value:
                raise ValueError(f"incompatible immutable RUNNING evidence: {running_path}")
    else:
        _write_immutable_json(
            running_path,
            {**expected_running, "started_at_utc": _utc_timestamp()},
        )

    manifest_path = attempt_root / "candidate_manifest.json"
    stored_manifest = _write_immutable_json(manifest_path, manifest)
    if stored_manifest.get("content_sha256") != _canonical_json_hash(manifest):
        raise ValueError("candidate manifest hash does not match the frozen grid")
    return stored_manifest


def _candidate_record_path(attempt_root: Path, index: int) -> Path:
    return attempt_root / "candidates" / f"candidate_{index:03d}.json"


def _candidate_record(
    *,
    index: int,
    candidate: tuple[float, float, float, float],
    duration_sec: float,
    seed: int,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "protocol_hash": protocol_hash(),
        "candidate_index": index,
        "candidate": list(candidate),
        "parameters": candidate_to_config(candidate),
        "evaluation_duration_sec": duration_sec,
        "evaluation_seed": seed,
        "result": dict(result),
    }


def _result_from_candidate_record(
    record: Mapping[str, Any],
    *,
    index: int,
    candidate: tuple[float, float, float, float],
    duration_sec: float,
    seed: int,
) -> dict[str, Any]:
    expected = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "protocol_hash": protocol_hash(),
        "candidate_index": index,
        "candidate": list(candidate),
        "parameters": candidate_to_config(candidate),
        "evaluation_duration_sec": duration_sec,
        "evaluation_seed": seed,
    }
    for key, expected_value in expected.items():
        if record.get(key) != expected_value:
            raise ValueError(f"candidate evidence is incompatible for index {index}")
    result = record.get("result")
    if not isinstance(result, Mapping):
        raise ValueError(f"candidate evidence has no result for index {index}")
    row = dict(result)
    # The grid manifest, not an evaluator-provided duplicate, is authoritative
    # for the candidate parameters carried into central ranking/freezing.
    row.update(candidate_to_config(candidate))
    row["candidate_index"] = index
    row["candidate"] = list(candidate)
    return row


def _load_completed_candidate_rows(
    attempt_root: Path,
    candidates: Sequence[tuple[float, float, float, float]],
    *,
    duration_sec: float,
    seed: int,
) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates):
        path = _candidate_record_path(attempt_root, index)
        if path.exists():
            rows[index] = _result_from_candidate_record(
                _read_immutable_json(path),
                index=index,
                candidate=candidate,
                duration_sec=duration_sec,
                seed=seed,
            )
    return rows


def _store_shard_results(
    attempt_root: Path,
    shard: Sequence[tuple[int, tuple[float, float, float, float]]],
    produced: Sequence[Mapping[str, Any]],
    rows: dict[int, dict[str, Any]],
    *,
    duration_sec: float,
    seed: int,
) -> None:
    expected_by_index = {index: candidate for index, candidate in shard}
    for result in produced:
        index = result.get("candidate_index")
        if isinstance(index, bool) or not isinstance(index, int) or index not in expected_by_index:
            raise ValueError("worker returned a candidate outside its assigned shard")
        candidate = expected_by_index[index]
        if result.get("candidate") != list(candidate):
            raise ValueError(f"worker returned mismatched parameters for candidate {index}")
        row = dict(result)
        row.pop("candidate_index", None)
        row.pop("candidate", None)
        record = _write_immutable_json(
            _candidate_record_path(attempt_root, index),
            _candidate_record(
                index=index,
                candidate=candidate,
                duration_sec=duration_sec,
                seed=seed,
                result=row,
            ),
        )
        rows[index] = _result_from_candidate_record(
            record,
            index=index,
            candidate=candidate,
            duration_sec=duration_sec,
            seed=seed,
        )
    missing = sorted(set(expected_by_index) - set(rows))
    if missing:
        raise RuntimeError(f"worker did not return all assigned candidates: {missing}")


def _write_shard_record(
    attempt_root: Path,
    shard_index: int,
    shard: Sequence[tuple[int, tuple[float, float, float, float]]],
) -> dict[str, Any]:
    records = [_read_immutable_json(_candidate_record_path(attempt_root, index)) for index, _ in shard]
    return _write_immutable_json(
        attempt_root / "shards" / f"shard_{shard_index:02d}.json",
        {
            "schema_version": ATTEMPT_SCHEMA_VERSION,
            "shard_index": shard_index,
            "candidate_indices": [index for index, _ in shard],
            "candidate_record_hashes": [record["content_sha256"] for record in records],
        },
    )


def _write_coverage_record(
    attempt_root: Path,
    rows: Mapping[int, Mapping[str, Any]],
    shards: Sequence[Sequence[tuple[int, tuple[float, float, float, float]]]],
) -> dict[str, Any]:
    expected_indices = list(range(EXPECTED_CANDIDATE_COUNT))
    actual_indices = sorted(rows)
    shard_indices = [index for shard in shards for index, _ in shard]
    coverage = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "expected_candidate_indices": expected_indices,
        "actual_candidate_indices": actual_indices,
        "missing_candidate_indices": sorted(set(expected_indices) - set(actual_indices)),
        "duplicate_candidate_indices": sorted(
            index for index in set(shard_indices) if shard_indices.count(index) != 1
        ),
        "shard_sizes": [len(shard) for shard in shards],
        "complete": actual_indices == expected_indices and [len(shard) for shard in shards] == [21, 20, 20, 20],
    }
    if not coverage["complete"]:
        raise RuntimeError("PID attempt coverage is incomplete")
    return _write_immutable_json(attempt_root / "coverage.json", coverage)


def _package_versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    names = ("numpy", "gymnasium", "pybullet", "torch", "stable-baselines3", "control")
    result: dict[str, str] = {}
    for name in names:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "unavailable"
    return result


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"frozen PID {label} must be a mapping")
    return value


def _validate_evaluation_git_sha(value: Any) -> None:
    if not isinstance(value, str) or len(value) != 40:
        raise ValueError("frozen PID evaluation Git SHA is invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("frozen PID evaluation Git SHA is invalid") from exc
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{value}^{{commit}}"],
        cwd=_repo_root(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("frozen PID evaluation Git SHA does not resolve to a commit")


def _require_external_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"frozen PID provenance {label} path is invalid")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"frozen PID provenance {label} path must be absolute")
    resolved = path.resolve()
    try:
        resolved.relative_to(_repo_root())
    except ValueError:
        return resolved
    raise ValueError(f"frozen PID provenance {label} path must be external to the repository")


def _artifact_provenance_entry(path: Path, stored: Mapping[str, Any] | None = None) -> dict[str, str]:
    record = dict(stored) if stored is not None else _read_immutable_json(path)
    content_hash = record.get("content_sha256")
    if not isinstance(content_hash, str):  # pragma: no cover - guarded by immutable reader
        raise ValueError(f"immutable evidence has no content hash: {path}")
    file_hash = _canonical_sha256(path) if path.exists() else _canonical_json_file_hash(record)
    return {
        "path": str(path.resolve()),
        "content_sha256": content_hash,
        "file_sha256": file_hash,
    }


def _source_identity(path: Path, evaluation_git_sha: str) -> dict[str, str]:
    """Bind the evaluated Git blob to the identical current working-tree file."""

    resolved = _resolve_repo_path(path).resolve()
    try:
        relative_path = resolved.relative_to(_repo_root()).as_posix()
    except ValueError as exc:  # pragma: no cover - fixed source paths below
        raise ValueError(f"PID source identity path is outside the repository: {resolved}") from exc
    result = subprocess.run(
        ["git", "show", f"{evaluation_git_sha}:{relative_path}"],
        cwd=_repo_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            f"PID source identity is unavailable at evaluation Git SHA: {relative_path}"
        )
    git_blob_digest = hashlib.sha256(
        result.stdout.replace(b"\r\n", b"\n")
    ).hexdigest()
    working_tree_digest = _canonical_sha256(resolved)
    if working_tree_digest != git_blob_digest:
        raise ValueError(
            "PID working-tree source does not match the evaluation Git blob: "
            f"{relative_path}"
        )
    return {
        "path": str(resolved),
        "git_blob_sha256": git_blob_digest,
        "working_tree_sha256": working_tree_digest,
    }


def _source_identities(evaluation_git_sha: str) -> dict[str, dict[str, str]]:
    """Return all source identities after proving their clean Git binding."""

    return {
        "protocol": _source_identity(PROTOCOL_PATH, evaluation_git_sha),
        "environment": _source_identity(ENV_SOURCE_PATH, evaluation_git_sha),
        "tuner": _source_identity(Path(__file__), evaluation_git_sha),
    }


def _raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_snapshot_source(evaluation_git_sha: str) -> tuple[tuple[str, ...], dict[str, bytes]]:
    """Read the complete snapshot tree and all its blobs once per immutable SHA."""

    cached = _GIT_SNAPSHOT_CACHE.get(evaluation_git_sha)
    if cached is not None:
        return cached
    tree = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            evaluation_git_sha,
            "--",
            "experiments/__init__.py",
            "experiments/circular_tracking",
            "gym_pybullet_drones",
        ],
        cwd=_repo_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tree.returncode != 0:
        raise ValueError("PID source snapshot is unavailable at the evaluation Git SHA")
    paths: list[str] = []
    for raw_path in tree.stdout.decode("utf-8").splitlines():
        if raw_path.startswith("gym_pybullet_drones/"):
            paths.append(raw_path)
        elif raw_path == "experiments/__init__.py" or (
            raw_path.startswith("experiments/circular_tracking/")
            and (
                raw_path.endswith(".py")
                or raw_path == str(PROTOCOL_PATH).replace("\\", "/")
            )
        ):
            paths.append(raw_path)
    ordered_paths = tuple(sorted(paths))
    evaluator_path = str(Path(__file__).resolve().relative_to(_repo_root())).replace("\\", "/")
    if evaluator_path not in ordered_paths:
        raise ValueError("PID source snapshot does not contain its evaluator module")
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=_repo_root(),
        input="".join(f"{evaluation_git_sha}:{path}\n" for path in ordered_paths).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if batch.returncode != 0:
        raise ValueError("PID source snapshot Git blob batch failed")
    cursor = 0
    blobs: dict[str, bytes] = {}
    for path in ordered_paths:
        newline = batch.stdout.find(b"\n", cursor)
        if newline < 0:
            raise ValueError(f"PID source snapshot is missing Git blob: {path}")
        header = batch.stdout[cursor:newline].split()
        cursor = newline + 1
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError(f"PID source snapshot is missing Git blob: {path}")
        try:
            size = int(header[2])
        except ValueError as exc:
            raise ValueError(f"PID source snapshot Git blob size is invalid: {path}") from exc
        blob = batch.stdout[cursor:cursor + size]
        if len(blob) != size or cursor + size >= len(batch.stdout) or batch.stdout[cursor + size:cursor + size + 1] != b"\n":
            raise ValueError(f"PID source snapshot Git blob is truncated: {path}")
        blobs[path] = blob
        cursor += size + 1
    if cursor != len(batch.stdout):
        raise ValueError("PID source snapshot Git blob batch has trailing data")
    cached = (ordered_paths, blobs)
    _GIT_SNAPSHOT_CACHE[evaluation_git_sha] = cached
    return cached


def _snapshot_relative_paths(evaluation_git_sha: str) -> list[str]:
    return list(_git_snapshot_source(evaluation_git_sha)[0])


def _git_blob_bytes(evaluation_git_sha: str, relative_path: str) -> bytes:
    try:
        return _git_snapshot_source(evaluation_git_sha)[1][relative_path]
    except KeyError as exc:
        raise ValueError(f"PID source snapshot is missing Git blob: {relative_path}") from exc


def _write_source_snapshot(attempt_root: Path, evaluation_git_sha: str) -> dict[str, Any]:
    """Materialize a deterministic, immutable worker source archive from Git blobs."""

    archive_path = attempt_root / SOURCE_SNAPSHOT_ARCHIVE_FILENAME
    relative_paths = _snapshot_relative_paths(evaluation_git_sha)
    temporary = archive_path.with_name(
        f".{archive_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with zipfile.ZipFile(temporary, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative_path in relative_paths:
                info = zipfile.ZipInfo(relative_path, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, _git_blob_bytes(evaluation_git_sha, relative_path))
        expected_archive_hash = _raw_sha256(temporary)
        if not _commit_new_file(archive_path, temporary.read_bytes()):
            if _raw_sha256(archive_path) != expected_archive_hash:
                raise ValueError("immutable PID source snapshot conflicts with the evaluation Git SHA")
    finally:
        if temporary.exists():
            temporary.unlink()
    return _write_immutable_json(
        attempt_root / SOURCE_SNAPSHOT_RECORD_FILENAME,
        {
            "schema_version": ATTEMPT_SCHEMA_VERSION,
            "evaluation_git_sha": evaluation_git_sha,
            "archive_path": str(archive_path.resolve()),
            "archive_sha256": expected_archive_hash,
            "included_paths_sha256": _canonical_json_hash(relative_paths),
        },
    )


def _snapshot_archive_evaluation_git_sha(archive_path: Path) -> str:
    """Read just enough immutable sidecar metadata to locate the Git commit."""

    record = _read_immutable_json(archive_path.parent / SOURCE_SNAPSHOT_RECORD_FILENAME)
    if (
        record.get("schema_version") != ATTEMPT_SCHEMA_VERSION
        or record.get("archive_path") != str(archive_path.resolve())
    ):
        raise ValueError("PID source snapshot archive metadata is invalid")
    evaluation_git_sha = record.get("evaluation_git_sha")
    _validate_evaluation_git_sha(evaluation_git_sha)
    return str(evaluation_git_sha)


def _validate_source_snapshot_archive(
    archive_path: Path,
    *,
    evaluation_git_sha: str,
    expected_archive_sha256: str | None = None,
) -> None:
    """Prove an archive has exactly the ordered Git-blob member set it claims."""

    if (
        expected_archive_sha256 is not None
        and _raw_sha256(archive_path) != expected_archive_sha256
    ):
        raise ValueError("PID source snapshot archive hash is invalid")
    if not zipfile.is_zipfile(archive_path):
        raise ValueError("PID source snapshot archive is invalid")
    expected_paths = _snapshot_relative_paths(evaluation_git_sha)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        member_names = [member.filename for member in members]
        if (
            len(member_names) != len(set(member_names))
            or member_names != expected_paths
        ):
            raise ValueError("PID source snapshot archive members do not exactly match Git")
        for member in members:
            if archive.read(member) != _git_blob_bytes(evaluation_git_sha, member.filename):
                raise ValueError("PID source snapshot archive members do not match Git blobs")


def _load_snapshot_evaluator(
    archive_path: Path,
    archive_sha256: str,
) -> Callable[[Mapping[str, Any], float, int], dict[str, Any]]:
    """Load the evaluator from a verified extracted Git snapshot, never the worktree."""

    resolved_archive = archive_path.resolve()
    if not resolved_archive.is_file() or _raw_sha256(resolved_archive) != archive_sha256:
        raise ValueError("PID worker source snapshot hash is invalid")
    evaluation_git_sha = _snapshot_archive_evaluation_git_sha(resolved_archive)
    _validate_source_snapshot_archive(
        resolved_archive,
        evaluation_git_sha=evaluation_git_sha,
        expected_archive_sha256=archive_sha256,
    )
    with tempfile.TemporaryDirectory(prefix="hidden_pid_snapshot_") as extraction_directory:
        extraction_root = Path(extraction_directory)
        with zipfile.ZipFile(resolved_archive) as archive:
            members = archive.namelist()
            if any(Path(name).is_absolute() or ".." in Path(name).parts for name in members):
                raise ValueError("PID worker source snapshot archive contains an unsafe path")
            archive.extractall(extraction_root)
        relative_tuner = Path(__file__).resolve().relative_to(_repo_root())
        snapshot_tuner = extraction_root / relative_tuner
        if not snapshot_tuner.is_file():
            raise ValueError("PID worker source snapshot lacks the evaluator module")

        prior_modules = {
            name: module
            for name, module in list(sys.modules.items())
            if name != __name__
            and (name == "experiments" or name.startswith("experiments.") or name == "gym_pybullet_drones" or name.startswith("gym_pybullet_drones."))
        }
        for name in prior_modules:
            sys.modules.pop(name, None)
        sys.path.insert(0, str(extraction_root))
        module_name = f"_hidden_pid_snapshot_{archive_sha256[:16]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, snapshot_tuner)
            if spec is None or spec.loader is None:  # pragma: no cover - guarded by file check
                raise ValueError("PID worker source snapshot cannot load evaluator")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            evaluator = getattr(module, "evaluate_pid_config", None)
            if not callable(evaluator):
                raise ValueError("PID worker source snapshot lacks evaluate_pid_config")
            return evaluator
        finally:
            sys.path.remove(str(extraction_root))
            sys.modules.pop(module_name, None)
            for name in list(sys.modules):
                if name != __name__ and (
                    name == "experiments"
                    or name.startswith("experiments.")
                    or name == "gym_pybullet_drones"
                    or name.startswith("gym_pybullet_drones.")
                ):
                    sys.modules.pop(name, None)
            sys.modules.update(prior_modules)


_SNAPSHOT_WORKER_BOOTSTRAP = """
import hashlib
import shutil
import sys
import tempfile
import zipfile

archive_path, expected_hash, request_path, response_path, poison_root = sys.argv[1:6]
with open(archive_path, "rb") as source_archive:
    actual_hash = hashlib.sha256(source_archive.read()).hexdigest()
if actual_hash != expected_hash:
    raise SystemExit("PID worker source snapshot hash is invalid")
extraction_root = tempfile.mkdtemp(prefix="hidden_pid_snapshot_")
try:
    with zipfile.ZipFile(archive_path) as archive:
        member_names = archive.namelist()
        if any(name.startswith(("/", "\\\\")) or ".." in name.split("/") for name in member_names):
            raise SystemExit("PID worker source snapshot contains an unsafe path")
        archive.extractall(extraction_root)
    sys.path.insert(0, extraction_root)
    if poison_root:
        sys.path.insert(1, poison_root)
    from experiments.circular_tracking.scripts.td3.tune_hidden_pid import _snapshot_worker_entry
    _snapshot_worker_entry(request_path, response_path)
finally:
    if extraction_root in sys.path:
        sys.path.remove(extraction_root)
    shutil.rmtree(extraction_root, ignore_errors=True)
"""


def _snapshot_worker_entry(request_path: str, response_path: str) -> None:
    """Execute a worker request after the bootstrap has installed snapshot-only imports."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    if not isinstance(request, Mapping):
        raise ValueError("PID snapshot worker request is invalid")
    for name in THREAD_LIMIT_ENV:
        os.environ[name] = "1"
    kind = request.get("kind")
    if kind == "probe":
        import importlib

        environment = importlib.import_module(
            "experiments.circular_tracking.rl_envs.hidden_disturbance_td3_env"
        )
        deferred_environment = importlib.reload(environment)
        response: Mapping[str, Any] = {
            "tuner_module": str(Path(__file__).resolve()),
            "environment_module": str(Path(environment.__file__).resolve()),
            "deferred_environment_module": str(Path(deferred_environment.__file__).resolve()),
        }
    elif kind == "shard":
        raw_tasks = request.get("tasks")
        if not isinstance(raw_tasks, list):
            raise ValueError("PID snapshot worker shard request is invalid")
        tasks: list[tuple[int, tuple[float, float, float, float], float, int]] = []
        for raw_task in raw_tasks:
            if not isinstance(raw_task, list) or len(raw_task) != 4:
                raise ValueError("PID snapshot worker task is invalid")
            index, candidate, duration, seed = raw_task
            if not isinstance(candidate, list) or len(candidate) != 4:
                raise ValueError("PID snapshot worker candidate is invalid")
            tasks.append(
                (
                    int(index),
                    tuple(float(value) for value in candidate),
                    float(duration),
                    int(seed),
                )
            )
        response = {"rows": _evaluate_shard(tasks)}
    else:
        raise ValueError("PID snapshot worker request kind is invalid")
    Path(response_path).write_text(
        json.dumps(_json_safe(response), ensure_ascii=False, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _run_snapshot_worker_process(
    archive_path: Path,
    archive_sha256: str,
    request: Mapping[str, Any],
    *,
    poison_root: Path | None = None,
) -> dict[str, Any]:
    """Launch an isolated Python worker whose first application import is snapshot code."""

    resolved_archive = archive_path.resolve()
    if _raw_sha256(resolved_archive) != archive_sha256:
        raise ValueError("PID worker source snapshot hash is invalid")
    with tempfile.TemporaryDirectory(prefix="hidden_pid_worker_request_") as temporary_directory:
        temporary_root = Path(temporary_directory)
        request_path = temporary_root / "request.json"
        response_path = temporary_root / "response.json"
        request_path.write_text(
            json.dumps(_json_safe(request), ensure_ascii=False, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment.update({name: "1" for name in THREAD_LIMIT_ENV})
        command = [
            sys.executable,
            "-I",
            "-c",
            _SNAPSHOT_WORKER_BOOTSTRAP,
            str(resolved_archive),
            archive_sha256,
            str(request_path),
            str(response_path),
            "" if poison_root is None else str(poison_root.resolve()),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=temporary_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=WORKER_DEADLINE_SEC,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("PID snapshot worker deadline expired") from exc
        if completed.returncode != 0:
            raise RuntimeError(
                "PID snapshot worker failed before producing a result: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )
        if not response_path.is_file():
            raise RuntimeError("PID snapshot worker produced no result")
        response = json.loads(response_path.read_text(encoding="utf-8"))
    if not isinstance(response, dict):
        raise ValueError("PID snapshot worker response is invalid")
    return response


def _run_snapshot_worker_probe(
    archive_path: Path,
    archive_sha256: str,
    *,
    poison_root: Path | None = None,
) -> dict[str, str]:
    response = _run_snapshot_worker_process(
        archive_path,
        archive_sha256,
        {"kind": "probe"},
        poison_root=poison_root,
    )
    expected_keys = {"tuner_module", "environment_module", "deferred_environment_module"}
    if set(response) != expected_keys or not all(
        isinstance(response[key], str) and response[key] for key in expected_keys
    ):
        raise ValueError("PID snapshot worker probe response is invalid")
    return {key: str(response[key]) for key in expected_keys}


def _run_snapshot_shards(
    archive_path: Path,
    archive_sha256: str,
    pending_shards: Sequence[Sequence[tuple[int, tuple[float, float, float, float], float, int]]],
) -> Iterable[list[dict[str, Any]]]:
    """Evaluate fixed shards concurrently through isolated snapshot-only processes."""

    def run_one(
        shard: Sequence[tuple[int, tuple[float, float, float, float], float, int]],
    ) -> list[dict[str, Any]]:
        response = _run_snapshot_worker_process(
            archive_path,
            archive_sha256,
            {
                "kind": "shard",
                "tasks": [
                    [index, list(candidate), duration, seed]
                    for index, candidate, duration, seed in shard
                ],
            },
        )
        rows = response.get("rows")
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("PID snapshot worker shard response is invalid")
        return [dict(row) for row in rows]

    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as pool:
        yield from pool.map(run_one, pending_shards)


def _source_snapshot_record(
    attempt_root: Path,
    source_snapshot: Mapping[str, Any],
    evaluation_git_sha: str,
) -> tuple[Path, str]:
    """Validate and unpack the immutable snapshot metadata used by workers."""

    if set(source_snapshot) != {
        "schema_version",
        "evaluation_git_sha",
        "archive_path",
        "archive_sha256",
        "included_paths_sha256",
        "content_sha256",
    }:
        raise ValueError("PID source snapshot record schema is invalid")
    if (
        source_snapshot.get("schema_version") != ATTEMPT_SCHEMA_VERSION
        or source_snapshot.get("evaluation_git_sha") != evaluation_git_sha
    ):
        raise ValueError("PID source snapshot record does not match the evaluation Git SHA")
    archive_path = _require_external_path(source_snapshot.get("archive_path"), "source snapshot")
    if archive_path != (attempt_root / SOURCE_SNAPSHOT_ARCHIVE_FILENAME).resolve():
        raise ValueError("PID source snapshot archive path does not match attempt root")
    archive_hash = source_snapshot.get("archive_sha256")
    if not isinstance(archive_hash, str) or len(archive_hash) != 64:
        raise ValueError("PID source snapshot archive hash is invalid")
    if not archive_path.is_file() or _raw_sha256(archive_path) != archive_hash:
        raise ValueError("PID source snapshot archive hash does not match")
    _validate_source_snapshot_archive(
        archive_path,
        evaluation_git_sha=evaluation_git_sha,
        expected_archive_sha256=archive_hash,
    )
    if source_snapshot.get("included_paths_sha256") != _canonical_json_hash(
        _snapshot_relative_paths(evaluation_git_sha)
    ):
        raise ValueError("PID source snapshot file set is invalid")
    return archive_path, archive_hash


def _evidence_scope(
    *,
    duration_sec: float,
    seed: int,
) -> dict[str, Any]:
    """The complete, non-negotiable validation scope indexed by an attempt."""

    return {
        "controller": "pid",
        "profile": "standard",
        "evaluation_duration_sec": duration_sec,
        "evaluation_seed": seed,
        "worker_count": WORKER_COUNT,
        "thread_limits": {name: "1" for name in THREAD_LIMIT_ENV},
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "candidate_parameter_order": list(CANDIDATE_PARAMETER_ORDER),
        "candidate_values": {name: list(values) for name, values in CANDIDATE_VALUES.items()},
        "candidate_indices": list(range(EXPECTED_CANDIDATE_COUNT)),
    }


def _indexed_entry(path: Path, **metadata: Any) -> dict[str, Any]:
    return {**metadata, **_artifact_provenance_entry(path)}


def _evidence_index_payload(
    attempt_root: Path,
    *,
    duration_sec: float,
    seed: int,
    command: Sequence[str],
    evaluation_git_sha: str | None = None,
) -> dict[str, Any]:
    """Bind every immutable attempt record into one external evidence graph."""

    resolved_evaluation_git_sha = evaluation_git_sha or _git_sha()
    _validate_evaluation_git_sha(resolved_evaluation_git_sha)

    candidates = [
        _indexed_entry(_candidate_record_path(attempt_root, index), candidate_index=index)
        for index in range(EXPECTED_CANDIDATE_COUNT)
    ]
    shards = [
        _indexed_entry(
            attempt_root / "shards" / f"shard_{shard_index:02d}.json",
            shard_index=shard_index,
        )
        for shard_index in range(WORKER_COUNT)
    ]
    return {
        "schema_version": EVIDENCE_INDEX_SCHEMA_VERSION,
        "attempt_root": str(attempt_root.resolve()),
        "evaluation_git_sha": resolved_evaluation_git_sha,
        "command": list(command),
        "scope": _evidence_scope(duration_sec=duration_sec, seed=seed),
        "source_identities": _source_identities(resolved_evaluation_git_sha),
        "records": {
            "running": _indexed_entry(attempt_root / "RUNNING.json"),
            "source_snapshot": _indexed_entry(attempt_root / SOURCE_SNAPSHOT_RECORD_FILENAME),
            "candidate_manifest": _indexed_entry(attempt_root / "candidate_manifest.json"),
            "candidates": candidates,
            "shards": shards,
            "coverage": _indexed_entry(attempt_root / "coverage.json"),
            "ranking": _indexed_entry(attempt_root / "ranking.json"),
            "winner_recheck": _indexed_entry(attempt_root / "winner_recheck.json"),
            "done": _indexed_entry(attempt_root / "DONE.json"),
        },
    }


def _write_evidence_index(
    attempt_root: Path,
    *,
    duration_sec: float,
    seed: int,
    command: Sequence[str],
    evaluation_git_sha: str | None = None,
) -> dict[str, Any]:
    return _write_immutable_json(
        attempt_root / EVIDENCE_INDEX_FILENAME,
        _evidence_index_payload(
            attempt_root,
            duration_sec=duration_sec,
            seed=seed,
            command=command,
            evaluation_git_sha=evaluation_git_sha,
        ),
    )


def _attempt_evidence_payload(
    attempt_root: Path,
    *,
    evidence_index: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "attempt_root": str(attempt_root.resolve()),
        "evidence_index": _artifact_provenance_entry(
            attempt_root / EVIDENCE_INDEX_FILENAME,
            evidence_index,
        ),
    }


def _validate_indexed_entry(
    attempt_root: Path,
    entry: Any,
    *,
    label: str,
    expected_path: Path,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    expected_metadata = dict(metadata or {})
    mapping = _require_mapping(entry, f"provenance {label}")
    if set(mapping) != {"path", "content_sha256", "file_sha256", *expected_metadata}:
        raise ValueError(f"frozen PID provenance {label} index schema is invalid")
    if any(mapping.get(key) != value for key, value in expected_metadata.items()):
        raise ValueError(f"frozen PID provenance {label} index metadata is invalid")
    indexed_path = _require_external_path(mapping.get("path"), label)
    if indexed_path != expected_path.resolve():
        raise ValueError(f"frozen PID provenance {label} path does not match attempt root")
    if not indexed_path.is_file():
        raise ValueError(f"frozen PID provenance {label} artifact is missing")
    record = _read_immutable_json(indexed_path)
    if record.get("content_sha256") != mapping.get("content_sha256"):
        raise ValueError(f"frozen PID provenance {label} content hash does not match")
    if _canonical_sha256(indexed_path) != mapping.get("file_sha256"):
        raise ValueError(f"frozen PID provenance {label} file hash does not match")
    return record


def _validate_source_identities(value: Any, evaluation_git_sha: str) -> None:
    identities = _require_mapping(value, "source identities")
    expected = _source_identities(evaluation_git_sha)
    if dict(identities) != expected:
        raise ValueError("frozen PID source identity is invalid")


def _validate_attempt_evidence(payload: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    evidence = _require_mapping(payload.get("attempt_evidence"), "attempt provenance")
    if set(evidence) != {
        "schema_version",
        "attempt_root",
        "evidence_index",
        "config_payload_sha256",
    }:
        raise ValueError("frozen PID provenance schema is invalid")
    if evidence.get("schema_version") != ATTEMPT_SCHEMA_VERSION:
        raise ValueError("frozen PID provenance schema version is invalid")
    if evidence.get("config_payload_sha256") != _frozen_config_payload_hash(payload):
        raise ValueError("frozen PID provenance config payload hash does not match")
    attempt_root = _require_external_path(evidence.get("attempt_root"), "attempt root")
    index = _validate_indexed_entry(
        attempt_root,
        evidence.get("evidence_index"),
        label="evidence index",
        expected_path=attempt_root / EVIDENCE_INDEX_FILENAME,
    )
    if set(index) != {
        "schema_version",
        "attempt_root",
        "evaluation_git_sha",
        "command",
        "scope",
        "source_identities",
        "records",
        "content_sha256",
    }:
        raise ValueError("frozen PID evidence index schema is invalid")
    if index.get("schema_version") != EVIDENCE_INDEX_SCHEMA_VERSION:
        raise ValueError("frozen PID evidence index schema version is invalid")
    if index.get("attempt_root") != str(attempt_root):
        raise ValueError("frozen PID evidence index attempt root is invalid")
    if index.get("evaluation_git_sha") != payload.get("evaluation_git_sha"):
        raise ValueError("frozen PID evidence index Git SHA is invalid")
    command = payload.get("command")
    if index.get("command") != command:
        raise ValueError("frozen PID evidence index command is invalid")
    expected_scope = _evidence_scope(
        duration_sec=float(payload["evaluation_duration_sec"]),
        seed=int(payload["evaluation_seed"]),
    )
    if index.get("scope") != expected_scope:
        raise ValueError("frozen PID evidence index scope is invalid")
    _validate_source_identities(
        index.get("source_identities"),
        str(index["evaluation_git_sha"]),
    )
    records = _require_mapping(index.get("records"), "evidence index records")
    if set(records) != {
        "running",
        "source_snapshot",
        "candidate_manifest",
        "candidates",
        "shards",
        "coverage",
        "ranking",
        "winner_recheck",
        "done",
    }:
        raise ValueError("frozen PID evidence index record schema is invalid")
    return attempt_root, {key: value for key, value in records.items()}


def _validate_complete_evidence_index(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate every edge in the immutable 81-candidate evidence graph."""

    attempt_root, entries = _validate_attempt_evidence(payload)
    duration = float(payload["evaluation_duration_sec"])
    seed = int(payload["evaluation_seed"])
    candidates = enumerate_pid_candidates()

    manifest = _validate_indexed_entry(
        attempt_root,
        entries["candidate_manifest"],
        label="candidate manifest",
        expected_path=attempt_root / "candidate_manifest.json",
    )
    expected_manifest = _attempt_manifest(candidates, duration_sec=duration, seed=seed)
    if {key: value for key, value in manifest.items() if key != "content_sha256"} != expected_manifest:
        raise ValueError("frozen PID provenance manifest does not match the frozen grid")

    source_snapshot = _validate_indexed_entry(
        attempt_root,
        entries["source_snapshot"],
        label="source snapshot",
        expected_path=attempt_root / SOURCE_SNAPSHOT_RECORD_FILENAME,
    )
    _source_snapshot_record(
        attempt_root,
        source_snapshot,
        str(payload["evaluation_git_sha"]),
    )

    running = _validate_indexed_entry(
        attempt_root,
        entries["running"],
        label="RUNNING",
        expected_path=attempt_root / "RUNNING.json",
    )
    expected_running = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "attempt_name": attempt_root.name,
        "protocol_hash": manifest["protocol_hash"],
        "candidate_manifest_sha256": manifest["content_sha256"],
        "evaluation_git_sha": payload["evaluation_git_sha"],
        "source_snapshot_sha256": source_snapshot["content_sha256"],
        "command": payload["command"],
        "thread_limits": {name: "1" for name in THREAD_LIMIT_ENV},
        "worker_count": WORKER_COUNT,
    }
    if (
        set(running) != {*expected_running, "started_at_utc", "content_sha256"}
        or any(running.get(key) != value for key, value in expected_running.items())
        or not isinstance(running.get("started_at_utc"), str)
        or not running["started_at_utc"]
    ):
        raise ValueError("frozen PID RUNNING evidence is invalid")

    candidate_entries = entries["candidates"]
    if not isinstance(candidate_entries, list) or len(candidate_entries) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError("frozen PID candidate evidence index is incomplete")
    candidate_records: dict[int, dict[str, Any]] = {}
    rows: dict[int, dict[str, Any]] = {}
    candidate_core_keys = {
        "schema_version",
        "protocol_hash",
        "candidate_index",
        "candidate",
        "parameters",
        "evaluation_duration_sec",
        "evaluation_seed",
        "result",
        "content_sha256",
    }
    for index, candidate in enumerate(candidates):
        record = _validate_indexed_entry(
            attempt_root,
            candidate_entries[index],
            label=f"candidate {index}",
            expected_path=_candidate_record_path(attempt_root, index),
            metadata={"candidate_index": index},
        )
        if set(record) != candidate_core_keys:
            raise ValueError(f"frozen PID candidate evidence schema is invalid for index {index}")
        candidate_records[index] = record
        rows[index] = _result_from_candidate_record(
            record,
            index=index,
            candidate=candidate,
            duration_sec=duration,
            seed=seed,
        )

    shards = split_candidate_shards(candidates, WORKER_COUNT)
    shard_entries = entries["shards"]
    if not isinstance(shard_entries, list) or len(shard_entries) != WORKER_COUNT:
        raise ValueError("frozen PID shard evidence index is incomplete")
    for shard_index, shard in enumerate(shards):
        shard_record = _validate_indexed_entry(
            attempt_root,
            shard_entries[shard_index],
            label=f"shard {shard_index}",
            expected_path=attempt_root / "shards" / f"shard_{shard_index:02d}.json",
            metadata={"shard_index": shard_index},
        )
        expected_indices = [index for index, _ in shard]
        expected_hashes = [candidate_records[index]["content_sha256"] for index in expected_indices]
        if (
            set(shard_record)
            != {
                "schema_version",
                "shard_index",
                "candidate_indices",
                "candidate_record_hashes",
                "content_sha256",
            }
            or shard_record.get("schema_version") != ATTEMPT_SCHEMA_VERSION
            or shard_record.get("shard_index") != shard_index
            or shard_record.get("candidate_indices") != expected_indices
            or shard_record.get("candidate_record_hashes") != expected_hashes
        ):
            raise ValueError(f"frozen PID shard evidence is invalid for shard {shard_index}")

    coverage = _validate_indexed_entry(
        attempt_root,
        entries["coverage"],
        label="coverage",
        expected_path=attempt_root / "coverage.json",
    )
    expected_coverage = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "expected_candidate_indices": list(range(EXPECTED_CANDIDATE_COUNT)),
        "actual_candidate_indices": list(range(EXPECTED_CANDIDATE_COUNT)),
        "missing_candidate_indices": [],
        "duplicate_candidate_indices": [],
        "shard_sizes": [len(shard) for shard in shards],
        "complete": True,
    }
    if {key: value for key, value in coverage.items() if key != "content_sha256"} != expected_coverage:
        raise ValueError("frozen PID provenance coverage is invalid")

    ranking_record = _validate_indexed_entry(
        attempt_root,
        entries["ranking"],
        label="ranking",
        expected_path=attempt_root / "ranking.json",
    )
    ranking = ranking_record.get("ranking")
    recomputed_ranking = rank_candidates(rows[index] for index in range(EXPECTED_CANDIDATE_COUNT))
    if (
        set(ranking_record)
        != {
            "schema_version",
            "candidate_manifest_sha256",
            "coverage_sha256",
            "accepted_candidate_indices",
            "ranking",
            "content_sha256",
        }
        or ranking_record.get("schema_version") != ATTEMPT_SCHEMA_VERSION
        or ranking_record.get("candidate_manifest_sha256") != manifest.get("content_sha256")
        or ranking_record.get("coverage_sha256") != coverage.get("content_sha256")
        or not isinstance(ranking, list)
        or ranking_record.get("accepted_candidate_indices")
        != [row["candidate_index"] for row in recomputed_ranking]
        or ranking != recomputed_ranking
        or payload.get("ranking_hash") != _canonical_json_hash(ranking)
    ):
        raise ValueError("frozen PID ranking evidence is invalid")
    if not ranking:
        raise ValueError("frozen PID ranking evidence has no accepted winner")

    winner = ranking[0]
    winner_index = winner.get("candidate_index")
    if isinstance(winner_index, bool) or not isinstance(winner_index, int) or winner_index not in rows:
        raise ValueError("frozen PID winner evidence is invalid")
    expected_original = dict(rows[winner_index])
    expected_original.pop("candidate_index", None)
    expected_original.pop("candidate", None)
    winner_recheck = _validate_indexed_entry(
        attempt_root,
        entries["winner_recheck"],
        label="winner recheck",
        expected_path=attempt_root / "winner_recheck.json",
    )
    if (
        set(winner_recheck)
        != {
            "schema_version",
            "decision",
            "winner_index",
            "candidate",
            "original_result",
            "recheck_result",
            "ranking_sha256",
            "content_sha256",
        }
        or winner_recheck.get("schema_version") != ATTEMPT_SCHEMA_VERSION
        or winner_recheck.get("decision") != "GO"
        or winner_recheck.get("winner_index") != winner_index
        or winner_recheck.get("candidate") != list(candidates[winner_index])
        or winner_recheck.get("ranking_sha256") != ranking_record.get("content_sha256")
        or winner_recheck.get("original_result") != expected_original
        or winner_recheck.get("recheck_result") != expected_original
        or not acceptance_passes(expected_original)
    ):
        raise ValueError("frozen PID winner recheck evidence is invalid")

    done = _validate_indexed_entry(
        attempt_root,
        entries["done"],
        label="DONE",
        expected_path=attempt_root / "DONE.json",
    )
    expected_done = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "decision": "GO",
        "candidate_manifest_sha256": manifest["content_sha256"],
        "coverage_sha256": coverage["content_sha256"],
        "ranking_sha256": ranking_record["content_sha256"],
        "winner_recheck_sha256": winner_recheck["content_sha256"],
    }
    if {key: value for key, value in done.items() if key != "content_sha256"} != expected_done:
        raise ValueError("frozen PID DONE evidence is invalid")
    return {
        "manifest": manifest,
        "coverage": coverage,
        "ranking_record": ranking_record,
        "ranking": ranking,
        "winner_recheck": winner_recheck,
        "done": done,
    }


def load_frozen_pid_config(path: Path | str = DEFAULT_FROZEN_PATH) -> dict[str, Any]:
    """Load and validate the frozen PID contract and its external evidence."""

    resolved = _resolve_repo_path(Path(path))
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("frozen PID config must be a JSON object")
    if payload.get("schema_version") != FROZEN_CONFIG_SCHEMA_VERSION:
        raise ValueError("frozen PID config schema version is unsupported")
    expected_hash = protocol_hash()
    if payload.get("protocol_hash") != expected_hash:
        raise ValueError("frozen PID config protocol hash does not match protocol")
    if payload.get("controller") != "pid" or payload.get("profile") != "standard":
        raise ValueError("frozen PID config has an invalid controller/profile")
    _validate_validation_scope(payload.get("evaluation_duration_sec"), payload.get("evaluation_seed"))
    if payload.get("geometry") != FROZEN_GEOMETRY:
        raise ValueError("frozen PID geometry is invalid")
    if payload.get("simulation") != FROZEN_SIMULATION:
        raise ValueError("frozen PID simulation metadata is invalid")
    if payload.get("control") != FROZEN_CONTROL:
        raise ValueError("frozen PID control metadata is invalid")
    if payload.get("environment_schema") != list(HiddenDisturbanceCircularTD3Env._SHARED_OBSERVATION_SCHEMA):
        raise ValueError("frozen PID environment schema is invalid")
    if payload.get("protocol_path") != str(PROTOCOL_PATH).replace("\\", "/"):
        raise ValueError("frozen PID protocol path is invalid")
    if payload.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        raise ValueError("frozen PID config candidate count is invalid")
    if tuple(payload.get("candidate_parameter_order", ())) != CANDIDATE_PARAMETER_ORDER:
        raise ValueError("frozen PID config candidate order is invalid")
    expected_values = {name: list(values) for name, values in CANDIDATE_VALUES.items()}
    if payload.get("candidate_values") != expected_values:
        raise ValueError("frozen PID config candidate values are invalid")
    parameters = _extract_parameters(payload)
    candidate_tuple = tuple(parameters[name] for name in CANDIDATE_PARAMETER_ORDER)
    if candidate_index(candidate_tuple) < 0:
        raise ValueError("frozen PID parameters are outside the candidate grid")
    if payload.get("winner_index") != candidate_index(candidate_tuple):
        raise ValueError("frozen PID winner index does not match parameters")
    if payload.get("pid_payload_hash") != _canonical_json_hash(parameters):
        raise ValueError("frozen PID payload hash does not match parameters")
    _validate_evaluation_git_sha(payload.get("evaluation_git_sha"))
    if payload.get("environment_source_sha256") != _source_identity(
        ENV_SOURCE_PATH,
        str(payload["evaluation_git_sha"]),
    )["git_blob_sha256"]:
        raise ValueError("frozen PID environment source digest does not match")
    package_versions = _require_mapping(payload.get("package_versions"), "package versions")
    expected_packages = {"numpy", "gymnasium", "pybullet", "torch", "stable-baselines3", "control"}
    if set(package_versions) != expected_packages or not all(
        isinstance(value, str) and value for value in package_versions.values()
    ):
        raise ValueError("frozen PID package metadata is invalid")
    if not isinstance(payload.get("python"), str) or not payload["python"]:
        raise ValueError("frozen PID Python metadata is invalid")
    if not isinstance(payload.get("platform"), str) or not payload["platform"]:
        raise ValueError("frozen PID platform metadata is invalid")
    command = payload.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise ValueError("frozen PID command metadata is invalid")
    acceptance = payload.get("acceptance")
    if acceptance != FROZEN_ACCEPTANCE:
        raise ValueError("frozen PID acceptance contract is invalid")
    winner_metrics = _require_mapping(payload.get("winner_metrics"), "winner metrics")
    expected_metric_keys = {
        "steady_position_rmse",
        "path_length_ratio",
        "mean_phase_error",
        "rotor_saturation_rate",
        "control_energy",
        "completed_steps",
    }
    if set(winner_metrics) != expected_metric_keys:
        raise ValueError("frozen PID winner metrics are invalid")
    winner_for_acceptance = {"failure": False, **winner_metrics}
    if not acceptance_passes(winner_for_acceptance):
        raise ValueError("frozen PID winner metrics fail acceptance")
    evidence_records = _validate_complete_evidence_index(payload)
    winner = evidence_records["ranking"][0]
    if (
        payload.get("winner_index") != winner.get("candidate_index")
        or {name: winner.get(name) for name in CANDIDATE_PARAMETER_ORDER} != parameters
        or {key: winner.get(key) for key in expected_metric_keys} != dict(winner_metrics)
    ):
        raise ValueError("frozen PID winner evidence is invalid")
    return payload


def _is_known_repository_stale_pid_config(path: Path | str = DEFAULT_FROZEN_PATH) -> bool:
    """Recognize only the checked-in pre-evidence-v2 schema-2 legacy config."""

    resolved = _resolve_repo_path(Path(path)).resolve()
    if resolved != _resolve_repo_path(DEFAULT_FROZEN_PATH).resolve():
        return False
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, Mapping) and payload.get("schema_version") == 2


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def build_frozen_payload(
    winner: Mapping[str, Any],
    *,
    command: Sequence[str],
    duration_sec: float,
    seed: int,
    ranking: Sequence[Mapping[str, Any]],
    attempt_evidence: Mapping[str, Any] | None = None,
    evaluation_git_sha: str | None = None,
) -> dict[str, Any]:
    duration, validation_seed = _validate_validation_scope(duration_sec, seed)
    resolved_evaluation_git_sha = evaluation_git_sha or _git_sha()
    _validate_evaluation_git_sha(resolved_evaluation_git_sha)
    source_identities = _source_identities(resolved_evaluation_git_sha)
    parameters = {name: float(winner[name]) for name in CANDIDATE_PARAMETER_ORDER}
    payload = {
        "schema_version": FROZEN_CONFIG_SCHEMA_VERSION,
        "controller": "pid",
        "profile": "standard",
        "geometry": dict(FROZEN_GEOMETRY),
        "simulation": dict(FROZEN_SIMULATION),
        "control": dict(FROZEN_CONTROL),
        "evaluation_duration_sec": duration,
        "evaluation_seed": validation_seed,
        "parameters": parameters,
        "winner_index": int(winner["candidate_index"]),
        "winner_metrics": {
            key: winner[key]
            for key in (
                "steady_position_rmse",
                "path_length_ratio",
                "mean_phase_error",
                "rotor_saturation_rate",
                "control_energy",
                "completed_steps",
            )
        },
        "acceptance": dict(FROZEN_ACCEPTANCE),
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "candidate_parameter_order": list(CANDIDATE_PARAMETER_ORDER),
        "candidate_values": {name: list(values) for name, values in CANDIDATE_VALUES.items()},
        "protocol_path": str(PROTOCOL_PATH).replace("\\", "/"),
        "protocol_hash": protocol_hash(),
        "evaluation_git_sha": resolved_evaluation_git_sha,
        "environment_schema": list(HiddenDisturbanceCircularTD3Env._SHARED_OBSERVATION_SCHEMA),
        "environment_source_sha256": source_identities["environment"]["git_blob_sha256"],
        "package_versions": _package_versions(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": list(command),
        "ranking_hash": _canonical_json_hash(list(ranking)),
        "pid_payload_hash": _canonical_json_hash(parameters),
    }
    if attempt_evidence is not None:
        payload["attempt_evidence"] = dict(attempt_evidence)
        payload["attempt_evidence"]["config_payload_sha256"] = _frozen_config_payload_hash(payload)
    return payload


def _write_new_frozen_payload(path: Path, payload: Mapping[str, Any]) -> None:
    if not _commit_new_file(path, _serialized_json_bytes(payload)):
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FileExistsError(
                f"refusing to replace unreadable frozen PID config: {path}"
            ) from exc
        if _canonical_json_hash(existing) == _canonical_json_hash(payload):
            return
        raise FileExistsError(
            f"refusing to replace frozen PID config: {path}; choose a new output path"
        )


def _ranking_payload(
    ranking: Sequence[Mapping[str, Any]],
    *,
    manifest: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "candidate_manifest_sha256": manifest["content_sha256"],
        "coverage_sha256": coverage["content_sha256"],
        "accepted_candidate_indices": [int(row["candidate_index"]) for row in ranking],
        "ranking": [dict(row) for row in ranking],
    }


def _recover_completed_attempt(
    output: Path,
    attempt_root: Path,
    *,
    duration_sec: float,
    seed: int,
) -> dict[str, Any]:
    """Recreate a missing config from a completed immutable GO evidence graph."""

    done = _read_immutable_json(attempt_root / "DONE.json")
    if (
        done.get("schema_version") != ATTEMPT_SCHEMA_VERSION
        or done.get("decision") != "GO"
    ):
        raise FileExistsError(f"PID tuning attempt is complete: {attempt_root}")
    index_path = attempt_root / EVIDENCE_INDEX_FILENAME
    index = _read_immutable_json(index_path)
    if (
        index.get("schema_version") != EVIDENCE_INDEX_SCHEMA_VERSION
        or index.get("attempt_root") != str(attempt_root)
        or index.get("scope") != _evidence_scope(duration_sec=duration_sec, seed=seed)
        or index.get("evaluation_git_sha") != _git_sha()
    ):
        raise ValueError("completed PID evidence cannot be recovered under this scope or Git SHA")
    evaluation_git_sha = index["evaluation_git_sha"]
    _validate_evaluation_git_sha(evaluation_git_sha)
    _validate_source_identities(index.get("source_identities"), evaluation_git_sha)
    command = index.get("command")
    if not isinstance(command, list) or not command or not all(
        isinstance(item, str) and item for item in command
    ):
        raise ValueError("completed PID evidence has an invalid command")
    records = _require_mapping(index.get("records"), "evidence index records")
    ranking_record = _validate_indexed_entry(
        attempt_root,
        records.get("ranking"),
        label="ranking",
        expected_path=attempt_root / "ranking.json",
    )
    ranking = ranking_record.get("ranking")
    if not isinstance(ranking, list) or not ranking or not isinstance(ranking[0], Mapping):
        raise ValueError("completed PID evidence has no recoverable winner")
    payload = build_frozen_payload(
        ranking[0],
        command=command,
        duration_sec=duration_sec,
        seed=seed,
        ranking=ranking,
        attempt_evidence=_attempt_evidence_payload(attempt_root, evidence_index=index),
        evaluation_git_sha=evaluation_git_sha,
    )
    # Validate the whole immutable graph before committing any recovered config.
    # A malformed DONE/index/candidate/shard may never turn into a partial output.
    _validate_complete_evidence_index(payload)
    _write_new_frozen_payload(output, payload)
    recovered = load_frozen_pid_config(output)
    if _canonical_json_hash(recovered) != _canonical_json_hash(payload):
        raise RuntimeError("completed PID evidence did not recover the exact frozen config")
    return recovered


def _recover_missing_done_for_existing_output(
    output: Path,
    attempt_root: Path,
) -> dict[str, Any]:
    """Restore only an indexed deterministic DONE sentinel, without starting work."""

    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("frozen PID output is not an object")
        bound_root, entries = _validate_attempt_evidence(payload)
        if bound_root != attempt_root:
            raise ValueError("frozen PID output binds another attempt root")
        evidence = _require_mapping(payload.get("attempt_evidence"), "attempt provenance")
        index_entry = _require_mapping(evidence.get("evidence_index"), "evidence index")
        index_path = _require_external_path(index_entry.get("path"), "evidence index")
        index = _read_immutable_json(index_path)
        evaluation_git_sha = payload.get("evaluation_git_sha")
        if not isinstance(evaluation_git_sha, str):
            raise ValueError("frozen PID output Git SHA is invalid")
        manifest = _validate_indexed_entry(
            attempt_root,
            entries["candidate_manifest"],
            label="candidate manifest",
            expected_path=attempt_root / "candidate_manifest.json",
        )
        source_snapshot = _validate_indexed_entry(
            attempt_root,
            entries["source_snapshot"],
            label="source snapshot",
            expected_path=attempt_root / SOURCE_SNAPSHOT_RECORD_FILENAME,
        )
        _source_snapshot_record(attempt_root, source_snapshot, evaluation_git_sha)
        _validate_indexed_entry(
            attempt_root,
            entries["running"],
            label="RUNNING",
            expected_path=attempt_root / "RUNNING.json",
        )
        candidate_entries = entries["candidates"]
        if not isinstance(candidate_entries, list) or len(candidate_entries) != EXPECTED_CANDIDATE_COUNT:
            raise ValueError("frozen PID candidate graph is incomplete")
        for candidate_index_value in range(EXPECTED_CANDIDATE_COUNT):
            _validate_indexed_entry(
                attempt_root,
                candidate_entries[candidate_index_value],
                label=f"candidate {candidate_index_value}",
                expected_path=_candidate_record_path(attempt_root, candidate_index_value),
                metadata={"candidate_index": candidate_index_value},
            )
        shard_entries = entries["shards"]
        if not isinstance(shard_entries, list) or len(shard_entries) != WORKER_COUNT:
            raise ValueError("frozen PID shard graph is incomplete")
        for shard_index in range(WORKER_COUNT):
            _validate_indexed_entry(
                attempt_root,
                shard_entries[shard_index],
                label=f"shard {shard_index}",
                expected_path=attempt_root / "shards" / f"shard_{shard_index:02d}.json",
                metadata={"shard_index": shard_index},
            )
        coverage = _validate_indexed_entry(
            attempt_root,
            entries["coverage"],
            label="coverage",
            expected_path=attempt_root / "coverage.json",
        )
        ranking = _validate_indexed_entry(
            attempt_root,
            entries["ranking"],
            label="ranking",
            expected_path=attempt_root / "ranking.json",
        )
        winner_recheck = _validate_indexed_entry(
            attempt_root,
            entries["winner_recheck"],
            label="winner recheck",
            expected_path=attempt_root / "winner_recheck.json",
        )
        ranked = ranking.get("ranking")
        if not isinstance(ranked, list) or not ranked or not isinstance(ranked[0], Mapping):
            raise ValueError("frozen PID ranking has no winner")
        winner = ranked[0]
        parameters = _extract_parameters(payload)
        expected_metric_keys = {
            "steady_position_rmse",
            "path_length_ratio",
            "mean_phase_error",
            "rotor_saturation_rate",
            "control_energy",
            "completed_steps",
        }
        if (
            payload.get("ranking_hash") != _canonical_json_hash(ranked)
            or payload.get("winner_index") != winner.get("candidate_index")
            or {name: winner.get(name) for name in CANDIDATE_PARAMETER_ORDER} != parameters
            or set(_require_mapping(payload.get("winner_metrics"), "winner metrics")) != expected_metric_keys
            or dict(_require_mapping(payload.get("winner_metrics"), "winner metrics"))
            != {key: winner.get(key) for key in expected_metric_keys}
            or payload.get("evaluation_git_sha") != index.get("evaluation_git_sha")
        ):
            raise ValueError("frozen PID output does not match immutable ranking")
        expected_done = {
            "schema_version": ATTEMPT_SCHEMA_VERSION,
            "decision": "GO",
            "candidate_manifest_sha256": manifest["content_sha256"],
            "coverage_sha256": coverage["content_sha256"],
            "ranking_sha256": ranking["content_sha256"],
            "winner_recheck_sha256": winner_recheck["content_sha256"],
        }
        expected_stored_done = _immutable_stored_payload(expected_done)
        expected_done_entry = {
            "path": str((attempt_root / "DONE.json").resolve()),
            "content_sha256": expected_stored_done["content_sha256"],
            "file_sha256": _canonical_json_file_hash(expected_stored_done),
        }
        if entries["done"] != expected_done_entry:
            raise ValueError("frozen PID missing DONE is not index-bound")
        _write_immutable_json(attempt_root / "DONE.json", expected_done)
        return payload
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise FileExistsError(
            f"refusing incomplete PID output before a complete immutable attempt: {output}"
        ) from exc


def tune_and_freeze(
    output: Path = DEFAULT_FROZEN_PATH,
    *,
    duration_sec: float = EVALUATION_DURATION_SEC,
    seed: int = EVALUATION_SEED,
    workers: int = 4,
    command: Sequence[str] | None = None,
    attempt_root: Path | str | None = None,
    _attempt_lock_acquired: bool = False,
) -> dict[str, Any] | None:
    """Run or resume one immutable, validation-only four-shard PID attempt."""

    duration, validation_seed = _validate_validation_scope(duration_sec, seed)
    _validate_worker_count(workers)
    if attempt_root is None:
        raise ValueError("PID tuning requires an explicit external attempt root")
    raw_attempt_root = Path(attempt_root)
    if not raw_attempt_root.is_absolute():
        raise ValueError("PID tuning requires an absolute external attempt root")
    resolved_output = _resolve_repo_path(Path(output))
    resolved_attempt_root = _require_external_path(
        str(raw_attempt_root),
        "attempt root",
    )
    if not _attempt_lock_acquired:
        with _exclusive_attempt_lock(resolved_attempt_root):
            return tune_and_freeze(
                output,
                duration_sec=duration,
                seed=validation_seed,
                workers=workers,
                command=command,
                attempt_root=resolved_attempt_root,
                _attempt_lock_acquired=True,
            )
    done_path = resolved_attempt_root / "DONE.json"
    if resolved_output.exists() and not done_path.exists():
        return _recover_missing_done_for_existing_output(
            resolved_output,
            resolved_attempt_root,
        )
    if done_path.exists():
        if resolved_output.exists():
            # Existing output is admissible only when the entire completed graph
            # and its outer frozen payload validate together.
            load_frozen_pid_config(resolved_output)
            raise FileExistsError(
                f"PID tuning attempt is complete: {resolved_attempt_root}; use a new output path"
            )
        return _recover_completed_attempt(
            resolved_output,
            resolved_attempt_root,
            duration_sec=duration,
            seed=validation_seed,
        )
    evaluation_git_sha = _git_sha()
    _validate_evaluation_git_sha(evaluation_git_sha)
    _source_identities(evaluation_git_sha)
    source_snapshot = _write_source_snapshot(resolved_attempt_root, evaluation_git_sha)
    snapshot_archive, snapshot_archive_sha256 = _source_snapshot_record(
        resolved_attempt_root,
        source_snapshot,
        evaluation_git_sha,
    )
    candidates = enumerate_pid_candidates()
    shards = split_candidate_shards(candidates, WORKER_COUNT)
    command_line = list(command or sys.argv)
    manifest = _attempt_manifest(candidates, duration_sec=duration, seed=validation_seed)
    stored_manifest = _prepare_attempt(
        resolved_attempt_root,
        manifest,
        command=command_line,
        evaluation_git_sha=evaluation_git_sha,
        source_snapshot=source_snapshot,
    )
    rows = _load_completed_candidate_rows(
        resolved_attempt_root,
        candidates,
        duration_sec=duration,
        seed=validation_seed,
    )

    pending_shards = [
        [
            (index, candidate, duration, validation_seed)
            for index, candidate in shard
            if index not in rows
        ]
        for shard in shards
    ]
    with _single_thread_worker_environment():
        produced_shards = _run_snapshot_shards(
            snapshot_archive,
            snapshot_archive_sha256,
            pending_shards,
        )
        for shard_index, produced in enumerate(produced_shards):
            _store_shard_results(
                resolved_attempt_root,
                shards[shard_index],
                produced,
                rows,
                duration_sec=duration,
                seed=validation_seed,
            )
            _write_shard_record(resolved_attempt_root, shard_index, shards[shard_index])

    coverage = _write_coverage_record(resolved_attempt_root, rows, shards)
    ranking = rank_candidates(rows[index] for index in sorted(rows))
    stored_ranking = _write_immutable_json(
        resolved_attempt_root / "ranking.json",
        _ranking_payload(
            ranking,
            manifest=stored_manifest,
            coverage=coverage,
        ),
    )

    if not ranking:
        winner_recheck = _write_immutable_json(
            resolved_attempt_root / "winner_recheck.json",
            {
                "schema_version": ATTEMPT_SCHEMA_VERSION,
                "decision": "NO-GO",
                "reason": "no_candidate_passed_frozen_acceptance",
                "ranking_sha256": stored_ranking["content_sha256"],
            },
        )
        done = _write_immutable_json(
            resolved_attempt_root / "DONE.json",
            {
                "schema_version": ATTEMPT_SCHEMA_VERSION,
                "decision": "NO-GO",
                "candidate_manifest_sha256": stored_manifest["content_sha256"],
                "coverage_sha256": coverage["content_sha256"],
                "ranking_sha256": stored_ranking["content_sha256"],
                "winner_recheck_sha256": winner_recheck["content_sha256"],
                "finished_at_utc": _utc_timestamp(),
            },
        )
        _write_evidence_index(
            resolved_attempt_root,
            duration_sec=duration,
            seed=validation_seed,
            command=command_line,
            evaluation_git_sha=evaluation_git_sha,
        )
        print(
            json.dumps(
                {
                    "attempt": _portable_path(resolved_attempt_root),
                    "candidate_count": len(rows),
                    "decision": done["decision"],
                },
                sort_keys=True,
            )
        )
        return None

    winner = ranking[0]
    winner_index = int(winner["candidate_index"])
    winner_candidate = candidate_from_index(winner_index)
    with _single_thread_worker_environment():
        recheck_response = _run_snapshot_worker_process(
            snapshot_archive,
            snapshot_archive_sha256,
            {
                "kind": "shard",
                "tasks": [[winner_index, list(winner_candidate), duration, validation_seed]],
            },
        )
    recheck_rows = recheck_response.get("rows")
    if not isinstance(recheck_rows, list) or len(recheck_rows) != 1 or not isinstance(recheck_rows[0], dict):
        raise ValueError("PID snapshot worker winner recheck response is invalid")
    recheck = dict(recheck_rows[0])
    original_metrics = dict(rows[winner_index])
    original_metrics.pop("candidate_index", None)
    original_metrics.pop("candidate", None)
    recheck_metrics = dict(recheck)
    recheck_metrics.pop("candidate_index", None)
    recheck_metrics.pop("candidate", None)
    recheck_metrics.update(candidate_to_config(winner_candidate))
    if (
        not acceptance_passes(recheck_metrics)
        or _canonical_json_hash(original_metrics) != _canonical_json_hash(recheck_metrics)
    ):
        raise RuntimeError("winner recheck did not reproduce the immutable candidate record")
    winner_recheck = _write_immutable_json(
        resolved_attempt_root / "winner_recheck.json",
        {
            "schema_version": ATTEMPT_SCHEMA_VERSION,
            "decision": "GO",
            "winner_index": winner_index,
            "candidate": list(winner_candidate),
            "original_result": original_metrics,
            "recheck_result": recheck_metrics,
            "ranking_sha256": stored_ranking["content_sha256"],
        },
    )

    done_payload = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "decision": "GO",
        "candidate_manifest_sha256": stored_manifest["content_sha256"],
        "coverage_sha256": coverage["content_sha256"],
        "ranking_sha256": stored_ranking["content_sha256"],
        "winner_recheck_sha256": winner_recheck["content_sha256"],
    }

    _write_immutable_json(resolved_attempt_root / "DONE.json", done_payload)
    evidence_index = _write_evidence_index(
        resolved_attempt_root,
        duration_sec=duration,
        seed=validation_seed,
        command=command_line,
        evaluation_git_sha=evaluation_git_sha,
    )
    payload = build_frozen_payload(
        winner,
        command=command_line,
        duration_sec=duration,
        seed=validation_seed,
        ranking=ranking,
        attempt_evidence=_attempt_evidence_payload(
            resolved_attempt_root,
            evidence_index=evidence_index,
        ),
        evaluation_git_sha=evaluation_git_sha,
    )
    _write_new_frozen_payload(resolved_output, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_FROZEN_PATH)
    parser.add_argument("--duration-sec", type=float, default=EVALUATION_DURATION_SEC)
    parser.add_argument("--seed", type=int, default=EVALUATION_SEED)
    parser.add_argument("--workers", type=int, default=WORKER_COUNT)
    parser.add_argument(
        "--attempt-root",
        type=Path,
        required=True,
        help="durable absolute directory outside this repository for immutable attempt evidence",
    )
    args = parser.parse_args(effective_argv)
    try:
        payload = tune_and_freeze(
            args.output,
            duration_sec=args.duration_sec,
            seed=args.seed,
            workers=args.workers,
            command=[sys.executable, "-m", "experiments.circular_tracking.scripts.td3.tune_hidden_pid", *effective_argv],
            attempt_root=args.attempt_root,
        )
    except (FileExistsError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    return 0 if payload is not None else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
