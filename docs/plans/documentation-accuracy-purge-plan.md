# Documentation Accuracy Purge — Plan

## 1. Introduction

Ariadne's documentation was written incrementally alongside the system, and the
system moved. Several load-bearing claims in `README.md` and under `docs/` no
longer describe what the code does: the README sells an "agentic" federated
system whose specialists are in fact 100% deterministic template compilers, the
`SPECIALIST_LLM_*` configuration block it implies is live has zero read sites,
the synthesis claims path is hardcoded deterministic with the LLM confined to
prose narration, and the headline evaluation numbers predate the 2026-07-26
standing evaluation record. Skill files point at a `web/src/` tree that no
longer exists and at a `utils/logger.py` that never did, and one agent-pointer
folder carries a full instruction file in violation of the repository's own
"pointers only" rule.

This plan audits every documentation surface in the repository, moves the root
directory down to a single document (`README.md`), rewrites that README against
what the code actually does, corrects the stale claims under `docs/`, fixes and
re-syncs the skill set across all three agent folders, indexes the evaluation
tree so a reader can tell current from superseded, and adds a regression test
so the next drift is caught by CI rather than by a reader.

## 2. Gaps & Unanswered Questions

- **What counts as root documentation.** *Resolved by the user:* `README.md`
  stays at the root and is rewritten; `commands_basic.md` and the untracked
  `ariadne-research-audit.md` move under `docs/`.
- **How aggressive the purge should be.** *Resolved by the user:* fix accuracy
  and prune obvious dead weight; `docs/plans/` is kept as a historical record.
- **README framing.** *Resolved by the user:* describe the system accurately —
  deterministic-first with opt-in LLM seams — and present the
  deterministic-beats-LLM-planning result as the finding it is.
- **The ~63 MB of committed experiment artifacts under
  `docs/evaluation/experiments/`.** *Assumption:* these are not dead weight —
  they are the per-question evidence backing the standing evaluation record and
  the only reproducible support for the arm table. They are indexed, not
  deleted. The untracked `untruncated-generic/` directory is an in-flight Arm G
  run belonging to uncommitted source changes and is left untouched.
- **`docs/skills/global-project-rules/SKILL.md` mandates `git push` at every
  step, but the operator's standing directive for this repository is commit
  without pushing.** *Assumption:* the skill is the inaccurate artifact and is
  corrected to "commit at every step; push only when explicitly asked," since a
  rule the project does not follow is exactly the kind of stale claim this work
  exists to remove.
- **Uncommitted source changes are present** (`utils/specialists/cypher/*`,
  `gremlin/builder.py`, `evaluation/experiment_untruncated.py` — the Arm G
  "generic-only" control). *Assumption:* leave them alone; document only what is
  committed, and do not describe Arm G as a result.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Record the audit and the plan

- **Locations**: `docs/plans/documentation-accuracy-purge-plan.md` (this file);
  findings summarized in §5 below.
- **Rationale**: The remediation steps each depend on a settled list of what is
  actually wrong. Recording it first means every later edit is traceable to a
  verified defect rather than to taste.
- **Action**: Undergo the verification/validation process for this phase — every
  finding in §5 must cite a file and a line that was read this session. Once
  validated, commit stating: Documentation Accuracy Purge (1/7) Complete:
  Recorded the repository-wide documentation audit and the staged remediation
  plan.

### Step 2: Reorganize the root directory

- **Locations**: `commands_basic.md` → `docs/commands.md`;
  `ariadne-research-audit.md` → `docs/research/audit-2026-08-03.md`; inbound
  references in `docs/structure.md`, `docs/skills/global-project-rules/SKILL.md`,
  and `.gitignore` if any.
- **Rationale**: The root is the first thing a reader sees; three documents at
  the root with no stated relationship is the compactness problem in miniature.
  `commands_basic.md` duplicates a subset of the README's command table and
  belongs beside `docs/structure.md`'s CLI reference. The research audit is a
  dated analysis artifact, not a root-level entry point, but it is the single
  most useful record of which claims went stale and must not be discarded.
- **Action**: Undergo the verification/validation process for this phase — `git
  ls-files` at the root must show `README.md` as the only markdown file, and the
  link checker must report no new broken references. Once validated, commit
  stating: Documentation Accuracy Purge (2/7) Complete: Moved the command
  cheatsheet and the research audit under docs/, leaving README.md as the only
  root document.

### Step 3: Rewrite `README.md`

- **Locations**: `README.md` (full rewrite); numbers sourced from
  `docs/evaluation/2026-07-26/README.md`; architecture claims sourced from
  `utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py`,
  `utils/synthesis/factory.py`, `utils/orchestration/config.py`,
  `utils/planner/config.py`.
- **Rationale**: This is the document the user asked to be replaced. Every
  architectural sentence must be checkable against a named file: the specialists
  compile hand-written templates and no LLM touches them; the synthesis claims
  are always deterministic and verified, with the LLM writing only the narrative
  prose; the planner's LLM drafter is opt-in and always backstopped; the
  retrieval loop defaults to five hops with a deterministic sufficiency judge.
  The Status section currently claims the Wk 14–15 documentation set is
  delivered while the roadmap table in the same file leaves Wk 14–15 unchecked —
  the two must agree.
- **Action**: Undergo the verification/validation process for this phase — every
  command in the README's tables must exist in `main.py`'s parser, every cited
  path must exist, and every metric must match a committed report. Once
  validated, commit stating: Documentation Accuracy Purge (3/7) Complete:
  Rewrote README.md to describe the deterministic-first pipeline and the
  2026-07-26 evaluation results accurately.

### Step 4: Correct the core documents under `docs/`

- **Locations**: `docs/purpose.md` (§ Example Analyst Flow — the Cypher and
  Gremlin specialists' roles are stated backwards), `docs/goals.md` (dead
  `notebooks/planning-schematic-agents.ipynb` citation; Wk 14–15 status),
  `docs/structure.md` (same dead notebook citation; `--graph` metavar omits
  `fixture-qa` which `GRAPH_ACTIONS` accepts; documentation index),
  `docs/evaluation/2026-07-26/README.md` (finding #2 quotes a −0.196 Arm B − Arm
  C delta that its own table computes as −0.1185, because the figure came from
  an earlier judge run).
- **Rationale**: `purpose.md` is the grant-facing description of the system and
  currently attributes the CAPEC query to the Cypher specialist and the ATT&CK
  mitigation query to the Gremlin specialist — precisely inverted, and the one
  error most likely to be read by a reviewer. The −0.196 figure is the number
  most likely to be quoted externally and is not reproducible from the table
  printed beside it.
- **Action**: Undergo the verification/validation process for this phase — run
  `uv run python -m pytest utils/specialists/tests/test_docs_contracts.py` and
  the link checker. Once validated, commit stating: Documentation Accuracy Purge
  (4/7) Complete: Corrected the inverted specialist roles in purpose.md, the
  dead notebook citations, and the unreproducible arm delta in the standing
  evaluation record.

### Step 5: Correct and consolidate the skills

- **Locations**: `docs/skills/woven-dusk-design/SKILL.md` (cites
  `web/src/styles/tokens.css` and `web/src/index.css`; the app is Next.js App
  Router and the tokens live in `web/app/globals.css`),
  `docs/skills/repository-structure/SKILL.md` (cites a `utils/logger.py` that
  does not exist), `docs/skills/global-project-rules/SKILL.md` (push rule, layer
  table, command block, skills table), `.cursor/rules/portfolio-readme/RULE.md`
  (a full instruction file inside a pointer-only folder, referencing a
  `portfolio-readme/references/` tree that is not in this repository), and the
  pointer sets `.claude/skills/`, `.agents/skills/`, `.cursor/rules/`.
- **Rationale**: The repository states its own rule — "Agent folders are
  pointers only — never duplicate instructions outside `docs/skills/`" — and one
  folder breaks it. Skills that name files which do not exist actively mislead
  the agents that read them first. Every canonical skill must have exactly one
  pointer in each of the three agent folders, and nothing else.
- **Action**: Undergo the verification/validation process for this phase — the
  new pointer-parity test from Step 7 must pass, and every path cited by a skill
  must resolve. Once validated, commit stating: Documentation Accuracy Purge
  (5/7) Complete: Fixed stale file references in the skills, made
  portfolio-readme canonical under docs/skills/, and re-synced all three agent
  pointer folders.

### Step 6: Index and prune `docs/evaluation/`

- **Locations**: new `docs/evaluation/README.md`; new
  `docs/evaluation/experiments/README.md`; `docs/evaluation/independent-eval.md`
  and `independent-eval-analysis.md` relocated under
  `docs/evaluation/archive/`.
- **Rationale**: `docs/evaluation/` currently holds five reports with no stated
  relationship, two of which (`independent-eval*`) describe a fix cycle that has
  since been merged and superseded by the 2026-07-26 record. A reader cannot
  tell which numbers are current. Eight `untruncated-*` experiment directories
  carry no index mapping a directory to an arm. Indexing costs nothing and
  removes the ambiguity; deleting the artifacts would remove the only evidence
  behind the headline result, so it is not done.
- **Action**: Undergo the verification/validation process for this phase — every
  report referenced by the new indexes must exist and every relocated file's
  inbound links must be updated. Once validated, commit stating: Documentation
  Accuracy Purge (6/7) Complete: Indexed the evaluation tree, archived the
  superseded independent-eval reports, and mapped each experiment directory to
  its arm.

### Step 7: Add a docs-accuracy regression test and validate the whole set

- **Locations**: `utils/specialists/tests/test_docs_contracts.py` (extend), new
  helper coverage for `README.md`, `docs/structure.md`, `docs/purpose.md`,
  `docs/goals.md`, and `docs/skills/**`.
- **Rationale**: Every defect fixed by Steps 2–6 is a defect that a test could
  have caught: a cited path that does not exist, a relative markdown link that
  does not resolve, a skill without a pointer in one of the three agent folders.
  The existing `test_docs_contracts.py` already applies the
  "every-cited-repo-path-exists" idea to four documents; widening it to the
  whole documentation set is the durable fix, and it satisfies the plan's tests
  requirement.
- **Action**: Undergo the verification/validation process for this phase — run
  `uv run python -m pytest utils/specialists/tests/test_docs_contracts.py`,
  `utils/kg_builder/tests/`, `utils/graph_loader/tests/`, and `api/tests/`. Once
  validated, commit stating: Documentation Accuracy Purge (7/7) Complete: Added
  a repository-wide documentation-accuracy regression test covering cited paths,
  markdown links, and agent-pointer parity.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Rewritten README | Accurate, deterministic-first project overview with verified metrics | `README.md` |
| Relocated command cheatsheet | The root command list, folded beside the CLI reference | `docs/commands.md` |
| Relocated research audit | The 2026-08-03 audit that identified the stale claims | `docs/research/audit-2026-08-03.md` |
| Corrected core docs | Specialist roles, dead citations, roadmap status, arm delta | `docs/purpose.md`, `docs/goals.md`, `docs/structure.md`, `docs/evaluation/2026-07-26/README.md` |
| Corrected skills | Real file paths, accurate operational rules, complete skills table | `docs/skills/**/SKILL.md` |
| Canonical portfolio-readme skill | Instruction file moved out of the Cursor pointer folder | `docs/skills/portfolio-readme/SKILL.md` |
| Re-synced agent pointers | One pointer per skill in each agent folder | `.claude/skills/`, `.agents/skills/`, `.cursor/rules/` |
| Evaluation index | Current vs superseded reports; arm-to-directory map | `docs/evaluation/README.md`, `docs/evaluation/experiments/README.md` |
| Docs-accuracy regression test | Cited-path, markdown-link, and pointer-parity assertions over the whole doc set | `utils/specialists/tests/test_docs_contracts.py` |
| Changelog entries | One `docs/changelog.jsonl` line per step | `docs/changelog.jsonl` |

## 5. Audit Findings

Every finding below was verified against the working tree at commit `769dee7`.

### 5.1 `README.md`

| # | Claim | Reality |
|---|---|---|
| R1 | "one agentic layer plans, queries, and synthesizes" | Query construction is a deterministic if-cascade over 17 Cypher and 11 Gremlin hand-written templates (`utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py`). No LLM touches the specialists. |
| R2 | Tech-stack table implies LLM stages throughout | `PLANNER_LLM_ENABLED`, `SPECIALIST_LLM_ENABLED`, `SYNTHESIS_LLM_ENABLED` all default to `false` in `.env.example`. |
| R3 | Implies a specialist LLM exists | `SPECIALIST_LLM_*` is parsed in `utils/specialists/config.py:78-98` and read nowhere else — dead configuration. |
| R4 | Synthesis "assembles a provenance-linked answer" without qualification | Claims are always composed deterministically (`utils/synthesis/factory.py:90`); the LLM only rewrites the narrative prose (`apply_llm_narrative`). `select_composer`/`HybridComposer` have no runtime caller. |
| R5 | Status: "the Wk 14–15 technical documentation set is delivered" | The roadmap table lower in the same file leaves Wk 14–15 unchecked. |
| R6 | Status quotes "18/18 correlations, 64/64 pairs, 0% unsupported claims" as the headline | Superseded by the 2026-07-26 record: 0.9972 correctness, 120/120 CORRECT, zero hallucinations (Arm A). |
| R7 | Does not mention the retrieval loop's default | `ORCH_MAX_HOPS` defaults to 5 (`utils/orchestration/config.py:31`) with a deterministic sufficiency judge and `ORCH_CHASE_FACETS` off. |

### 5.2 `docs/`

| # | Location | Defect |
|---|---|---|
| D1 | `docs/purpose.md:43-44` | The Cypher and Gremlin specialists' roles are inverted — the CAPEC query is attributed to Cypher and the ATT&CK mitigation query to Gremlin. |
| D2 | `docs/goals.md:31`, `docs/structure.md:324` | Cite `notebooks/planning-schematic-agents.ipynb`; no `notebooks/` directory exists. |
| D3 | `docs/goals.md:46` | Wk 14–15 unchecked although the documentation set it names is delivered. |
| D4 | `docs/structure.md:254` (via `main.py:254`) | The `--graph` metavar omits `fixture-qa`, which `GRAPH_ACTIONS` accepts. |
| D5 | `docs/evaluation/2026-07-26/README.md:57-58` | Finding #2 quotes Arm B − Arm C = −0.196; the table at lines 33–35 gives 0.8505 − 0.9690 = −0.1185. The −0.196 came from a pre-fix judge run. |
| D6 | `docs/evaluation/` | Five reports, no index; `independent-eval*` superseded by the 2026-07-26 record with nothing saying so. |
| D7 | `docs/evaluation/experiments/` | Eight arm directories, no index mapping directory to arm. |

### 5.3 Skills

| # | Location | Defect |
|---|---|---|
| S1 | `docs/skills/woven-dusk-design/SKILL.md:398-399` | Cites `web/src/styles/tokens.css` and `web/src/index.css`; no `web/src/` exists — tokens live in `web/app/globals.css`. |
| S2 | `docs/skills/repository-structure/SKILL.md:94` | Cites `utils/logger.py`, which does not exist. |
| S3 | `docs/skills/global-project-rules/SKILL.md:38` | Mandates `git push` at every step; the operator's standing directive for this repository is commit without pushing. |
| S4 | `docs/skills/global-project-rules/SKILL.md:32` | "Future: TBD — Synthesis agent, graph fixtures, evaluation" — all three shipped. |
| S5 | `docs/skills/global-project-rules/SKILL.md:93-104` | Skills table omits `portfolio-readme`. |
| S6 | `.cursor/rules/portfolio-readme/RULE.md` | A full instruction file in a pointer-only folder, with no canonical `docs/skills/portfolio-readme/`, no `.claude`/`.agents` counterpart, and a reference to a `portfolio-readme/references/` tree absent from this repository. |
| S7 | `docs/skills/` | `SETUP.md` exists for four skills and not the other four; no test enforces pointer parity across the three agent folders. |
