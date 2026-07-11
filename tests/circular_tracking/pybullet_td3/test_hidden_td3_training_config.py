"""Contract tests for the matched hidden-disturbance TD3 trainer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.training.train_hidden_td3 import (
    ALLOWED_TOTAL_TIMESTEPS,
    CHECKPOINT_STEPS,
    TRAINING_PROFILES,
    build_td3_model,
    build_training_config,
    finalize_run,
    make_training_environment,
    prepare_run_directory,
)


def _final_actor_linear(actor: object) -> torch.nn.Linear:
    linears = [
        module
        for module in actor.mu.modules()
        if isinstance(module, torch.nn.Linear)
    ]
    assert linears
    return linears[-1]


def test_direct_and_residual_training_share_nonstructural_hyperparameters():
    direct = build_training_config(
        mode="direct_td3", seed=0, total_timesteps=20_000
    )
    residual = build_training_config(
        mode="residual_td3", seed=0, total_timesteps=20_000
    )

    ignored = {"mode", "action_semantics", "zero_output_initialization", "noise_physical"}
    assert {key: value for key, value in direct.items() if key not in ignored} == {
        key: value for key, value in residual.items() if key not in ignored
    }
    assert direct["td3"] == residual["td3"] == {
        "policy": "MlpPolicy",
        "policy_kwargs": {"net_arch": [256, 256]},
        "learning_rate": 1e-3,
        "batch_size": 256,
        "buffer_size": 1_000_000,
        "learning_starts": 2_000,
        "gamma": 0.99,
        "tau": 0.005,
        "train_freq": 1,
        "gradient_steps": 1,
        "policy_delay": 2,
    }
    assert direct["noise_physical"]["behavior_sigma_rpm"] == residual["noise_physical"]["behavior_sigma_rpm"]
    assert direct["noise_physical"]["target_sigma_rpm"] == residual["noise_physical"]["target_sigma_rpm"]
    assert direct["rollout_duration_sec"] == 20.0
    assert direct["checkpoint_steps"] == list(CHECKPOINT_STEPS)
    assert direct["training_profiles"] == list(TRAINING_PROFILES)
    assert direct["training_profile_probabilities"] == [0.25] * 4


def test_residual_actor_output_is_zeroed_and_direct_actor_output_is_small():
    direct_config = build_training_config(
        mode="direct_td3", seed=0, total_timesteps=200
    )
    residual_config = build_training_config(
        mode="residual_td3", seed=0, total_timesteps=200
    )
    direct_env = make_training_environment(direct_config)
    residual_env = make_training_environment(residual_config)
    try:
        direct_model = build_td3_model(direct_env, direct_config)
        residual_model = build_td3_model(residual_env, residual_config)

        direct_final = _final_actor_linear(direct_model.actor)
        residual_final = _final_actor_linear(residual_model.actor)
        residual_target_final = _final_actor_linear(residual_model.actor_target)

        assert torch.count_nonzero(residual_final.weight) == 0
        assert torch.count_nonzero(residual_final.bias) == 0
        assert torch.count_nonzero(residual_target_final.weight) == 0
        assert torch.count_nonzero(residual_target_final.bias) == 0
        assert torch.count_nonzero(direct_final.weight) > 0
        assert torch.max(torch.abs(direct_final.weight)) <= 3e-3
        assert torch.count_nonzero(direct_final.bias) == 0
    finally:
        direct_env.close()
        residual_env.close()


@pytest.mark.parametrize(
    ("mode", "seed", "total_timesteps"),
    [
        ("pid", 0, 200),
        ("residual_td3_no_gate", 0, 200),
        ("direct_td3", 200, 200),
        ("direct_td3", 300, 200),
        ("direct_td3", 0, 201),
        ("direct_td3", 0, 0),
    ],
)
def test_training_config_rejects_modes_seeds_and_budgets_outside_frozen_scope(
    mode: str,
    seed: int,
    total_timesteps: int,
):
    with pytest.raises((TypeError, ValueError)):
        build_training_config(
            mode=mode,
            seed=seed,
            total_timesteps=total_timesteps,
        )


def test_training_config_has_required_provenance_and_never_exposes_test_or_unseen():
    config = build_training_config(
        mode="residual_td3", seed=4, total_timesteps=100_000
    )

    required = {
        "git_sha",
        "protocol_hash",
        "frozen_pid_parameters",
        "frozen_pid_payload_hash",
        "frozen_pid_config_hash",
        "package_versions",
        "environment_schema",
        "environment_source_sha256",
        "seed",
        "total_timesteps",
        "mode",
        "action_semantics",
        "observation_normalization",
        "noise_physical",
    }
    assert required <= config.keys()
    assert config["seed"] == 4
    assert config["total_timesteps"] == 100_000
    assert set(config["training_profiles"]) == {
        "standard",
        "random_wind",
        "actuator_loss",
        "compound",
    }
    serialized = json.dumps(config, sort_keys=True)
    assert "test" not in config["training_profiles"]
    assert "unseen" not in config["training_profiles"]
    assert '"test"' not in serialized
    assert '"unseen"' not in serialized
    assert ALLOWED_TOTAL_TIMESTEPS == (200, 2_000, 5_000, 20_000, 50_000, 100_000)


def test_run_metadata_is_immutable_and_has_running_and_done_states(tmp_path: Path):
    config = build_training_config(
        mode="direct_td3", seed=0, total_timesteps=200
    )
    output_folder = tmp_path / "task6" / "direct_seed0"
    run_paths = prepare_run_directory(
        output_folder,
        config,
        command=["py", "-3.11", "-m", "hidden_trainer"],
    )

    assert run_paths.output_folder == output_folder
    assert run_paths.checkpoint_folder.is_dir()
    stored_config = json.loads((output_folder / "config.json").read_text(encoding="utf-8"))
    running = json.loads((output_folder / "RUNNING.json").read_text(encoding="utf-8"))
    assert stored_config == config
    assert running["status"] == "running"
    assert running["config_sha256"]
    with pytest.raises(FileExistsError):
        prepare_run_directory(output_folder, config, command=["repeat"])

    finalize_run(run_paths, status="completed", total_timesteps=200)
    done = json.loads((output_folder / "DONE.json").read_text(encoding="utf-8"))
    assert done["status"] == "completed"
    assert done["total_timesteps"] == 200
    assert done["config_sha256"] == running["config_sha256"]
