# MPC Imitation Readout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and deploy nonzero RL-v2 neural-network readout weights from MPC-plus-feedforward teacher trajectories.

**Architecture:** Extract the existing 32→16 deterministic feature map into a shared function, collect gated teacher residuals during MPC rollouts, and fit the 16→5 readout with regularized least squares in inverse-tanh space. Preserve the existing 120-slot model interface, then use the current CEM loop only to tune safe residual blends, bias corrections, and global scales around the cloned policy.

**Tech Stack:** MATLAB R2026a, Simulink, MATLAB function-based tests, fixed-step quadrotor rollouts.

---

### Task 1: Regression test for the zero-weight defect

**Files:**
- Create: `tests/test_quadrotor_rl_v2_imitation.m`
- Read: `results/policies/rl_v2/quadrotor_rl_v2_policy.mat`

- [ ] **Step 1: Write a test that requires a trained readout**

```matlab
function tests = test_quadrotor_rl_v2_imitation
tests = functiontests(localfunctions);
end

function testSavedPolicyHasTrainedReadout(testCase)
rootDir = fileparts(fileparts(mfilename('fullpath')));
data = load(fullfile(rootDir, 'results', 'policies', 'rl_v2', ...
    'quadrotor_rl_v2_policy.mat'), 'bestPolicySlots');
weights = data.bestPolicySlots(4:83);
verifyGreaterThanOrEqual(testCase, nnz(abs(weights) > 1e-10), 60);
verifyTrue(testCase, all(isfinite(weights)));
end
```

- [ ] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
matlab -batch "r=runtests('tests/test_quadrotor_rl_v2_imitation.m'); assertSuccess(r)"
```

Expected: FAIL because the current nonzero readout count is `0`, below `60`.

### Task 2: Shared inference features and readout fitter

**Files:**
- Create: `scripts/quadrotor_rl_v2_features_core.m`
- Create: `scripts/fit_quadrotor_rl_v2_readout.m`
- Modify: `scripts/quadrotor_rl_v2_policy_core.m:89-146`
- Modify: `tests/test_quadrotor_rl_v2_imitation.m`

- [ ] **Step 1: Add failing synthetic fitting and feature-consistency tests**

The fitter test constructs deterministic hidden states, synthetic nonzero teacher targets, calls:

```matlab
[slots, stats] = fit_quadrotor_rl_v2_readout(hidden, targets, gates, 1e-4);
```

and verifies at least 60 nonzero values in `slots(4:83)`, finite values, and:

```matlab
verifyLessThan(testCase, stats.rmse, 0.35 * stats.zeroBaselineRmse);
```

The feature test calls:

```matlab
[features, hidden, tempGate, residualGate] = ...
    quadrotor_rl_v2_features_core(t, x, ref, env, p);
```

and verifies sizes `[32,1]`, `[16,1]`, finite values, and gates in `[0,1]`.

- [ ] **Step 2: Run tests and verify missing-function failures**

Expected: FAIL with undefined `fit_quadrotor_rl_v2_readout` or `quadrotor_rl_v2_features_core`.

- [ ] **Step 3: Implement the shared feature function**

Move the existing feature normalization, temperature/dust gate calculation, preview references, clipping, and fixed 32→16 sinusoidal projection from `quadrotor_rl_v2_policy_core` into:

```matlab
function [features, hidden, tempGate, residualGate] = ...
    quadrotor_rl_v2_features_core(t, x, ref, env, p)
```

Keep all numerical constants identical to the current deployed policy.

- [ ] **Step 4: Implement regularized inverse-tanh readout fitting**

The fitter must:

```matlab
valid = gates(:) > 0.05;
effectiveTargets = targets(valid, :) ./ gates(valid);
outputScales = max(1.25 * max(abs(effectiveTargets), [], 1), 1e-3);
activationTargets = atanh(min(max(effectiveTargets ./ outputScales, -0.95), 0.95));
design = [hidden(valid, :), ones(nnz(valid), 1)];
coeff = (design.' * design + ridge * diag([ones(1,16), 0])) \ ...
    (design.' * activationTargets);
```

Store `coeff(1:16,:)` by output in `slots(4:83)`, biases in `slots(84:88)`, and `outputScales` in `slots(89:93)`. Compute predictions through the same tanh/scaling/gating path and return RMSE plus zero-baseline RMSE.

- [ ] **Step 5: Replace duplicated inference features with the shared function**

`quadrotor_rl_v2_policy_core` must call the shared function and keep the existing readout index mapping unchanged.

- [ ] **Step 6: Run the focused tests**

Expected: synthetic fitter and feature tests PASS; saved-policy test remains FAIL until retraining.

### Task 3: MPC teacher dataset and cloned CEM initialization

**Files:**
- Modify: `scripts/train_quadrotor_rl_v2_policy.m:43-151`
- Modify: `scripts/train_quadrotor_rl_v2_policy.m:188-218`
- Modify: `scripts/train_quadrotor_rl_v2_policy.m:302-325`
- Modify: `tests/test_quadrotor_rl_v2_imitation.m`

- [ ] **Step 1: Add a failing dataset test**

Call the training function with a data-only mode or a public helper and verify that the returned imitation structure contains:

```matlab
hidden        % N-by-16
targets       % N-by-5
gates         % N-by-1
```

with matching row counts, finite values, and at least 100 gated samples.

- [ ] **Step 2: Run it and verify the missing-data failure**

Expected: FAIL because the existing imitation structure only stores compact rollout rows.

- [ ] **Step 3: Collect full teacher samples**

For each standard, temperature, and dust rollout:

```matlab
[~, hidden, tempGate, residualGate] = ...
    quadrotor_rl_v2_features_core(t, x, ref, env, pBase);
[ffA, ffT, ffTau] = quadrotor_disturbance_compensation_core(x, env, pBase);
teacher = [ffA + tempGate * (mpcA - baseA); ...
           ffT - 1.0; mean(ffTau - 1.0)];
```

Append hidden rows, teacher rows, and residual gates. Reject NaN/Inf before fitting.

- [ ] **Step 4: Initialize CEM from fitted slots**

Fit `imitationSlots` before the CEM loop. Change compact genes to:

```matlab
mu = [0.05, 0.05, 1.00, zeros(1,5), 1.00, 1.00, 1.00];
lowerBounds = [0, 0, 0.75, -0.25*ones(1,5), 0.70, 0.70, 0.70];
upperBounds = [0.25, 0.25, 1.25, 0.25*ones(1,5), 1.30, 1.30, 1.30];
```

Update `materialize_genes(baseSlots, genes)` so it preserves `baseSlots(4:83)`, applies bias genes as deltas to `baseSlots(84:88)`, and changes only slots `94:100`.

- [ ] **Step 5: Save fit diagnostics**

Store `training.imitationFit` and include nonzero count, fit RMSE, and zero-baseline RMSE in the Markdown summary.

- [ ] **Step 6: Run focused tests**

Expected: all unit tests PASS except the saved-policy assertion, which requires a new training run.

### Task 4: Train, persist, and rebuild

**Files:**
- Update: `results/policies/rl_v2/quadrotor_rl_v2_policy.mat`
- Update: `results/data/quadrotor_rl_v2_mpc_imitation_data.mat`
- Update: `results/data/quadrotor_rl_v2_training_log.csv`
- Update: `models/quadrotor_strategy_rl_v2.slx`

- [ ] **Step 1: Back up the current validated policy artifact**

Copy the current `.mat` to `results/policies/rl_v2/quadrotor_rl_v2_policy_before_imitation.mat`; never overwrite this backup.

- [ ] **Step 2: Run smoke-profile training**

Run:

```powershell
matlab -batch "cd('E:/1-AI辅助工作/科研项目/干扰环境仿真/quadrotor_env_comparison'); addpath('scripts'); train_quadrotor_rl_v2_policy('smoke');"
```

Expected: training completes with finite cost and reports at least 60 nonzero readout weights.

- [ ] **Step 3: Run the complete unit test**

Expected: the saved-policy test now PASS.

- [ ] **Step 4: Rebuild strategy models**

Run:

```powershell
matlab -batch "cd('E:/1-AI辅助工作/科研项目/干扰环境仿真/quadrotor_env_comparison'); addpath('scripts'); build_controller_strategy_models;"
```

- [ ] **Step 5: Inspect embedded model weights**

Load `quadrotor_strategy_rl_v2.slx`, read the `控制策略参数/核心公式` chart, parse assignments `p_out(124:203)`, and verify at least 60 are nonzero.

### Task 5: Three-environment benchmark and final verification

**Files:**
- Update: `results/data/quadrotor_rl_v2_mpc_benchmark_metrics.csv`
- Update: `results/data/quadrotor_rl_v2_mpc_benchmark_results.mat`
- Update: `results/data/quadrotor_strategy_model_smoke_tests.csv`

- [ ] **Step 1: Run all strategy smoke tests**

Run:

```powershell
matlab -batch "cd('E:/1-AI辅助工作/科研项目/干扰环境仿真/quadrotor_env_comparison'); addpath('scripts'); run_strategy_model_smoke_tests;"
```

Expected: all models produce finite states and rotor speeds.

- [ ] **Step 2: Run the RL-v2/MPC benchmark**

Run:

```powershell
matlab -batch "cd('E:/1-AI辅助工作/科研项目/干扰环境仿真/quadrotor_env_comparison'); addpath('scripts'); run_rl_v2_mpc_benchmark('smoke');"
```

Expected: standard, temperature, and dust rows complete without NaN/Inf or rotor saturation.

- [ ] **Step 3: Enforce acceptance checks**

Load the metrics CSV and assert:

```matlab
temperatureRlCost <= 1.10 * temperatureMpcCost
all(rlV2RotorSaturationRate == 0)
all(isfinite(rlV2CompositeCost))
```

Compare standard and dust costs against the pre-change CSV and reject the new policy if either degrades by more than 10%.

- [ ] **Step 4: Run fresh final verification**

Re-run the complete MATLAB test file, inspect the saved `.mat`, inspect the embedded `.slx`, and print the three RL-v2 versus MPC composite costs in one command. Completion requires zero failed tests and all acceptance assertions passing.

## Execution note

This directory is not a Git repository, so commit steps are intentionally omitted. Artifact backup and fresh verification replace the usual commit/revert safety points.
