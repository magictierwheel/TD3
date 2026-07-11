# Task 6 v2 — Direct TD3 safety interface

## Implemented

- Fixed analytic physical observation scaling shared by Direct, Residual, training and evaluation.
- Direct final actor layer uses small DDPG-style weights and zero bias; target is synchronized.
- TD3 retains a 2k update delay but uses smooth bounded safe warm-up actions instead of full action-space sampling.
- Direct and Residual normalized noise differ only to match behavior/target RMS and caps in actual RPM.
- Immutable snapshot functions save/restore model+optimizers, replay buffer, normalization contract, step counter and RNG state.

## Gate 0

- Focused tests: 25 passed.
- Reward ordering: safe `-4.3953` > delayed failure `-33.0931` > immediate failure `-52.3428` at gamma `0.99`.
- Safe 20-second horizon truncates; true tilt failures terminate; SB3 marks time-limit transitions correctly.
- Direct representative actor output max `0.001933`; normalized observation max `0.68646`; final-layer gradient is nonzero.

## Gate 1 attempt 01

- Residual was safe for 200 steps in standard and compound.
- Direct used smooth bounded torque components but reached horizontal/altitude termination at 72/64 steps. This is the one permitted causal correction: Direct warm-up now uses collective-only noise, avoiding torque accumulation before an actor can learn attitude control.

## Gate 1 attempt 02 — NO-GO

- The collective-only correction eliminated torque, motor asymmetry and motor saturation, but Direct TD3 still terminated in compound at step 73 with `altitude_limit`.
- Maximum action magnitude was `0.01495`; maximum slew was `0.01306`; no tilt failure occurred. The remaining failure is therefore not the original tanh/RPM saturation or motor-jump mechanism.
- Per the authorized rule, no further warm-up/reward/action-interface change, Gate 2, Gate 3, Stage A v2 or Stage B v2 was run.

## Gate 1 v2.1 conditional pass

- The missing Direct-standard confirmation completed all 200 steps: no termination, no motor boundary behavior and zero motor asymmetry.
- The recorded compound altitude failure is now classified as insufficient unlearned control authority, not unsafe action generation. Gate 2 is authorized with the v2.1 training curriculum.

## Gate 2 — PASS

- Direct and Residual were run to 2k for seeds 0 and 1 under the curriculum.
- Each run had at least one full 960-step episode. Replay nonterminal fractions were 99.85%–99.90%, so the v1 short-failure buffer pathology did not recur.
