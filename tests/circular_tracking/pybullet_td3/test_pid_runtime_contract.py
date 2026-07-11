from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.training.pid_contract import (
    EXPECTED_PAYLOAD_HASH,
    EXPECTED_RAW_SHA256,
    load_pid_runtime_contract,
)
from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.study_paths import (
    FROZEN_PID_PATH,
)


def test_archived_pid_raw_hash() -> None:
    payload = json.loads(FROZEN_PID_PATH.read_text(encoding="utf-8"))
    archive_path = FROZEN_PID_PATH.parent / "../../../archive/20_hidden_disturbance_v1/provenance/hidden_pid_frozen.schema4.json"
    archive_path = archive_path.resolve()
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == EXPECTED_RAW_SHA256
    assert payload["derived_from"]["raw_sha256"] == EXPECTED_RAW_SHA256


def test_valid_parameters_and_payload_hash() -> None:
    payload = load_pid_runtime_contract(FROZEN_PID_PATH)
    assert payload["pid_payload_hash"] == EXPECTED_PAYLOAD_HASH


def test_changed_parameters_rejected(tmp_path: Path) -> None:
    payload = json.loads(FROZEN_PID_PATH.read_text(encoding="utf-8"))
    payload["parameters"]["pid_xy_d_scale"] = 1.0
    changed = tmp_path / "frozen_pid.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="parameter values are invalid"):
        load_pid_runtime_contract(changed)


def test_extra_top_level_field_rejected(tmp_path: Path) -> None:
    payload = json.loads(FROZEN_PID_PATH.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    changed = tmp_path / "frozen_pid.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="top-level fields are invalid"):
        load_pid_runtime_contract(changed)
