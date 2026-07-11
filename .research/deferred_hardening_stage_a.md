# Deferred hardening until Stage A

These items are intentionally deferred under the 2026-07-11 minimal-scientific-viability policy. They must be revisited after Stage A results or during Task 10 reproducibility audit, but do not block fair, controlled local Stage A execution.

- Multi-parent atomic writes, file locks, and concurrent attempt competition.
- Automatic complex recovery when `DONE.json` is missing or evidence is partially written.
- ZIP member adversarial validation, malicious-input defenses, and extensive recovery graph handling beyond a fresh-attempt workflow.
- Perfect child-timeout cleanup, cache/LRU memory tuning, legacy schema fingerprint compatibility, and rare crash/exception paths.
- Production/distributed-run scalability and non-scientific security hardening.

For Stage A runs: create a new external immutable `attempt_NN` directory, never overwrite it, retain failures as evidence, and use a new attempt directory for any infrastructure retry.
