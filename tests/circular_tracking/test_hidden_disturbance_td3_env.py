"""Contract tests for deterministic hidden disturbance processes."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, fields, is_dataclass
import hashlib
import inspect
from itertools import product
import math

import numpy as np
import pytest

import experiments.circular_tracking.rl_envs.disturbance_processes as disturbance_processes_module
import experiments.circular_tracking.rl_envs.hidden_disturbance_td3_env as hidden_env_module
from experiments.circular_tracking.rl_envs.disturbance_processes import (
    HiddenDisturbanceProcess,
    HiddenDisturbanceSample,
)
from experiments.circular_tracking.rl_envs.hidden_disturbance_td3_env import (
    HiddenDisturbanceCircularTD3Env,
)
from gym_pybullet_drones.control.DSLPIDControl import DSLPIDControl
from gym_pybullet_drones.envs.CtrlAviary import CtrlAviary
from gym_pybullet_drones.utils.enums import DroneModel, Physics


SAMPLE_FIELD_NAMES = (
    "wind_x",
    "wind_y",
    "thrust_efficiency",
    "torque_efficiency",
)
GOLDEN_COMPOUND_9025_FINGERPRINT = (
    "fbfc4bcb19f850f153984ae0f3eed0044427ac9de8e0458aa6f6b4e8f9dd95c1"
)


def _schedule_fingerprint(process: HiddenDisturbanceProcess) -> str:
    rows = ["hidden-disturbance-schedule-v1"]
    for time, value in zip(process.knot_times, process.knot_values, strict=True):
        rows.append(
            "\t".join(
                (
                    time.hex(),
                    value.wind_x.hex(),
                    value.wind_y.hex(),
                    value.thrust_efficiency.hex(),
                    value.torque_efficiency.hex(),
                )
            )
        )
    payload = "\n".join(rows).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


class ScriptedGenerator:
    """Minimal deterministic stand-in for the Generator methods under test."""

    def __init__(
        self,
        *,
        random_values: tuple[float, ...],
        uniform_values: tuple[float, ...],
    ) -> None:
        self._random_values = random_values
        self._uniform_values = uniform_values
        self._random_index = 0
        self._uniform_index = 0
        self.calls: list[tuple[object, ...]] = []

    def random(self) -> float:
        if self._random_index >= len(self._random_values):
            raise AssertionError("unexpected extra random() call")
        value = self._random_values[self._random_index]
        self._random_index += 1
        self.calls.append(("random",))
        return value

    def uniform(self, low: float, high: float) -> float:
        if self._uniform_index >= len(self._uniform_values):
            raise AssertionError("unexpected extra uniform() call")
        value = self._uniform_values[self._uniform_index]
        self._uniform_index += 1
        self.calls.append(("uniform", float(low), float(high)))
        return value

    @property
    def exhausted(self) -> bool:
        return (
            self._random_index == len(self._random_values)
            and self._uniform_index == len(self._uniform_values)
        )


def _install_scripted_generator(
    monkeypatch: pytest.MonkeyPatch,
    generator: ScriptedGenerator,
) -> list[int]:
    requested_seeds: list[int] = []
    scripted_bit_generator = object()

    def scripted_pcg64(seed: int) -> object:
        requested_seeds.append(int(seed))
        return scripted_bit_generator

    def scripted_generator(bit_generator: object) -> ScriptedGenerator:
        assert bit_generator is scripted_bit_generator
        return generator

    monkeypatch.setattr(
        disturbance_processes_module.np.random,
        "PCG64",
        scripted_pcg64,
    )
    monkeypatch.setattr(
        disturbance_processes_module.np.random,
        "Generator",
        scripted_generator,
    )
    return requested_seeds


def _expected_interpolation(
    left: HiddenDisturbanceSample,
    right: HiddenDisturbanceSample,
    alpha: float,
) -> HiddenDisturbanceSample:
    return HiddenDisturbanceSample(
        wind_x=(1.0 - alpha) * left.wind_x + alpha * right.wind_x,
        wind_y=(1.0 - alpha) * left.wind_y + alpha * right.wind_y,
        thrust_efficiency=(
            (1.0 - alpha) * left.thrust_efficiency
            + alpha * right.thrust_efficiency
        ),
        torque_efficiency=(
            (1.0 - alpha) * left.torque_efficiency
            + alpha * right.torque_efficiency
        ),
    )


def test_hidden_disturbance_fixed_seed_schedule_has_golden_fingerprint() -> None:
    process = HiddenDisturbanceProcess(
        seed=9025,
        profile="compound",
        horizon_sec=20.0,
    )

    assert _schedule_fingerprint(process) == GOLDEN_COMPOUND_9025_FINGERPRINT


def test_hidden_disturbance_explicit_pcg64_is_independent_of_default_rng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alternate_generator_requests: list[int] = []

    def alternate_default_rng(seed: int) -> np.random.Generator:
        alternate_generator_requests.append(int(seed))
        return np.random.Generator(np.random.PCG64DXSM(int(seed)))

    monkeypatch.setattr(
        disturbance_processes_module.np.random,
        "default_rng",
        alternate_default_rng,
    )

    process = HiddenDisturbanceProcess(
        seed=9025,
        profile="compound",
        horizon_sec=20.0,
    )

    assert _schedule_fingerprint(process) == GOLDEN_COMPOUND_9025_FINGERPRINT
    assert alternate_generator_requests == []


def test_hidden_disturbance_scripted_generator_locks_compound_draw_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_radius_u = 0.25
    second_radius_u = 0.04
    first_angle = math.pi / 3.0
    generator = ScriptedGenerator(
        random_values=(first_radius_u, second_radius_u),
        uniform_values=(
            first_angle,
            0.91,
            0.97,
            1.25,
            0.0,
            0.93,
            0.99,
        ),
    )
    requested_seeds = _install_scripted_generator(monkeypatch, generator)

    process = HiddenDisturbanceProcess(
        seed=9022,
        profile="compound",
        horizon_sec=0.25,
    )

    first = HiddenDisturbanceSample(
        1.5 * math.sqrt(first_radius_u) * math.cos(first_angle),
        1.5 * math.sqrt(first_radius_u) * math.sin(first_angle),
        0.91,
        0.97,
    )
    second = HiddenDisturbanceSample(
        1.5 * math.sqrt(second_radius_u),
        0.0,
        0.93,
        0.99,
    )
    alpha = 0.25 / 1.25

    assert requested_seeds == [9022]
    assert process.knot_times == (0.0, 1.25)
    assert process.knot_values == (first, second)
    assert process.sample(0.0) == first
    assert process.sample(0.25) == _expected_interpolation(first, second, alpha)
    assert generator.calls == [
        ("random",),
        ("uniform", 0.0, 2.0 * math.pi),
        ("uniform", 0.90, 1.00),
        ("uniform", 0.90, 1.00),
        ("uniform", 1.0, 3.0),
        ("random",),
        ("uniform", 0.0, 2.0 * math.pi),
        ("uniform", 0.90, 1.00),
        ("uniform", 0.90, 1.00),
    ]
    assert generator.exhausted


def test_hidden_disturbance_scripted_generator_continues_new_values_to_thirty_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knot_count = 16
    random_values = tuple((index + 1) / 100.0 for index in range(knot_count))
    uniform_values: list[float] = []
    expected_calls: list[tuple[object, ...]] = []
    expected_values: list[HiddenDisturbanceSample] = []

    for index, radius_u in enumerate(random_values):
        if index > 0:
            uniform_values.append(2.0)
            expected_calls.append(("uniform", 1.0, 3.0))
        thrust = 0.901 + 0.001 * index
        torque = 0.951 + 0.001 * index
        uniform_values.extend((0.0, thrust, torque))
        expected_calls.extend(
            (
                ("random",),
                ("uniform", 0.0, 2.0 * math.pi),
                ("uniform", 0.90, 1.00),
                ("uniform", 0.90, 1.00),
            )
        )
        expected_values.append(
            HiddenDisturbanceSample(
                1.5 * math.sqrt(radius_u),
                0.0,
                thrust,
                torque,
            )
        )

    generator = ScriptedGenerator(
        random_values=random_values,
        uniform_values=tuple(uniform_values),
    )
    requested_seeds = _install_scripted_generator(monkeypatch, generator)

    process = HiddenDisturbanceProcess(
        seed=9023,
        profile="compound",
        horizon_sec=30.0,
    )

    expected_times = tuple(float(2 * index) for index in range(knot_count))
    expected_value_tuple = tuple(expected_values)
    post_twenty_values = process.knot_values[11:]
    interval_calls = [
        call
        for call in generator.calls
        if call[0] == "uniform" and call[1:] == (1.0, 3.0)
    ]

    assert requested_seeds == [9023]
    assert process.knot_times == expected_times
    assert process.knot_values == expected_value_tuple
    assert process.knot_times[10] == 20.0
    assert process.knot_times[11:] == (22.0, 24.0, 26.0, 28.0, 30.0)
    assert post_twenty_values == expected_value_tuple[11:]
    assert len(set(post_twenty_values)) == len(post_twenty_values)
    assert all(value != process.knot_values[10] for value in post_twenty_values)
    assert process.sample(21.0) == _expected_interpolation(
        expected_value_tuple[10],
        expected_value_tuple[11],
        0.5,
    )
    assert interval_calls == [("uniform", 1.0, 3.0)] * 15
    assert generator.calls == expected_calls
    assert generator.exhausted


def test_hidden_disturbance_scripted_generator_uses_unseen_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ScriptedGenerator(
        random_values=(0.36, 0.64),
        uniform_values=(0.0, 0.81, 0.89, 0.75, 0.0, 0.82, 0.88),
    )
    requested_seeds = _install_scripted_generator(monkeypatch, generator)

    process = HiddenDisturbanceProcess(
        seed=9024,
        profile="unseen",
        horizon_sec=0.25,
    )

    first = HiddenDisturbanceSample(2.5 * math.sqrt(0.36), 0.0, 0.81, 0.89)
    second = HiddenDisturbanceSample(2.5 * math.sqrt(0.64), 0.0, 0.82, 0.88)

    assert requested_seeds == [9024]
    assert process.knot_times == (0.0, 0.75)
    assert process.knot_values == (first, second)
    assert process.sample(0.0) == first
    assert generator.calls == [
        ("random",),
        ("uniform", 0.0, 2.0 * math.pi),
        ("uniform", 0.80, 0.90),
        ("uniform", 0.80, 0.90),
        ("uniform", 0.5, 1.5),
        ("random",),
        ("uniform", 0.0, 2.0 * math.pi),
        ("uniform", 0.80, 0.90),
        ("uniform", 0.80, 0.90),
    ]
    assert generator.exhausted


def test_hidden_disturbance_sample_is_frozen_slotted_and_scalar() -> None:
    sample = HiddenDisturbanceSample(
        np.float64(0.25),
        np.float32(-0.5),
        np.float64(0.95),
        1,
    )

    assert is_dataclass(sample)
    assert tuple(field.name for field in fields(sample)) == SAMPLE_FIELD_NAMES
    assert not hasattr(sample, "__dict__")
    assert all(type(getattr(sample, name)) is float for name in SAMPLE_FIELD_NAMES)
    assert sample.wind_xy == (0.25, -0.5)
    assert type(sample.wind_xy) is tuple
    assert all(type(component) is float for component in sample.wind_xy)
    assert sample == HiddenDisturbanceSample(0.25, -0.5, 0.95, 1.0)

    with pytest.raises(FrozenInstanceError):
        sample.wind_x = 0.0  # type: ignore[misc]


def test_hidden_disturbance_profiles_are_exactly_the_frozen_set() -> None:
    assert HiddenDisturbanceProcess.PROFILES == {
        "standard",
        "random_wind",
        "actuator_loss",
        "compound",
        "unseen",
    }


def test_hidden_disturbance_same_seed_repeats_independent_of_query_order() -> None:
    forward = HiddenDisturbanceProcess(
        seed=9000,
        profile="compound",
        horizon_sec=20.0,
    )
    reverse = HiddenDisturbanceProcess(
        seed=9000,
        profile="compound",
        horizon_sec=20.0,
    )
    query_times = tuple(float(time) for time in np.linspace(0.0, 20.0, 81))

    forward_values = {time: forward.sample(time) for time in query_times}
    reverse_values = {
        time: reverse.sample(time) for time in reversed(query_times)
    }

    assert forward.knot_times == reverse.knot_times
    assert forward.knot_values == reverse.knot_values
    assert forward_values == reverse_values
    assert [forward.sample(time) for time in reversed(query_times)] == [
        forward_values[time] for time in reversed(query_times)
    ]


def test_hidden_disturbance_does_not_mutate_global_numpy_rng() -> None:
    original_state = np.random.get_state()
    try:
        np.random.seed(9001)
        expected = np.random.random(12)
        np.random.seed(9001)

        process = HiddenDisturbanceProcess(
            seed=9002,
            profile="unseen",
            horizon_sec=30.0,
        )
        for time in (0.0, 7.5, 19.0, 20.0, 29.5, 30.0):
            process.sample(time)

        actual = np.random.random(12)
    finally:
        np.random.set_state(original_state)

    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize(
    (
        "profile",
        "seed",
        "wind_limit",
        "efficiency_min",
        "efficiency_max",
        "wind_enabled",
        "loss_enabled",
    ),
    (
        ("standard", 9003, 0.0, 1.0, 1.0, False, False),
        ("random_wind", 9004, 1.5, 1.0, 1.0, True, False),
        ("actuator_loss", 9005, 0.0, 0.90, 1.0, False, True),
        ("compound", 9006, 1.5, 0.90, 1.0, True, True),
        ("unseen", 9007, 2.5, 0.80, 0.90, True, True),
    ),
)
def test_hidden_disturbance_profile_invariants_and_bounds(
    profile: str,
    seed: int,
    wind_limit: float,
    efficiency_min: float,
    efficiency_max: float,
    wind_enabled: bool,
    loss_enabled: bool,
) -> None:
    process = HiddenDisturbanceProcess(
        seed=seed,
        profile=profile,
        horizon_sec=20.0,
    )
    samples = process.knot_values + tuple(
        process.sample(float(time)) for time in np.linspace(0.0, 20.0, 201)
    )

    assert isinstance(process.knot_times, tuple)
    assert isinstance(process.knot_values, tuple)
    assert process.knot_times[0] == 0.0
    assert process.sample(0.0) == process.knot_values[0]

    for sample in samples:
        assert all(type(getattr(sample, name)) is float for name in SAMPLE_FIELD_NAMES)
        assert np.hypot(*sample.wind_xy) <= wind_limit + 1e-12
        assert efficiency_min <= sample.thrust_efficiency <= efficiency_max
        assert efficiency_min <= sample.torque_efficiency <= efficiency_max
        if not wind_enabled:
            assert sample.wind_xy == (0.0, 0.0)
        if not loss_enabled:
            assert sample.thrust_efficiency == 1.0
            assert sample.torque_efficiency == 1.0


@pytest.mark.parametrize(
    ("profile", "seed", "interval_min", "interval_max"),
    (
        ("random_wind", 9008, 1.0, 3.0),
        ("actuator_loss", 9009, 1.0, 3.0),
        ("compound", 9010, 1.0, 3.0),
        ("unseen", 9011, 0.5, 1.5),
    ),
)
def test_hidden_disturbance_full_intervals_bracket_the_horizon(
    profile: str,
    seed: int,
    interval_min: float,
    interval_max: float,
) -> None:
    process = HiddenDisturbanceProcess(
        seed=seed,
        profile=profile,
        horizon_sec=20.0,
    )
    intervals = np.diff(process.knot_times)

    assert process.knot_times[-1] >= process.horizon_sec
    assert len(process.knot_values) == len(process.knot_times)
    assert np.all(intervals >= interval_min - 1e-12)
    assert np.all(intervals <= interval_max + 1e-12)


@pytest.mark.parametrize(
    ("profile", "seed", "interval_min"),
    (
        ("compound", 9012, 1.0),
        ("unseen", 9013, 0.5),
    ),
)
def test_hidden_disturbance_final_interval_is_never_clipped(
    profile: str,
    seed: int,
    interval_min: float,
) -> None:
    process = HiddenDisturbanceProcess(
        seed=seed,
        profile=profile,
        horizon_sec=0.25,
    )

    assert len(process.knot_times) == 2
    assert process.knot_times[-1] >= interval_min
    assert process.knot_times[-1] > process.horizon_sec


def test_hidden_disturbance_is_exact_at_knots_and_linear_at_midpoints() -> None:
    process = HiddenDisturbanceProcess(
        seed=9014,
        profile="compound",
        horizon_sec=20.0,
    )

    for knot_time, knot_value in zip(process.knot_times, process.knot_values):
        if knot_time <= process.horizon_sec:
            assert process.sample(knot_time) == knot_value

    for index in range(len(process.knot_times) - 1):
        left_time = process.knot_times[index]
        right_time = process.knot_times[index + 1]
        midpoint = left_time + 0.5 * (right_time - left_time)
        if midpoint > process.horizon_sec:
            continue
        expected = _expected_interpolation(
            process.knot_values[index],
            process.knot_values[index + 1],
            0.5,
        )
        actual = process.sample(midpoint)
        np.testing.assert_allclose(
            [getattr(actual, name) for name in SAMPLE_FIELD_NAMES],
            [getattr(expected, name) for name in SAMPLE_FIELD_NAMES],
            rtol=0.0,
            atol=1e-15,
        )


def test_hidden_disturbance_thirty_second_schedule_is_fresh_after_twenty() -> None:
    process = HiddenDisturbanceProcess(
        seed=9015,
        profile="compound",
        horizon_sec=30.0,
    )
    times = process.knot_times

    assert times[-1] >= 30.0
    assert sum(time > 20.0 for time in times) >= 4

    query_time = 25.0
    right_index = int(np.searchsorted(times, query_time, side="right"))
    left_index = right_index - 1
    assert times[left_index] > 20.0
    assert times[right_index] > query_time

    alpha = (query_time - times[left_index]) / (
        times[right_index] - times[left_index]
    )
    assert process.sample(query_time) == _expected_interpolation(
        process.knot_values[left_index],
        process.knot_values[right_index],
        alpha,
    )


def test_hidden_disturbance_rejects_invalid_profile() -> None:
    with pytest.raises(ValueError, match="profile"):
        HiddenDisturbanceProcess(
            seed=9016,
            profile="wind",
            horizon_sec=20.0,
        )


@pytest.mark.parametrize(
    "seed",
    (None, True, False, 9000.0, np.float64(9000.0), "9000"),
)
def test_hidden_disturbance_rejects_noninteger_seed(seed: object) -> None:
    with pytest.raises(TypeError, match="seed"):
        HiddenDisturbanceProcess(
            seed=seed,  # type: ignore[arg-type]
            profile="standard",
            horizon_sec=20.0,
        )


def test_hidden_disturbance_accepts_numpy_integer_seed() -> None:
    process = HiddenDisturbanceProcess(
        seed=np.int64(9017),
        profile="standard",
        horizon_sec=np.float64(20.0),
    )

    assert process.sample(20.0) == HiddenDisturbanceSample(0.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize(
    ("horizon_sec", "error_type"),
    (
        (None, TypeError),
        (True, TypeError),
        ("20", TypeError),
        (0.0, ValueError),
        (-1.0, ValueError),
        (np.nan, ValueError),
        (np.inf, ValueError),
        (-np.inf, ValueError),
    ),
)
def test_hidden_disturbance_rejects_invalid_horizon(
    horizon_sec: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type, match="horizon_sec"):
        HiddenDisturbanceProcess(
            seed=9018,
            profile="standard",
            horizon_sec=horizon_sec,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "time_sec",
    (-1e-12, 20.0000001, np.nan, np.inf, -np.inf),
)
def test_hidden_disturbance_rejects_nonfinite_or_out_of_domain_sample_time(
    time_sec: float,
) -> None:
    process = HiddenDisturbanceProcess(
        seed=9019,
        profile="compound",
        horizon_sec=20.0,
    )

    with pytest.raises(ValueError, match="time_sec"):
        process.sample(time_sec)


def test_hidden_disturbance_accepts_both_closed_domain_boundaries() -> None:
    process = HiddenDisturbanceProcess(
        seed=9020,
        profile="unseen",
        horizon_sec=20.0,
    )

    assert process.sample(np.float64(0.0)) == process.knot_values[0]
    assert isinstance(process.sample(np.float64(20.0)), HiddenDisturbanceSample)


def test_hidden_disturbance_constructor_arguments_are_explicit() -> None:
    with pytest.raises(TypeError):
        HiddenDisturbanceProcess(profile="standard", horizon_sec=20.0)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        HiddenDisturbanceProcess(seed=9021, profile="standard")  # type: ignore[call-arg]


def test_hidden_environment_has_exact_supported_controller_modes() -> None:
    assert HiddenDisturbanceCircularTD3Env.SUPPORTED_CONTROLLER_MODES == frozenset(
        {
            "pid",
            "direct_td3",
            "residual_td3",
            "residual_td3_no_gate",
        }
    )


def test_hidden_environment_directly_subclasses_ctrl_aviary_and_pins_timing() -> None:
    env = HiddenDisturbanceCircularTD3Env(
        controller_mode="pid",
        disturbance_profile="standard",
        rollout_duration_sec=20.0,
    )
    try:
        assert type(env).__bases__ == (CtrlAviary,)
        assert env.PHYSICS is Physics.PYB
        assert env.PYB_FREQ == 240
        assert env.CTRL_FREQ == 48
        assert env.PYB_STEPS_PER_CTRL == 5
    finally:
        env.close()


@contextmanager
def _environment(
    controller_mode: str,
    *,
    disturbance_profile: str = "standard",
    rollout_duration_sec: float = 20.0,
    **pid_shaping: object,
) -> Iterator[HiddenDisturbanceCircularTD3Env]:
    env = HiddenDisturbanceCircularTD3Env(
        controller_mode=controller_mode,
        disturbance_profile=disturbance_profile,
        rollout_duration_sec=rollout_duration_sec,
        **pid_shaping,
    )
    try:
        yield env
    finally:
        env.close()


def _pid_state_fingerprint(env: HiddenDisturbanceCircularTD3Env) -> tuple[object, ...]:
    controller = env._pid_controller
    return (
        controller.control_counter,
        controller.last_rpy.tobytes(),
        controller.last_pos_e.tobytes(),
        controller.integral_pos_e.tobytes(),
        controller.last_rpy_e.tobytes(),
        controller.integral_rpy_e.tobytes(),
    )


def _history_copy(env: HiddenDisturbanceCircularTD3Env) -> tuple[np.ndarray, ...]:
    return tuple(frame.copy() for frame in env._history)


def _array_fingerprint(value: object) -> tuple[object, ...]:
    array = np.asarray(value)
    return (array.shape, array.dtype.str, array.tobytes())


def _runtime_fingerprint(
    env: HiddenDisturbanceCircularTD3Env,
) -> tuple[object, ...]:
    live_position, live_orientation = hidden_env_module.p.getBasePositionAndOrientation(
        env.DRONE_IDS[0],
        physicsClientId=env.CLIENT,
    )
    live_velocity, live_angular_velocity = hidden_env_module.p.getBaseVelocity(
        env.DRONE_IDS[0],
        physicsClientId=env.CLIENT,
    )
    return (
        env.step_counter,
        env._completed_physics_substeps,
        env._physics_substeps_started,
        getattr(env, "_episode_done", None),
        getattr(env, "_reset_required", None),
        _pid_state_fingerprint(env),
        _array_fingerprint(env._pid_rpm_cache),
        _array_fingerprint(env._last_policy_action),
        _array_fingerprint(env._last_applied_rpm),
        _array_fingerprint(env._previous_applied_rpm),
        tuple(_array_fingerprint(frame) for frame in env._history),
        _array_fingerprint(env.pos),
        _array_fingerprint(env.quat),
        _array_fingerprint(env.rpy),
        _array_fingerprint(env.vel),
        _array_fingerprint(env.ang_v),
        _array_fingerprint(live_position),
        _array_fingerprint(live_orientation),
        _array_fingerprint(live_velocity),
        _array_fingerprint(live_angular_velocity),
        env._last_applied_disturbance,
    )


def _valid_action(controller_mode: str) -> np.ndarray:
    shape = (1,) if controller_mode == "pid" else (4,)
    return np.zeros(shape, dtype=np.float32)


def _invalid_action(controller_mode: str, case: str) -> object:
    shape = (1,) if controller_mode == "pid" else (4,)
    if case == "python_scalar":
        return 0.0
    if case == "zero_dimensional":
        return np.array(0.0)
    if case == "two_dimensional":
        return np.zeros((1, 4), dtype=np.float32)
    if case == "wrong_length":
        return np.zeros(2 if controller_mode == "pid" else 3, dtype=np.float32)
    if case == "boolean":
        return np.zeros(shape, dtype=bool)
    if case == "non_real":
        return np.full(shape, "bad", dtype=object)
    if case == "complex":
        return np.zeros(shape, dtype=np.complex128)
    if case == "nan":
        return np.full(shape, np.nan)
    if case == "positive_infinity":
        return np.full(shape, np.inf)
    if case == "negative_infinity":
        return np.full(shape, -np.inf)
    if case == "above_range":
        return np.full(shape, 1.000001)
    if case == "below_range":
        return np.full(shape, -1.000001)
    raise AssertionError(f"unknown invalid-action case: {case}")


@pytest.mark.parametrize(
    "controller_mode",
    ("direct_td3", "residual_td3", "residual_td3_no_gate"),
)
def test_hidden_environment_td3_modes_have_matched_four_vector_action_spaces(
    controller_mode: str,
) -> None:
    env = HiddenDisturbanceCircularTD3Env(
        controller_mode=controller_mode,
        disturbance_profile="standard",
        rollout_duration_sec=20.0,
    )
    try:
        assert env.action_space.shape == (4,)
        assert env.action_space.dtype == np.dtype(np.float32)
        np.testing.assert_array_equal(env.action_space.low, -np.ones(4))
        np.testing.assert_array_equal(env.action_space.high, np.ones(4))
    finally:
        env.close()


def test_hidden_environment_rejects_unsupported_controller_mode() -> None:
    with pytest.raises(ValueError, match="controller_mode"):
        HiddenDisturbanceCircularTD3Env(
            controller_mode="oracle_td3",
            disturbance_profile="standard",
            rollout_duration_sec=20.0,
        )


def test_hidden_environment_rejects_unsupported_disturbance_profile() -> None:
    with pytest.raises(ValueError, match="disturbance_profile"):
        HiddenDisturbanceCircularTD3Env(
            controller_mode="pid",
            disturbance_profile="wind",
            rollout_duration_sec=20.0,
        )


@pytest.mark.parametrize(
    ("rollout_duration_sec", "error_type"),
    (
        (None, TypeError),
        (True, TypeError),
        ("20", TypeError),
        (0.0, ValueError),
        (-1.0, ValueError),
        (np.nan, ValueError),
        (np.inf, ValueError),
        (-np.inf, ValueError),
    ),
)
def test_hidden_environment_rejects_invalid_rollout_duration(
    rollout_duration_sec: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type, match="rollout_duration_sec"):
        HiddenDisturbanceCircularTD3Env(
            controller_mode="pid",
            disturbance_profile="standard",
            rollout_duration_sec=rollout_duration_sec,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "action",
    (
        np.array([0.0, -1.0, 1.0, 0.25], dtype=np.float32),
        np.array([-1.0, 1.0, 0.5, -0.5], dtype=np.float32),
    ),
)
def test_direct_td3_action_mapping_uses_hover_centered_span_and_final_clipping(
    action: np.ndarray,
) -> None:
    with _environment("direct_td3") as env:
        expected = np.clip(
            env.HOVER_RPM + action * (env.MAX_RPM - env.HOVER_RPM),
            0.0,
            env.MAX_RPM,
        )

        actual = env._preprocessAction(action)

        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)


@pytest.mark.parametrize(
    "action",
    (
        np.zeros(4, dtype=np.float32),
        np.array([-1.0, 0.25, 1.0, 1.0], dtype=np.float32),
    ),
)
def test_residual_no_gate_action_mapping_uses_pid_plus_bounded_residual(
    action: np.ndarray,
) -> None:
    with _environment("residual_td3_no_gate") as env:
        pid_rpm = env.MAX_RPM * np.array([0.05, 0.50, 0.95, 1.00])
        env._pid_rpm_cache = pid_rpm.copy()
        expected = np.clip(
            pid_rpm + action * (0.10 * env.MAX_RPM),
            0.0,
            env.MAX_RPM,
        )

        actual = env._preprocessAction(action)

        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)


def test_pid_action_mapping_ignores_dummy_action_and_returns_cached_command() -> None:
    with _environment("pid") as env:
        pid_rpm = env.MAX_RPM * np.array([0.2, 0.4, 0.6, 0.8])
        env._pid_rpm_cache = pid_rpm.copy()

        actual = env._preprocessAction(np.array([0.75], dtype=np.float32))

        np.testing.assert_allclose(actual, pid_rpm, rtol=0.0, atol=0.0)


def test_td3_policy_observation_contract_is_shared_at_reset_and_after_step() -> None:
    with (
        _environment("direct_td3") as direct,
        _environment("residual_td3") as residual,
        _environment("residual_td3_no_gate") as no_gate,
    ):
        direct_obs, _ = direct.reset(seed=9030)
        residual_obs, _ = residual.reset(seed=9030)
        no_gate_obs, _ = no_gate.reset(seed=9030)

        expected_td3_schema = (
            "position",
            "velocity",
            "attitude",
            "angular_velocity",
            "reference_position",
            "reference_velocity",
            "position_error",
            "velocity_error",
            "last_policy_action",
            "applied_motor_rpm",
            "pid_rpm",
        )
        assert direct.SENSOR_NOISE_MODEL == "none"
        assert direct.HISTORY_LENGTH == 8
        assert direct.HISTORY_FRAME_SIZE == 32
        for env, observation in (
            (direct, direct_obs),
            (residual, residual_obs),
            (no_gate, no_gate_obs),
        ):
            assert env.observation_schema == expected_td3_schema
            assert observation.shape == (8 * 32 + 4,)
            assert env.observation_space.contains(observation)
            np.testing.assert_array_equal(
                env.observation_space.low,
                direct.observation_space.low,
            )
            np.testing.assert_array_equal(
                env.observation_space.high,
                direct.observation_space.high,
            )

        for env in (direct, residual, no_gate):
            observation, _, _, _, _ = env.step(np.zeros(4, dtype=np.float32))
            assert env.observation_schema == expected_td3_schema
            assert observation.shape == (8 * 32 + 4,)
            assert env.observation_space.contains(observation)
            np.testing.assert_array_equal(
                env.observation_space.low,
                direct.observation_space.low,
            )
            np.testing.assert_array_equal(
                env.observation_space.high,
                direct.observation_space.high,
            )


def test_direct_td3_observation_ends_with_current_cached_pid_rpm() -> None:
    with _environment("direct_td3") as env:
        reset_observation, _ = env.reset(seed=9031)
        np.testing.assert_array_equal(
            reset_observation[-4:],
            env._pid_rpm_cache.astype(reset_observation.dtype),
        )

        step_observation, _, _, _, _ = env.step(np.zeros(4, dtype=np.float32))

        np.testing.assert_array_equal(
            step_observation[-4:],
            env._pid_rpm_cache.astype(step_observation.dtype),
        )


def test_compute_obs_is_idempotent_and_pid_and_history_pure() -> None:
    with _environment("residual_td3") as env:
        reset_obs, _ = env.reset(seed=9031)
        history_before = _history_copy(env)
        pid_before = _pid_state_fingerprint(env)

        obs_a = env._computeObs()
        obs_b = env._computeObs()

        np.testing.assert_array_equal(obs_a, reset_obs)
        np.testing.assert_array_equal(obs_b, reset_obs)
        assert _pid_state_fingerprint(env) == pid_before
        for before, after in zip(
            history_before,
            _history_copy(env),
            strict=True,
        ):
            np.testing.assert_array_equal(after, before)


def test_pid_cache_and_history_advance_exactly_once_per_control_step() -> None:
    with _environment("residual_td3") as env:
        env.reset(seed=9032)
        assert env._pid_controller.control_counter == 1
        assert env._completed_physics_substeps == 0
        history_before = _history_copy(env)

        env.step(np.zeros(4, dtype=np.float32))

        assert env._pid_controller.control_counter == 2
        assert env._completed_physics_substeps == 5
        history_after = _history_copy(env)
        assert len(history_after) == env.HISTORY_LENGTH
        for expected, actual in zip(
            history_before[1:],
            history_after[:-1],
            strict=True,
        ):
            np.testing.assert_array_equal(actual, expected)

        pid_after_step = _pid_state_fingerprint(env)
        history_after_step = _history_copy(env)
        env._computeObs()
        env._computeObs()
        assert _pid_state_fingerprint(env) == pid_after_step
        for before, after in zip(
            history_after_step,
            _history_copy(env),
            strict=True,
        ):
            np.testing.assert_array_equal(after, before)


@pytest.mark.parametrize(
    ("position_error", "expected_gate"),
    (
        (0.0, 0.0),
        (0.03, 0.0),
        (0.115, 0.5),
        (0.20, 1.0),
        (0.50, 1.0),
    ),
)
def test_observable_gate_uses_exact_position_error_thresholds(
    position_error: float,
    expected_gate: float,
) -> None:
    with _environment("residual_td3") as env:
        env.reset(seed=9033)
        reference_position, _ = env._reference_at_time(0.0)
        env.pos[0] = reference_position - np.array([position_error, 0.0, 0.0])
        env._pid_rpm_cache = np.full(4, 0.5 * env.MAX_RPM)

        assert env._compute_gate() == pytest.approx(expected_gate, abs=1e-15)


@pytest.mark.parametrize(
    ("pid_fraction", "expected_gate"),
    (
        (0.00, 0.0),
        (0.05, 0.5),
        (0.10, 1.0),
        (0.50, 1.0),
        (0.95, 0.5),
        (1.00, 0.0),
    ),
)
def test_observable_gate_uses_exact_pid_headroom_thresholds(
    pid_fraction: float,
    expected_gate: float,
) -> None:
    with _environment("residual_td3") as env:
        env.reset(seed=9034)
        reference_position, _ = env._reference_at_time(0.0)
        env.pos[0] = reference_position - np.array([0.20, 0.0, 0.0])
        env._pid_rpm_cache = np.full(4, pid_fraction * env.MAX_RPM)

        assert env._compute_gate() == pytest.approx(expected_gate, abs=1e-15)


def test_no_gate_ablation_is_exactly_one_and_gate_ignores_hidden_truth() -> None:
    with (
        _environment("residual_td3") as gated,
        _environment("residual_td3_no_gate") as no_gate,
    ):
        gated.reset(seed=9035)
        no_gate.reset(seed=9035)
        reference_position, _ = gated._reference_at_time(0.0)
        observable_position = reference_position - np.array([0.115, 0.0, 0.0])
        for env in (gated, no_gate):
            env.pos[0] = observable_position.copy()
            env._pid_rpm_cache = np.full(4, 0.05 * env.MAX_RPM)

        gated._last_applied_disturbance = HiddenDisturbanceSample(
            1.0,
            -0.5,
            0.90,
            0.95,
        )
        gate_a = gated._compute_gate()
        gated._last_applied_disturbance = HiddenDisturbanceSample(
            -1.0,
            0.5,
            1.0,
            1.0,
        )
        gate_b = gated._compute_gate()

        assert gate_a == pytest.approx(0.25, abs=1e-15)
        assert gate_b == gate_a
        assert no_gate._compute_gate() == 1.0


def test_gated_residual_mapping_uses_observable_gate_and_clipped_final_rpm() -> None:
    with _environment("residual_td3") as env:
        env.reset(seed=9036)
        reference_position, _ = env._reference_at_time(0.0)
        env.pos[0] = reference_position - np.array([0.20, 0.0, 0.0])
        pid_rpm = env.MAX_RPM * np.array([0.05, 0.50, 0.95, 0.50])
        env._pid_rpm_cache = pid_rpm.copy()
        action = np.array([-1.0, -1.0, 1.0, 1.0], dtype=np.float32)
        gate = env._compute_gate()
        expected = np.clip(
            pid_rpm + gate * action * (0.10 * env.MAX_RPM),
            0.0,
            env.MAX_RPM,
        )

        actual = env._preprocessAction(action)

        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)


def test_shared_reward_matches_frozen_nonterminal_formula_using_applied_rpm() -> None:
    with _environment("direct_td3") as env:
        env.reset(seed=9037)
        reference_position, reference_velocity = env._reference_at_time(0.0)
        env.pos[0] = reference_position + np.array([0.6, -0.8, 0.2])
        env.vel[0] = reference_velocity + np.array([0.3, -0.4, 0.5])
        env.rpy[0] = np.array([0.3, -0.4, 1.2])
        env._last_policy_action = np.array([99.0, -99.0, 50.0, -50.0])
        env._last_applied_rpm = env.MAX_RPM * np.array([0.0, 0.25, 0.50, 1.0])
        env._previous_applied_rpm = env.MAX_RPM * np.array([0.10, 0.20, 0.40, 0.90])

        position_error_norm = np.linalg.norm(reference_position - env.pos[0]) / 2.0
        velocity_error_norm = np.linalg.norm(reference_velocity - env.vel[0]) / 3.0
        altitude_error_norm = abs(env.pos[0, 2] - reference_position[2]) / 2.0
        tilt_norm = np.linalg.norm(env.rpy[0, :2]) / math.pi
        energy = np.mean((env._last_applied_rpm / env.MAX_RPM) ** 2)
        smoothness = (
            np.mean(
                np.abs(env._last_applied_rpm - env._previous_applied_rpm)
            )
            / env.MAX_RPM
        )
        saturation = np.mean(
            (env._last_applied_rpm <= 0.0)
            | (env._last_applied_rpm >= env.MAX_RPM)
        )
        expected = -(
            2.0 * position_error_norm
            + 0.5 * velocity_error_norm
            + 1.0 * altitude_error_norm
            + 0.2 * tilt_norm
            + 0.05 * energy
            + 0.05 * smoothness
            + 2.0 * saturation
        )

        assert env._computeReward() == pytest.approx(expected, abs=1e-15)


def test_identical_state_and_applied_rpm_have_identical_reward_across_td3_modes() -> None:
    with (
        _environment("direct_td3") as direct,
        _environment("residual_td3") as residual,
        _environment("residual_td3_no_gate") as no_gate,
    ):
        for env in (direct, residual, no_gate):
            env.reset(seed=9038)
            reference_position, reference_velocity = env._reference_at_time(0.0)
            env.pos[0] = reference_position + np.array([0.2, -0.1, 0.05])
            env.vel[0] = reference_velocity + np.array([0.4, 0.1, -0.2])
            env.rpy[0] = np.array([0.1, -0.2, 0.7])
            env._last_applied_rpm = env.MAX_RPM * np.array([0.2, 0.4, 0.6, 0.8])
            env._previous_applied_rpm = env.MAX_RPM * np.array([0.1, 0.3, 0.5, 0.7])
        direct._last_policy_action = np.full(4, 50.0)
        residual._last_policy_action = np.full(4, -50.0)
        no_gate._last_policy_action = np.array([1.0, -1.0, 1.0, -1.0])

        rewards = [env._computeReward() for env in (direct, residual, no_gate)]

        assert rewards[1] == pytest.approx(rewards[0], abs=0.0)
        assert rewards[2] == pytest.approx(rewards[0], abs=0.0)


@pytest.mark.parametrize(
    "controller_mode",
    ("direct_td3", "residual_td3", "residual_td3_no_gate"),
)
def test_td3_truth_profile_and_seed_do_not_change_policy_observation_gate_or_reward(
    controller_mode: str,
) -> None:
    with (
        _environment(controller_mode, disturbance_profile="compound") as compound,
        _environment(controller_mode, disturbance_profile="unseen") as unseen,
    ):
        compound.reset(seed=9039)
        unseen.reset(seed=9040)
        shared_pid_rpm = compound.MAX_RPM * np.array([0.20, 0.35, 0.50, 0.65])
        shared_applied_rpm = compound.MAX_RPM * np.array([0.25, 0.40, 0.55, 0.70])
        shared_previous_rpm = compound.MAX_RPM * np.array([0.20, 0.30, 0.50, 0.60])
        for env in (compound, unseen):
            env._pid_rpm_cache = shared_pid_rpm.copy()
            env._last_applied_rpm = shared_applied_rpm.copy()
            env._previous_applied_rpm = shared_previous_rpm.copy()
        compound._last_applied_disturbance = HiddenDisturbanceSample(
            1.0,
            -0.5,
            0.90,
            0.92,
        )
        unseen._last_applied_disturbance = HiddenDisturbanceSample(
            -2.0,
            1.0,
            0.80,
            0.85,
        )

        compound_obs = compound._computeObs()
        unseen_obs = unseen._computeObs()

        np.testing.assert_array_equal(compound_obs, unseen_obs)
        assert compound._compute_gate() == unseen._compute_gate()
        assert compound._computeReward() == unseen._computeReward()
        forbidden_tokens = (
            "wind",
            "efficiency",
            "profile",
            "seed",
            "disturbance",
            "scenario",
        )
        assert all(
            token not in field
            for field in compound.observation_schema
            for token in forbidden_tokens
        )


def test_terminal_transition_contains_failure_penalty_and_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _environment("direct_td3", disturbance_profile="standard") as env:
        env.reset(seed=9061)
        state = env._getDroneStateVector(0).copy()
        reference_position, _ = env._reference_at_time(0.0)
        state[0:2] = reference_position[0:2] + np.array([2.1, 0.0])
        monkeypatch.setattr(env, "_getDroneStateVector", lambda _: state.copy())

        _, reward, terminated, truncated, info = env.step(
            _valid_action("direct_td3")
        )

        assert terminated is True
        assert truncated is False
        assert info["failure_reason"] == "horizontal_error_limit"
        assert env.failure_penalty == 50.0
        assert reward < -45.0


def test_terminal_penalty_changes_reward_by_exactly_fifty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _environment("direct_td3", disturbance_profile="standard") as env:
        env.reset(seed=9062)
        state = env._getDroneStateVector(0).copy()
        safe_state = state.copy()
        failing_state = state.copy()
        reference_position, _ = env._reference_at_time(0.0)
        failing_state[0:2] = reference_position[0:2] + np.array([2.1, 0.0])
        current = safe_state
        monkeypatch.setattr(
            env,
            "_getDroneStateVector",
            lambda _: current.copy(),
        )

        safe_reward = env._computeReward()
        current = failing_state
        failing_reward = env._computeReward()

        assert safe_reward - failing_reward == pytest.approx(50.0, abs=1e-15)


@pytest.mark.parametrize(
    ("mutator", "expected"),
    (
        (lambda state, ref: state.__setitem__(0, np.nan), "non_finite_state"),
        (lambda state, ref: state.__setitem__(2, 3.1), "altitude_limit"),
        (lambda state, ref: state.__setitem__(7, 0.91), "tilt_limit"),
        (
            lambda state, ref: state.__setitem__(slice(0, 2), ref[:2] + [2.01, 0.0]),
            "horizontal_error_limit",
        ),
        (lambda state, ref: None, ""),
    ),
)
def test_failure_reason_priority_matrix(
    monkeypatch: pytest.MonkeyPatch,
    mutator: object,
    expected: str,
) -> None:
    with _environment("pid", disturbance_profile="standard") as env:
        env.reset(seed=9063)
        state = env._getDroneStateVector(0).copy()
        reference_position, _ = env._reference_at_time(0.0)
        mutator(state, reference_position)  # type: ignore[operator]
        monkeypatch.setattr(env, "_getDroneStateVector", lambda _: state.copy())
        assert env._failure_reason_for_current_state() == expected


@pytest.mark.parametrize(
    ("field", "value", "outside", "reference_z"),
    (
        ("altitude", 0.1, np.nextafter(0.1, -np.inf), -1.4),
        ("altitude", 3.0, np.nextafter(3.0, np.inf), 1.5),
        ("altitude_error", 2.5, np.nextafter(2.5, np.inf), 1.0),
        ("roll", 0.9, np.nextafter(0.9, np.inf), 1.0),
        ("pitch", 0.9, np.nextafter(0.9, np.inf), 1.0),
        ("horizontal", 2.0, np.nextafter(2.0, np.inf), 1.0),
    ),
)
def test_failure_boundaries_are_strictly_exceeded(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: float,
    outside: float,
    reference_z: float,
) -> None:
    with _environment("pid", disturbance_profile="standard") as env:
        env.reset(seed=9064)
        state = env._getDroneStateVector(0).copy()
        reference_position, reference_velocity = env._reference_at_time(0.0)
        reference_position = reference_position.copy()
        reference_position[2] = reference_z
        monkeypatch.setattr(
            env,
            "_reference_at_time",
            lambda _: (reference_position.copy(), reference_velocity.copy()),
        )

        def set_field(target: np.ndarray, target_value: float) -> None:
            target[:] = env._getDroneStateVector(0)
            if field == "altitude":
                target[2] = target_value
            elif field == "altitude_error":
                target[2] = target_value
            elif field == "roll":
                target[7] = target_value
            elif field == "pitch":
                target[8] = target_value
            elif field == "horizontal":
                target[0:2] = reference_position[:2] + np.array(
                    [target_value, 0.0]
                )
            else:  # pragma: no cover - parameter table is exhaustive
                raise AssertionError(field)

        set_field(state, value)
        monkeypatch.setattr(env, "_getDroneStateVector", lambda _: state.copy())
        assert env._failure_reason_for_current_state() == ""

        set_field(state, outside)
        reason = env._failure_reason_for_current_state()
        assert reason in {"altitude_limit", "tilt_limit", "horizontal_error_limit"}


def test_failure_helper_is_pure_uncached_and_uses_completed_substep_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _environment("pid", disturbance_profile="standard") as env:
        env.reset(seed=9065)
        env.step(_valid_action("pid"))
        state = env._getDroneStateVector(0).copy()
        before = _runtime_fingerprint(env)
        reference_calls: list[float] = []
        original_reference = env._reference_at_time

        def recording_reference(time_sec: float) -> tuple[np.ndarray, np.ndarray]:
            reference_calls.append(float(time_sec))
            return original_reference(time_sec)

        monkeypatch.setattr(env, "_reference_at_time", recording_reference)
        monkeypatch.setattr(env, "_getDroneStateVector", lambda _: state.copy())
        assert env._failure_reason_for_current_state() == ""
        assert reference_calls == [pytest.approx(5.0 / 240.0)]
        assert _runtime_fingerprint(env) == before

        state[0:2] += np.array([2.1, 0.0])
        assert env._failure_reason_for_current_state() == "horizontal_error_limit"
        assert _runtime_fingerprint(env) == before


def test_reward_termination_and_info_call_failure_helper_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _environment("direct_td3", disturbance_profile="standard") as env:
        env.reset(seed=9066)
        calls = 0
        original_helper = env._failure_reason_for_current_state

        def counted_helper() -> str:
            nonlocal calls
            calls += 1
            return original_helper()

        monkeypatch.setattr(env, "_failure_reason_for_current_state", counted_helper)
        env._computeReward()
        env._computeTerminated()
        info = env._computeInfo()
        assert calls == 3
        assert info["failure_reason"] == ""


@pytest.mark.parametrize(
    ("state_field", "bad_value"),
    (
        ("pos", np.nan),
        ("vel", np.inf),
    ),
)
def test_nonfinite_state_reward_fails_closed_without_mutating_runtime(
    state_field: str,
    bad_value: float,
) -> None:
    with _environment("direct_td3", disturbance_profile="standard") as env:
        env.reset(seed=9067)
        state_array = getattr(env, state_field)
        state_array[0, 0] = bad_value
        before = _runtime_fingerprint(env)

        reason = env._failure_reason_for_current_state()
        reward = env._computeReward()
        terminated = env._computeTerminated()

        assert reason == "non_finite_state"
        assert np.isfinite(reward)
        assert reward == pytest.approx(-50.0, abs=0.0)
        assert terminated is True
        after = _runtime_fingerprint(env)
        assert after == before


def test_huge_finite_state_reward_overflow_fails_closed() -> None:
    with _environment("direct_td3", disturbance_profile="standard") as env:
        env.reset(seed=9068)
        env.pos[0, 0] = 1.0e308

        reward = env._computeReward()

        assert env._failure_reason_for_current_state() == "horizontal_error_limit"
        assert np.isfinite(reward)
        assert reward == pytest.approx(-50.0, abs=0.0)


def test_circular_reference_has_frozen_radius_period_height_and_velocity() -> None:
    with _environment("pid") as env:
        position_0, velocity_0 = env._reference_at_time(0.0)
        position_quarter, velocity_quarter = env._reference_at_time(2.5)
        position_period, velocity_period = env._reference_at_time(10.0)

        np.testing.assert_allclose(position_0, [0.3, 0.0, 1.0], atol=1e-15)
        np.testing.assert_allclose(
            velocity_0,
            [0.0, 0.3 * 2.0 * math.pi / 10.0, 0.0],
            atol=1e-15,
        )
        np.testing.assert_allclose(position_quarter, [0.0, 0.3, 1.0], atol=1e-15)
        np.testing.assert_allclose(
            velocity_quarter,
            [-0.3 * 2.0 * math.pi / 10.0, 0.0, 0.0],
            atol=1e-15,
        )
        np.testing.assert_allclose(position_period, position_0, atol=1e-15)
        np.testing.assert_allclose(velocity_period, velocity_0, atol=1e-15)


def test_disturbance_is_sampled_once_at_each_exact_physics_substep_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_times: list[float] = []
    original_sample = HiddenDisturbanceProcess.sample

    def recording_sample(
        process: HiddenDisturbanceProcess,
        time_sec: float,
    ) -> HiddenDisturbanceSample:
        sample_times.append(float(time_sec))
        return original_sample(process, time_sec)

    monkeypatch.setattr(HiddenDisturbanceProcess, "sample", recording_sample)
    with _environment("pid", disturbance_profile="compound") as env:
        env.reset(seed=9041)
        env.step(np.zeros(1, dtype=np.float32))
        env.step(np.zeros(1, dtype=np.float32))

        np.testing.assert_allclose(
            sample_times,
            np.arange(10, dtype=float) / 240.0,
            rtol=0.0,
            atol=0.0,
        )
        assert env._completed_physics_substeps == 10


def test_hidden_physics_uses_live_world_position_incremental_wind_and_separate_efficiencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    force_calls: list[dict[str, object]] = []
    torque_calls: list[dict[str, object]] = []
    base_position = np.array([1.25, -0.75, 1.10])
    base_velocity = np.array([2.0, -1.0, 0.5])

    def get_base_pose(body_id: int, *, physicsClientId: int) -> tuple[object, object]:
        assert body_id == env.DRONE_IDS[0]
        assert physicsClientId == env.CLIENT
        return base_position.copy(), np.array([0.0, 0.0, 0.0, 1.0])

    def get_base_velocity(
        body_id: int,
        *,
        physicsClientId: int,
    ) -> tuple[object, object]:
        assert body_id == env.DRONE_IDS[0]
        assert physicsClientId == env.CLIENT
        return base_velocity.copy(), np.zeros(3)

    def record_force(
        bodyUniqueId: int,
        linkIndex: int,
        forceObj: object,
        posObj: object,
        flags: int,
        *,
        physicsClientId: int,
    ) -> None:
        force_calls.append(
            {
                "body": bodyUniqueId,
                "link": linkIndex,
                "force": np.asarray(forceObj, dtype=float),
                "position": np.asarray(posObj, dtype=float),
                "flags": flags,
                "client": physicsClientId,
            }
        )

    def record_torque(
        bodyUniqueId: int,
        linkIndex: int,
        torqueObj: object,
        flags: int,
        *,
        physicsClientId: int,
    ) -> None:
        torque_calls.append(
            {
                "body": bodyUniqueId,
                "link": linkIndex,
                "torque": np.asarray(torqueObj, dtype=float),
                "flags": flags,
                "client": physicsClientId,
            }
        )

    with _environment("pid", disturbance_profile="compound") as env:
        env.reset(seed=9042)
        fixed_sample = HiddenDisturbanceSample(1.0, -0.5, 0.80, 0.60)
        assert env._disturbance_process is not None
        env._disturbance_process._knot_times = (0.0,)
        env._disturbance_process._knot_values = (fixed_sample,)
        monkeypatch.setattr(
            hidden_env_module.p,
            "getBasePositionAndOrientation",
            get_base_pose,
        )
        monkeypatch.setattr(hidden_env_module.p, "getBaseVelocity", get_base_velocity)
        monkeypatch.setattr(hidden_env_module.p, "applyExternalForce", record_force)
        monkeypatch.setattr(hidden_env_module.p, "applyExternalTorque", record_torque)
        rpm = np.array([1000.0, 2000.0, 3000.0, 4000.0])

        env._physics(rpm, 0)

        assert len(force_calls) == 5
        for index, call in enumerate(force_calls[:4]):
            np.testing.assert_allclose(
                call["force"],
                [0.0, 0.0, env.KF * rpm[index] ** 2 * 0.80],
                rtol=0.0,
                atol=0.0,
            )
            assert call["link"] == index
            assert call["flags"] == hidden_env_module.p.LINK_FRAME
            assert call["client"] == env.CLIENT

        expected_motor_torques = env.KM * rpm**2 * 0.60
        expected_z_torque = (
            -expected_motor_torques[0]
            + expected_motor_torques[1]
            - expected_motor_torques[2]
            + expected_motor_torques[3]
        )
        assert len(torque_calls) == 1
        np.testing.assert_allclose(
            torque_calls[0]["torque"],
            [0.0, 0.0, expected_z_torque],
            rtol=0.0,
            atol=0.0,
        )
        assert torque_calls[0]["link"] == 4
        assert torque_calls[0]["flags"] == hidden_env_module.p.LINK_FRAME

        wind_call = force_calls[4]
        wind_world = np.array([1.0, -0.5, 0.0])
        relative_velocity = base_velocity - wind_world
        expected_wind_force = -0.5 * 1.225 * 0.05 * (
            np.linalg.norm(relative_velocity) * relative_velocity
            - np.linalg.norm(base_velocity) * base_velocity
        )
        np.testing.assert_allclose(
            wind_call["force"],
            expected_wind_force,
            rtol=1e-15,
            atol=1e-15,
        )
        np.testing.assert_array_equal(wind_call["position"], base_position)
        assert wind_call["link"] == -1
        assert wind_call["flags"] == hidden_env_module.p.WORLD_FRAME
        assert wind_call["client"] == env.CLIENT
        assert env._last_applied_disturbance is fixed_sample


def test_standard_profile_applies_exactly_zero_incremental_wind_force(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wind_forces: list[np.ndarray] = []

    def record_force(
        bodyUniqueId: int,
        linkIndex: int,
        forceObj: object,
        posObj: object,
        flags: int,
        *,
        physicsClientId: int,
    ) -> None:
        if linkIndex == -1:
            wind_forces.append(np.asarray(forceObj, dtype=float))

    with _environment("pid", disturbance_profile="standard") as env:
        env.reset(seed=9043)
        monkeypatch.setattr(
            hidden_env_module.p,
            "getBasePositionAndOrientation",
            lambda body_id, *, physicsClientId: (
                np.array([0.8, -0.4, 1.2]),
                np.array([0.0, 0.0, 0.0, 1.0]),
            ),
        )
        monkeypatch.setattr(
            hidden_env_module.p,
            "getBaseVelocity",
            lambda body_id, *, physicsClientId: (
                np.array([2.0, -1.0, 0.5]),
                np.zeros(3),
            ),
        )
        monkeypatch.setattr(hidden_env_module.p, "applyExternalForce", record_force)
        monkeypatch.setattr(
            hidden_env_module.p,
            "applyExternalTorque",
            lambda *args, **kwargs: None,
        )

        env._physics(np.full(4, env.HOVER_RPM), 0)

        assert len(wind_forces) == 1
        np.testing.assert_array_equal(wind_forces[0], np.zeros(3))


def test_info_returns_exact_last_applied_sample_without_resampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_times: list[float] = []
    original_sample = HiddenDisturbanceProcess.sample

    def recording_sample(
        process: HiddenDisturbanceProcess,
        time_sec: float,
    ) -> HiddenDisturbanceSample:
        sample_times.append(float(time_sec))
        return original_sample(process, time_sec)

    monkeypatch.setattr(HiddenDisturbanceProcess, "sample", recording_sample)
    with _environment("pid", disturbance_profile="compound") as env:
        env.reset(seed=9044)
        _, _, _, _, step_info = env.step(np.zeros(1, dtype=np.float32))
        sample_count_after_step = len(sample_times)

        info_a = env._computeInfo()
        info_b = env._computeInfo()

        assert sample_count_after_step == 5
        assert len(sample_times) == sample_count_after_step
        assert step_info["disturbance_truth"] is env._last_applied_disturbance
        assert info_a["disturbance_truth"] is env._last_applied_disturbance
        assert info_b["disturbance_truth"] is env._last_applied_disturbance


@pytest.mark.parametrize("rollout_duration_sec", (20.0, 30.0))
def test_disturbance_process_horizon_matches_explicit_rollout_duration(
    rollout_duration_sec: float,
) -> None:
    with _environment(
        "pid",
        disturbance_profile="compound",
        rollout_duration_sec=rollout_duration_sec,
    ) as env:
        env.reset(seed=9045)

        assert env._disturbance_process is not None
        assert env._disturbance_process.horizon_sec == rollout_duration_sec
        assert env._disturbance_process.knot_times[-1] >= rollout_duration_sec
        if rollout_duration_sec == 30.0:
            assert any(time > 20.0 for time in env._disturbance_process.knot_times)


def test_truncation_and_post_step_info_use_completed_substep_time() -> None:
    duration = 5.0 / 240.0
    with _environment(
        "pid",
        disturbance_profile="standard",
        rollout_duration_sec=duration,
    ) as env:
        env.reset(seed=9046)

        _, _, terminated, truncated, info = env.step(
            np.zeros(1, dtype=np.float32)
        )

        assert terminated is False
        assert truncated is True
        assert info["time_sec"] == pytest.approx(duration, abs=0.0)
        np.testing.assert_allclose(
            info["reference_position"],
            env._reference_at_time(duration)[0],
            rtol=0.0,
            atol=0.0,
        )


def test_zero_residual_matches_pid_for_fifty_same_seed_control_steps() -> None:
    with (
        _environment("pid", disturbance_profile="compound") as pid,
        _environment("residual_td3", disturbance_profile="compound") as residual,
    ):
        pid.reset(seed=9047)
        residual.reset(seed=9047)

        for _ in range(50):
            _, pid_reward, pid_terminated, pid_truncated, pid_info = pid.step(
                np.zeros(1, dtype=np.float32)
            )
            (
                _,
                residual_reward,
                residual_terminated,
                residual_truncated,
                residual_info,
            ) = residual.step(np.zeros(4, dtype=np.float32))

            np.testing.assert_allclose(
                pid_info["rpm"],
                residual_info["rpm"],
                rtol=0.0,
                atol=1e-6,
            )
            np.testing.assert_allclose(pid.pos, residual.pos, rtol=0.0, atol=1e-12)
            np.testing.assert_allclose(pid.vel, residual.vel, rtol=0.0, atol=1e-12)
            assert residual_reward == pytest.approx(pid_reward, abs=1e-12)
            assert (pid_terminated, pid_truncated) == (
                residual_terminated,
                residual_truncated,
            )
            assert pid_info["disturbance_truth"] == residual_info["disturbance_truth"]


def test_rl_envs_package_preserves_legacy_export_and_adds_hidden_environment() -> None:
    import experiments.circular_tracking.rl_envs as rl_envs

    assert rl_envs.CircularResidualTD3Env.__name__ == "CircularResidualTD3Env"
    assert rl_envs.HiddenDisturbanceCircularTD3Env is HiddenDisturbanceCircularTD3Env
    assert set(rl_envs.__all__) == {
        "CircularResidualTD3Env",
        "HiddenDisturbanceCircularTD3Env",
    }


def test_pid_shaping_constructor_inputs_are_keyword_only_with_frozen_defaults() -> None:
    parameters = inspect.signature(HiddenDisturbanceCircularTD3Env).parameters
    expected_defaults = {
        "reference_velocity_gain": 1.0,
        "pid_xy_p_scale": 1.0,
        "pid_xy_d_scale": 1.0,
        "pid_target_step_limit": 0.0,
    }

    for name, default in expected_defaults.items():
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default == default


def test_pid_shaping_accepts_every_frozen_grid_candidate() -> None:
    candidates = product(
        (0.5, 0.75, 1.0),
        (0.5, 0.75, 1.0),
        (0.75, 1.0, 1.25),
        (0.0, 0.05, 0.10),
    )
    count = 0
    for velocity_gain, p_scale, d_scale, step_limit in candidates:
        with _environment(
            "pid",
            reference_velocity_gain=velocity_gain,
            pid_xy_p_scale=p_scale,
            pid_xy_d_scale=d_scale,
            pid_target_step_limit=step_limit,
        ) as env:
            config = env.pid_shaping_config
            assert config.reference_velocity_gain == velocity_gain
            assert config.pid_xy_p_scale == p_scale
            assert config.pid_xy_d_scale == d_scale
            assert config.pid_target_step_limit == step_limit
        count += 1

    assert count == 81


@pytest.mark.parametrize(
    "field_name",
    (
        "reference_velocity_gain",
        "pid_xy_p_scale",
        "pid_xy_d_scale",
        "pid_target_step_limit",
    ),
)
@pytest.mark.parametrize(
    ("invalid_value", "error_type"),
    (
        (True, TypeError),
        ("1.0", TypeError),
        (None, TypeError),
        (np.nan, ValueError),
        (np.inf, ValueError),
        (-np.inf, ValueError),
    ),
)
def test_pid_shaping_rejects_bool_nonreal_and_nonfinite_values(
    field_name: str,
    invalid_value: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(
        error_type,
        match=rf"{field_name} must be a finite real number",
    ):
        HiddenDisturbanceCircularTD3Env(
            controller_mode="pid",
            **{field_name: invalid_value},
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    (
        ("reference_velocity_gain", -1e-12, "must be greater than or equal to zero"),
        ("pid_target_step_limit", -1e-12, "must be greater than or equal to zero"),
        ("pid_xy_p_scale", 0.0, "must be greater than zero"),
        ("pid_xy_p_scale", -1e-12, "must be greater than zero"),
        ("pid_xy_d_scale", 0.0, "must be greater than zero"),
        ("pid_xy_d_scale", -1e-12, "must be greater than zero"),
    ),
)
def test_pid_shaping_rejects_values_outside_frozen_domains(
    field_name: str,
    invalid_value: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=rf"{field_name} {message}"):
        HiddenDisturbanceCircularTD3Env(
            controller_mode="pid",
            **{field_name: invalid_value},
        )


def test_pid_shaping_config_is_normalized_slotted_frozen_and_read_only() -> None:
    with _environment(
        "pid",
        reference_velocity_gain=np.float64(0.75),
        pid_xy_p_scale=np.int64(1),
        pid_xy_d_scale=np.float32(1.25),
        pid_target_step_limit=np.float64(0.05),
    ) as env:
        config = env.pid_shaping_config

        assert is_dataclass(config)
        assert not isinstance(config, dict)
        assert not hasattr(config, "__dict__")
        assert all(
            isinstance(getattr(config, field.name), float)
            for field in fields(config)
        )
        assert (
            config.reference_velocity_gain,
            config.pid_xy_p_scale,
            config.pid_xy_d_scale,
            config.pid_target_step_limit,
        ) == (0.75, 1.0, 1.25, 0.05)
        with pytest.raises(FrozenInstanceError):
            config.reference_velocity_gain = 0.5  # type: ignore[misc]
        with pytest.raises(AttributeError):
            env.pid_shaping_config = config  # type: ignore[misc]


@pytest.mark.parametrize("step_limit", (0.0, 0.10))
def test_pid_cache_uses_exact_shaped_compute_control_targets(
    step_limit: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _environment(
        "pid",
        reference_velocity_gain=0.75,
        pid_target_step_limit=step_limit,
    ) as env:
        env.reset(seed=9048)
        env._completed_physics_substeps = 600
        current_position = np.array([0.4, -0.2, 0.6])
        env.pos[0] = current_position
        captured: dict[str, np.ndarray] = {}
        original_compute = env._pid_controller.computeControl

        def recording_compute(**kwargs: object) -> tuple[np.ndarray, np.ndarray, float]:
            captured["target_pos"] = np.asarray(kwargs["target_pos"]).copy()
            captured["target_vel"] = np.asarray(kwargs["target_vel"]).copy()
            return original_compute(**kwargs)

        monkeypatch.setattr(
            env._pid_controller,
            "computeControl",
            recording_compute,
        )
        counter_before = env._pid_controller.control_counter

        env._update_pid_cache()

        reference_position, reference_velocity = env._reference_at_time(2.5)
        displacement = reference_position - current_position
        if step_limit == 0.0:
            expected_target_position = reference_position
        else:
            expected_target_position = (
                current_position
                + displacement / np.linalg.norm(displacement) * step_limit
            )
        np.testing.assert_allclose(
            captured["target_pos"],
            expected_target_position,
            rtol=0.0,
            atol=0.0,
        )
        np.testing.assert_allclose(
            captured["target_vel"],
            0.75 * reference_velocity,
            rtol=0.0,
            atol=0.0,
        )
        assert env._pid_controller.control_counter == counter_before + 1


def test_pid_shaping_does_not_change_reference_policy_surfaces_reward_or_gate() -> None:
    with (
        _environment("residual_td3") as default,
        _environment(
            "residual_td3",
            reference_velocity_gain=0.5,
            pid_xy_p_scale=0.5,
            pid_xy_d_scale=1.25,
            pid_target_step_limit=0.10,
        ) as shaped,
    ):
        default.reset(seed=9049)
        shaped.reset(seed=9049)
        common_pid_rpm = default.MAX_RPM * np.array([0.20, 0.35, 0.50, 0.65])
        for env in (default, shaped):
            env._pid_rpm_cache = common_pid_rpm.copy()
            env._last_applied_rpm = env.MAX_RPM * np.array([0.3, 0.4, 0.5, 0.6])
            env._previous_applied_rpm = env.MAX_RPM * np.array([0.2, 0.3, 0.4, 0.5])

        for time_sec in (0.0, 2.5, 10.0, 19.75):
            default_reference = default._reference_at_time(time_sec)
            shaped_reference = shaped._reference_at_time(time_sec)
            np.testing.assert_array_equal(default_reference[0], shaped_reference[0])
            np.testing.assert_array_equal(default_reference[1], shaped_reference[1])
        np.testing.assert_array_equal(default._computeObs(), shaped._computeObs())
        assert default._computeReward() == shaped._computeReward()
        assert default._compute_gate() == shaped._compute_gate()
        default_info = default._computeInfo()
        shaped_info = shaped._computeInfo()
        np.testing.assert_array_equal(
            default_info["reference_position"],
            shaped_info["reference_position"],
        )
        np.testing.assert_array_equal(
            default_info["reference_velocity"],
            shaped_info["reference_velocity"],
        )


def test_pid_xy_scales_are_stock_relative_and_leave_all_other_gains_unchanged() -> None:
    stock = DSLPIDControl(drone_model=DroneModel.CF2X)
    stock_gains = {
        name: getattr(stock, name).copy()
        for name in (
            "P_COEFF_FOR",
            "I_COEFF_FOR",
            "D_COEFF_FOR",
            "P_COEFF_TOR",
            "I_COEFF_TOR",
            "D_COEFF_TOR",
        )
    }
    with _environment(
        "pid",
        pid_xy_p_scale=0.5,
        pid_xy_d_scale=1.25,
    ) as env:
        controller = env._pid_controller

        np.testing.assert_array_equal(
            controller.P_COEFF_FOR[:2],
            stock_gains["P_COEFF_FOR"][:2] * 0.5,
        )
        np.testing.assert_array_equal(
            controller.D_COEFF_FOR[:2],
            stock_gains["D_COEFF_FOR"][:2] * 1.25,
        )
        assert controller.P_COEFF_FOR[2] == stock_gains["P_COEFF_FOR"][2]
        assert controller.D_COEFF_FOR[2] == stock_gains["D_COEFF_FOR"][2]
        for name in (
            "I_COEFF_FOR",
            "P_COEFF_TOR",
            "I_COEFF_TOR",
            "D_COEFF_TOR",
        ):
            np.testing.assert_array_equal(
                getattr(controller, name),
                stock_gains[name],
            )
        for name, untouched in stock_gains.items():
            np.testing.assert_array_equal(getattr(stock, name), untouched)


def test_pid_resets_state_without_reapplying_scales_and_keeps_lifecycle_exact() -> None:
    with _environment(
        "pid",
        reference_velocity_gain=0.75,
        pid_xy_p_scale=0.5,
        pid_xy_d_scale=1.25,
        pid_target_step_limit=0.05,
    ) as env:
        env.reset(seed=9050)
        first_reset_state = _pid_state_fingerprint(env)
        p_coefficients = env._pid_controller.P_COEFF_FOR.copy()
        d_coefficients = env._pid_controller.D_COEFF_FOR.copy()
        assert env._pid_controller.control_counter == 1

        env._computeObs()
        env._computeObs()
        assert env._pid_controller.control_counter == 1
        env.step(np.zeros(1, dtype=np.float32))
        assert env._pid_controller.control_counter == 2

        env.reset(seed=9050)

        assert _pid_state_fingerprint(env) == first_reset_state
        np.testing.assert_array_equal(
            env._pid_controller.P_COEFF_FOR,
            p_coefficients,
        )
        np.testing.assert_array_equal(
            env._pid_controller.D_COEFF_FOR,
            d_coefficients,
        )
        env.reset(seed=9050)
        assert _pid_state_fingerprint(env) == first_reset_state
        np.testing.assert_array_equal(
            env._pid_controller.P_COEFF_FOR,
            p_coefficients,
        )
        np.testing.assert_array_equal(
            env._pid_controller.D_COEFF_FOR,
            d_coefficients,
        )


def test_pid_shaping_environments_do_not_share_or_contaminate_gain_arrays() -> None:
    stock = DSLPIDControl(drone_model=DroneModel.CF2X)
    with (
        _environment(
            "pid",
            pid_xy_p_scale=0.5,
            pid_xy_d_scale=0.75,
        ) as lower,
        _environment(
            "pid",
            pid_xy_p_scale=1.0,
            pid_xy_d_scale=1.25,
        ) as upper,
    ):
        assert not np.shares_memory(
            lower._pid_controller.P_COEFF_FOR,
            upper._pid_controller.P_COEFF_FOR,
        )
        assert not np.shares_memory(
            lower._pid_controller.D_COEFF_FOR,
            upper._pid_controller.D_COEFF_FOR,
        )
        np.testing.assert_array_equal(
            lower._pid_controller.P_COEFF_FOR[:2],
            stock.P_COEFF_FOR[:2] * 0.5,
        )
        np.testing.assert_array_equal(
            upper._pid_controller.P_COEFF_FOR[:2],
            stock.P_COEFF_FOR[:2],
        )
        np.testing.assert_array_equal(
            lower._pid_controller.D_COEFF_FOR[:2],
            stock.D_COEFF_FOR[:2] * 0.75,
        )
        np.testing.assert_array_equal(
            upper._pid_controller.D_COEFF_FOR[:2],
            stock.D_COEFF_FOR[:2] * 1.25,
        )


@pytest.mark.parametrize(
    "controller_mode",
    ("pid", "direct_td3", "residual_td3", "residual_td3_no_gate"),
)
@pytest.mark.parametrize(
    "case",
    (
        "python_scalar",
        "zero_dimensional",
        "two_dimensional",
        "wrong_length",
        "boolean",
        "non_real",
        "complex",
        "nan",
        "positive_infinity",
        "negative_infinity",
        "above_range",
        "below_range",
    ),
)
def test_public_step_rejects_invalid_actions_before_any_mutation(
    controller_mode: str,
    case: str,
) -> None:
    with _environment(controller_mode) as env:
        env.reset(seed=9051)
        before = _runtime_fingerprint(env)
        invalid_action = _invalid_action(controller_mode, case)
        if case in {"boolean", "non_real", "complex"}:
            error_type = TypeError
            message = "real numeric"
        elif case in {
            "python_scalar",
            "zero_dimensional",
            "two_dimensional",
            "wrong_length",
        }:
            error_type = ValueError
            message = "shape"
        elif case in {"nan", "positive_infinity", "negative_infinity"}:
            error_type = ValueError
            message = "finite"
        else:
            error_type = ValueError
            message = r"\[-1, 1\]"

        with pytest.raises(error_type, match=message):
            env.step(invalid_action)  # type: ignore[arg-type]

        assert _runtime_fingerprint(env) == before
        _, _, terminated, truncated, _ = env.step(_valid_action(controller_mode))
        assert terminated is False
        assert truncated is False
        assert env._completed_physics_substeps == 5


@pytest.mark.parametrize(
    "controller_mode",
    ("pid", "direct_td3", "residual_td3", "residual_td3_no_gate"),
)
@pytest.mark.parametrize(
    "case",
    (
        "python_scalar",
        "zero_dimensional",
        "two_dimensional",
        "wrong_length",
        "boolean",
        "non_real",
        "complex",
        "nan",
        "positive_infinity",
        "negative_infinity",
        "above_range",
        "below_range",
    ),
)
def test_private_preprocess_rejects_invalid_actions_without_cache_corruption(
    controller_mode: str,
    case: str,
) -> None:
    with _environment(controller_mode) as env:
        env.reset(seed=9052)
        before = _runtime_fingerprint(env)

        with pytest.raises((TypeError, ValueError)):
            env._preprocessAction(  # type: ignore[arg-type]
                _invalid_action(controller_mode, case)
            )

        assert _runtime_fingerprint(env) == before


def test_reset_reallocates_fixed_cache_shapes_after_attempted_private_misuse() -> None:
    with _environment("residual_td3") as env:
        env.reset(seed=9053)
        env._pid_rpm_cache = np.ones(2)
        env._last_policy_action = np.ones(3)
        env._last_applied_rpm = np.ones(5)
        env._previous_applied_rpm = np.ones(6)
        env._history.clear()
        env._history.append(np.ones(1))

        observation, _ = env.reset(seed=9053)

        for value in (
            env._pid_rpm_cache,
            env._last_policy_action,
            env._last_applied_rpm,
            env._previous_applied_rpm,
        ):
            assert value.shape == (4,)
        assert len(env._history) == env.HISTORY_LENGTH
        assert all(frame.shape == (env.HISTORY_FRAME_SIZE,) for frame in env._history)
        assert env.observation_space.contains(observation)


def test_nonaligned_duration_fails_before_base_or_pybullet_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_constructor_called = False

    def forbidden_base_constructor(*args: object, **kwargs: object) -> None:
        nonlocal base_constructor_called
        base_constructor_called = True
        raise AssertionError("base constructor must not run")

    monkeypatch.setattr(CtrlAviary, "__init__", forbidden_base_constructor)

    with pytest.raises(ValueError, match="multiple of 1/48"):
        HiddenDisturbanceCircularTD3Env(
            controller_mode="pid",
            rollout_duration_sec=0.03,
        )

    assert base_constructor_called is False


@pytest.mark.parametrize(
    ("requested_duration", "expected_steps"),
    (
        (1.0 / 48.0, 1),
        (1.0 / 48.0 + 5e-13, 1),
        (20.0, 960),
        (30.0, 1440),
    ),
)
def test_aligned_duration_is_normalized_to_exact_control_steps(
    requested_duration: float,
    expected_steps: int,
) -> None:
    with _environment(
        "pid",
        rollout_duration_sec=requested_duration,
    ) as env:
        assert env.rollout_duration_sec == expected_steps / 48.0
        assert env._rollout_control_steps == expected_steps


def test_step_before_reset_is_rejected_without_mutation() -> None:
    with _environment("direct_td3") as env:
        before = _runtime_fingerprint(env)

        with pytest.raises(RuntimeError, match="reset.*required"):
            env.step(_valid_action("direct_td3"))

        assert _runtime_fingerprint(env) == before


def test_step_after_truncation_is_rejected_before_action_validation() -> None:
    with _environment(
        "direct_td3",
        rollout_duration_sec=1.0 / 48.0,
    ) as env:
        env.reset(seed=9054)
        _, _, terminated, truncated, _ = env.step(_valid_action("direct_td3"))
        assert terminated is False
        assert truncated is True
        after_done = _runtime_fingerprint(env)

        with pytest.raises(RuntimeError, match="episode.*reset"):
            env.step(np.array(0.0))

        assert _runtime_fingerprint(env) == after_done


def test_step_after_termination_is_rejected_before_action_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _environment("direct_td3") as env:
        env.reset(seed=9055)
        monkeypatch.setattr(env, "_computeTerminated", lambda: True)

        _, _, terminated, truncated, _ = env.step(_valid_action("direct_td3"))

        assert terminated is True
        assert truncated is False
        after_done = _runtime_fingerprint(env)
        with pytest.raises(RuntimeError, match="episode.*reset"):
            env.step(np.array(0.0))
        assert _runtime_fingerprint(env) == after_done


def test_pybullet_exception_latches_reset_required_and_reset_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InjectedPyBulletFailure(RuntimeError):
        pass

    with _environment("direct_td3") as env:
        env.reset(seed=9056)
        failure_calls = 0

        def fail_step_simulation(*, physicsClientId: int) -> None:
            nonlocal failure_calls
            failure_calls += 1
            assert physicsClientId == env.CLIENT
            raise InjectedPyBulletFailure("injected stepSimulation failure")

        with monkeypatch.context() as patch:
            patch.setattr(
                hidden_env_module.p,
                "stepSimulation",
                fail_step_simulation,
            )
            with pytest.raises(InjectedPyBulletFailure):
                env.step(_valid_action("direct_td3"))
            after_failure = _runtime_fingerprint(env)

            with pytest.raises(RuntimeError, match="reset.*required"):
                env.step(_valid_action("direct_td3"))

            assert failure_calls == 1
            assert _runtime_fingerprint(env) == after_failure

        observation, _ = env.reset(seed=9056)
        assert env.observation_space.contains(observation)
        assert env._completed_physics_substeps == 0
        assert env._physics_substeps_started == 0
        env.step(_valid_action("direct_td3"))
        assert env._completed_physics_substeps == 5


def test_post_step_exception_latches_reset_required_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InjectedPostStepFailure(RuntimeError):
        pass

    with _environment("direct_td3") as env:
        env.reset(seed=9057)
        update_calls = 0

        def fail_pid_refresh() -> None:
            nonlocal update_calls
            update_calls += 1
            raise InjectedPostStepFailure("injected PID refresh failure")

        with monkeypatch.context() as patch:
            patch.setattr(env, "_update_pid_cache", fail_pid_refresh)
            with pytest.raises(InjectedPostStepFailure):
                env.step(_valid_action("direct_td3"))
            after_failure = _runtime_fingerprint(env)

            with pytest.raises(RuntimeError, match="reset.*required"):
                env.step(_valid_action("direct_td3"))

            assert update_calls == 1
            assert _runtime_fingerprint(env) == after_failure

        observation, _ = env.reset(seed=9057)
        assert env.observation_space.contains(observation)
        env.step(_valid_action("direct_td3"))
        assert env._completed_physics_substeps == 5


@pytest.mark.parametrize(
    ("duration_sec", "seed"),
    ((20.0, 9058), (30.0, 9059)),
)
def test_full_aligned_horizon_samples_only_valid_substeps_and_rejects_extra_step(
    duration_sec: float,
    seed: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_times: list[float] = []
    original_sample = HiddenDisturbanceProcess.sample

    def recording_sample(
        process: HiddenDisturbanceProcess,
        time_sec: float,
    ) -> HiddenDisturbanceSample:
        sample_times.append(float(time_sec))
        return original_sample(process, time_sec)

    monkeypatch.setattr(HiddenDisturbanceProcess, "sample", recording_sample)
    with _environment(
        "direct_td3",
        disturbance_profile="standard",
        rollout_duration_sec=duration_sec,
    ) as env:
        env.reset(seed=seed)
        total_control_steps = int(duration_sec * 48)
        final_info: dict[str, object] | None = None
        for control_step in range(total_control_steps):
            _, _, terminated, truncated, final_info = env.step(
                _valid_action("direct_td3")
            )
            assert terminated is False
            assert truncated is (control_step == total_control_steps - 1)

        expected_samples = int(duration_sec * 240)
        assert len(sample_times) == expected_samples
        assert sample_times[0] == 0.0
        assert sample_times[-1] == (expected_samples - 1) / 240.0
        assert env._completed_physics_substeps == expected_samples
        assert final_info is not None
        assert final_info["time_sec"] == duration_sec
        after_done = _runtime_fingerprint(env)

        with pytest.raises(RuntimeError, match="episode.*reset"):
            env.step(np.array(0.0))

        assert len(sample_times) == expected_samples
        assert _runtime_fingerprint(env) == after_done


def test_one_control_step_is_minimum_complete_horizon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_times: list[float] = []
    original_sample = HiddenDisturbanceProcess.sample

    def recording_sample(
        process: HiddenDisturbanceProcess,
        time_sec: float,
    ) -> HiddenDisturbanceSample:
        sample_times.append(float(time_sec))
        return original_sample(process, time_sec)

    monkeypatch.setattr(HiddenDisturbanceProcess, "sample", recording_sample)
    with _environment(
        "pid",
        disturbance_profile="standard",
        rollout_duration_sec=1.0 / 48.0,
    ) as env:
        env.reset(seed=9060)
        _, _, terminated, truncated, info = env.step(_valid_action("pid"))

        assert terminated is False
        assert truncated is True
        np.testing.assert_array_equal(sample_times, np.arange(5) / 240.0)
        assert info["time_sec"] == 1.0 / 48.0
