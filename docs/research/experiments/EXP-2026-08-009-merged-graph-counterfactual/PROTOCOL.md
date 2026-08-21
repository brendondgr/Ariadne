# PROTOCOL — EXP-2026-08-009 Does federating beat merging?

> The protocol is fixed in advance as executable code: `scripts/merged_sweep.py`
> defines the phases, their order, the grader and its budget, and is committed
> before any phase runs. Results are written afterwards, as always.

## Question

`CLAIMS.md` C-015 — *"federating across two engines outperforms merging both
sources into a single graph"* — has been `unsupported` since the record was
established, with the note *"the merged-single-graph baseline has never been
built."* `OPEN_QUESTIONS.md` Q5 calls it the part the funder cares about, and
D-005 names it as one of the two baselines that must exist before any archival
submission.

It exists now. This experiment asks what it scores.

## Hypothesis

**Stated before the run.** Two predictions, each able to come out either way.

1. **On correctness the two will not separate.** The merged arm runs the same
   schema-driven primitives over the same authored plans; a single store removes
   a cross-engine hop but does not add information. A difference inside the
   grader's own 0.0050 spread is the expected result.
2. **The merged arm will complete more cross-source chains.** In one store the
   consumer sub-question's seeds are reachable without leaving the engine. The
   pre-registered prediction is that consumer sub-questions skipped for want of
   a join value are fewer for `merged` than for `generic`.

If (1) holds, C-015 as written — *federating outperforms merging* — is not
supported by correctness, and the honest reading is that the federation
argument has to rest on something other than answer quality.

## Setup

Three arms, one grader, one session:

| arm | stores | query construction | role |
|---|---|---|---|
| `merged` | **one** (both catalogues) | schema-derived primitives | under test |
| `generic` | two, two languages | schema-derived primitives | **the like-for-like comparison** |
| `deterministic` | two, two languages | hand-written templates | secondary reading |

`merged` against `generic` is the comparison that isolates the architecture:
identical query capability, identical authored plans, identical questions. The
number of stores is the only variable. `deterministic` is graded alongside
because it is the arm the paper leads with, and reading the merged arm only
against it would confound storage with templating.

**The plan is held constant.** The merged arm replays the same authored plans as
every other arm — two sub-questions and a declared join for a federated
question — dispatched to one specialist instead of two. An arm that also
collapsed the decomposition would differ from `generic` in two ways at once and
the result would not say which one moved it.

## Data

- **Generated set 1** (30), `docs/evaluation/banks/bank-2026-08-19/`
- **Generated set 2** (30), `docs/evaluation/banks/bank-2026-08-20/` — shares no
  entity with set 1 or with holdout v1

Both were drawn against an exclusion registry and authored by a model shown one
entity and nothing about the system. Gold is computed from the raw STIX/XML.

The merged store: `data-merged/`, built by `utils/kg_builder/merge.py` from the
same pinned canonical artifacts both federated arms query — 9138 nodes, 34641
relationships — loaded into a second, isolated Neo4j on port 5458.

## Procedure

```bash
uv run python scripts/merged_sweep.py --out docs/evaluation/merged-2026-08-21
```

Phases, in order:

| phase | what it does |
|---|---|
| `P0` | reload the CAPEC Gremlin fixture; run all eight merged-store separation checks; confirm both banks and both federated arms' committed answers are on disk |
| `M1-run`, `M1-judge` | run and grade `merged` on set 1 |
| `M2-run`, `M2-judge` | run and grade `merged` on set 2 |
| `M3-judge-generic-*` | re-grade the committed `generic` answers, both sets |
| `M4-judge-deterministic-*` | re-grade the committed `deterministic` answers, both sets |
| `M9` | write the plain-language report |

**The federated arms are re-judged, not re-run.** Their answers are already on
disk. Re-running `generic` would add run-to-run variance — it has a language
model in the loop, and the narrator arm measured 0.0283 against itself — while
removing only grader variance, which is 0.0050. Judging the saved files with
this session's grader removes the grader from the comparison and adds nothing.

Judgments are written to a `.c015` sidecar so the committed judgments are never
touched, and `roll_up` counts `.judgment` exactly once so a suffixed file cannot
be read as a plain one. `force=True` on every pass, so an interrupted attempt
cannot leave one cell graded by an earlier pass.

## Measures

- **Primary:** judged correctness, mean over 30 questions with a 95% bootstrap
  interval, `merged` against `generic`.
- **Secondary:** consumer sub-questions skipped for want of a join value;
  answers containing a statement absent from the retrieved evidence; refusals
  carrying the executed query.

## Analysis

Point estimates with bootstrap intervals, read against the grader's measured
run-to-run spread of **0.0050** (EXP-2026-08-007, three passes over one fixed
set of deterministic answers). No paired test across arms: the arms are
different systems answering the same questions, and the pairing that matters —
same questions, same grader, same session — is built into the design rather
than computed afterwards.

## Threats to validity, recorded before the numbers

- **The merged arm receives two identifier reconciliations at build time**
  (D-017) that the federated arms perform in code at query time. Without them
  the merged store cannot resolve a `CAPEC-66` seed at all and would score near
  zero for a plumbing reason. This is the merged condition, not a concession —
  but it must be stated with any result.
- **A consequence of that does favour the merged arm**: it can take a join value
  off a *neighbour's* identifier, which a federated specialist cannot act on
  because the other store is out of reach. This is a real property of
  single-store architecture and is reported as one of the things merging buys,
  not hidden in a normaliser.
- **n = 30 per set**, two sets. Small.
- **Neither grader has ever been checked against a human** (Q6).
- **Every question is anchored.** The open-ended regime, where the two designs
  might differ most, is unmeasured (Q4).
