# Hidden-Disturbance TD3 Paper Results

This namespace is reserved for the revised comparison of PID, Direct TD3, and PID-based Residual TD3 under hidden stochastic disturbances.

Only runs satisfying the revised information boundary belong here. Controllers must not receive disturbance truth, scenario labels, PID-FF imitation targets, or disturbance-magnitude gates.

Legacy oracle/PID-FF runs remain in:

```text
../td3_residual_paper/
```

Never merge the two namespaces in one aggregate table.

Required run metadata:

- git revision and package versions;
- controller and action semantics;
- observation schema and history length;
- reward/failure-penalty version;
- frozen PID configuration hash;
- training seed and step budget;
- validation, test, and unseen seed sets;
- disturbance-process profile and ranges;
- checkpoint identity and selection rule.

See `stage_status.md` before starting or resuming work.
