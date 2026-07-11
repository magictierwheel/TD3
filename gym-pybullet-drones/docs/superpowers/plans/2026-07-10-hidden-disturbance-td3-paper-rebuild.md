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

- [ ] **Step 2: Add only disposable training artifacts to `.gitignore`**

Add patterns for replay buffers, tensorboard logs, caches, and videos under the new namespace. Do not ignore CSV/JSON summaries, frozen configuration files, or manuscript figures.

- [ ] **Step 3: Verify the legacy tree is unchanged**

Run:

```powershell
git diff -- experiments/circular_tracking/rl_envs/circular_residual_td3_env.py experiments/circular_tracking/results/td3_residual_paper
```

Expected: no new diff produced by this task.

- [ ] **Step 4: Commit**

```powershell
git add .gitignore experiments/circular_tracking/results/hidden_disturbance_td3_paper/README.md
git commit -m "docs: separate revised hidden-disturbance results"
```

### Task 2: Implement Deterministic Hidden Disturbance Processes

**Files:**
- Create: `experiments/circular_tracking/rl_envs/disturbance_processes.py`
- Test: `tests/circular_tracking/test_hidden_disturbance_td3_env.py`

- [ ] **Step 1: Write failing reproducibility and range tests**

```python
import numpy as np

from experiments.circular_tracking.rl_envs.disturbance_processes import HiddenDisturbanceProcess


def test_hidden_disturbance_process_repeats_for_same_seed():
    left = HiddenDisturbanceProcess(seed=9000, profile="compound")
    right = HiddenDisturbanceProcess(seed=9000, profile="compound")
    left_values = [left.sample(t) for t in np.linspace(0.0, 20.0, 41)]
    right_values = [right.sample(t) for t in np.linspace(0.0, 20.0, 41)]
    assert left_values == right_values


def test_train_profile_stays_inside_declared_ranges():
    process = HiddenDisturbanceProcess(seed=7, profile="compound")
    for t in np.linspace(0.0, 20.0, 201):
        value = process.sample(float(t))
        assert np.linalg.norm(value.wind_xy) <= 1.5 + 1e-9
        assert 0.90 <= value.thrust_efficiency <= 1.0
        assert 0.90 <= value.torque_efficiency <= 1.0
```

- [ ] **Step 2: Run the tests and verify import failure**

Run:

```powershell
py -3.11 -m pytest tests/circular_tracking/test_hidden_disturbance_td3_env.py -v
```

Expected: FAIL because `disturbance_processes.py` does not exist.

- [ ] **Step 3: Implement the process contract**

Implement an immutable sample type and a process that pre-generates piecewise-linear knots every 1-3 seconds for training profiles and every 0.5-1.5 seconds for `unseen`. Use train ranges `wind <= 1.5 m/s` and efficiencies `0.90-1.00`; use unseen ranges `wind <= 2.5 m/s` and efficiencies `0.80-0.90`. `standard` must return zero wind and unit efficiencies. The RNG must be local to the process and seeded explicitly. Construct the process with `horizon_sec=duration_sec`; training uses 20 seconds and evaluation uses 30 seconds, so the final 10 evaluation seconds must not reuse a frozen terminal sample.

```python
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
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

    def __init__(self, seed: int, profile: str, horizon_sec: float = 20.0):
        if profile not in self.PROFILES:
            raise ValueError(f"Unsupported disturbance profile: {profile}")
        self.profile = profile
        self.horizon_sec = float(horizon_sec)
        self.rng = np.random.default_rng(seed)
        times = [0.0]
        while times[-1] < self.horizon_sec:
            interval = (0.5, 1.5) if self.profile == "unseen" else (1.0, 3.0)
            times.append(min(self.horizon_sec, times[-1] + float(self.rng.uniform(*interval))))
        self.times = np.asarray(times, dtype=float)
        self.values = [self._draw_value() for _ in self.times]

    def _draw_value(self) -> HiddenDisturbanceSample:
        if self.profile == "standard":
            return HiddenDisturbanceSample(0.0, 0.0, 1.0, 1.0)
        wind_limit = 2.5 if self.profile == "unseen" else 1.5
        efficiency_range = (0.80, 0.90) if self.profile == "unseen" else (0.90, 1.00)
        use_wind = self.profile in {"random_wind", "compound", "unseen"}
        use_loss = self.profile in {"actuator_loss", "compound", "unseen"}
        wind_x = float(self.rng.uniform(-wind_limit, wind_limit)) if use_wind else 0.0
        wind_y_limit = float(np.sqrt(max(wind_limit**2 - wind_x**2, 0.0)))
        wind_y = float(self.rng.uniform(-wind_y_limit, wind_y_limit)) if use_wind else 0.0
        thrust = float(self.rng.uniform(*efficiency_range)) if use_loss else 1.0
        torque = float(self.rng.uniform(*efficiency_range)) if use_loss else 1.0
        return HiddenDisturbanceSample(wind_x, wind_y, thrust, torque)

    def sample(self, time_sec: float) -> HiddenDisturbanceSample:
        t = float(np.clip(time_sec, 0.0, self.horizon_sec))
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

- [ ] **Step 4: Run the tests**

Expected: both process tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add experiments/circular_tracking/rl_envs/disturbance_processes.py tests/circular_tracking/test_hidden_disturbance_td3_env.py
git commit -m "feat: add hidden time-varying disturbances"
```

### Task 3: Build The Fair Three-Controller Environment

**Files:**
- Create: `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py`
- Modify: `experiments/circular_tracking/rl_envs/__init__.py`
- Test: `tests/circular_tracking/test_hidden_disturbance_td3_env.py`

- [ ] **Step 1: Add failing interface tests**

```python
import numpy as np

from experiments.circular_tracking.rl_envs import HiddenDisturbanceCircularTD3Env
from experiments.circular_tracking.rl_envs.disturbance_processes import HiddenDisturbanceSample


def test_policy_observation_is_independent_of_hidden_truth_metadata():
    env = HiddenDisturbanceCircularTD3Env(controller_mode="residual_td3", disturbance_profile="compound")
    try:
        obs_a, _ = env.reset(seed=9001)
        env._disturbance = HiddenDisturbanceSample(1.5, -1.5, 0.90, 0.90)
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

- [ ] **Step 2: Verify the tests fail because the new environment is absent**

Run the test file and expect an import failure.

- [ ] **Step 3: Implement the environment modes and matched motor interface**

The new class must expose only `pid`, `direct_td3`, `residual_td3`, and `residual_td3_no_gate`. Direct TD3 and both residual modes use four-dimensional actions. Residual commands use:

```python
delta_rpm = gate * action * residual_rpm_limit
rpm = np.clip(pid_rpm + delta_rpm, 0.0, self.MAX_RPM)
```

Direct commands use:

```python
rpm = np.clip(self.HOVER_RPM + action * direct_rpm_span, 0.0, self.MAX_RPM)
```

The observation may contain current and short-history measurable state, reference, tracking error, PID RPM for residual modes, and prior action. It must never contain the disturbance sample, profile name, or seed.

- [ ] **Step 4: Replace the oracle gate with an observable-state gate**

Use tracking error and motor headroom only:

```python
error_gate = np.clip((position_error - 0.03) / (0.20 - 0.03), 0.0, 1.0)
headroom = np.min(np.minimum(pid_rpm, self.MAX_RPM - pid_rpm)) / self.MAX_RPM
headroom_gate = np.clip(headroom / 0.10, 0.0, 1.0)
gate = float(error_gate * headroom_gate)
```

Keep these thresholds in the frozen environment configuration and include a no-gate residual mode for ablation.

- [ ] **Step 5: Apply hidden disturbances only in physics and logging**

At every PyBullet substep, sample the process at current time, apply drag at the current base position, and scale thrust and torque efficiencies. Put the truth in `info["disturbance_truth"]` for offline analysis only; do not route it through `_computeObs()` or gate calculations.

- [ ] **Step 6: Export and run the tests**

Modify `rl_envs/__init__.py` to export `HiddenDisturbanceCircularTD3Env`. Run the test file; expect observation-boundary and zero-residual tests to PASS.

- [ ] **Step 7: Commit**

```powershell
git add experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py experiments/circular_tracking/rl_envs/__init__.py tests/circular_tracking/test_hidden_disturbance_td3_env.py
git commit -m "feat: add fair hidden-disturbance TD3 environment"
```

### Task 4: Fix Terminal Reward Semantics Before Any Training

**Files:**
- Modify: `experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py`
- Test: `tests/circular_tracking/test_hidden_disturbance_td3_env.py`

- [ ] **Step 1: Add a failing terminal-reward test**

```python
import numpy as np


def test_terminal_transition_contains_failure_penalty(monkeypatch):
    env = HiddenDisturbanceCircularTD3Env(controller_mode="direct_td3", disturbance_profile="standard")
    try:
        env.reset(seed=0)
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

- [ ] **Step 2: Run the test and verify it fails**

Expected: the current reward is computed before a fresh failure reason is available.

- [ ] **Step 3: Implement one pure failure-state helper**

Both reward and termination must call the same helper:

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

- [ ] **Step 4: Run all environment tests**

Expected: terminal reward, termination reason, zero residual, and hidden-information tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py tests/circular_tracking/test_hidden_disturbance_td3_env.py
git commit -m "fix: include terminal failure penalty in TD3 reward"
```

### Task 5: Tune And Freeze A Valid Nominal PID

**Files:**
- Create: `experiments/circular_tracking/scripts/td3/tune_hidden_pid.py`
- Create: `experiments/circular_tracking/config/hidden_pid_frozen.json`
- Test: `tests/circular_tracking/test_hidden_pid_acceptance.py`

- [ ] **Step 1: Write the PID acceptance test**

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

- [ ] **Step 2: Run and verify failure with the legacy conservative PID**

Expected: FAIL because the current standard RMSE is about 0.35 m and path length is too short.

- [ ] **Step 3: Implement a validation-only grid search**

Evaluate combinations of:

```python
reference_velocity_gain = [0.5, 0.75, 1.0]
pid_xy_p_scale = [0.5, 0.75, 1.0]
pid_xy_d_scale = [0.75, 1.0, 1.25]
pid_target_step_limit = [0.0, 0.05, 0.10]
```

Rank only failure-free candidates by steady RMSE, phase error, and path-length-ratio deviation. Write the winning values and the evaluation command into `hidden_pid_frozen.json`. Do not tune PID on disturbed test seeds.

- [ ] **Step 4: Run tuning and acceptance**

```powershell
py -3.11 -m experiments.circular_tracking.scripts.td3.tune_hidden_pid --output experiments/circular_tracking/config/hidden_pid_frozen.json
py -3.11 -m pytest tests/circular_tracking/test_hidden_pid_acceptance.py -v
```

Expected: one frozen PID configuration passes all nominal criteria.

- [ ] **Step 5: Commit**

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
