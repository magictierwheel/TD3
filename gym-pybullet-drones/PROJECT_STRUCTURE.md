# Project Structure

The repository keeps shared simulator code, task-specific experiments, legacy paper evidence, and the revised hidden-disturbance study separate. Do not merge result namespaces.

## Root Research Documents

- `RL_PAPER_EXECUTION_PLAN.md`
  - Authoritative revised paper plan.
  - Defines PID/Direct TD3/Residual TD3, hidden information boundary, failure history, stage gates, and acceptance criteria.
- `.research/design_brief.md`
  - Falsifiable research question, mechanism, identifiability, validation, and risk register.
- `docs/superpowers/specs/2026-07-10-hidden-disturbance-td3-paper-redesign.md`
  - Approved architecture-level design.
- `docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md`
  - Test-first implementation and experiment plan.
- `AGENTS.md`
  - Concise mandatory instructions for future agents.
- `PROJECT_HANDOFF.md`
  - Human-readable current status and legacy boundary.

## Core Package

- `gym_pybullet_drones/`
  - `envs/`: shared PyBullet/Gymnasium environments such as `CtrlAviary`.
  - `tasks/hover/envs/`: hover-task environments.
  - `control/`: shared controllers including `DSLPIDControl`, MRAC, and CTBRControl.
  - `examples/`: backward-compatible command wrappers.
  - `assets/`: URDF, visual, firmware, and example assets.
  - `utils/`: enums, logging, and helpers.
- `tests/`
  - Existing package/example tests.
  - Revised paper tests belong under `tests/circular_tracking/`.
- `pyproject.toml`
  - Python package metadata and dependencies.

## Circular Tracking Research

- `experiments/circular_tracking/`
  - Main research line for circular and periodic tracking.

### Revised Hidden-Disturbance Study

The following files are planned by the revised paper and may not exist yet:

```text
experiments/circular_tracking/rl_envs/disturbance_processes.py
experiments/circular_tracking/rl_envs/hidden_disturbance_td3_env.py
experiments/circular_tracking/scripts/td3/tune_hidden_pid.py
experiments/circular_tracking/scripts/td3/train_hidden_td3.py
experiments/circular_tracking/scripts/td3/evaluate_hidden_td3.py
experiments/circular_tracking/scripts/td3/summarize_hidden_td3.py
experiments/circular_tracking/analysis/hidden_td3_metric_schema.md
experiments/circular_tracking/analysis/hidden_td3_claim_evidence_ledger.csv
experiments/circular_tracking/results/hidden_disturbance_td3_paper/
```

All revised main-paper evidence must live in this namespace. No controller receives true disturbance parameters.

### Legacy Oracle/PID-FF Pilot

```text
experiments/circular_tracking/rl_envs/circular_residual_td3_env.py
experiments/circular_tracking/scripts/td3/train_direct_td3.py
experiments/circular_tracking/scripts/td3/train_residual_td3.py
experiments/circular_tracking/scripts/td3/evaluate_td3_controllers.py
experiments/circular_tracking/results/td3_residual_paper/
experiments/circular_tracking/analysis/claim_evidence_ledger.csv
experiments/circular_tracking/analysis/plan_completion_audit.md
```

These files remain reproducibility and diagnostic evidence for the superseded oracle/PID-FF approach. They must not be silently edited into the revised experiment or merged into new tables.

### Existing Classical/Periodic Scripts

- `scripts/position_pid/run_position_pid_circle.py`
  - Existing X-Y circular reference and DSL PID example.
  - Useful for nominal PID study, but the revised paper must freeze its own accepted PID configuration.
- `scripts/downwash_periodic/run_downwash_periodic.py`
  - Periodic motion with downwash; not a revised main scenario.
- `scripts/velocity_input/run_velocity_input_periodic.py`
  - Periodic velocity-input experiment; not a revised main controller.

### Simulink Legacy Package

- `experiments/circular_tracking/simulink_residual_rl/`
  - Historical Simulink residual-RL, PID-FF, MPC, and ADRC material.
  - It may inform discussion but cannot share numeric tables with the revised PyBullet experiment.

## Other Experiment Lines

- `experiments/hover_rl_reproduction/`
  - PPO hover reproduction and saved outputs; not circular tracking evidence.
- `experiments/hover_fixed_point/`
  - Fixed-point controller baselines; currently not the circular task.

## Paper Documents

- `docs/paper/README.md`
  - Current/legacy paper-file boundary; read before opening a draft.
- `docs/paper/manuscript.md`, `method.md`, `results.md`, and `manuscript.docx`
  - Legacy oracle/PID-FF draft until revised evidence exists.
- Planned revised writing surface:

```text
docs/paper/revised_outline.md
docs/paper/revised_method.md
docs/paper/revised_results.md
```

Only after the revised claims pass acceptance should these replace the legacy manuscript.

## Reproducibility And Tools

- `reproducibility/docker/`: Docker reproducibility environment.
- `tools/visualization/`: rendering and live-progress utilities.
- `docs/guides/`, `docs/reports/`, `docs/assets/`, `docs/visualizations/`: supporting documentation and generated material.

## Result-Storage Rule

```text
legacy results  -> experiments/circular_tracking/results/td3_residual_paper/
revised results -> experiments/circular_tracking/results/hidden_disturbance_td3_paper/
```

Never overwrite legacy results, never train revised models into the legacy directory, and never aggregate across the two namespaces.
