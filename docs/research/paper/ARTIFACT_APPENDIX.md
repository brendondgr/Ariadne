# Artifact Appendix

Started early by design: the appendix is typically ~2 pages and assembles almost
entirely from `manifest.yaml` + `PROTOCOL.md`, which is why those fields exist in
the shape they do.

**Status: draft. Not submittable — see Blockers.**

---

## A.1 Abstract

Ariadne answers security-analyst questions in English by querying two separate
live graph databases in their native query languages — MITRE ATT&CK in Neo4j via
Cypher and MITRE CAPEC in a TinkerPop Gremlin Server via Gremlin — joining
results on shared ATT&CK technique identifiers, and returning an answer in which
every claim carries a citation to a retrieved record and the executed query that
produced it. The artifact includes the full pipeline, the 120-question evaluation
catalogue with computed gold, the seven-arm experiment harness, the failure
localisation classifier, and the complete run artifacts behind every reported
number.

## A.2 Artifact check-list

| Field | Value |
|---|---|
| Algorithm | Deterministic template routing with cross-engine federated join |
| Program | Python 3.13; `uv` for dependency management |
| Data set | MITRE ATT&CK 19.0, MITRE CAPEC 3.9 (checksummed), 120-question golden catalogue |
| Run-time environment | Linux; Docker for Neo4j + TinkerPop Gremlin Server |
| Hardware | Commodity workstation. **No GPU required** for the deterministic arms. |
| Metrics | Judge-scored correctness, completeness, faithfulness, groundedness; deterministic answer coverage; wall clock |
| Output | Per-question answer + full retrieved evidence + executed queries + independent judgment |
| Experiments | 11 recorded — see [`../INDEX.md`](../INDEX.md) |
| Disk | ~62 MB of run artifacts, ~56 MB of source data |
| Wall clock | Arm A: **1.6 s** for 120 questions. LLM arms: 500–1,050 s each, plus judging. |
| Publicly available? | ❌ **Not yet — see Blockers** |
| Archived (DOI)? | ❌ **No** |

## A.3 Description

### How to access

Repository clone. **⚠️ No archival DOI exists.** GitHub alone does **not**
satisfy the *Available* badge — Zenodo, Figshare, or Dryad is required.

### Hardware dependencies

None beyond a commodity machine for the deterministic arms. The LLM arms need an
OpenAI-compatible endpoint; the recorded runs used a locally served Gemma 4 31B
via vLLM.

### Software dependencies

Python 3.13, `uv`, Docker. Node for the web workbench (not needed to reproduce
results).

### Data sets

Downloaded and checksum-verified by `uv run main.py --download`; pins in
`data/versions.json`. See [`../datasets/DATASETS.md`](../datasets/DATASETS.md).

## A.4 Installation

```bash
uv sync
uv run main.py --docker start
uv run main.py --download
uv run main.py --build attack && uv run main.py --build capec
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
```

**Verify the fixtures are non-empty before proceeding.** An empty CAPEC fixture
returns "no records" rather than failing, which silently invalidates every CAPEC
and federated result.

## A.5 Evaluation and expected results

### Fully reproducible

```bash
uv run main.py --component-eval          # EXP-2026-07-008
uv run main.py --e2e-eval                # EXP-2026-07-009 (omit --judge)
uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --root docs/evaluation/experiments/untruncated-fixed --workers 4
```

Arm A is byte-reproducible and completes in **1.6 s**. Component and end-to-end
deterministic metrics reproduce exactly.

### Not reproducible without an equivalent judge

Every judged correctness figure depends on 120 independent Sonnet 5 agents per
arm — 840 across the study. The **judgments are committed** under
`docs/evaluation/experiments/`, hashed in each experiment's `data/POINTERS.md`,
so the *aggregation* is reproducible from the artifacts even where the judging is
not.

## A.6 Experiment customization

Arms are selected by `--arm {deterministic,gold_llm,llm,llm_loop,gold_loop_llm,generic}`.
Per-arm env overlays are in `untruncated_env()` in
`utils/evaluation/experiment_untruncated.py`.

## A.7 Notes and blockers

**Honest statement of what a committee would hit:**

1. ✅ **LICENSE — resolved 2026-08-18.** Apache-2.0, chosen by the operator;
   the patent grant is the usual reason to prefer it over MIT for a research
   artifact with industrial funding. `NOTICE` remains the third-party data
   attribution and is independent of it. **Still outstanding:** institutional
   sign-off — the copyright line reads *Florida State University*, which is the
   ordinary owner for grant-funded university work but has not been confirmed,
   and the Innovation Challenge Fund terms have not been checked for a release
   constraint. Both are one-line changes while the repository is unpublished.
2. ❌ **No archival DOI.**
3. ⚠️ **`n_runs: 1`, seeds unrecorded** for every arm. *Results Reproduced*
   within tolerance is achievable for Arm A and questionable for the judged arms,
   because no tolerance was ever characterised (open question Q2).
4. ⚠️ **The judged arms depend on a commercial model** for grading and a
   self-hosted model for generation whose quantisation and served context window
   are unrecorded (Q11, Q12).
5. ⚠️ **`code.commit: unknown`** on all 11 back-filled experiments. Re-run under
   the current protocol before submission rather than shipping the back-fill.

Item 2 is the remaining blocker. Item 1 is resolved subject to the sign-off
noted above. Items 3–5 are disclosures, and each is already recorded in the
relevant experiment's `ISSUES.md`.
