# Pipeline Error-Handling & Recovery Plan

## 1. Introduction

The `--yolo-all` data pipeline (`utils/yolo.py`) currently fails hard on the first
error in a step. The reported failure — `Build canonical graph … relationship type
not in schema: authored` — is a symptom of a deeper fragility: the build writes
canonical artifacts into an **existing** directory without cleaning it
(`ensure_dir` only `mkdir`s), `schema.json`'s `relationship_types` is generated
from a **fixed allowlist constant**, and `_step_build` **skips** rebuilding whenever
a (possibly stale or partially written) `manifest.json` is present. A stale/partial
"graph already existing" on disk can therefore disagree with a freshly written
schema and crash validation, with no recovery path. There is no backup, retry, or
failure-classification logic anywhere in the pipeline.

This plan adds a small, well-tested recovery layer that implements the requested
policy: **(a)** when a failure stems from an artifact/graph already existing on disk
(stale state), back it up (make a copy) and rebuild clean — never just fail; **(b)**
for other failures, retry transient errors with bounded backoff, and for
non-recoverable errors stop with a clear, actionable "needs human input" message
instead of an opaque crash.

## 2. Gaps & Unanswered Questions

- **Where do backups live?** *Assumption*: under `data/graphs/<dataset>/_backups/canonical-<UTC-timestamp>/`. `data/*` is git-ignored, so backups are never committed and never picked up by validators (which reference explicit paths only).
- **Which errors are "transient" vs "needs human"?** *Assumption*: `ConnectionError`, `TimeoutError`, and connection-related `OSError` are transient (retry). `ArtifactValidationError` on an already-populated dir is "stale state" (backup + rebuild clean). A validation failure on a *freshly cleaned* build, or any other unexpected exception, is "needs human input" (do not loop).
- **Should the loader (DB writes) also back up?** *Assumption*: No. The loader already uses idempotent `MERGE` upserts, so a pre-existing graph in Neo4j/Gremlin is handled by design. The backup-and-replace policy applies to on-disk **canonical artifacts**; the loader gets retry + classification only.
- **Push to GitHub?** Per the task instructions, work is **committed but not pushed**; this overrides the global rule's push step. The worktree is merged into `main` locally at the end.
- **Pre-existing test failures** (`test_integration_docker`, `test_verify_fails_without_runtime_manifest`) are unrelated to this work and out of scope.

## 3. Hierarchical Step-by-Step Instructions

### Step 0: Plan & worktree (this document)
- **Locations**: `docs/plans/error-handling-recovery-plan.md`; git worktree `error-handling-recovery` under `.claude/worktrees/error-handling`.
- **Rationale**: Capture the approach and isolate the work before touching code.
- **Action**: Undergo the verification/tests/validation process for this phase (baseline test run). Once validated, commit to GitHub (no push) stating: Pipeline Error-Handling (0/4) Complete: Added the recovery plan and baselined the test suite in an isolated worktree.

### Step 1: Recovery utility module
- **Locations**: new `utils/recovery.py` — `backup_directory()`, `prepare_clean_dir()`, `restore_directory()`, `classify_failure()` (returns `stale_state` | `transient` | `needs_human`), `retry_with_backoff()`, and a `BackupRecord` dataclass. New tests `utils/graph_loader/tests/test_recovery.py` (co-located with `test_yolo.py` per repo convention).
- **Rationale**: A single, dependency-free, unit-tested home for the copy-then-replace, classification, and retry primitives that both the builder and the pipeline runner consume. Building this first lets later steps wire to a tested seam.
- **Action**: Undergo the verification/tests/validation process for this phase (`pytest utils/graph_loader/tests/test_recovery.py`). Once validated, commit to GitHub (no push) stating: Pipeline Error-Handling (1/4) Complete: Added a tested recovery utility (backup/clean/restore, failure classification, bounded retry).

### Step 2: Backup-and-replace in the builder
- **Locations**: `utils/kg_builder/main.py` — `KGBuildRunner.build_attack()` and `build_capec()`: replace the bare `ensure_dir(canonical_dir)` with a backup-then-clean of any existing canonical directory via `utils/recovery.prepare_clean_dir()`. New tests in `utils/kg_builder/tests/test_build_recovery.py` (using the existing CAPEC fixture path).
- **Rationale**: Guarantees every build starts from a clean canonical directory, so stale leftovers can never cause a `relationship type not in schema` mismatch; the prior copy is preserved for recovery. This is the "make a new copy, then replace" policy at the build layer.
- **Action**: Undergo the verification/tests/validation process for this phase (`pytest utils/kg_builder/tests/`). Once validated, commit to GitHub (no push) stating: Pipeline Error-Handling (2/4) Complete: The builder now backs up any existing canonical artifacts and rebuilds into a clean directory.

### Step 3: Resilient pipeline runner
- **Locations**: `utils/yolo.py` — add a `needs_input` `StepStatus` (symbol/label + table renderer); change `_step_build` to validate existing artifacts (`validate_canonical_artifacts`) and, when invalid, back up + rebuild clean rather than skip or fail; wrap network/IO steps (`_step_docker_start`, `_step_load_attack`, `_step_load_capec`, `_step_verify`) with `retry_with_backoff` + `classify_failure`, surfacing non-transient failures as `needs_input` with an actionable detail. Extend `utils/graph_loader/tests/test_yolo.py`.
- **Rationale**: This is where the requested policy becomes user-visible: existing-artifact failures self-heal via backup+replace, transient failures retry, and genuinely stuck failures ask for human input instead of crashing opaquely.
- **Action**: Undergo the verification/tests/validation process for this phase (`pytest utils/graph_loader/tests/test_yolo.py` + full util suites). Once validated, commit to GitHub (no push) stating: Pipeline Error-Handling (3/4) Complete: The pipeline runner self-heals stale artifacts, retries transient errors, and flags non-recoverable failures for human input.

### Step 4: Documentation
- **Locations**: `docs/structure.md` (record `utils/recovery.py` and the `_backups/` layout), `README.md` (brief note on the recovery behavior), and a `docs/changelog.jsonl` entry per step.
- **Rationale**: Keep the repo map and operator docs truthful about the new module and behavior.
- **Action**: Undergo the verification/tests/validation process for this phase (full util suites green). Once validated, commit to GitHub (no push) stating: Pipeline Error-Handling (4/4) Complete: Documented the recovery module and pipeline behavior. Then merge the worktree into `main`.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Recovery utilities | Backup/clean/restore, failure classification, bounded retry | `utils/recovery.py` |
| Recovery unit tests | Cover backup+replace, classification, retry/backoff | `utils/graph_loader/tests/test_recovery.py` |
| Builder backup-and-replace | Build into a clean canonical dir, preserving a backup | `utils/kg_builder/main.py` |
| Builder recovery tests | Stale canonical dir is backed up and rebuilt clean | `utils/kg_builder/tests/test_build_recovery.py` |
| Resilient runner | Self-heal stale artifacts; retry transient; flag needs-human | `utils/yolo.py` |
| Runner tests | Repair path, retry path, needs-input status | `utils/graph_loader/tests/test_yolo.py` |
| Docs & changelog | Repo map, operator note, per-step changelog entries | `docs/structure.md`, `README.md`, `docs/changelog.jsonl` |
