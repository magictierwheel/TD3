from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any
from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.study_paths import ARCHIVE_ROOT
EXPECTED_RAW_SHA256="c7530d2725d4c55b31252f89c1ed126ae140a35789b3c653b86e955165e48ef3"
EXPECTED_PAYLOAD_HASH="624e86cf7452410e15608774d5630512bd8a7f48f5d4e8d30fd5a8dcca37b99a"
EXPECTED_PARAMETERS={"pid_target_step_limit":0.0,"pid_xy_d_scale":1.25,"pid_xy_p_scale":1.0,"reference_velocity_gain":1.0}
EXPECTED_DERIVED_FROM={"path":"../../../archive/20_hidden_disturbance_v1/provenance/hidden_pid_frozen.schema4.json","raw_sha256":EXPECTED_RAW_SHA256,"evaluation_git_sha":"f19e99103d2700b3a9bd5cb4baf9ec2e31b7385d","source_protocol_hash":"e6edc37f6f89ec6684917f71f20444dd45b6e745f299b8ea6bf165d71e294359","evidence_index_content_sha256":"c94b41c77eed7f10dcb1d319f347458dec00c2d9c4334ee22def536383f7b851"}
def _canonical_json_hash(payload: object)->str:
    encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
def _require_exact_keys(payload: dict[str,Any], expected:set[str], label:str)->None:
    if set(payload)!=expected: raise ValueError(f"PID runtime contract {label} fields are invalid")
def load_pid_runtime_contract(path: Path | str)->dict[str,Any]:
    resolved_contract=Path(path).resolve(); payload=json.loads(resolved_contract.read_text(encoding="utf-8"))
    if not isinstance(payload,dict): raise ValueError("PID runtime contract must be an object")
    _require_exact_keys(payload,{"schema_version","contract","parameters","pid_payload_hash","derived_from"},"top-level")
    if type(payload["schema_version"]) is not int or payload["schema_version"]!=1: raise ValueError("PID runtime contract schema is invalid")
    if payload["contract"]!="inherited_frozen_pid_runtime_contract": raise ValueError("PID runtime contract kind is invalid")
    parameters=payload["parameters"]
    if not isinstance(parameters,dict): raise ValueError("PID runtime parameters must be an object")
    _require_exact_keys(parameters,set(EXPECTED_PARAMETERS),"parameter")
    if any(type(value) not in (int,float) for value in parameters.values()): raise ValueError("PID runtime parameter types are invalid")
    if parameters!=EXPECTED_PARAMETERS: raise ValueError("PID runtime parameter values are invalid")
    if payload["pid_payload_hash"]!=EXPECTED_PAYLOAD_HASH: raise ValueError("PID runtime parameter identity is invalid")
    if _canonical_json_hash(parameters)!=EXPECTED_PAYLOAD_HASH: raise ValueError("PID runtime parameter hash is invalid")
    derived=payload["derived_from"]
    if not isinstance(derived,dict): raise ValueError("PID runtime provenance is invalid")
    _require_exact_keys(derived,set(EXPECTED_DERIVED_FROM),"provenance")
    if not all(isinstance(value,str) for value in derived.values()): raise ValueError("PID runtime provenance types are invalid")
    if derived!=EXPECTED_DERIVED_FROM: raise ValueError("PID runtime provenance identity is invalid")
    archive_root=ARCHIVE_ROOT.resolve(); relative_archive=Path(derived["path"])
    if relative_archive.is_absolute(): raise ValueError("PID runtime archive path must be relative")
    archive_path=(resolved_contract.parent/relative_archive).resolve()
    try: archive_path.relative_to(archive_root)
    except ValueError as exc: raise ValueError("PID runtime archive path escapes the archive root") from exc
    expected_archive=(archive_root/"20_hidden_disturbance_v1"/"provenance"/"hidden_pid_frozen.schema4.json").resolve()
    if archive_path!=expected_archive: raise ValueError("PID runtime archive path is not canonical")
    if not archive_path.is_file(): raise ValueError("archived PID evidence is missing")
    if hashlib.sha256(archive_path.read_bytes()).hexdigest()!=EXPECTED_RAW_SHA256: raise ValueError("archived PID evidence hash is invalid")
    return payload
