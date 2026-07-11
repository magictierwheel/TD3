# Pre-migration repository inventory

**Date:** 2026-07-12

**Branch:** `integration/hidden-td3-rebuild`

**HEAD:** `915195b3f27c8dafd6ef494276cbf439060d7d70`

**Tag:** `layout-pre-migration-20260712` (peeled SHA `915195b3f27c8dafd6ef494276cbf439060d7d70`)

**Remote `td3/main`:** `678afb90353171a360ee47d296adf29581aaa5e4`

## Purpose and scope

This inventory captures the repository state immediately before migration. It is a documentation-only record: no model training, evaluation, tuning, or other training-state mutation was performed for this inventory.

## Preflight checks

- Active runs: `0`.
- Process check: after excluding the checker itself, no `train_hidden_td3`, `evaluate_hidden_td3`, or `tune_hidden_pid` processes were running.

## Legacy anchors and frozen PID payload

- Old-anchor PID loader historical validation (with path adaptation): successful; payload SHA-256 `624e86cf7452410e15608774d5630512bd8a7f48f5d4e8d30fd5a8dcca37b99a`.
- Current frozen PID raw SHA-256: `c7530d2725d4c55b31252f89c1ed126ae140a35789b3c653b86e955165e48ef3`.

## Replay Buffer

- Files: `8`
- Total size: `16,864,079,016` bytes

## MATLAB source

Source label: **main-worktree complete copy**.

Files: `108`; Simulink models: `9`.

Exact model names:

- `quadrotor_dust.slx`
- `quadrotor_standard.slx`
- `quadrotor_strategy_adrc.slx`
- `quadrotor_strategy_mpc.slx`
- `quadrotor_strategy_pid_ff.slx`
- `quadrotor_strategy_pid.slx`
- `quadrotor_strategy_rl_v2.slx`
- `quadrotor_strategy_rl.slx`
- `quadrotor_temperature.slx`

## Pre-migration baseline

The one and only baseline command run was:

```text
py -3.11 -m pytest tests -q
```

Result: `328 passed, 2 failed, 52 errors, 11 warnings` in `65.54s (0:01:05)`, exit code `1`.

The 52 errors were mainly pre-existing Windows `PermissionError` failures under `C:\Users\audib\AppData\Local\Temp\pytest-of-audib`. The two failures were pre-existing old frozen-PID tests reporting a protocol hash mismatch and a stale-schema expected-message mismatch. These failures are recorded as baseline conditions and were not rerun or fixed during inventory capture.
