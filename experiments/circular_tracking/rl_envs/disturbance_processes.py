"""Deterministic hidden disturbance schedules for circular tracking."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True, slots=True)
class HiddenDisturbanceSample:
    """One immutable wind and actuator-efficiency sample."""

    wind_x: float
    wind_y: float
    thrust_efficiency: float
    torque_efficiency: float

    def __post_init__(self) -> None:
        for field_name in (
            "wind_x",
            "wind_y",
            "thrust_efficiency",
            "torque_efficiency",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))

    @property
    def wind_xy(self) -> tuple[float, float]:
        """Return the immutable horizontal wind vector."""

        return (self.wind_x, self.wind_y)


class HiddenDisturbanceProcess:
    """Pre-generated piecewise-linear hidden disturbance process."""

    PROFILES = frozenset(
        {
            "standard",
            "random_wind",
            "actuator_loss",
            "compound",
            "unseen",
        }
    )

    _WIND_PROFILES = frozenset({"random_wind", "compound", "unseen"})
    _LOSS_PROFILES = frozenset({"actuator_loss", "compound", "unseen"})
    _NOMINAL_SAMPLE = HiddenDisturbanceSample(0.0, 0.0, 1.0, 1.0)

    def __init__(self, seed: int, profile: str, horizon_sec: float) -> None:
        if profile not in self.PROFILES:
            raise ValueError(f"Unsupported disturbance profile: {profile}")
        if isinstance(seed, (bool, np.bool_)) or not isinstance(
            seed,
            (int, np.integer),
        ):
            raise TypeError("seed must be an integer")
        if isinstance(horizon_sec, (bool, np.bool_)) or not isinstance(
            horizon_sec,
            (int, float, np.integer, np.floating),
        ):
            raise TypeError("horizon_sec must be a finite positive number")

        horizon = float(horizon_sec)
        if not math.isfinite(horizon) or horizon <= 0.0:
            raise ValueError("horizon_sec must be finite and positive")

        self.profile = profile
        self.horizon_sec = horizon
        self._rng = np.random.Generator(np.random.PCG64(int(seed)))

        if profile == "standard":
            self._knot_times = (0.0,)
            self._knot_values = (self._NOMINAL_SAMPLE,)
            return

        knot_times = [0.0]
        knot_values = [self._draw_value()]
        interval_min, interval_max = self._interval_range()
        while knot_times[-1] < self.horizon_sec:
            interval = float(self._rng.uniform(interval_min, interval_max))
            knot_times.append(float(knot_times[-1] + interval))
            knot_values.append(self._draw_value())

        self._knot_times = tuple(knot_times)
        self._knot_values = tuple(knot_values)

    @property
    def knot_times(self) -> tuple[float, ...]:
        """Return immutable knot times for the generated schedule."""

        return self._knot_times

    @property
    def knot_values(self) -> tuple[HiddenDisturbanceSample, ...]:
        """Return immutable values corresponding to :attr:`knot_times`."""

        return self._knot_values

    def _interval_range(self) -> tuple[float, float]:
        if self.profile == "unseen":
            return (0.5, 1.5)
        return (1.0, 3.0)

    def _draw_value(self) -> HiddenDisturbanceSample:
        if self.profile in self._WIND_PROFILES:
            wind_limit = 2.5 if self.profile == "unseen" else 1.5
            radius = wind_limit * math.sqrt(float(self._rng.random()))
            angle = float(self._rng.uniform(0.0, 2.0 * math.pi))
            wind_x = float(radius * math.cos(angle))
            wind_y = float(radius * math.sin(angle))
            wind_norm = math.hypot(wind_x, wind_y)
            if wind_norm > wind_limit:
                scale = wind_limit / wind_norm
                wind_x *= scale
                wind_y *= scale
        else:
            wind_x = 0.0
            wind_y = 0.0

        if self.profile in self._LOSS_PROFILES:
            efficiency_min, efficiency_max = (
                (0.80, 0.90) if self.profile == "unseen" else (0.90, 1.00)
            )
            thrust_efficiency = float(
                self._rng.uniform(efficiency_min, efficiency_max)
            )
            torque_efficiency = float(
                self._rng.uniform(efficiency_min, efficiency_max)
            )
        else:
            thrust_efficiency = 1.0
            torque_efficiency = 1.0

        return HiddenDisturbanceSample(
            wind_x=wind_x,
            wind_y=wind_y,
            thrust_efficiency=thrust_efficiency,
            torque_efficiency=torque_efficiency,
        )

    def sample(self, time_sec: float) -> HiddenDisturbanceSample:
        """Interpolate the pre-generated process at a valid rollout time."""

        if isinstance(time_sec, (bool, np.bool_)) or not isinstance(
            time_sec,
            (int, float, np.integer, np.floating),
        ):
            raise ValueError(
                "time_sec must be finite and inside [0, horizon_sec]"
            )
        time = float(time_sec)
        if (
            not math.isfinite(time)
            or time < 0.0
            or time > self.horizon_sec
        ):
            raise ValueError(
                "time_sec must be finite and inside [0, horizon_sec]"
            )

        if self.profile == "standard":
            return self._NOMINAL_SAMPLE

        right_index = bisect_right(self._knot_times, time)
        left_index = right_index - 1
        if self._knot_times[left_index] == time:
            return self._knot_values[left_index]
        if right_index >= len(self._knot_times):
            return self._knot_values[-1]

        left_time = self._knot_times[left_index]
        right_time = self._knot_times[right_index]
        alpha = (time - left_time) / (right_time - left_time)
        left = self._knot_values[left_index]
        right = self._knot_values[right_index]
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


__all__ = ["HiddenDisturbanceProcess", "HiddenDisturbanceSample"]
