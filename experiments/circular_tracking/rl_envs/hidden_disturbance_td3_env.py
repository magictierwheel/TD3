"""Fair circular-tracking environment with hidden disturbances."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from numbers import Real

import numpy as np
import pybullet as p
from gymnasium import spaces

from experiments.circular_tracking.rl_envs.disturbance_processes import (
    HiddenDisturbanceProcess,
    HiddenDisturbanceSample,
)
from gym_pybullet_drones.control.DSLPIDControl import DSLPIDControl
from gym_pybullet_drones.envs.CtrlAviary import CtrlAviary
from gym_pybullet_drones.utils.enums import DroneModel, Physics


@dataclass(frozen=True, slots=True)
class PIDShapingConfig:
    """Immutable normalized inputs for the conventional PID baseline."""

    reference_velocity_gain: float = 1.0
    pid_xy_p_scale: float = 1.0
    pid_xy_d_scale: float = 1.0
    pid_target_step_limit: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "reference_velocity_gain",
            "pid_xy_p_scale",
            "pid_xy_d_scale",
            "pid_target_step_limit",
        ):
            value = getattr(self, field_name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
                raise TypeError(f"{field_name} must be a finite real number")
            normalized = float(value)
            if not math.isfinite(normalized):
                raise ValueError(f"{field_name} must be a finite real number")
            object.__setattr__(self, field_name, normalized)

        if self.reference_velocity_gain < 0.0:
            raise ValueError(
                "reference_velocity_gain must be greater than or equal to zero"
            )
        if self.pid_target_step_limit < 0.0:
            raise ValueError(
                "pid_target_step_limit must be greater than or equal to zero"
            )
        if self.pid_xy_p_scale <= 0.0:
            raise ValueError("pid_xy_p_scale must be greater than zero")
        if self.pid_xy_d_scale <= 0.0:
            raise ValueError("pid_xy_d_scale must be greater than zero")


class HiddenDisturbanceCircularTD3Env(CtrlAviary):
    """Circular-tracking interface shared by PID and TD3 controllers."""

    HISTORY_LENGTH = 8
    HISTORY_FRAME_SIZE = 32
    CONTROL_FREQ_HZ = 48
    # Allow only floating-point conversion noise, then normalize to whole steps.
    _ROLLOUT_DURATION_TOLERANCE_SEC = 1e-12
    REFERENCE_RADIUS_M = 0.3
    REFERENCE_PERIOD_SEC = 10.0
    REFERENCE_HEIGHT_M = 1.0
    SENSOR_NOISE_MODEL = "none"
    AIR_DENSITY_KG_M3 = 1.225
    WIND_CDA_M2 = 0.05
    failure_penalty = 50.0
    _SHARED_OBSERVATION_SCHEMA = (
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
    )
    _HISTORY_FIELD_WIDTHS = (3, 3, 3, 3, 3, 3, 3, 3, 4, 4)
    SUPPORTED_CONTROLLER_MODES = frozenset(
        {
            "pid",
            "direct_td3",
            "residual_td3",
            "residual_td3_no_gate",
        }
    )

    def __init__(
        self,
        *,
        controller_mode: str,
        disturbance_profile: str = "standard",
        rollout_duration_sec: float = 20.0,
        reference_velocity_gain: float = 1.0,
        pid_xy_p_scale: float = 1.0,
        pid_xy_d_scale: float = 1.0,
        pid_target_step_limit: float = 0.0,
        gui: bool = False,
    ) -> None:
        if controller_mode not in self.SUPPORTED_CONTROLLER_MODES:
            raise ValueError(f"Unsupported controller_mode: {controller_mode}")
        if disturbance_profile not in HiddenDisturbanceProcess.PROFILES:
            raise ValueError(
                f"Unsupported disturbance_profile: {disturbance_profile}"
            )
        if isinstance(rollout_duration_sec, (bool, np.bool_)) or not isinstance(
            rollout_duration_sec,
            (int, float, np.integer, np.floating),
        ):
            raise TypeError(
                "rollout_duration_sec must be a finite positive number"
            )
        duration = float(rollout_duration_sec)
        if not math.isfinite(duration) or duration <= 0.0:
            raise ValueError(
                "rollout_duration_sec must be finite and positive"
        )
        requested_control_steps = duration * self.CONTROL_FREQ_HZ
        if not math.isfinite(requested_control_steps):
            raise ValueError(
                "rollout_duration_sec must be a multiple of 1/48 s"
            )
        control_steps = int(round(requested_control_steps))
        normalized_duration = control_steps / self.CONTROL_FREQ_HZ
        if (
            control_steps < 1
            or abs(duration - normalized_duration)
            > self._ROLLOUT_DURATION_TOLERANCE_SEC
        ):
            raise ValueError(
                "rollout_duration_sec must be a multiple of 1/48 s"
            )

        self.controller_mode = controller_mode
        self.disturbance_profile = disturbance_profile
        self.rollout_duration_sec = normalized_duration
        self._rollout_control_steps = control_steps
        self._pid_shaping_config = PIDShapingConfig(
            reference_velocity_gain=reference_velocity_gain,
            pid_xy_p_scale=pid_xy_p_scale,
            pid_xy_d_scale=pid_xy_d_scale,
            pid_target_step_limit=pid_target_step_limit,
        )
        self._pid_rpm_cache = np.zeros(4, dtype=float)
        self._last_policy_action = np.zeros(4, dtype=float)
        self._last_applied_rpm = np.zeros(4, dtype=float)
        self._previous_applied_rpm = np.zeros(4, dtype=float)
        self._history: deque[np.ndarray] = deque(maxlen=self.HISTORY_LENGTH)
        self._completed_physics_substeps = 0
        self._physics_substeps_started = 0
        self._disturbance_process: HiddenDisturbanceProcess | None = None
        self._last_applied_disturbance: HiddenDisturbanceSample | None = None
        self._episode_done = False
        self._reset_required = True
        super().__init__(
            num_drones=1,
            initial_xyzs=np.array([[0.3, 0.0, 1.0]], dtype=float),
            physics=Physics.PYB,
            pyb_freq=240,
            ctrl_freq=self.CONTROL_FREQ_HZ,
            gui=gui,
            record=False,
            obstacles=False,
            user_debug_gui=False,
        )
        self._pid_controller = DSLPIDControl(drone_model=DroneModel.CF2X)
        self._pid_controller.P_COEFF_FOR[:2] *= (
            self._pid_shaping_config.pid_xy_p_scale
        )
        self._pid_controller.D_COEFF_FOR[:2] *= (
            self._pid_shaping_config.pid_xy_d_scale
        )

    @property
    def pid_shaping_config(self) -> PIDShapingConfig:
        """Return the immutable normalized PID construction inputs."""

        return self._pid_shaping_config

    @property
    def observation_schema(self) -> tuple[str, ...]:
        """Describe the field-major history layout returned to a policy."""

        if self.controller_mode in {
            "direct_td3",
            "residual_td3",
            "residual_td3_no_gate",
        }:
            return self._SHARED_OBSERVATION_SCHEMA + ("pid_rpm",)
        return self._SHARED_OBSERVATION_SCHEMA

    def _actionSpace(self) -> spaces.Box:
        """Return an ignored one-value PID action or a matched TD3 four-vector."""

        shape = (1,) if self.controller_mode == "pid" else (4,)
        return spaces.Box(
            low=np.full(shape, -1.0, dtype=np.float32),
            high=np.full(shape, 1.0, dtype=np.float32),
            dtype=np.float32,
        )

    def _observationSpace(self) -> spaces.Box:
        reference_speed = (
            2.0
            * math.pi
            * self.REFERENCE_RADIUS_M
            / self.REFERENCE_PERIOD_SEC
        )
        frame_lows = (
            np.full(3, -np.inf),
            np.full(3, -np.inf),
            np.full(3, -math.pi),
            np.full(3, -np.inf),
            np.array(
                [
                    -self.REFERENCE_RADIUS_M,
                    -self.REFERENCE_RADIUS_M,
                    self.REFERENCE_HEIGHT_M,
                ]
            ),
            np.array([-reference_speed, -reference_speed, 0.0]),
            np.full(3, -np.inf),
            np.full(3, -np.inf),
            np.full(4, -1.0),
            np.zeros(4),
        )
        frame_highs = (
            np.full(3, np.inf),
            np.full(3, np.inf),
            np.full(3, math.pi),
            np.full(3, np.inf),
            np.array(
                [
                    self.REFERENCE_RADIUS_M,
                    self.REFERENCE_RADIUS_M,
                    self.REFERENCE_HEIGHT_M,
                ]
            ),
            np.array([reference_speed, reference_speed, 0.0]),
            np.full(3, np.inf),
            np.full(3, np.inf),
            np.full(4, 1.0),
            np.full(4, self.MAX_RPM),
        )
        low = np.concatenate(
            [np.tile(values, self.HISTORY_LENGTH) for values in frame_lows]
        )
        high = np.concatenate(
            [np.tile(values, self.HISTORY_LENGTH) for values in frame_highs]
        )
        if self.controller_mode in {
            "direct_td3",
            "residual_td3",
            "residual_td3_no_gate",
        }:
            low = np.concatenate((low, np.zeros(4)))
            high = np.concatenate((high, np.full(4, self.MAX_RPM)))
        return spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    def reset(
        self,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        self._history = deque(maxlen=self.HISTORY_LENGTH)
        self._pid_rpm_cache = np.zeros(4, dtype=float)
        self._last_policy_action = np.zeros(4, dtype=float)
        self._last_applied_rpm = np.zeros(4, dtype=float)
        self._previous_applied_rpm = np.zeros(4, dtype=float)
        self._completed_physics_substeps = 0
        self._physics_substeps_started = 0
        self._episode_done = False
        self._reset_required = True
        self._disturbance_process = None
        self._last_applied_disturbance = None
        try:
            super().reset(seed=seed, options=options)

            process_seed = (
                int(seed)
                if seed is not None
                else int(self.np_random.integers(0, np.iinfo(np.int64).max))
            )
            self._disturbance_process = HiddenDisturbanceProcess(
                seed=process_seed,
                profile=self.disturbance_profile,
                horizon_sec=self.rollout_duration_sec,
            )
            self._pid_controller.reset()
            self._update_pid_cache()
            initial_frame = self._current_history_frame()
            for _ in range(self.HISTORY_LENGTH):
                self._history.append(initial_frame.copy())
            observation, info = self._computeObs(), self._computeInfo()
        except Exception:
            self._reset_required = True
            raise
        self._reset_required = False
        return observation, info

    def step(
        self,
        action: np.ndarray,
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        if self._reset_required:
            raise RuntimeError("reset required before step")
        if self._episode_done:
            raise RuntimeError("episode is done; reset required before step")
        self._validate_action(action)
        try:
            super().step(action)
            self._completed_physics_substeps = self._physics_substeps_started
            self._update_pid_cache()
            self._history.append(self._current_history_frame())
            observation = self._computeObs()
            reward = self._computeReward()
            terminated = bool(self._computeTerminated())
            truncated = bool(self._computeTruncated())
            info = self._computeInfo()
        except Exception:
            self._reset_required = True
            raise
        self._episode_done = terminated or truncated
        return observation, reward, terminated, truncated, info

    def _validate_action(self, action: object) -> np.ndarray:
        """Validate policy actions before any environment state can change."""

        expected_shape = (1,) if self.controller_mode == "pid" else (4,)
        try:
            policy_action = np.asarray(action)
        except (TypeError, ValueError) as exc:
            raise TypeError("action must be real numeric data") from exc
        if policy_action.shape != expected_shape:
            raise ValueError(
                f"action shape must be exactly {expected_shape}; "
                f"received {policy_action.shape}"
            )
        if policy_action.dtype.kind not in "iuf":
            raise TypeError("action must be real numeric data")
        if not np.all(np.isfinite(policy_action)):
            raise ValueError("action values must be finite")
        if np.any(policy_action < -1.0) or np.any(policy_action > 1.0):
            raise ValueError("action values must lie in [-1, 1]")
        return policy_action

    def _preprocessAction(self, action: np.ndarray) -> np.ndarray:
        policy_action = self._validate_action(action)
        if self.controller_mode == "pid":
            self._last_policy_action.fill(0.0)
            applied_rpm = self._pid_rpm_cache.copy()
        elif self.controller_mode == "direct_td3":
            self._last_policy_action = np.clip(
                policy_action,
                -1.0,
                1.0,
            ).astype(float)
            applied_rpm = np.clip(
                self.HOVER_RPM
                + policy_action * (self.MAX_RPM - self.HOVER_RPM),
                0.0,
                self.MAX_RPM,
            )
        else:
            self._last_policy_action = np.clip(
                policy_action,
                -1.0,
                1.0,
            ).astype(float)
            gate = self._compute_gate()
            applied_rpm = np.clip(
                self._pid_rpm_cache
                + gate * policy_action * (0.10 * self.MAX_RPM),
                0.0,
                self.MAX_RPM,
            )

        self._previous_applied_rpm = self._last_applied_rpm.copy()
        self._last_applied_rpm = np.asarray(applied_rpm, dtype=float).copy()
        return applied_rpm

    def _compute_gate(self) -> float:
        if self.controller_mode == "residual_td3_no_gate":
            return 1.0
        reference_position, _ = self._reference_at_time(
            self._completed_physics_substeps / self.PYB_FREQ
        )
        position_error = float(np.linalg.norm(reference_position - self.pos[0]))
        error_gate = np.clip(
            (position_error - 0.03) / (0.20 - 0.03),
            0.0,
            1.0,
        )
        headroom = float(
            np.min(
                np.minimum(
                    self._pid_rpm_cache,
                    self.MAX_RPM - self._pid_rpm_cache,
                )
            )
            / self.MAX_RPM
        )
        headroom_gate = np.clip(headroom / 0.10, 0.0, 1.0)
        return float(error_gate * headroom_gate)

    def _reference_at_time(
        self,
        time_sec: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        angular_rate = 2.0 * math.pi / self.REFERENCE_PERIOD_SEC
        phase = angular_rate * time_sec
        reference_position = np.array(
            [
                self.REFERENCE_RADIUS_M * math.cos(phase),
                self.REFERENCE_RADIUS_M * math.sin(phase),
                self.REFERENCE_HEIGHT_M,
            ]
        )
        reference_velocity = np.array(
            [
                -self.REFERENCE_RADIUS_M * angular_rate * math.sin(phase),
                self.REFERENCE_RADIUS_M * angular_rate * math.cos(phase),
                0.0,
            ]
        )
        return reference_position, reference_velocity

    def _update_pid_cache(self) -> None:
        reference_position, reference_velocity = self._reference_at_time(
            self._completed_physics_substeps / self.PYB_FREQ
        )
        target_position = reference_position
        step_limit = self._pid_shaping_config.pid_target_step_limit
        if step_limit > 0.0:
            displacement = reference_position - self.pos[0]
            distance = float(np.linalg.norm(displacement))
            if distance > step_limit:
                target_position = (
                    self.pos[0] + displacement / distance * step_limit
                )
        rpm, _, _ = self._pid_controller.computeControl(
            control_timestep=self.CTRL_TIMESTEP,
            cur_pos=self.pos[0],
            cur_quat=self.quat[0],
            cur_vel=self.vel[0],
            cur_ang_vel=self.ang_v[0],
            target_pos=target_position,
            target_vel=(
                self._pid_shaping_config.reference_velocity_gain
                * reference_velocity
            ),
        )
        self._pid_rpm_cache = np.clip(
            np.asarray(rpm, dtype=float),
            0.0,
            self.MAX_RPM,
        )

    def _current_history_frame(self) -> np.ndarray:
        reference_position, reference_velocity = self._reference_at_time(
            self._completed_physics_substeps / self.PYB_FREQ
        )
        return np.concatenate(
            (
                self.pos[0],
                self.vel[0],
                self.rpy[0],
                self.ang_v[0],
                reference_position,
                reference_velocity,
                reference_position - self.pos[0],
                reference_velocity - self.vel[0],
                self._last_policy_action,
                self._last_applied_rpm,
            )
        )

    def _computeObs(self) -> np.ndarray:
        if self._history:
            history = np.stack(tuple(self._history))
        else:
            current = self._current_history_frame()
            history = np.repeat(
                current[np.newaxis, :],
                self.HISTORY_LENGTH,
                axis=0,
            )

        fields: list[np.ndarray] = []
        offset = 0
        for width in self._HISTORY_FIELD_WIDTHS:
            fields.append(history[:, offset : offset + width].reshape(-1))
            offset += width
        observation = np.concatenate(fields)
        if self.controller_mode in {
            "direct_td3",
            "residual_td3",
            "residual_td3_no_gate",
        }:
            observation = np.concatenate((observation, self._pid_rpm_cache))
        return observation.astype(np.float32)

    def _failure_reason_for_current_state(self) -> str:
        """Return the canonical failure reason for one current-state snapshot.

        The helper deliberately reads the simulator state and the reference at
        the completed-substep clock, then performs only local comparisons. It
        does not cache a result or mutate any environment/controller state, so
        reward, termination, and info can each evaluate the same transition
        independently.
        """

        state = np.asarray(self._getDroneStateVector(0), dtype=float)
        reference_position, _ = self._reference_at_time(
            self._completed_physics_substeps / self.PYB_FREQ
        )
        if not np.all(np.isfinite(state)):
            return "non_finite_state"
        altitude = float(state[2])
        reference_altitude = float(reference_position[2])
        if (
            abs(altitude - reference_altitude) > 1.5
            or altitude < 0.1
            or altitude > 3.0
        ):
            return "altitude_limit"
        if abs(float(state[7])) > 0.9 or abs(float(state[8])) > 0.9:
            return "tilt_limit"
        with np.errstate(over="ignore", invalid="ignore"):
            horizontal_error = np.linalg.norm(
                state[0:2] - reference_position[0:2]
            )
        if horizontal_error > 2.0:
            return "horizontal_error_limit"
        return ""

    def _computeReward(self) -> float:
        failure_reason = self._failure_reason_for_current_state()
        if failure_reason == "non_finite_state":
            return -float(self.failure_penalty)
        reference_position, reference_velocity = self._reference_at_time(
            self._completed_physics_substeps / self.PYB_FREQ
        )
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            applied_rpm = np.clip(
                self._last_applied_rpm,
                0.0,
                self.MAX_RPM,
            )
            previous_applied_rpm = np.clip(
                self._previous_applied_rpm,
                0.0,
                self.MAX_RPM,
            )
            position_error_norm = (
                np.linalg.norm(reference_position - self.pos[0]) / 2.0
            )
            velocity_error_norm = (
                np.linalg.norm(reference_velocity - self.vel[0]) / 3.0
            )
            altitude_error_norm = (
                abs(self.pos[0, 2] - reference_position[2]) / 2.0
            )
            tilt_norm = np.linalg.norm(self.rpy[0, :2]) / math.pi
            applied_motor_energy = np.mean((applied_rpm / self.MAX_RPM) ** 2)
            applied_motor_smoothness = (
                np.mean(np.abs(applied_rpm - previous_applied_rpm))
                / self.MAX_RPM
            )
            saturation_fraction = np.mean(
                (applied_rpm <= 0.0) | (applied_rpm >= self.MAX_RPM)
            )
            reward = -float(
                2.0 * position_error_norm
                + 0.5 * velocity_error_norm
                + 1.0 * altitude_error_norm
                + 0.2 * tilt_norm
                + 0.05 * applied_motor_energy
                + 0.05 * applied_motor_smoothness
                + 2.0 * saturation_fraction
            )
        if not np.isfinite(reward):
            return -float(self.failure_penalty if failure_reason else 0.0)
        if failure_reason:
            reward -= self.failure_penalty
        return reward

    def _computeTerminated(self) -> bool:
        return bool(self._failure_reason_for_current_state())

    def _computeTruncated(self) -> bool:
        return bool(
            self._completed_physics_substeps
            >= self._rollout_control_steps * self.PYB_STEPS_PER_CTRL
        )

    def _computeInfo(self) -> dict[str, object]:
        time_sec = self._completed_physics_substeps / self.PYB_FREQ
        failure_reason = self._failure_reason_for_current_state()
        reference_position, reference_velocity = self._reference_at_time(time_sec)
        gate: float | None = None
        if self.controller_mode in {"residual_td3", "residual_td3_no_gate"}:
            gate = self._compute_gate()
        return {
            "time_sec": time_sec,
            "reference_position": reference_position.copy(),
            "reference_velocity": reference_velocity.copy(),
            "position_error": (reference_position - self.pos[0]).copy(),
            "velocity_error": (reference_velocity - self.vel[0]).copy(),
            "rpm": self._last_applied_rpm.copy(),
            "pid_rpm": self._pid_rpm_cache.copy(),
            "gate": gate,
            "failure_reason": failure_reason,
            "disturbance_truth": self._last_applied_disturbance,
        }

    def _physics(self, rpm: np.ndarray, nth_drone: int) -> None:
        if self._disturbance_process is None:
            raise RuntimeError("reset() must be called before step()")
        sample_time = self._physics_substeps_started / self.PYB_FREQ
        disturbance = self._disturbance_process.sample(sample_time)
        self._last_applied_disturbance = disturbance

        rpm_squared = np.asarray(rpm, dtype=float) ** 2
        motor_forces = rpm_squared * self.KF * disturbance.thrust_efficiency
        motor_torques = rpm_squared * self.KM * disturbance.torque_efficiency
        z_torque = float(
            -motor_torques[0]
            + motor_torques[1]
            - motor_torques[2]
            + motor_torques[3]
        )
        for motor_index, force in enumerate(motor_forces):
            p.applyExternalForce(
                self.DRONE_IDS[nth_drone],
                motor_index,
                forceObj=[0.0, 0.0, float(force)],
                posObj=[0.0, 0.0, 0.0],
                flags=p.LINK_FRAME,
                physicsClientId=self.CLIENT,
            )
        p.applyExternalTorque(
            self.DRONE_IDS[nth_drone],
            4,
            torqueObj=[0.0, 0.0, z_torque],
            flags=p.LINK_FRAME,
            physicsClientId=self.CLIENT,
        )

        base_position, _ = p.getBasePositionAndOrientation(
            self.DRONE_IDS[nth_drone],
            physicsClientId=self.CLIENT,
        )
        base_velocity, _ = p.getBaseVelocity(
            self.DRONE_IDS[nth_drone],
            physicsClientId=self.CLIENT,
        )
        base_position_array = np.asarray(base_position, dtype=float)
        base_velocity_array = np.asarray(base_velocity, dtype=float)
        wind_world = np.array(
            [disturbance.wind_x, disturbance.wind_y, 0.0],
            dtype=float,
        )
        relative_velocity = base_velocity_array - wind_world
        wind_force = -0.5 * self.AIR_DENSITY_KG_M3 * self.WIND_CDA_M2 * (
            np.linalg.norm(relative_velocity) * relative_velocity
            - np.linalg.norm(base_velocity_array) * base_velocity_array
        )
        p.applyExternalForce(
            self.DRONE_IDS[nth_drone],
            -1,
            forceObj=wind_force.tolist(),
            posObj=base_position_array.tolist(),
            flags=p.WORLD_FRAME,
            physicsClientId=self.CLIENT,
        )
        self._physics_substeps_started += 1


__all__ = ["HiddenDisturbanceCircularTD3Env", "PIDShapingConfig"]
