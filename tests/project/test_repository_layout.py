import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE_CONFIGS = {
    "00_foundation_and_pid": {
        "stage_id": "00_foundation_and_pid",
        "status": "GO",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 0,
        "training_seeds": [],
        "evaluation_seed_partition": "none",
        "controllers": ["pid"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": [],
        "go_rule": "Archived frozen-PID raw SHA-256 and inherited runtime-contract payload hash both match the registered identities.",
        "stop_rule": "Any frozen-PID identity mismatch blocks every later stage.",
    },
    "10_bootstrap_preflight": {
        "stage_id": "10_bootstrap_preflight",
        "status": "NO-GO",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 5000,
        "training_seeds": [0, 1],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "direct_td3", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["00_foundation_and_pid:GO"],
        "go_rule": "The archived v2.1 Gate 3 decision must be GO.",
        "stop_rule": "The archived v2.1 Gate 3 NO-GO blocks Stage A and requires a separately approved method revision.",
    },
    "20_stage_a_20k": {
        "stage_id": "20_stage_a_20k",
        "status": "blocked",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 20000,
        "training_seeds": [0],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["00_foundation_and_pid:GO", "10_bootstrap_preflight:GO"],
        "go_rule": "Not evaluable while protocol/current.json has training_authorized=false; a replacement protocol must define and freeze the GO rule before training.",
        "stop_rule": "10_bootstrap_preflight:NO-GO blocks execution.",
    },
    "30_stage_b_50k": {
        "stage_id": "30_stage_b_50k",
        "status": "not_started",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 50000,
        "training_seeds": [0, 1, 2],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["20_stage_a_20k:GO"],
        "go_rule": "Not evaluable until an authorized replacement protocol freezes a Stage B rule before training.",
        "stop_rule": "Any Stage A result other than GO blocks execution.",
    },
    "40_stage_c_100k": {
        "stage_id": "40_stage_c_100k",
        "status": "not_started",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 100000,
        "training_seeds": [0, 1, 2, 3, 4],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["30_stage_b_50k:GO"],
        "go_rule": "Not evaluable until an authorized replacement protocol freezes a Stage C rule before training.",
        "stop_rule": "Any Stage B result other than GO blocks execution.",
    },
    "50_final_evaluation": {
        "stage_id": "50_final_evaluation",
        "status": "not_started",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 0,
        "training_seeds": [0, 1, 2, 3, 4],
        "evaluation_seed_partition": "test_200_219_and_unseen_300_319",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["40_stage_c_100k:GO"],
        "go_rule": "No optimization or checkpoint selection is permitted; report every paired held-out and unseen result.",
        "stop_rule": "Do not open test or unseen partitions before Stage C GO and protocol freeze.",
    },
}


def test_two_research_lines_exist():
    circular = ROOT / "experiments" / "circular_tracking"
    assert (circular / "matlab_simulink").is_dir()
    assert (circular / "pybullet_td3").is_dir()


def test_current_stage_skeleton_is_complete():
    stages = ROOT / "experiments" / "circular_tracking" / "pybullet_td3" / "studies" / "pid_residual_td3" / "stages"
    assert {p.name for p in stages.iterdir() if p.is_dir()} == set(STAGE_CONFIGS)
    for stage in STAGE_CONFIGS:
        root = stages / stage
        for required in (
            root / "README.md",
            root / "config" / "stage.json",
            root / "manifests" / "README.md",
            root / "evidence" / "README.md",
            root / "runs" / "README.md",
        ):
            assert required.is_file()
        assert json.loads((root / "config" / "stage.json").read_text(encoding="utf-8")) == STAGE_CONFIGS[stage]


def test_retired_research_paths_are_absent():
    retired = (
        "experiments/hover_rl_reproduction",
        "experiments/hover_fixed_point",
        "gym_pybullet_drones/examples/learn.py",
        "gym_pybullet_drones/examples/play.py",
        "gym_pybullet_drones/examples/mrac.py",
    )
    for relative in retired:
        assert not (ROOT / relative).exists(), relative


def tracked_files():
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [Path(item.decode("utf-8")) for item in output.split(b"\0") if item]


def test_required_root_entries_are_visible():
    required = {
        ".github", ".research", "docs", "experiments", "gym_pybullet_drones",
        "reproducibility", "tests", "tools", "README.md", "AGENTS.md",
        "PROJECT_HANDOFF.md", "STATUS.md", "ROADMAP.md", "pyproject.toml",
    }
    assert required <= {path.name for path in ROOT.iterdir()}


def test_workspace_mirror_entries_are_absent():
    for name in ("gym-pybullet-drones", "research_papers", "wt-gpd"):
        assert not (ROOT / name).exists()


def test_nine_simulink_models_are_tracked():
    models = [
        path for path in tracked_files()
        if path.parts[:4] == ("experiments", "circular_tracking", "matlab_simulink", "models")
        and path.suffix == ".slx"
    ]
    assert len(models) == 9


def test_no_tracked_file_exceeds_50_mib():
    oversized = []
    for relative in tracked_files():
        path = ROOT / relative
        if path.is_file() and path.stat().st_size > 50 * 1024 * 1024:
            oversized.append((relative.as_posix(), path.stat().st_size))
    assert oversized == []
