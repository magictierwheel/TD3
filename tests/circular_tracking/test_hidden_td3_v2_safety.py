"""Focused protocol-v2 safety checks for the hidden-disturbance TD3 interface."""

from __future__ import annotations

import random

import numpy as np
import torch

from experiments.circular_tracking.rl_envs.hidden_disturbance_td3_env import (
    HiddenDisturbanceCircularTD3Env,
)
from experiments.circular_tracking.scripts.td3.train_hidden_td3 import (
    CorrelatedMotorActionNoise,
    FixedObservationScaleWrapper,
    SafeWarmupActionGenerator,
    build_action_noise_spec,
    build_td3_model,
    build_training_config,
    make_training_environment,
    restore_training_snapshot,
    save_training_snapshot,
    training_profile_probabilities,
)
from experiments.circular_tracking.scripts.td3.evaluate_hidden_td3 import (
    make_evaluation_environment,
)


def test_v2_fixed_physical_observation_scale_is_shared_and_rpm_safe() -> None:
    config = build_training_config(mode="direct_td3", seed=0, total_timesteps=200)
    raw_env = HiddenDisturbanceCircularTD3Env(
        controller_mode="direct_td3", disturbance_profile="standard", rollout_duration_sec=20.0
    )
    scaled_env = FixedObservationScaleWrapper(raw_env)
    try:
        raw_env.reset(seed=9000)
        raw = raw_env._computeObs().copy()
        scaled, _ = scaled_env.reset(seed=9000)
        assert raw.shape == scaled.shape == (260,)
        assert np.max(raw[-4:]) > 10_000.0
        assert np.allclose(scaled[-4:], raw[-4:] / raw_env.MAX_RPM)
        assert float(np.max(np.abs(scaled))) < 10.0
        assert config["observation_normalization"]["kind"] == "fixed_physical_v2"
    finally:
        scaled_env.close()


def test_v2_noise_is_matched_in_actual_rpm_units() -> None:
    direct = build_action_noise_spec("direct_td3")
    residual = build_action_noise_spec("residual_td3")

    assert 0.02 <= direct["behavior_sigma_normalized"] <= 0.03
    assert 0.05 <= direct["target_sigma_normalized"] <= 0.06
    assert 0.10 <= direct["target_clip_normalized"] <= 0.15
    assert np.isclose(direct["behavior_sigma_rpm"], residual["behavior_sigma_rpm"])
    assert np.isclose(direct["target_sigma_rpm"], residual["target_sigma_rpm"])
    assert np.isclose(direct["target_clip_rpm"], residual["target_clip_rpm"])


def test_v2_direct_actor_is_small_unsaturated_and_has_gradient() -> None:
    config = build_training_config(mode="direct_td3", seed=0, total_timesteps=200)
    env = make_training_environment(config)
    try:
        model = build_td3_model(env, config)
        observation, _ = env.reset(seed=0)
        observation_tensor = torch.as_tensor(observation).reshape(1, -1)
        output = model.actor(observation_tensor)
        target_output = model.actor_target(observation_tensor)
        assert torch.max(torch.abs(output)).item() < 0.02
        assert torch.allclose(output, target_output)
        model.actor.zero_grad(set_to_none=True)
        output.sum().backward()
        final_layer = [m for m in model.actor.mu.modules() if isinstance(m, torch.nn.Linear)][-1]
        assert final_layer.weight.grad is not None
        assert torch.count_nonzero(final_layer.weight.grad) > 0
    finally:
        env.close()


def test_v2_warmup_is_smooth_bounded_and_never_uses_full_action_space() -> None:
    generator = SafeWarmupActionGenerator(mode="direct_td3", seed=7)
    actions = np.vstack([generator.sample() for _ in range(100)])
    assert actions.shape == (100, 4)
    assert float(np.max(np.abs(actions))) <= 0.05 + 1e-7
    assert float(np.max(np.abs(np.diff(actions, axis=0)))) <= 0.02 + 1e-7
    assert np.allclose(actions, actions[:, :1])


def test_v2_snapshot_restores_model_replay_steps_and_rng(tmp_path) -> None:
    config = build_training_config(mode="residual_td3", seed=0, total_timesteps=200)
    env = make_training_environment(config)
    try:
        model = build_td3_model(env, config)
        model.num_timesteps = 123
        snapshot = save_training_snapshot(model=model, env=env, output_folder=tmp_path)
        expected_python = random.random()
        expected_numpy = float(np.random.random())
        expected_torch = float(torch.rand(()))
        random.seed(999)
        np.random.seed(999)
        torch.manual_seed(999)
        restored = restore_training_snapshot(snapshot=snapshot, env=env)
        assert restored.num_timesteps == 123
        assert random.random() == expected_python
        assert np.isclose(np.random.random(), expected_numpy)
        assert np.isclose(float(torch.rand(())), expected_torch)
    finally:
        env.close()


def test_v2_evaluation_reuses_the_training_observation_transform() -> None:
    parameters = build_training_config(mode="direct_td3", seed=0, total_timesteps=200)[
        "frozen_pid_parameters"
    ]
    direct = make_evaluation_environment("direct_td3", "standard", parameters)
    residual = make_evaluation_environment("residual_td3", "compound", parameters)
    try:
        assert isinstance(direct, FixedObservationScaleWrapper)
        assert isinstance(residual, FixedObservationScaleWrapper)
        assert direct.observation_space == residual.observation_space
    finally:
        direct.close()
        residual.close()


def test_v21_curriculum_is_identical_for_both_modes_and_reaches_equal_mix() -> None:
    assert np.allclose(training_profile_probabilities(0), [0.75, 0.25, 0.0, 0.0])
    assert np.allclose(training_profile_probabilities(2_000), [0.75, 0.25, 0.0, 0.0])
    assert np.allclose(training_profile_probabilities(5_000), [0.25, 0.25, 0.25, 0.25])
    midpoint = training_profile_probabilities(3_500)
    assert np.allclose(midpoint, [0.5, 0.25, 0.125, 0.125])


def test_v21_mixer_noise_is_zero_at_update_start_and_ramps_afterward() -> None:
    noise = CorrelatedMotorActionNoise(sigma=0.03, clip=0.05, seed=3)
    noise.set_training_step(2_000)
    assert np.allclose(noise(), 0.0)
    noise.set_training_step(5_000)
    sample = noise()
    assert np.max(np.abs(sample)) <= 0.05
    assert not np.allclose(sample, sample[:1])


def test_v21_gate_budgets_admit_only_the_authorized_2k_and_5k_short_runs() -> None:
    assert build_training_config(mode="direct_td3", seed=0, total_timesteps=2_000)["total_timesteps"] == 2_000
    assert build_training_config(mode="residual_td3", seed=1, total_timesteps=5_000)["total_timesteps"] == 5_000
