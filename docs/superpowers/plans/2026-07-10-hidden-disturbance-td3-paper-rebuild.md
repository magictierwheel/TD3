# Hidden-Disturbance TD3 Paper Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the circular-tracking paper around a fair comparison of PID, end-to-end Direct TD3, and PID-based Residual TD3 under hidden time-varying disturbances.

**Architecture:** Keep the existing oracle/PID-FF environment and result folders untouched as legacy evidence. Add a new hidden-disturbance environment with one shared observable-state interface, matched four-motor action semantics, state-derived safety gating, and a reward whose terminal penalty is computed from the current state. Use staged 20k/50k/100k training gates and paired held-out evaluation.

**Tech Stack:** Python 3.11, PyBullet, Gymnasium, Stable-Baselines3 TD3, NumPy, pytest, CSV/JSON, Matplotlib.

---

## File Map

- Create `experiments/circular_tracking/rl_envs/disturbance_processes.py`: hidden time-varying wind and actuator-efficiency processes.
- Create `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py`: new fair three-controller environment.
- Modify `experiments/circular_tracking/rl_envs/__init__.py`: export the new environment without changing the legacy export.
- Create `tests/circular_tracking/test_hidden_disturbance_td3_env.py`: information-boundary, reward, action, and PID invariants.
- Create `experiments/circular_tracking/scripts/td3/tune_hidden_pid.py`: freeze a valid nominal PID configuration.
- Create `experiments/circular_tracking/scripts/td3/train_hidden_td3.py`: matched Direct/Residual training and checkpoints.
- Create `experiments/circular_tracking/scripts/td3/evaluate_hidden_td3.py`: paired held-out rollout export.
- Create `experiments/circular_tracking/scripts/td3/summarize_hidden_td3.py`: hierarchical aggregation and confidence intervals.
- Create `experiments/circular_tracking/analysis/hidden_td3_metric_schema.md`: revised metric contract.
- Create `experiments/circular_tracking/analysis/hidden_td3_claim_evidence_ledger.csv`: revised claims only.
- Create `docs/paper/revised_outline.md`, `revised_method.md`, and `revised_results.md`: new-paper writing surface.
- Preserve `experiments/circular_tracking/rl_envs/circular_residual_td3_env.py` and existing `td3_residual_paper` results as legacy evidence.

### Task 1: Lock Legacy Evidence And Add The New Result Namespace

**Files:**
- Create: `experiments/circular_tracking/results/hidden_disturbance_td3_paper/README.md`
- Modify: `.gitignore`

- [x] **Step 1: Write the result-boundary README**

```markdown
# Hidden-Disturbance TD3 Paper Results

Only revised PID, Direct TD3, and Residual TD3 runs with no disturbance truth belong here.
Legacy oracle-observation, PID-FF imitation, gate-min, and 5000-step runs remain under
`../td3_residual_paper/` and must never be merged into revised main tables.

Required run metadata: git revision, Python/package versions, training seed, validation
seeds, test seeds, disturbance ranges, observation schema, action schema, reward version,
PID configuration hash, and model checkpoint identity.
```

- [x] **Step 2: Add only disposable training artifacts to `.gitignore`**

Add patterns for replay buffers, tensorboard logs, caches, and videos under the new namespace. Do not ignore CSV/JSON summaries, frozen configuration files, or manuscript figures.

- [x] **Step 3: Verify the legacy tree is unchanged**

Run:

```powershell
git diff -- experiments/circular_tracking/rl_envs/circular_residual_td3_env.py experiments/circular_tracking/results/td3_residual_paper
```

Expected: no new diff produced by this task.

- [x] **Step 4: Commit**

```powershell
git add .gitignore experiments/circular_tracking/results/hidden_disturbance_td3_paper/README.md
git commit -m "docs: separate revised hidden-disturbance results"
```

### Task 2: Implement Deterministic Hidden Disturbance Processes

**Files:**
- Create: `experiments/circular_tracking/rl_envs/disturbance_processes.py`
- Test: `tests/circular_tracking/test_hidden_disturbance_td3_env.py`

- [x] **Step 1: Write failing reproducibility and range tests**

```python
import numpy as np

from experiments.circular_tracking.rl_envs.disturbance_processes import HiddenDisturbanceProcess


def test_hidden_disturbance_process_repeats_for_same_seed():
    left = HiddenDisturbanceProcess(seed=9000, profile="compound", horizon_sec=20.0)
    right = HiddenDisturbanceProcess(seed=9000, profile="compound", horizon_sec=20.0)
    left_values = [left.sample(t) for t in np.linspace(0.0, 20.0, 41)]
    right_values = [right.sample(t) for t in np.linspace(0.0, 20.0, 41)]
    assert left_values == right_values


def test_train_profile_stays_inside_declared_ranges():
    process = HiddenDisturbanceProcess(seed=9001, profile="compound", horizon_sec=20.0)
    for t in np.linspace(0.0, 20.0, 201):
        value = process.sample(float(t))
        assert np.linalg.norm(value.wind_xy) <= 1.5 + 1e-9
        assert 0.90 <= value.thrust_efficiency <= 1.0
        assert 0.90 <= value.torque_efficiency <= 1.0
```

Before production code, extend the RED matrix with unit-test seeds only from `9000-9099`:

- immutable scalar sample and tuple-valued `wind_xy`;
- query-order-independent same-seed reproducibility;
- no mutation of global NumPy RNG state;
- exact disabled-component invariants for all five profiles;
- full knot intervals within the declared ranges, with a final bracketing knot at or beyond the horizon;
- exact piecewise-linear values at knots and midpoints;
- a 30-second process with non-frozen knots and samples after 20 seconds;
- fail-fast invalid profile, seed, horizon, and nonfinite/out-of-domain sample times.

- [x] **Step 2: Run the tests and verify import failure**

Run:

```powershell
py -3.11 -m pytest tests/circular_tracking/test_hidden_disturbance_td3_env.py -v
```

Expected: FAIL because `disturbance_processes.py` does not exist.

- [x] **Step 3: Implement the process contract**

Implement an immutable sample type and a process that pre-generates piecewise-linear knots every 1-3 seconds for training profiles and every 0.5-1.5 seconds for `unseen`. Use train ranges `wind <= 1.5 m/s` and efficiencies `0.90-1.00`; use unseen ranges `wind <= 2.5 m/s` and efficiencies `0.80-0.90`. `standard` must return zero wind and unit efficiencies. The RNG must be local to the process and seeded explicitly. `horizon_sec` is required, finite, positive, and equal to the rollout duration: training passes 20 seconds and evaluation passes 30 seconds. Generate full sampled intervals until a final knot brackets the horizon instead of clipping the last interval, so the final 10 evaluation seconds cannot reuse a frozen 20-second terminal sample. Sampling is valid only for finite `time_sec` in the closed interval `[0, horizon_sec]`.

```python
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class HiddenDisturbanceSample:
    wind_x: float
    wind_y: float
    thrust_efficiency: float
    torque_efficiency: float

    @property
    def wind_xy(self) -> tuple[float, float]:
        return (self.wind_x, self.wind_y)


class HiddenDisturbanceProcess:
    PROFILES = {"standard", "random_wind", "actuator_loss", "compound", "unseen"}

    def __init__(self, seed: int, profile: str, horizon_sec: float):
        if profile not in self.PROFILES:
            raise ValueError(f"Unsupported disturbance profile: {profile}")
        if not isinstance(seed, (int, np.integer)):
            raise TypeError("seed must be an integer")
        self.profile = profile
        self.horizon_sec = float(horizon_sec)
        if not np.isfinite(self.horizon_sec) or self.horizon_sec <= 0.0:
            raise ValueError("horizon_sec must be finite and positive")
        self.rng = np.random.default_rng(int(seed))
        if self.profile == "standard":
            self.times = np.asarray([0.0, self.horizon_sec], dtype=float)
            self.values = [self._draw_value(), self._draw_value()]
            return
        times = [0.0]
        while times[-1] < self.horizon_sec:
            interval = (0.5, 1.5) if self.profile == "unseen" else (1.0, 3.0)
            times.append(times[-1] + float(self.rng.uniform(*interval)))
        self.times = np.asarray(times, dtype=float)
        self.values = [self._draw_value() for _ in self.times]

    def _draw_value(self) -> HiddenDisturbanceSample:
        if self.profile == "standard":
            return HiddenDisturbanceSample(0.0, 0.0, 1.0, 1.0)
        wind_limit = 2.5 if self.profile == "unseen" else 1.5
        efficiency_range = (0.80, 0.90) if self.profile == "unseen" else (0.90, 1.00)
        use_wind = self.profile in {"random_wind", "compound", "unseen"}
        use_loss = self.profile in {"actuator_loss", "compound", "unseen"}
        if use_wind:
            radius = wind_limit * float(np.sqrt(self.rng.random()))
            angle = float(self.rng.uniform(0.0, 2.0 * np.pi))
            wind_x = float(radius * np.cos(angle))
            wind_y = float(radius * np.sin(angle))
        else:
            wind_x = 0.0
            wind_y = 0.0
        thrust = float(self.rng.uniform(*efficiency_range)) if use_loss else 1.0
        torque = float(self.rng.uniform(*efficiency_range)) if use_loss else 1.0
        return HiddenDisturbanceSample(wind_x, wind_y, thrust, torque)

    def sample(self, time_sec: float) -> HiddenDisturbanceSample:
        t = float(time_sec)
        if not np.isfinite(t) or t < 0.0 or t > self.horizon_sec:
            raise ValueError("time_sec must be finite and inside [0, horizon_sec]")
        right = int(np.searchsorted(self.times, t, side="right"))
        if right == 0:
            return self.values[0]
        if right >= len(self.times):
            return self.values[-1]
        left = right - 1
        width = self.times[right] - self.times[left]
        alpha = 0.0 if width <= 0.0 else (t - self.times[left]) / width
        a, b = self.values[left], self.values[right]
        return HiddenDisturbanceSample(
            wind_x=float((1.0 - alpha) * a.wind_x + alpha * b.wind_x),
            wind_y=float((1.0 - alpha) * a.wind_y + alpha * b.wind_y),
            thrust_efficiency=float((1.0 - alpha) * a.thrust_efficiency + alpha * b.thrust_efficiency),
            torque_efficiency=float((1.0 - alpha) * a.torque_efficiency + alpha * b.torque_efficiency),
        )
```

- [x] **Step 4: Run the tests**

Expected: the complete process RED matrix passes.

- [x] **Step 5: Commit**

```powershell
git add experiments/circular_tracking/rl_envs/disturbance_processes.py tests/circular_tracking/test_hidden_disturbance_td3_env.py
git commit -m "feat: add hidden time-varying disturbances"
```

### Task 3: Build The Fair Three-Controller Environment

**Files:**
- Create: `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py`
- Modify: `experiments/circular_tracking/rl_envs/__init__.py`
- Test: `tests/circular_tracking/test_hidden_disturbance_td3_env.py`

- [x] **Step 1: Add failing interface tests**

```python
import numpy as np

from experiments.circular_tracking.rl_envs import HiddenDisturbanceCircularTD3Env
from experiments.circular_tracking.rl_envs.disturbance_processes import HiddenDisturbanceSample


def test_policy_observation_is_independent_of_hidden_truth_metadata():
    env = HiddenDisturbanceCircularTD3Env(controller_mode="residual_td3", disturbance_profile="compound")
    try:
        obs_a, _ = env.reset(seed=9001)
        env._disturbance = HiddenDisturbanceSample(1.0, -0.5, 0.90, 0.90)
        obs_b = env._computeObs()
        np.testing.assert_allclose(obs_a, obs_b)
        assert env.observation_schema == (
            "position", "velocity", "attitude", "angular_velocity", "reference",
            "tracking_error", "history", "pid_rpm", "last_action",
        )
    finally:
        env.close()


def test_zero_residual_matches_pid_motor_command():
    pid = HiddenDisturbanceCircularTD3Env(controller_mode="pid", disturbance_profile="compound")
    residual = HiddenDisturbanceCircularTD3Env(controller_mode="residual_td3", disturbance_profile="compound")
    try:
        pid.reset(seed=9002)
        residual.reset(seed=9002)
        for _ in range(50):
            _, _, p_term, p_trunc, p_info = pid.step(np.zeros(1, dtype=np.float32))
            _, _, r_term, r_trunc, r_info = residual.step(np.zeros(4, dtype=np.float32))
            np.testing.assert_allclose(p_info["rpm"], r_info["rpm"], rtol=0.0, atol=1e-6)
            assert (p_term, p_trunc) == (r_term, r_trunc)
    finally:
        pid.close()
        residual.close()
```

Also add RED tests for the exact supported-mode set, matched four-vector TD3 action spaces, Direct/Residual mapping formulas, eight-step shared history, observation idempotence and PID-state purity, gate thresholds/truth invariance, reward invariance for identical applied RPM, monotonic per-substep disturbance times, live-base-position world-frame force application, and separate thrust/torque efficiency scaling.

- [x] **Step 2: Verify the tests fail because the new environment is absent**

Run the test file and expect an import failure.

- [x] **Step 3: Implement the environment modes and matched motor interface**

Subclass `CtrlAviary` directly; do not subclass or copy implementation details from the legacy residual environment. Pin the first implementation to frozen `Physics.PYB`, 240 Hz physics, and 48 Hz control. Maintain a dedicated completed-physics-substep counter because `BaseAviary.step()` does not advance `step_counter` inside its five `_physics()` calls. Compute the stateful PID command exactly once per control instant, cache it for action preprocessing and observation, and keep `_computeObs()` idempotent.

The new class must expose only `pid`, `direct_td3`, `residual_td3`, and `residual_td3_no_gate`. Direct TD3 and both residual modes use four-dimensional actions. Residual commands use:

```python
delta_rpm = gate * action * residual_rpm_limit
rpm = np.clip(pid_rpm + delta_rpm, 0.0, self.MAX_RPM)
```

Direct commands use:

```python
rpm = np.clip(self.HOVER_RPM + action * direct_rpm_span, 0.0, self.MAX_RPM)
```

The observation contains current and short-history measurable state, reference, tracking error, prior action, and the current frozen PID RPM for both TD3 modes. Direct and Residual must have the same schema, Box bounds, and observation dimension; PID RPM is controller-derived nonprivileged information, not disturbance truth. It must never contain the disturbance sample, profile name, or seed.

- [x] **Step 4: Replace the oracle gate with an observable-state gate**

Use tracking error and motor headroom only:

```python
error_gate = np.clip((position_error - 0.03) / (0.20 - 0.03), 0.0, 1.0)
headroom = np.min(np.minimum(pid_rpm, self.MAX_RPM - pid_rpm)) / self.MAX_RPM
headroom_gate = np.clip(headroom / 0.10, 0.0, 1.0)
gate = float(error_gate * headroom_gate)
```

Keep these thresholds in the frozen environment configuration and include a no-gate residual mode for ablation.

- [x] **Step 5: Apply hidden disturbances only in physics and logging**

At every PyBullet substep, sample the process at `substep_index / 240` before applying that substep. Scale motor thrust by the sampled scalar thrust efficiency and yaw/reaction torque by the sampled scalar torque efficiency. Query the live base position and velocity from PyBullet every substep, then apply the frozen incremental wind force

```python
relative = base_velocity - wind_world
wind_force = -0.5 * rho * cda * (
    np.linalg.norm(relative) * relative
    - np.linalg.norm(base_velocity) * base_velocity
)
```

to `linkIndex=-1` at the live `base_position` in `p.WORLD_FRAME`. This makes the extra standard-scene wind force exactly zero and prevents the historical world-origin moment bug. Cache the exact sample actually applied and put it in `info["disturbance_truth"]` for offline analysis only; do not resample in info and do not route truth through `_computeObs()`, gate, reward, or model selection.

- [x] **Step 6: Export and run the tests**

Modify `rl_envs/__init__.py` to export `HiddenDisturbanceCircularTD3Env`. Run the test file; expect observation-boundary and zero-residual tests to PASS.

- [x] **Step 7: Commit**

```powershell
git add experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py experiments/circular_tracking/rl_envs/__init__.py tests/circular_tracking/test_hidden_disturbance_td3_env.py
git commit -m "feat: add fair hidden-disturbance TD3 environment"
```

### Corrective Addendum A1: Reopen The Shared TD3 Observation Contract

This pre-training protocol correction supersedes the earlier residual-only PID-RPM wording. It changes no seeds, budgets, thresholds, reward, disturbance range, or held-out result; it fixes a discovered information/capacity confound before any Stage A run.

**Files:**
- Modify: `experiments/circular_tracking/config/hidden_td3_protocol.json`
- Modify: `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py`
- Modify: `tests/circular_tracking/test_hidden_disturbance_td3_env.py`
- Modify: `experiments/circular_tracking/scripts/td3/tune_hidden_pid.py`
- Modify: `experiments/circular_tracking/config/hidden_pid_frozen.json`
- Modify: `experiments/circular_tracking/scripts/td3/train_hidden_td3.py`
- Modify: `tests/circular_tracking/test_hidden_pid_acceptance.py`
- Modify: `tests/circular_tracking/test_hidden_td3_training_config.py`

- [x] **Step 1: Freeze Protocol 1.0.2 before any new TD3 smoke or training**

Freeze one shared policy observation: eight 32-dimensional nonprivileged history frames plus the current four-dimensional command emitted by the same frozen PID at the same control instant, for a 260-dimensional Direct and Residual TD3 input. The PID command is controller-derived rather than disturbance truth; it must not be supplied to only one TD3 mode.

- [x] **Step 2: Write RED parity and boundary tests**

Require Direct, Residual, and residual-no-gate to have equal TD3 observation schema, shape (260), and Box bounds after reset and a synchronized step. Require the final four Direct features to equal the cached current PID RPM; require mutation of disturbance truth/profile/seed metadata not to change either policy observation. Preserve zero-residual-equals-PID, action mapping, reward, and terminal semantics tests.

- [x] **Step 3: Correct the environment without changing PID or action behavior**

Append the already cached current PID RPM to Direct as well as the two residual modes. Do not alter PID cache timing, the PID controller, Direct's hover-centered action mapping, Residual's delta mapping, gate formula, reward, termination, disturbance physics, or privileged-information boundary.

- [ ] **Step 4: Harden current-environment PID evidence before any re-freeze**

The old immutable attempt lacks per-step traces and cannot prove all 81 candidate rankings survived the interface correction. Do not build a 162-run dual-source parity attestation. Instead, first write RED/GREEN tests and strengthen the producer/loader evidence chain: a versioned external evidence index must bind `RUNNING`, manifest, all 81 candidate records, all four shards, coverage, ranking, winner recheck, and `DONE`, with content/file hashes; the loader must traverse that index and recompute ranking from candidate records. A bare winner recheck is never sufficient.

- [ ] **Step 5: Run a new full validation-only PID grid and regenerate the freeze**

From a clean committed source, run a unique external `attempt_02` root for the canonical 81 candidates in four shards at standard seed 100 for 30 seconds, followed by a winner recheck. Independently load and verify the complete evidence chain, then regenerate `hidden_pid_frozen.json` with the new protocol/environment/source hashes and current full-ranking provenance. Never overwrite or reuse the old attempt as current evidence.

- [ ] **Step 6: Repair TD3 metadata and repeat diagnostic smoke**

Record actual policy schema, dimension, actor/critic observation input dimensions, importable module command, committed Git SHA, and source hashes. Run fresh non-overwriting Direct and Residual 200-step `attempt_02` smoke directories only after the corrected PID freeze validates. `attempt_01` is diagnostic-only.

### Task 4: Fix Terminal Reward Semantics Before Any Training

**Files:**
- Modify: `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py`
- Test: `tests/circular_tracking/test_hidden_disturbance_td3_env.py`

- [x] **Step 1: Add a failing terminal-reward test**

```python
import numpy as np


def test_terminal_transition_contains_failure_penalty(monkeypatch):
    env = HiddenDisturbanceCircularTD3Env(controller_mode="direct_td3", disturbance_profile="standard")
    try:
        env.reset(seed=9003)
        state = env._getDroneStateVector(0).copy()
        reference = env._reference(env._current_time())["pos"]
        state[0:2] = reference[0:2] + np.array([2.1, 0.0])
        monkeypatch.setattr(env, "_getDroneStateVector", lambda _: state)
        reward = env._computeReward()
        assert env._failure_reason_for_current_state() == "horizontal_error_limit"
        assert env.failure_penalty == 50.0
        assert reward <= -45.0
    finally:
        env.close()
```

- [x] **Step 2: Run the test and verify it fails**

Expected: the current reward is computed before a fresh failure reason is available.

- [x] **Step 3: Implement one pure failure-state helper**

Both reward and termination must call the same pure helper. The priority order and thresholds below are frozen in `hidden_td3_protocol.json`; do not import them from the legacy environment or change them per mode:

```python
def _failure_reason_for_current_state(self) -> str:
    state = self._getDroneStateVector(0)
    if not np.all(np.isfinite(state)):
        return "non_finite_state"
    if abs(state[2] - self.height) > 1.5 or state[2] < 0.1 or state[2] > 3.0:
        return "altitude_limit"
    if abs(state[7]) > 0.9 or abs(state[8]) > 0.9:
        return "tilt_limit"
    ref = self._reference(self._current_time())
    if np.linalg.norm(state[0:2] - ref["pos"][0:2]) > 2.0:
        return "horizontal_error_limit"
    return ""
```

`_computeReward()` reads this helper directly and subtracts `failure_penalty`; `_computeTerminated()` returns whether the same helper is non-empty.

- [x] **Step 4: Run all environment tests**

Expected: terminal reward, termination reason, zero residual, and hidden-information tests PASS.

- [x] **Step 5: Commit**

```powershell
git add experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py tests/circular_tracking/test_hidden_disturbance_td3_env.py
git commit -m "fix: include terminal failure penalty in TD3 reward"
```

### Task 5: Tune And Freeze A Valid Nominal PID

**Files:**
- Create: `experiments/circular_tracking/scripts/td3/tune_hidden_pid.py`
- Create: `experiments/circular_tracking/config/hidden_pid_frozen.json`
- Test: `tests/circular_tracking/test_hidden_pid_acceptance.py`

- [x] **Step 1: Write the PID acceptance test**

```python
from experiments.circular_tracking.scripts.td3.tune_hidden_pid import (
    evaluate_pid_config,
    load_frozen_pid_config,
)


def test_frozen_pid_tracks_three_nominal_circles():
    metrics = evaluate_pid_config(
        config=load_frozen_pid_config(),
        duration_sec=30.0,
        seed=100,
    )
    assert not metrics["failure"]
    assert metrics["steady_position_rmse"] < 0.1
    assert 0.9 <= metrics["path_length_ratio"] <= 1.1
```

- [x] **Step 2: Run and verify failure with the legacy conservative PID**

Expected: FAIL because the current standard RMSE is about 0.35 m and path length is too short.

- [x] **Step 3: Implement a validation-only grid search**

Evaluate combinations of:

```python
reference_velocity_gain = [0.5, 0.75, 1.0]
pid_xy_p_scale = [0.5, 0.75, 1.0]
pid_xy_d_scale = [0.75, 1.0, 1.25]
pid_target_step_limit = [0.0, 0.05, 0.10]
```

Rank only failure-free candidates by steady RMSE, phase error, and path-length-ratio deviation. Write the winning values and the evaluation command into `hidden_pid_frozen.json`. Do not tune PID on disturbed test seeds.

- [x] **Step 4: Run tuning and acceptance**

```powershell
py -3.11 -m experiments.circular_tracking.scripts.td3.tune_hidden_pid --output experiments/circular_tracking/config/hidden_pid_frozen.json
py -3.11 -m pytest tests/circular_tracking/test_hidden_pid_acceptance.py -v
```

Expected: one frozen PID configuration passes all nominal criteria.

- [x] **Step 5: Commit**

```powershell
git add experiments/circular_tracking/scripts/td3/tune_hidden_pid.py experiments/circular_tracking/config/hidden_pid_frozen.json tests/circular_tracking/test_hidden_pid_acceptance.py
git commit -m "feat: freeze valid circular-tracking PID baseline"
```

### Task 6: Add Matched Direct And Residual TD3 Training

**Files:**
- Create: `experiments/circular_tracking/scripts/td3/train_hidden_td3.py`
- Test: `tests/circular_tracking/test_hidden_td3_training_config.py`

- [ ] **Step 1: Add a failing shared-configuration test**

```python
from experiments.circular_tracking.scripts.td3.train_hidden_td3 import build_training_config


def test_direct_and_residual_training_share_nonstructural_hyperparameters():
    direct = build_training_config(mode="direct_td3", seed=0, total_timesteps=20_000)
    residual = build_training_config(mode="residual_td3", seed=0, total_timesteps=20_000)
    ignored = {"mode", "action_semantics", "zero_output_initialization"}
    assert {k: v for k, v in direct.items() if k not in ignored} == {
        k: v for k, v in residual.items() if k not in ignored
    }
```

- [ ] **Step 2: Implement one training entry point**

Use one parser and one `build_training_config()` for both modes. Freeze episode duration at 20 seconds, save checkpoints at 5k/10k/20k/50k/100k, and write Python/package versions plus the PID configuration hash to `config.json`.

- [ ] **Step 3: Zero-initialize only the residual output layer**

After TD3 construction, find the final `torch.nn.Linear` module in `model.actor.mu`, set its weight and bias to zero, then copy actor state into `actor_target`. This makes the initial residual policy reproduce PID without PID-FF demonstrations.

- [ ] **Step 4: Run a 200-step smoke for both modes**

```powershell
py -3.11 -m experiments.circular_tracking.scripts.td3.train_hidden_td3 --mode direct_td3 --seed 0 --total-timesteps 200 --output-folder experiments/circular_tracking/results/hidden_disturbance_td3_paper/smoke/direct_seed0
py -3.11 -m experiments.circular_tracking.scripts.td3.train_hidden_td3 --mode residual_td3 --seed 0 --total-timesteps 200 --output-folder experiments/circular_tracking/results/hidden_disturbance_td3_paper/smoke/residual_seed0
```

Expected: both save model, progress, monitor, and config files; residual starts with zero output.

- [ ] **Step 5: Commit**

```powershell
git add experiments/circular_tracking/scripts/td3/train_hidden_td3.py tests/circular_tracking/test_hidden_td3_training_config.py
git commit -m "feat: add matched hidden-disturbance TD3 training"
```

### Task 7: Add Failure-Aware Paired Evaluation And Statistics

**Files:**
- Create: `experiments/circular_tracking/scripts/td3/evaluate_hidden_td3.py`
- Create: `experiments/circular_tracking/scripts/td3/summarize_hidden_td3.py`
- Create: `experiments/circular_tracking/analysis/hidden_td3_metric_schema.md`
- Test: `tests/circular_tracking/test_hidden_td3_metrics.py`

- [ ] **Step 1: Write failing metric tests**

```python
import math

import numpy as np

from experiments.circular_tracking.scripts.td3.evaluate_hidden_td3 import compute_metrics
from experiments.circular_tracking.scripts.td3.summarize_hidden_td3 import summarize_hierarchical


def test_failed_rollout_is_not_reported_as_full_horizon_steady_rmse():
    rows = [
        {
            "time": float(time),
            "pos_error": 0.25,
            "xy_path_increment": 0.01,
            "reference_path_increment": 0.01,
            "phase_error": 0.1,
        }
        for time in np.arange(0.0, 8.0, 1.0 / 48.0)
    ]
    metrics = compute_metrics(
        trajectory_rows=rows,
        period=10.0,
        duration_sec=30.0,
        failure=True,
    )
    assert math.isnan(metrics["steady_position_rmse_success_only"])
    assert metrics["flight_time_sec"] < 10.0
    assert metrics["failure_penalized_horizon_error"] >= 2.0


def test_hierarchical_summary_preserves_training_and_disturbance_counts():
    rows = []
    for training_seed in range(3):
        for disturbance_seed in range(200, 203):
            rows.append(
                {
                    "controller": "residual_td3",
                    "scenario": "compound",
                    "training_seed": training_seed,
                    "disturbance_seed": disturbance_seed,
                    "failure": False,
                    "steady_position_rmse_success_only": 0.2 + 0.01 * training_seed,
                }
            )
    result = summarize_hierarchical(rows)[0]
    assert result["num_training_seeds"] == 3
    assert result["num_disturbance_seeds"] == 3
    assert result["num_rollouts"] == 9
```

- [ ] **Step 2: Implement the revised schema**

Include `flight_time_sec`, `completion_rate`, `path_length_ratio`, `mean_phase_error`, `steady_position_rmse_success_only`, and `failure_penalized_horizon_error`. Preserve controller, training seed, disturbance seed, scenario, checkpoint, and exact model path.

- [ ] **Step 3: Implement paired export**

For each scenario/seed, create one disturbance process and reset every controller against that identical process. Log disturbance truth only in rollout metadata, never in controller observations.

- [ ] **Step 4: Implement hierarchical aggregation**

Aggregate within each training seed over paired disturbance seeds, then summarize across training seeds. Produce clustered bootstrap confidence intervals by resampling training seeds and paired disturbance seeds. Never label nine reused disturbances as nine independent seeds.

- [ ] **Step 5: Run tests**

Expected: all metric and aggregation tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add experiments/circular_tracking/scripts/td3/evaluate_hidden_td3.py experiments/circular_tracking/scripts/td3/summarize_hidden_td3.py experiments/circular_tracking/analysis/hidden_td3_metric_schema.md tests/circular_tracking/test_hidden_td3_metrics.py
git commit -m "feat: add failure-aware paired TD3 evaluation"
```

### Task 8: Execute The Staged Go/No-Go Experiment

**Files:**
- Create: `experiments/circular_tracking/results/hidden_disturbance_td3_paper/stage_status.md`

- [ ] **Step 1: Run Stage A for seed 0 to 20k**

Train Direct and Residual TD3, then evaluate checkpoints on validation seeds 100-109 in standard, random_wind, actuator_loss, and compound.

- [ ] **Step 2: Apply the Stage A gate**

Continue only if Residual TD3 has zero standard-scene failures and success-only steady RMSE no greater than `1.10 * PID`. In compound, it must improve relative to PID or Direct TD3 by at least one fewer failure among the ten validation seeds, or—when failure counts are equal—by at least 5% lower failure-penalized horizon error. Record raw paired values, the exact rule evaluation, and `GO` or `NO-GO` in `stage_status.md`.

- [ ] **Step 3: Run Stage B to 50k for seeds 0-2 only after GO**

Resume seed 0 and train seeds 1-2 with identical configuration. Select one global checkpoint budget from validation aggregate performance.

- [ ] **Step 4: Apply the Stage B gate**

Require the residual improvement direction in at least two of three training seeds. Per seed, this means passing the standard gate and satisfying the same compound improvement rule against both PID and Direct TD3. Select one budget for both TD3 modes and every training seed using the fixed order: failure rate, failure-penalized horizon error, success-only steady RMSE, then smaller budget. If it fails, stop and write a diagnostic paper; do not increase the budget to search for a favorable result.

- [ ] **Step 5: Run Stage C to 100k for seeds 0-4 only after Stage B GO**

Resume existing seeds and add seeds 3-4. Freeze the protocol before opening test seeds 200-219.

- [ ] **Step 6: Run final held-out and unseen tests**

Evaluate all controllers on test seeds 200-219 and nominal-geometry unseen seeds 300-319. Do not run the deferred `R=0.4,T=8` or `R=0.5,T=12` geometry transfer in the current protocol, and mark those claims unsupported. Do not modify method or hyperparameters after reading these results.

- [ ] **Step 7: Commit only compact evidence**

```powershell
git add experiments/circular_tracking/results/hidden_disturbance_td3_paper/stage_status.md experiments/circular_tracking/results/hidden_disturbance_td3_paper/**/config.json experiments/circular_tracking/results/hidden_disturbance_td3_paper/**/summary_metrics*.csv
git commit -m "results: add staged hidden-disturbance TD3 evidence"
```

### Task 9: Rebuild Claims And Manuscript From Revised Evidence Only

**Files:**
- Create: `experiments/circular_tracking/analysis/hidden_td3_claim_evidence_ledger.csv`
- Create: `docs/paper/revised_outline.md`
- Create: `docs/paper/revised_method.md`
- Create: `docs/paper/revised_results.md`
- Modify: `docs/paper/manuscript.md`

- [ ] **Step 1: Create revised claims**

Use only:

```text
N1: PID provides a conventional feedback baseline under hidden disturbances.
N2: Residual TD3 is safer or more sample-efficient than Direct TD3 at matched budgets.
N3: Residual TD3 improves compound tracking relative to frozen PID without standard degradation.
N4: State-derived gating limits harmful residual actions.
N5: Unseen results characterize, rather than guarantee, generalization.
```

Bind every claim to revised result folders and predeclared acceptance rules.

- [ ] **Step 2: Write the revised paper structure**

Remove Phase/pilot/directory-log narration from the manuscript. State the hidden-information boundary before controller equations. Present failure rate before RMSE and include seed-level paired effects.

- [ ] **Step 3: Archive legacy interpretation in one bounded subsection**

Explain that oracle disturbance observations, PID-FF imitation, a stale terminal reward, half-period training episodes, confounded gates, and repeated test-set use motivated the redesign. Do not quote legacy performance as revised evidence.

- [ ] **Step 4: Generate publication figures**

Create an information-boundary diagram, learning curves at equal budgets, paired main metrics with 95% confidence intervals, representative full-horizon trajectories, error-time plots, and gate/no-gate ablation. Reject blank, smoke-only, or early-termination-only figures.

- [ ] **Step 5: Regenerate Word output and verify it**

Use the existing document-generation path, open with `python-docx`, and verify that every table and figure referenced by the text exists.

- [ ] **Step 6: Commit**

```powershell
git add experiments/circular_tracking/analysis/hidden_td3_claim_evidence_ledger.csv docs/paper/revised_outline.md docs/paper/revised_method.md docs/paper/revised_results.md docs/paper/manuscript.md docs/paper/manuscript.docx
git commit -m "docs: rebuild paper around hidden disturbances"
```

### Task 10: Final Reproducibility Audit

**Files:**
- Create: `experiments/circular_tracking/analysis/hidden_td3_completion_audit.md`

- [ ] **Step 1: Run all targeted tests**

```powershell
py -3.11 -m pytest tests/circular_tracking -v
py -3.11 -m compileall experiments/circular_tracking/rl_envs experiments/circular_tracking/scripts/td3
```

Expected: all tests pass and compileall exits zero.

- [ ] **Step 2: Audit information leakage**

Search controller observation and gate code for disturbance truth fields. Confirm such fields appear only in physics application and offline logging.

- [ ] **Step 3: Audit evidence independence**

Confirm separate training, validation, test, and unseen seed sets; one global selected checkpoint budget; five training seeds for positive final claims; and twenty paired test disturbances per scenario.

- [ ] **Step 4: Audit claim language**

Reject claims of guaranteed stability, online adaptation, real-world deployment, or superiority over PID-FF/MPC/DOB unless separate evidence exists.

- [ ] **Step 5: Write the completion audit and commit**

```powershell
git add experiments/circular_tracking/analysis/hidden_td3_completion_audit.md
git commit -m "docs: audit revised TD3 paper evidence"
```
