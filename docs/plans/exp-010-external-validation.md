# EXP-2026-08-010 — External validation

*Plan, written 2026-08-21, before any number exists.*

## 1. The question this answers

Every correctness figure this project has ever published comes from a question
bank that Ariadne co-authored. Two mechanisms produced them: hand-written
templates (co-authorship bias measured at **0.147**), and an LLM given the
schema (blind to the code, but still schema-aware). The record has flagged this
in four separate places — Q1, Q16, `bank-2026-08-19/CARD.md`, and the external
audit's "Moderate" resource-novelty rating.

A web search for human-authored ATT&CK/CAPEC question sets returned nothing
(2026-08-21). But that search conflated two needs. Q16 wants *human phrasing*
and remains blocked. **Q1 wants questions written by someone who did not write
the answering code — and that is available today.**

So: **does Ariadne's measured accuracy survive contact with questions it did not
write?**

## 2. What makes this different from every prior experiment

Three properties, none of which any prior Ariadne experiment has had.

**External authorship.** Questions come from two published benchmarks, used
verbatim where possible.

**No language model in the metric.** Both sources have set-valued gold made of
ATT&CK identifiers. Scoring is set comparison — precision, recall, F1, exact
match. Every prior headline number ran through a local LLM judge that has never
been checked against a human. This one does not.

**An oracle baseline.** Both benchmarks predate ATT&CK 19.0. When Ariadne misses
a gold id, that is either Ariadne's fault or the benchmark's staleness, and
those are indistinguishable without a control. The oracle is a direct graph
lookup — the best any retriever over this data could do. Ariadne is scored
*against the oracle*, not against 1.0.

## 3. Data

### X1 — CTIBench `cti-ate`
60 rows. Each is an ATT&CK software page URL plus the techniques ATT&CK itself
records that software as using. Gold is MITRE's own mapping, rolled up to parent
techniques.

Verified during reconnaissance:
- 46 of 60 software entries exist in the loaded ATT&CK 19.0
- 14 absent: 13 Mobile (Ariadne loads Enterprise only), 1 Enterprise (S0440, dropped between snapshots)
- On the 46, **291 of 292 gold ids are present in the graph** (99.7%) — so the ceiling is real, not a data gap
- Licence CC-BY-NC-SA-4.0

### X2 — AttackQA, enumerative subset
25,335 rows total. About 3,200 belong to `relationships_*_for_*` and
`techniques_sub` / `techniques_parent` families, whose answers explicitly
enumerate ATT&CK identifiers. Those are set-valued and exactly scorable.
Questions used **verbatim**. Licence Apache-2.0.

The `human_question` flag in this dataset means *a human wrote the generator
script*, not *a human wrote the question*. It is not used for anything, and the
trap is recorded so nobody later reads it as human authorship.

## 4. Conditions

Reconnaissance turned up something that reshapes the design. Every published
Ariadne arm — `deterministic`, `generic`, `merged`, `generic_composed` — replays
a **pre-authored plan** carried in the bank entry (`PLANNER_LLM_ENABLED=false`,
"gold plan is replayed; planner never runs"). The bank hands the system the
source, the entity types, and the seed ids. Only `run_llm` reads the raw
question and plans it itself.

So co-authorship is not just phrasing. It is structural. Two conditions:

| condition | what it gets | comparable to |
|---|---|---|
| **plan-given** | plan derived mechanically from the external item by one declared rule | every published figure |
| **plan-free** | the raw external question text, nothing else | what a user actually experiences |

The gap between them has never been measured on questions Ariadne did not write.
It is the most interesting number this experiment can produce.

## 5. Arms

| arm | plan | composer | why |
|---|---|---|---|
| `oracle` | — | direct graph lookup | ceiling; isolates benchmark staleness |
| `deterministic` | given | templates | the arm the paper leads with |
| `generic` | given | LLM narrator, no templates | the strongest arm |
| `llm` | **from text** | LLM | the plan-free condition |

## 6. Pre-registered hypotheses

**H1 — retrieval holds.** Plan-given Ariadne recall will land within 0.05 of the
oracle. The graph holds the answers; retrieving them is what the system claims to
do. *Refuted if the gap exceeds 0.05.*

**H2 — external questions score lower than internal ones.** Co-authorship bias
of 0.147 predicts a drop against the 0.92–1.00 band the internal banks produce.
*Refuted if external scores match internal scores.*

**H3 — precision is low for everyone, including the oracle.** ATT&CK 19.0 records
more technique uses than either benchmark's snapshot. Reconnaissance already
shows the graph returning 31 techniques where gold has 8. If the oracle's
precision is as low as Ariadne's, the shortfall is staleness, not error.

**H4 — plan-free scores below plan-given.** How far below is the size of the
structural co-authorship advantage.

## 7. Steps

Each step ends with a validation gate and a commit.

1. **Scaffold** via `make new-experiment SLUG=external-validation`; write
   `PROTOCOL.md` with §6 verbatim *before any code runs*. Gate: `make validate-research`.
2. **Fetch layer** — pinned-revision downloads to a gitignored cache. Nothing
   from CC-BY-NC-SA-4.0 is committed. Gate: unit tests over a fixture.
3. **Item builder** — external rows to bank entries by one declared rule.
   Gate: tests pinning the rule; coverage report against ATT&CK 19.0.
4. **Oracle** — direct graph lookup per family. Gate: reproduces the
   reconnaissance numbers (46 present, 291/292 recoverable) exactly.
5. **Scorer** — id extraction plus set metrics, identical treatment for oracle
   and Ariadne. Gate: tests over hand-built cases including the failure modes.
6. **Run** — oracle, then plan-given arms, then plan-free. Gate: per-phase
   results written as they land.
7. **Report** — plain language, every number from `metrics.json`. Gate:
   `make validate-research`, full test suite.

## 8. Decisions to record

- **D-018** Oracle baseline, because staleness and error are otherwise indistinguishable.
- **D-019** No language model in the primary metric.
- **D-020** CC-BY-NC-SA-4.0 data is fetched, never committed; results are ours.
- **D-021** Items whose gold is absent from ATT&CK 19.0 are excluded and counted, not silently dropped.
- **D-022** Gold granularity per source: cti-ate rolls to parent techniques, AttackQA keeps sub-techniques.

## 9. What this cannot show

- Nothing about human phrasing. Both sources are machine-generated. **Q16 stays open.**
- Enterprise ATT&CK only. Mobile and ICS are out of scope.
- CAPEC is untouched — neither benchmark covers it.
- Enumerative questions only. Nothing about open-ended asks (Q4).
