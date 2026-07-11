# Task 8 — staged GO/NO-GO experiments

## Stage A

- Training: seed 0, Direct and Residual TD3, 20,000 steps, fresh `attempt_02` folders.
- Validation: paired PID/Direct/Residual, seeds 100–109 only, standard/random-wind/actuator-loss/compound.
- Identity: training and evaluation Git SHA `3006bcce8dd944382305c42d0d37da26a366e48e`; canonical protocol hash `e6edc37f6f89ec6684917f71f20444dd45b6e745f299b8ea6bf165d71e294359`.
- Global selection used all Direct/Residual 5k/10k/20k rows and one checkpoint-invariant, paired-identical PID row set. Selected checkpoint: 5,000.
- Result: **GO**. The standard gate passed; compound improved over Direct under the pre-registered equal-failure/5%-error criterion, but not over PID.
- Evidence: `experiments/circular_tracking/results/hidden_disturbance_td3_paper/stage_A/aggregate/attempt_02/`.

## Next

Run the frozen Stage B 50k seed-0/1/2 direction pilot. No test or unseen evaluation is authorized.
