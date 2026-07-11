# Stage 10 — Bootstrap preflight

- stage_id: `10_bootstrap_preflight`
- status: `NO-GO`
- protocol_path: `../../../protocol/current.json`
- budget_steps: `5000`
- training_seeds: `[0, 1]`
- evaluation_seed_partition: `validation_100_109`
- controllers: `["pid", "direct_td3", "residual_td3"]`
- scenarios: `["standard", "random_wind", "actuator_loss", "compound"]`
- prerequisites: `["00_foundation_and_pid:GO"]`
- go_rule: "The archived v2.1 Gate 3 decision must be GO."
- stop_rule: "The archived v2.1 Gate 3 NO-GO blocks Stage A and requires a separately approved method revision."
