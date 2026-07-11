---
project: "Hidden-disturbance residual TD3 for quadrotor circular tracking"
last_updated: "2026-07-10"
stage: design
status: reviewed
source: "user-approved redesign after legacy oracle/PID-FF pilot review"
gap_verdict: "conditional-go: proceed only after reward, baseline, information-boundary, and evaluation fixes"
placeholder_segments: []
---

# Design brief

## 1. Research question

**Sharpened RQ** (one sentence, falsifiable):

When PID, end-to-end TD3, and PID-based residual TD3 receive the same observable flight state but no true disturbance parameters, does the PID residual prior improve training safety, sample efficiency, and circular-tracking robustness under hidden time-varying disturbances?

**Falsification condition** (what would you observe if FALSE):

At the same global training budget, residual TD3 does not reduce failure rate or paired tracking error relative to Direct TD3, and does not improve compound-disturbance tracking relative to the frozen PID baseline across most training seeds.

**Smallest answerable version** (1-week prototype scope):

Fix the terminal reward and nominal PID first, then train Direct TD3 and Residual TD3 for 20k steps with seed 0 on hidden random wind and actuator-loss disturbances. Continue to a 50k, three-training-seed pilot only if the residual controller remains safe and improves on PID or Direct TD3 in validation.

## 2. Expected mechanism

**Causal chain**:

Hidden disturbances create observable position, velocity, attitude, and control errors. PID reacts through feedback and integral action but leaves transient and nonlinear residual error. A bounded residual actor uses only observable state/error history to learn that remaining correction. The PID command keeps early exploration near a viable controller, so residual TD3 should require fewer samples and fail less often than a policy that learns motor commands end to end.

**Most uncertain step**:

Whether a short observable history contains enough information for a feed-forward TD3 actor to infer useful disturbance compensation without an explicit disturbance observer.

**First step you'd bet breaks**:

The critic may fail to learn a stable value gradient from the limited multi-disturbance replay distribution, causing the residual actor to degrade the PID baseline rather than improve it.

## 3. Identifiability check

**Discriminating condition**:

Use one shared plant, disturbance realization, state interface, reward, motor-command range, training budget, validation protocol, and held-out test set. Direct TD3 outputs four motor commands; Residual TD3 outputs four bounded motor-command deltas added to the same PID baseline. Disturbance parameters and scenario labels are absent from both policies. Paired differences across identical test disturbances distinguish a residual-prior benefit from easier test cases.

**Confounders to rule out**:

- Different action semantics or reward functions between Direct TD3 and Residual TD3.
- A nominal PID that does not actually complete the circular trajectory.
- A gate that reads true disturbance magnitude or scenario identity.
- Different observation histories, sensor noise, termination limits, or motor bounds.
- Per-seed checkpoint cherry-picking or repeated use of the final test set during tuning.
- Treating repeated test disturbances across trained policies as independent samples.
- Comparing full-horizon RMSE with metrics computed on early-terminated trajectories.

**Missing-data plan**:

Run 3 training seeds for the 50k direction pilot and 5 training seeds for final evidence. Use 10 validation disturbance seeds and 20 untouched paired test seeds per scenario. Add flight time, success-conditioned RMSE, and a failure-penalized horizon metric before drawing controller conclusions.

## 4. Validation plan

**Success metric**:

Primary metrics are failure rate and paired steady circular-tracking RMSE. Secondary metrics are path-length ratio, phase error, maximum position error, flight time, tilt, rotor saturation, total motor energy, and motor-command smoothness. Report hierarchical or clustered 95% confidence intervals over training seed and disturbance seed.

**Baseline being beaten**:

Residual TD3 must beat Direct TD3 on safety and sample efficiency and beat the frozen conventional PID on compound-disturbance tracking without materially degrading the standard scene. PID has state feedback and its normal integral memory but no explicit disturbance observer.

**Negative control**:

Zero residual action must reproduce PID exactly. A residual actor before learning must also reproduce PID through zero output initialization. Standard no-disturbance evaluation should show no improvement claim and should expose any accidental residual drift.

## 5. Risk register

| # | Risk | Early-warning signal | Mitigation |
|---|---|---|---|
| 1 | Terminal failure penalty is absent or stale | A terminal-transition unit test shows no penalty; failed episodes have ordinary final rewards | Compute termination status before final reward or calculate failure directly from state; add a regression test before retraining |
| 2 | PID baseline does not track the nominal circle | RMSE is comparable to radius, path-length ratio is far below 0.9, or phase error remains large | Tune PID only on nominal validation data; freeze it before any RL experiment |
| 3 | Hidden disturbance makes the policy input non-Markov | Single-frame policies vary sharply by seed and fail when disturbance direction changes | Give both TD3 policies the same short observable state/error/action history; test single-frame history as an ablation |
| 4 | Residual improvement is caused by an easier interface or gate | Direct and residual policies use different motor ranges, rewards, or privileged gate inputs | Use matched four-motor action semantics, shared reward, observable-state gate, and explicit interface tests |
| 5 | Test leakage or pseudo-replication creates a false positive | Hyperparameters change after viewing test seeds; pooled rows look significant but training-seed effects disagree | Freeze protocol before using seeds 200-219; aggregate hierarchically and publish seed-level paired effects |
| 6 | Training remains too short to distinguish learning from noise | The selected model is always an early checkpoint and learning curves have no stable trend | Use staged 20k/50k/100k gates, continue only when validation trends justify more computation |
| 7 | Disturbance model remains physically weak | Results depend on constant episode labels or oracle-like parameters | Use hidden time-varying wind and actuator efficiency processes; document ranges and test stronger/faster unseen processes separately |

## Notes

- Core paper controllers are exactly PID, Direct TD3, and PID + Residual TD3.
- PID-FF, MPC, disturbance observers, oracle disturbance vectors, and PID-FF imitation are removed from the new main method and experiment matrix.
- Legacy oracle/PID-FF results remain available only as diagnostic history. They must not be mixed into revised main tables.
- The first target is a simulation-only short paper. PID plus a disturbance observer may later be added as a fourth strong baseline, but it is not silently folded into the conventional PID baseline.
