from __future__ import annotations
from pathlib import Path

def find_repository_root(start: Path | None = None) -> Path:
    cursor = (start or Path(__file__)).resolve()
    if cursor.is_file(): cursor = cursor.parent
    for candidate in (cursor, *cursor.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "experiments").is_dir(): return candidate
    raise RuntimeError("repository root containing pyproject.toml and experiments/ was not found")

REPO_ROOT = find_repository_root()
PYBULLET_TD3_ROOT = REPO_ROOT / "experiments" / "circular_tracking" / "pybullet_td3"
STUDY_ROOT = PYBULLET_TD3_ROOT / "studies" / "pid_residual_td3"
PROTOCOL_PATH = STUDY_ROOT / "protocol" / "current.json"
FROZEN_PID_PATH = STUDY_ROOT / "protocol" / "frozen_pid.json"
ACTIVE_STAGES_ROOT = STUDY_ROOT / "stages"
ENVIRONMENT_SOURCE_PATH = STUDY_ROOT / "code" / "environments" / "hidden_disturbance_td3_env.py"
DISTURBANCE_PROCESS_SOURCE_PATH = STUDY_ROOT / "code" / "environments" / "disturbance_processes.py"
TUNER_SOURCE_PATH = STUDY_ROOT / "code" / "training" / "tune_hidden_pid.py"
TRAINER_SOURCE_PATH = STUDY_ROOT / "code" / "training" / "train_hidden_td3.py"
EVALUATOR_SOURCE_PATH = STUDY_ROOT / "code" / "evaluation" / "evaluate_hidden_td3.py"
SUMMARIZER_SOURCE_PATH = STUDY_ROOT / "code" / "analysis" / "summarize_hidden_td3.py"
STUDY_RUNS_ROOT = ACTIVE_STAGES_ROOT
ARCHIVE_ROOT = PYBULLET_TD3_ROOT / "archive"
