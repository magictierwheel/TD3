# P0 Bootstrap Report

## Workspace snapshot

- Status: complete
- Backup: `E:\rlbk\gpd-preparallel-20260710`
- Source files: 7,942
- Source bytes: 2,010,989,469
- Backup files: 7,942
- Backup bytes: 2,010,989,469
- Legacy result files inventoried: 7,443
- Research files hashed: 142
- Hash errors: 0

## Durable control bootstrap

- Status: complete
- Owner: root coordinator
- Shared state is root-only; subagents may read but must not edit it.
- Protocol SHA-256: `d50e750c7c803d68cb46a35a7e083fa052786402491be05288dcec4c855b2d3a`
- Execution JSON and journal JSONL parsed successfully.
- Revised Markdown/JSON/CSV evidence is trackable; model ZIP artifacts remain ignored.

## Pending P0 gates

- Create isolated integration and implementation worktrees.

## Baseline test classification

- Command: `py -3.11 -m pytest tests -q`
- Result: 1 passed, 4 failed.
- Common failure: `pybullet.error: Cannot load URDF file`.
- The referenced `cf2x.urdf` exists and is readable.
- A minimal diagnostic reproduced failure from the Unicode workspace path and successful loading from an ASCII path using identical files.
- Root cause: PyBullet's Windows URDF loader does not accept the current non-ASCII absolute path.

## Unicode asset-path implementer

- Commit: `e4d107c474368aebcc8fd172380a5da4c637d3bc`
- RED: 3 focused failures because the resolver did not exist.
- Focused GREEN: 3 passed with real PyBullet `loadURDF` calls.
- Implementer full baseline: 8 passed, 11 existing warnings.
- Two-process check: independent ASCII cache paths.
- Status: awaiting independent specification review.

### First specification review

- Result: changes requested.
- Gap 1: the initial focused RED stopped at missing-module import before executing the real PyBullet failure.
- Gap 2: an ASCII absolute string was normalized by `Path` rather than returned exactly unchanged.
- Action: returned to the same implementer; quality review remains blocked until re-review passes.

### Specification fixes

- Commit: `b95718fe9d34a4bb6e06a6701352557e54ad6f4e`
- ASCII identity RED reproduced and fixed.
- Real PyBullet RED reproduced through `CtrlAviary -> BaseAviary -> p.loadURDF` with the resolver temporarily removed.
- Focused GREEN: 4 passed.
- Implementer full suite: 9 passed, 13 existing warnings.
- Status: awaiting specification re-review.

### Specification re-review

- Result: approved.
- Verified real `p.loadURDF` regression RED and restored GREEN.
- Verified exact ASCII-string identity, process-isolated ASCII cache, whitelist, and unchanged physics/control semantics.
- Status: awaiting code-quality and reproducibility review.

### First code-quality review

- Result: changes requested; no Critical issues.
- Important: support non-filesystem `Traversable` package resources.
- Important: reject relative mesh traversal outside source/cache roots.
- Important: commit multiprocessing isolation and cleanup regression tests.
- Quality review must be repeated after the same implementer fixes these items.

### Code-quality fixes

- Commit: `da16fce4e8d51c9c64324119a4352bfc2423c094`
- Added real ZIP Traversable materialization.
- Added mesh traversal, symlink escape, and non-regular-file rejection.
- Added content-addressed atomic idempotent staging.
- Added absolute ASCII cache enforcement and process finalizer cleanup.
- Focused: 15 passed; full suite: 20 passed; multiprocessing: 1 passed.
- Status: awaiting code-quality re-review.

### Code-quality re-review

- Result: one Important portability issue remains.
- The spawn test currently relies on the repository itself having a Unicode path; it must create and pass its own Unicode source directory.
- A low-risk atomic-write fallback will also be added for filesystems without hard-link support.

### Portability fixes

- Commit: `434f92d6fb70b82a15b9222e80364d5d8edc40d6`
- Spawn test now creates its own Unicode source and is independent of checkout path.
- Hard-link `EPERM` falls back to atomic replace with concurrent-target handling.
- Focused: 16 passed; full suite: 21 passed; targeted spawn/fallback: 2 passed.
- Status: awaiting final code-quality re-review.

### Final code-quality re-review

- Result: approved; no Critical or Important issues.
- Checkout-independent spawn staging and cleanup verified.
- Hard-link fallback accepted.
- Status: awaiting root fresh verification.

### Root verification

- `py -3.11 -m pip check`: clean.
- Focused asset tests: 16 passed, 2 existing warnings.
- Full baseline: 21 passed, 13 existing warnings in 23.64 seconds.
- Commit-range diff check: clean.
- Changed-file compileall: clean.
- Unicode asset-path blocker: complete.

## Research baseline

- Commit: `b49709d4ac1ad50475254f3c0a7f970394c36999`
- Files committed: 128.
- Audited text/source/config size: 718,636 bytes.
- Large legacy results, generated media, Office files, models, and binary Simulink artifacts were not committed.
- Legacy trailing whitespace was preserved as a documented snapshot-format exception.

## Parallel P0 audits

- Baseline allowlist audit: complete; generated media, Office files, Simulink binary results, models, and legacy results remain excluded.
- Dependency/test audit: complete; Python 3.11 is mandatory and dependencies pass `pip check`.
- Protocol/spec review: complete; seed ranges, exact recovery commands, stage logic, reward semantics, shared locks, and default-next-action precedence required correction before baseline.
