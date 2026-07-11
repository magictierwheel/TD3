# Stage 20 — Stage A (20k)

- stage_id: `20_stage_a_20k`
- status: `blocked`
- protocol_path: `../../../protocol/current.json`
- budget_steps: `20000`
- training_seeds: `[0]`
- evaluation_seed_partition: `validation_100_109`
- controllers: `["pid", "residual_td3"]`
- scenarios: `["standard", "random_wind", "actuator_loss", "compound"]`
- prerequisites: `["00_foundation_and_pid:GO", "10_bootstrap_preflight:GO"]`
- go_rule: "Not evaluable while protocol/current.json has training_authorized=false; a replacement protocol must define and freeze the GO rule before training."
- stop_rule: "10_bootstrap_preflight:NO-GO blocks execution."
