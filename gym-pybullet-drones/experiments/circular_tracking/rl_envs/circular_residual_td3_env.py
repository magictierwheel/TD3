"""Circular tracking environment for residual TD3 experiments."""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict

import numpy as np
import pybullet as p
import pybullet_data
from gymnasium import spaces

from gym_pybullet_drones.control.DSLPIDControl import DSLPIDControl
from gym_pybullet_drones.envs.CtrlAviary import CtrlAviary
from gym_pybullet_drones.utils.enums import DroneModel, Physics


@dataclass(frozen=True)
class DisturbanceParams:
    """Episode-level environmental parameters."""

    wind_x: float = 0.0
    wind_y: float = 0.0
    density_scale: float = 1.0
    thermal_acc_z: float = 0.0
    thrust_efficiency: float = 1.0
    torque_efficiency: float = 1.0

    @property
    def wind(self) -> np.ndarray:
        return np.array([self.wind_x, self.wind_y, 0.0], dtype=float)

    @property
    def density_loss(self) -> float:
        return 1.0 - self.density_scale

    @property
    def thrust_loss(self) -> float:
        return 1.0 - self.thrust_efficiency

    @property
    def torque_loss(self) -> float:
        return 1.0 - self.torque_efficiency


class CircularResidualTD3Env(CtrlAviary):
    """Single-drone circular tracking environment for TD3 variants.

    The public action space is a flat normalized vector for Stable-Baselines3.
    Internally `_preprocessAction()` converts that vector to a `(1, 4)` RPM
    command compatible with `BaseAviary.step()`.
    """

    SUPPORTED_MODES = {
        "pid",
        "pid_ff",
        "residual_td3",
        "disturbance_aware_residual_td3",
        "disturbance_aware_residual_td3_no_gate",
        "direct_td3",
    }
    SUPPORTED_SCENARIOS = {"standard", "wind", "thermal", "dust", "compound", "unseen"}
    SCENARIO_SETS = {
        "train": (("standard", 0.2), ("wind", 0.2), ("thermal", 0.2), ("dust", 0.2), ("compound", 0.2)),
        "validation": (("standard", 0.2), ("wind", 0.2), ("thermal", 0.2), ("dust", 0.2), ("compound", 0.2)),
        "test": (("standard", 0.2), ("wind", 0.2), ("thermal", 0.2), ("dust", 0.2), ("compound", 0.2)),
        "unseen": (("unseen", 1.0),),
    }

    POSITION_SCALE = 2.0
    VELOCITY_SCALE = 3.0
    ACCELERATION_SCALE = 5.0
    ANGLE_SCALE = np.pi
    ANGULAR_VELOCITY_SCALE = 8.0
    WIND_SCALE = 3.0
    THERMAL_ACC_SCALE = 1.0
    DENSITY_LOSS_SCALE = 0.3
    EFFICIENCY_LOSS_SCALE = 0.3

    DELTA_ACC_MAX = 2.0
    DELTA_THRUST_SCALE_MAX = 0.20
    DELTA_TORQUE_SCALE_MAX = 0.20
    K_ACC_TO_POS = 0.05
    K_ACC_TO_VEL = 0.10
    WIND_CDA = 0.05
    RHO0 = 1.225

    def __init__(
        self,
        controller_mode: str = "pid",
        scenario: str = "standard",
        scenario_set: str | None = None,
        drone_model: DroneModel = DroneModel.CF2X,
        physics: Physics = Physics.PYB,
        pyb_freq: int = 240,
        ctrl_freq: int = 48,
        duration_sec: float = 12.0,
        radius: float = 0.3,
        period: float = 10.0,
        height: float = 1.0,
        reference_velocity_gain: float = 0.0,
        pid_target_step_limit: float = 0.03,
        pid_xy_p_scale: float = 0.5,
        pid_xy_d_scale: float = 1.0,
        residual_gate_min: float = 0.0,
        gui: bool = False,
        record: bool = False,
        output_folder: str = "results",
    ) -> None:
        if controller_mode not in self.SUPPORTED_MODES:
            raise ValueError(f"Unsupported controller_mode: {controller_mode}")
        if scenario not in self.SUPPORTED_SCENARIOS:
            raise ValueError(f"Unsupported scenario: {scenario}")
        if scenario_set is not None and scenario_set not in self.SCENARIO_SETS:
            raise ValueError(f"Unsupported scenario_set: {scenario_set}")

        self.controller_mode = controller_mode
        self.scenario = scenario
        self.scenario_set = scenario_set
        self.duration_sec = float(duration_sec)
        self.radius = float(radius)
        self.period = float(period)
        self.height = float(height)
        self.reference_velocity_gain = float(reference_velocity_gain)
        self.pid_target_step_limit = float(pid_target_step_limit)
        self.pid_xy_p_scale = float(pid_xy_p_scale)
        self.pid_xy_d_scale = float(pid_xy_d_scale)
        self.residual_gate_min = float(np.clip(residual_gate_min, 0.0, 1.0))
        self.action_dim = self._action_dim_for_mode(controller_mode)
        self.obs_dim = self._obs_dim_for_mode(controller_mode)
        self._disturbance = DisturbanceParams()
        self._last_policy_action = np.zeros(self.action_dim, dtype=np.float32)
        self._prev_policy_action = np.zeros(self.action_dim, dtype=np.float32)
        self._last_action_delta = 0.0
        self._last_action_energy = 0.0
        self._last_saturation_fraction = 0.0
        self._last_gate = 0.0
        self._last_pid_rpm = np.zeros(4, dtype=float)
        self._last_rpm = np.zeros(4, dtype=float)
        self._failure_reason = ""
        self._episode_rng = np.random.default_rng(0)

        initial_xyzs = np.array([[self.radius, 0.0, self.height]], dtype=float)
        initial_rpys = np.zeros((1, 3), dtype=float)

        super().__init__(
            drone_model=drone_model,
            num_drones=1,
            neighbourhood_radius=np.inf,
            initial_xyzs=initial_xyzs,
            initial_rpys=initial_rpys,
            physics=physics,
            pyb_freq=pyb_freq,
            ctrl_freq=ctrl_freq,
            gui=gui,
            record=record,
            obstacles=False,
            user_debug_gui=False,
            output_folder=output_folder,
        )
        self.pid_controller = DSLPIDControl(drone_model=drone_model)
        self.residual_pid_controller = DSLPIDControl(drone_model=drone_model)
        self._base_p_coeff_for = self.pid_controller.P_COEFF_FOR.copy()
        self._base_d_coeff_for = self.pid_controller.D_COEFF_FOR.copy()
        self._configure_pid_gains()

    def reset(self, seed: int | None = None, options: dict | None = None):
        if seed is not None:
            self._episode_rng = np.random.default_rng(seed)

        if options and "scenario" in options:
            scenario = options["scenario"]
            if scenario not in self.SUPPORTED_SCENARIOS:
                raise ValueError(f"Unsupported scenario: {scenario}")
            self.scenario = scenario
        elif self.scenario_set:
            self.scenario = self._sample_scenario_from_set(self._episode_rng)

        self._disturbance = self._sample_disturbance(self._episode_rng)
        self._last_policy_action = np.zeros(self.action_dim, dtype=np.float32)
        self._prev_policy_action = np.zeros(self.action_dim, dtype=np.float32)
        self._last_action_delta = 0.0
        self._last_action_energy = 0.0
        self._last_saturation_fraction = 0.0
        self._last_gate = 0.0
        self._last_pid_rpm = np.zeros(4, dtype=float)
        self._last_rpm = np.zeros(4, dtype=float)
        self._failure_reason = ""
        if hasattr(self, "pid_controller"):
            self.pid_controller.reset()
            self.residual_pid_controller.reset()
            self._configure_pid_gains()
        return super().reset(seed=seed, options=options)

    def _action_dim_for_mode(self, mode: str) -> int:
        if mode == "direct_td3":
            return 4
        if mode in {
            "residual_td3",
            "disturbance_aware_residual_td3",
            "disturbance_aware_residual_td3_no_gate",
        }:
            return 5
        return 1

    def _obs_dim_for_mode(self, mode: str) -> int:
        if mode == "direct_td3":
            return 33
        if mode in {"disturbance_aware_residual_td3", "disturbance_aware_residual_td3_no_gate"}:
            return 41
        if mode in {"pid", "pid_ff"}:
            return 30
        return 34

    def _actionSpace(self):
        return spaces.Box(
            low=-np.ones(self.action_dim, dtype=np.float32),
            high=np.ones(self.action_dim, dtype=np.float32),
            dtype=np.float32,
        )

    def _observationSpace(self):
        return spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.obs_dim,),
            dtype=np.float32,
        )

    def _computeObs(self):
        state = self._getDroneStateVector(0)
        ref = self._reference(self._current_time())
        pos = state[0:3]
        rpy = state[7:10]
        vel = state[10:13]
        ang_vel = state[13:16]
        pos_error = ref["pos"] - pos
        vel_error = ref["vel"] - vel

        obs_parts = [
            pos / self.POSITION_SCALE,
            vel / self.VELOCITY_SCALE,
            rpy / self.ANGLE_SCALE,
            ang_vel / self.ANGULAR_VELOCITY_SCALE,
            ref["pos"] / self.POSITION_SCALE,
            ref["vel"] / self.VELOCITY_SCALE,
            ref["acc"] / self.ACCELERATION_SCALE,
            pos_error / self.POSITION_SCALE,
            vel_error / self.VELOCITY_SCALE,
            np.array([np.sin(ref["phase_angle"]), np.cos(ref["phase_angle"])]),
            self._last_policy_action.astype(float),
        ]
        if self.controller_mode in {"disturbance_aware_residual_td3", "disturbance_aware_residual_td3_no_gate"}:
            disturbance_obs = np.array(
                [
                    self._disturbance.wind_x / self.WIND_SCALE,
                    self._disturbance.wind_y / self.WIND_SCALE,
                    0.0,
                    self._disturbance.density_loss / self.DENSITY_LOSS_SCALE,
                    self._disturbance.thermal_acc_z / self.THERMAL_ACC_SCALE,
                    self._disturbance.thrust_loss / self.EFFICIENCY_LOSS_SCALE,
                    self._disturbance.torque_loss / self.EFFICIENCY_LOSS_SCALE,
                ],
                dtype=float,
            )
            obs_parts.append(disturbance_obs)

        obs = np.concatenate(obs_parts).astype(np.float32)
        if obs.shape != self.observation_space.shape:
            raise RuntimeError(
                f"Observation shape {obs.shape} does not match {self.observation_space.shape}"
            )
        return obs

    def _preprocessAction(self, action):
        flat_action = np.asarray(action, dtype=float).reshape(-1)
        if flat_action.size != self.action_dim:
            raise ValueError(
                f"Expected action_dim={self.action_dim}, got action shape {np.asarray(action).shape}"
            )
        flat_action = np.clip(flat_action, -1.0, 1.0)
        state = self._getDroneStateVector(0)
        ref = self._reference(self._current_time())

        base_target_vel = self.reference_velocity_gain * ref["vel"]
        base_target_pos = self._limit_pid_target(state[0:3], ref["pos"])
        pid_rpm = self._compute_pid_rpm(state, base_target_pos, base_target_vel, ref["yaw"])
        rpm = pid_rpm.copy()
        gate = 0.0

        if self.controller_mode == "direct_td3":
            rpm_delta = 0.25 * (self.MAX_RPM - self.HOVER_RPM)
            rpm = self.HOVER_RPM + flat_action * rpm_delta
        elif self.controller_mode == "pid_ff":
            feedforward_acc = self._disturbance_compensation_accel(state)
            target_pos = self._limit_pid_target(state[0:3], ref["pos"] + self.K_ACC_TO_POS * feedforward_acc)
            target_vel = base_target_vel + self.K_ACC_TO_VEL * feedforward_acc
            rpm = self._compute_pid_rpm(
                state,
                target_pos,
                target_vel,
                ref["yaw"],
                controller=self.residual_pid_controller,
            )
            rpm = self._apply_pid_feedforward_scales(rpm)
        elif self.controller_mode in {
            "residual_td3",
            "disturbance_aware_residual_td3",
            "disturbance_aware_residual_td3_no_gate",
        }:
            gate = self._safety_gate(pid_rpm) if self.controller_mode == "disturbance_aware_residual_td3" else 1.0
            residual_acc = gate * flat_action[0:3] * self.DELTA_ACC_MAX
            target_pos = self._limit_pid_target(state[0:3], ref["pos"] + self.K_ACC_TO_POS * residual_acc)
            target_vel = base_target_vel + self.K_ACC_TO_VEL * residual_acc
            rpm = self._compute_pid_rpm(
                state,
                target_pos,
                target_vel,
                ref["yaw"],
                controller=self.residual_pid_controller,
            )
            thrust_scale = 1.0 + gate * flat_action[3] * self.DELTA_THRUST_SCALE_MAX
            torque_scale = 1.0 + gate * flat_action[4] * self.DELTA_TORQUE_SCALE_MAX
            rpm = self._apply_rpm_scales(rpm, thrust_scale, torque_scale)
        elif self.controller_mode == "pid":
            rpm = pid_rpm

        rpm = np.clip(rpm, 0.0, self.MAX_RPM)
        self._prev_policy_action = self._last_policy_action.copy()
        self._last_policy_action = flat_action.astype(np.float32)
        self._last_action_delta = float(np.mean((self._last_policy_action - self._prev_policy_action) ** 2))
        self._last_action_energy = float(np.mean(self._last_policy_action**2))
        self._last_saturation_fraction = self._compute_saturation_fraction(rpm)
        self._last_gate = float(gate)
        self._last_pid_rpm = pid_rpm.copy()
        self._last_rpm = rpm.copy()
        return rpm.reshape(1, 4)

    def feedforward_residual_action(self) -> np.ndarray:
        """Return a PID-FF-inspired residual action for imitation warm-starts.

        The returned action uses the same normalized 5-D semantics as residual
        TD3. For the gated disturbance-aware mode, the target accounts for the
        current safety gate so the effective residual approximates the analytic
        PID-FF correction. In standard conditions the gate is zero and the
        method returns a zero residual target.
        """
        if self.action_dim != 5:
            raise RuntimeError("feedforward_residual_action() is only defined for residual modes")

        state = self._getDroneStateVector(0)
        ref = self._reference(self._current_time())
        base_target_vel = self.reference_velocity_gain * ref["vel"]
        base_target_pos = self._limit_pid_target(state[0:3], ref["pos"])
        pid_rpm = self._compute_pid_rpm(state, base_target_pos, base_target_vel, ref["yaw"])
        if self.controller_mode == "disturbance_aware_residual_td3":
            gate = self._safety_gate(pid_rpm)
        else:
            gate = 1.0

        action = np.zeros(5, dtype=np.float32)
        if gate <= 1e-6:
            return action

        feedforward_acc = self._disturbance_compensation_accel(state)
        action[0:3] = np.clip(
            feedforward_acc / (gate * self.DELTA_ACC_MAX),
            -1.0,
            1.0,
        )

        thrust_efficiency = max(self._disturbance.thrust_efficiency, 0.1)
        thermal_scale = max(0.2, 1.0 - self._disturbance.thermal_acc_z / max(self.G, 1e-6))
        desired_thrust_scale = float(np.sqrt(thermal_scale / thrust_efficiency))
        action[3] = np.clip(
            (desired_thrust_scale - 1.0) / (gate * self.DELTA_THRUST_SCALE_MAX),
            -1.0,
            1.0,
        )
        action[4] = 0.0
        return action.astype(np.float32)

    def _computeReward(self):
        state = self._getDroneStateVector(0)
        ref = self._reference(self._current_time())
        pos_error = np.linalg.norm(ref["pos"] - state[0:3]) / self.POSITION_SCALE
        vel_error = np.linalg.norm(ref["vel"] - state[10:13]) / self.VELOCITY_SCALE
        z_error = abs(state[2] - self.height) / self.POSITION_SCALE
        tilt = np.linalg.norm(state[7:9]) / self.ANGLE_SCALE
        reward = (
            -2.0 * pos_error
            -0.5 * vel_error
            -1.0 * z_error
            -0.2 * tilt
            -0.05 * self._last_action_energy
            -0.05 * self._last_action_delta
            -2.0 * self._last_saturation_fraction
        )
        if self._failure_reason:
            reward -= 50.0
        return float(reward)

    def _computeTerminated(self):
        state = self._getDroneStateVector(0)
        self._failure_reason = ""
        if not np.all(np.isfinite(state)):
            self._failure_reason = "non_finite_state"
        elif abs(state[2] - self.height) > 1.5:
            self._failure_reason = "altitude_error_limit"
        elif state[2] < 0.1 or state[2] > 3.0:
            self._failure_reason = "altitude_bounds"
        elif abs(state[7]) > 0.9 or abs(state[8]) > 0.9:
            self._failure_reason = "tilt_limit"
        else:
            ref = self._reference(self._current_time())
            if np.linalg.norm(state[0:2] - ref["pos"][0:2]) > 2.0:
                self._failure_reason = "horizontal_error_limit"
        return bool(self._failure_reason)

    def _computeTruncated(self):
        return bool(self._next_time() >= self.duration_sec)

    def _computeInfo(self):
        ref = self._reference(self._current_time())
        return {
            "time": self._current_time(),
            "reference": {
                "pos": ref["pos"].copy(),
                "vel": ref["vel"].copy(),
                "acc": ref["acc"].copy(),
                "phase": ref["phase"],
                "yaw": ref["yaw"],
            },
            "disturbance": asdict(self._disturbance),
            "rpm": self._last_rpm.copy(),
            "pid_rpm": self._last_pid_rpm.copy(),
            "policy_action": self._last_policy_action.copy(),
            "gate": self._last_gate,
            "saturation_fraction": self._last_saturation_fraction,
            "control_energy": float(np.mean((self._last_rpm / self.MAX_RPM) ** 2)) if self.MAX_RPM > 0 else 0.0,
            "action_delta": self._last_action_delta,
            "failure_reason": self._failure_reason,
        }

    def _physics(self, rpm, nth_drone):
        forces = np.array(rpm**2) * self.KF * self._disturbance.thrust_efficiency
        torques = np.array(rpm**2) * self.KM * self._disturbance.torque_efficiency
        if self.DRONE_MODEL == DroneModel.RACE:
            torques = -torques
        z_torque = -torques[0] + torques[1] - torques[2] + torques[3]
        for motor_idx in range(4):
            p.applyExternalForce(
                self.DRONE_IDS[nth_drone],
                motor_idx,
                forceObj=[0, 0, forces[motor_idx]],
                posObj=[0, 0, 0],
                flags=p.LINK_FRAME,
                physicsClientId=self.CLIENT,
            )
        p.applyExternalTorque(
            self.DRONE_IDS[nth_drone],
            4,
            torqueObj=[0, 0, z_torque],
            flags=p.LINK_FRAME,
            physicsClientId=self.CLIENT,
        )
        self._apply_disturbance_forces(nth_drone)

    def _apply_disturbance_forces(self, nth_drone: int) -> None:
        base_pos, _ = p.getBasePositionAndOrientation(self.DRONE_IDS[nth_drone], physicsClientId=self.CLIENT)
        linear_vel, _ = p.getBaseVelocity(self.DRONE_IDS[nth_drone], physicsClientId=self.CLIENT)
        rel_vel = np.asarray(linear_vel, dtype=float) - self._disturbance.wind
        rho = self.RHO0 * self._disturbance.density_scale
        drag_force = -0.5 * rho * self.WIND_CDA * np.linalg.norm(rel_vel) * rel_vel
        thermal_force = np.array([0.0, 0.0, self.M * self._disturbance.thermal_acc_z])
        total_force = drag_force + thermal_force
        if np.linalg.norm(total_force) > 0.0:
            p.applyExternalForce(
                self.DRONE_IDS[nth_drone],
                -1,
                forceObj=total_force.tolist(),
                posObj=base_pos,
                flags=p.WORLD_FRAME,
                physicsClientId=self.CLIENT,
            )

    def _reference(self, t: float) -> Dict[str, np.ndarray | float]:
        omega = 2.0 * np.pi / self.period
        phase_angle = omega * t
        pos = np.array(
            [
                self.radius * np.cos(phase_angle),
                self.radius * np.sin(phase_angle),
                self.height,
            ],
            dtype=float,
        )
        vel = np.array(
            [
                -self.radius * omega * np.sin(phase_angle),
                self.radius * omega * np.cos(phase_angle),
                0.0,
            ],
            dtype=float,
        )
        acc = np.array(
            [
                -self.radius * omega**2 * np.cos(phase_angle),
                -self.radius * omega**2 * np.sin(phase_angle),
                0.0,
            ],
            dtype=float,
        )
        return {
            "pos": pos,
            "vel": vel,
            "acc": acc,
            "phase": (t % self.period) / self.period,
            "phase_angle": phase_angle,
            "yaw": 0.0,
        }

    def _compute_pid_rpm(
        self,
        state: np.ndarray,
        target_pos: np.ndarray,
        target_vel: np.ndarray,
        target_yaw: float,
        controller: DSLPIDControl | None = None,
    ) -> np.ndarray:
        active_controller = controller or self.pid_controller
        rpm, _, _ = active_controller.computeControl(
            control_timestep=self.CTRL_TIMESTEP,
            cur_pos=state[0:3],
            cur_quat=state[3:7],
            cur_vel=state[10:13],
            cur_ang_vel=state[13:16],
            target_pos=target_pos,
            target_rpy=np.array([0.0, 0.0, target_yaw]),
            target_vel=target_vel,
        )
        return np.asarray(rpm, dtype=float)

    def _configure_pid_gains(self) -> None:
        for controller in (self.pid_controller, self.residual_pid_controller):
            controller.P_COEFF_FOR = self._base_p_coeff_for.copy()
            controller.D_COEFF_FOR = self._base_d_coeff_for.copy()
            controller.P_COEFF_FOR[0:2] *= self.pid_xy_p_scale
            controller.D_COEFF_FOR[0:2] *= self.pid_xy_d_scale

    def _limit_pid_target(self, current_pos: np.ndarray, desired_pos: np.ndarray) -> np.ndarray:
        delta = desired_pos - current_pos
        distance = float(np.linalg.norm(delta))
        if self.pid_target_step_limit <= 0 or distance <= self.pid_target_step_limit:
            return desired_pos
        return current_pos + delta / distance * self.pid_target_step_limit

    def _apply_rpm_scales(self, rpm: np.ndarray, thrust_scale: float, torque_scale: float) -> np.ndarray:
        mean_rpm = float(np.mean(rpm))
        centered = rpm - mean_rpm
        return mean_rpm * thrust_scale + centered * torque_scale

    def _compute_saturation_fraction(self, rpm: np.ndarray) -> float:
        low = rpm <= 0.02 * self.MAX_RPM
        high = rpm >= 0.98 * self.MAX_RPM
        return float(np.mean(np.logical_or(low, high)))

    def _disturbance_compensation_accel(self, state: np.ndarray) -> np.ndarray:
        rel_vel = state[10:13] - self._disturbance.wind
        rho = self.RHO0 * self._disturbance.density_scale
        drag_comp = 0.5 * rho * self.WIND_CDA * np.linalg.norm(rel_vel) * rel_vel / self.M
        thermal_comp = np.array([0.0, 0.0, -self._disturbance.thermal_acc_z], dtype=float)
        return drag_comp + thermal_comp

    def _apply_pid_feedforward_scales(self, rpm: np.ndarray) -> np.ndarray:
        thrust_efficiency = max(self._disturbance.thrust_efficiency, 0.1)
        thermal_scale = max(0.2, 1.0 - self._disturbance.thermal_acc_z / max(self.G, 1e-6))
        thrust_scale = np.sqrt(thermal_scale / thrust_efficiency)
        return rpm * thrust_scale

    def _safety_gate(self, pid_rpm: np.ndarray) -> float:
        disturbance_norm = np.linalg.norm(
            np.array(
                [
                    self._disturbance.wind_x / self.WIND_SCALE,
                    self._disturbance.wind_y / self.WIND_SCALE,
                    self._disturbance.thermal_acc_z / self.THERMAL_ACC_SCALE,
                    self._disturbance.density_loss / self.DENSITY_LOSS_SCALE,
                    self._disturbance.thrust_loss / self.EFFICIENCY_LOSS_SCALE,
                    self._disturbance.torque_loss / self.EFFICIENCY_LOSS_SCALE,
                ],
                dtype=float,
            )
        )
        gate_disturbance = float(np.clip(disturbance_norm, 0.0, 1.0))
        margin_upper = (self.MAX_RPM - pid_rpm) / self.MAX_RPM
        margin_lower = pid_rpm / self.MAX_RPM
        saturation_margin = float(np.min(np.minimum(margin_upper, margin_lower)))
        gate_saturation = float(np.clip(saturation_margin / 0.15, 0.0, 1.0))
        if gate_disturbance <= 1e-9:
            return 0.0
        gated = gate_disturbance * gate_saturation
        return float(min(max(gated, self.residual_gate_min), gate_saturation))

    def _sample_scenario_from_set(self, rng: np.random.Generator) -> str:
        entries = self.SCENARIO_SETS[self.scenario_set or "train"]
        scenarios = [entry[0] for entry in entries]
        probabilities = np.array([entry[1] for entry in entries], dtype=float)
        probabilities = probabilities / probabilities.sum()
        return str(rng.choice(scenarios, p=probabilities))

    def _sample_disturbance(self, rng: np.random.Generator) -> DisturbanceParams:
        if self.scenario == "standard":
            return DisturbanceParams()
        if self.scenario == "wind":
            return DisturbanceParams(
                wind_x=float(rng.uniform(-1.5, 1.5)),
                wind_y=float(rng.uniform(-1.5, 1.5)),
            )
        if self.scenario == "thermal":
            return DisturbanceParams(
                density_scale=float(rng.uniform(0.85, 1.0)),
                thermal_acc_z=float(rng.uniform(0.0, 0.8)),
            )
        if self.scenario == "dust":
            return DisturbanceParams(
                thrust_efficiency=float(rng.uniform(0.90, 1.0)),
                torque_efficiency=float(rng.uniform(0.90, 1.0)),
            )
        if self.scenario == "compound":
            return DisturbanceParams(
                wind_x=float(rng.uniform(-1.5, 1.5)),
                wind_y=float(rng.uniform(-1.5, 1.5)),
                density_scale=float(rng.uniform(0.85, 1.0)),
                thermal_acc_z=float(rng.uniform(0.0, 0.8)),
                thrust_efficiency=float(rng.uniform(0.90, 1.0)),
                torque_efficiency=float(rng.uniform(0.90, 1.0)),
            )
        if self.scenario == "unseen":
            return DisturbanceParams(
                wind_x=float(rng.uniform(-2.5, 2.5)),
                wind_y=float(rng.uniform(-2.5, 2.5)),
                density_scale=float(rng.uniform(0.75, 0.90)),
                thermal_acc_z=float(rng.uniform(0.5, 1.2)),
                thrust_efficiency=float(rng.uniform(0.82, 0.92)),
                torque_efficiency=float(rng.uniform(0.82, 0.92)),
            )
        raise ValueError(f"Unsupported scenario: {self.scenario}")

    def _current_time(self) -> float:
        return float(self.step_counter * self.PYB_TIMESTEP)

    def _next_time(self) -> float:
        return float((self.step_counter + self.PYB_STEPS_PER_CTRL) * self.PYB_TIMESTEP)

    def _housekeeping(self):
        """Initialize PyBullet state with an ASCII-safe URDF asset path.

        PyBullet on Windows can fail to load URDF files when the absolute path
        contains non-ASCII characters. This project often lives in a Chinese
        path, so the paper environment mirrors the package assets into the
        system temp directory before loading the drone model.
        """
        self.RESET_TIME = time.time()
        self.step_counter = 0
        self.first_render_call = True
        self.X_AX = -1 * np.ones(self.NUM_DRONES)
        self.Y_AX = -1 * np.ones(self.NUM_DRONES)
        self.Z_AX = -1 * np.ones(self.NUM_DRONES)
        self.GUI_INPUT_TEXT = -1 * np.ones(self.NUM_DRONES)
        self.USE_GUI_RPM = False
        self.last_input_switch = 0
        self.last_clipped_action = np.zeros((self.NUM_DRONES, 4))
        self.gui_input = np.zeros(4)
        self.pos = np.zeros((self.NUM_DRONES, 3))
        self.quat = np.zeros((self.NUM_DRONES, 4))
        self.rpy = np.zeros((self.NUM_DRONES, 3))
        self.vel = np.zeros((self.NUM_DRONES, 3))
        self.ang_v = np.zeros((self.NUM_DRONES, 3))
        if self.PHYSICS == Physics.DYN:
            self.rpy_rates = np.zeros((self.NUM_DRONES, 3))

        p.setGravity(0, 0, -self.G, physicsClientId=self.CLIENT)
        p.setRealTimeSimulation(0, physicsClientId=self.CLIENT)
        p.setTimeStep(self.PYB_TIMESTEP, physicsClientId=self.CLIENT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.CLIENT)
        self.PLANE_ID = p.loadURDF("plane.urdf", physicsClientId=self.CLIENT)

        asset_dir = self._ascii_asset_dir()
        drone_urdf = str(asset_dir / self.URDF)
        self.DRONE_IDS = np.array(
            [
                p.loadURDF(
                    drone_urdf,
                    self.INIT_XYZS[i, :],
                    p.getQuaternionFromEuler(self.INIT_RPYS[i, :]),
                    flags=p.URDF_USE_INERTIA_FROM_FILE,
                    physicsClientId=self.CLIENT,
                )
                for i in range(self.NUM_DRONES)
            ]
        )
        if self.GUI and self.USER_DEBUG:
            for i in range(self.NUM_DRONES):
                self._showDroneLocalAxes(i)
        if self.OBSTACLES:
            self._addObstacles()

    def _ascii_asset_dir(self) -> Path:
        target = Path(tempfile.gettempdir()) / "gym_pybullet_drones_assets_ascii"
        marker = target / ".asset_mirror_complete"
        if marker.exists():
            return target
        source = Path(__file__).resolve().parents[3] / "gym_pybullet_drones" / "assets"
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            destination = target / item.name
            if item.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
        marker.write_text("ok", encoding="ascii")
        return target
