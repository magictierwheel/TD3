# Hidden-Disturbance TD3 Paper Results

This namespace is reserved for the revised hidden-disturbance paper comparison.

Only revised PID, Direct TD3, and Residual TD3 runs with no disturbance truth belong here. Controllers must not receive disturbance truth, scenario labels, PID-FF imitation targets, or disturbance-magnitude gates.

The following legacy categories are excluded:

- oracle observation runs;
- PID-FF imitation runs;
- gate-min runs;
- 5000-step runs.

They remain under:

```text
../td3_residual_paper/
```

These legacy runs must never enter revised main tables. Never merge the two namespaces in one aggregate table.

Required run metadata:

- Git revision;
- Python version and package versions;
- training seed;
- validation seeds;
- test seeds and any separate unseen seed set;
- disturbance ranges and disturbance-process profile;
- observation schema and history length;
- action schema and controller/action semantics;
- reward version, including the failure-penalty definition;
- PID configuration hash;
- model checkpoint identity and selection rule;
- training step budget.

Checkpoint identity convention:

- Learned controllers must record the SHA-256 content digest of the exact checkpoint bytes plus a stable artifact locator, such as a repository-relative path or immutable artifact URI.
- PID must record model checkpoint identity as `N/A`.

See `stage_status.md` before starting or resuming work.
