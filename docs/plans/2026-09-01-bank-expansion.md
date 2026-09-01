# Bank expansion — from 16 hand-written categories to a released benchmark

**Filed 2026-09-01.** Supersedes nothing; it is the first plan that has a
measured denominator to work against
([EXP-2026-09-001](../research/experiments/EXP-2026-09-001-schema-census/)).

## Why

Every conclusion this project has reached is limited by **30 questions per
bank**. Eight grading passes in August proved that conclusively: the instruments
are trustworthy and the sample is not. The schema census then found that the
question space itself was never mapped — the 16 hand-written categories reach
**12 of 33 edge types (36.4%)** and **0 of 12 facet properties**.

## The principle everything hangs on

**The model never determines an answer.** Gold is computed deterministically
from the pinned raw files; the model's only job is turning a structured spec
into natural English. That is what makes the bank self-expanding (bump the
snapshot, regenerate), graph-grounded (gold comes from the graph), and
architecture-blind (the generator never sees a template, a query string, or
anything named Ariadne).

The payoff is larger than volume: **if gold is a computed set, most of the bank
scores without a judge at all** — precision/recall/F1 against gold. That moves
the headline metric off LLM judging, which is the study's largest
methodological gap and the one a reviewer will reach for first.

## Decisions taken (2026-09-01)

| # | Decision | Consequence |
|---|---|---|
| 1 | **400–600 questions.** | Enough to resolve differences the 30-question banks could not. |
| 2 | **Deliberately over-sample the under-represented shapes.** | See the warning below — this is not a neutral sample and must never be reported as one. |
| 3 | **Never-asked shapes go in the same bank as covered ones.** | Maximum transparency: the system faces its whole graph in one number. |
| 4 | **Release the executable gold (Q26: yes).** | The paper ships a benchmark. Query form is serialized from a census triple, so it is co-authored by neither arm. |
| 5 | **Step 6 is a reported diagnostic, not a stop-gate.** | Follows from #3: we do not hide shapes the system may fail. Inferred from the transparency goal — say so if that is wrong. |
| 6 | **No fan-out cap** (Q29 answered negatively). | Width does not predict score. Width becomes a *stratified variable*, not a filter. |

### The warning that comes with decision 2

A bank stratified toward the odd corners of the graph is **not a sample of a
realistic question distribution**. Its headline accuracy is not comparable to
the 30-question banks, and a drop against them would not mean the system got
worse.

Three things follow and all three are mandatory:

1. Report **per-shape and per-tier**, never a single pooled number alone.
2. Report a **reweighted estimate** alongside it — the same per-shape scores
   reweighted to the census's natural instance distribution — so a
   like-for-like figure exists.
3. State the stratification in the bank's own metadata, so no later run can
   quote the pooled figure without meeting the caveat.

## Steps

### Step 1 — Composition enumerator (deterministic, no model) — **DONE 2026-09-01**

`utils/specialists/evalset/composition.py`, over a shared raw-graph layer
(`raw_graph.py`) that the census now also uses. Run with
`uv run python scripts/enumerate_compositions.py --per-shape 4`.

**2,372 specs, 165 distinct path shapes, and 100% census coverage — all 33 edge
types, including all 21 that had never carried a question.**

| tier | specs | | |
|---|---:|---|---:|
| D0 unanswerable | 370 | attack | 975 |
| D1 property | 130 | capec | 1,129 |
| D2 forward hop | 125 | federated | 268 |
| D3 reverse hop | 69 | | |
| D4 two hop | 965 | gold width median | 2 |
| D5 constrained | 459 | gold width p90 | 15 |
| D6 cross-source | 254 | gold width max | 858 |

**Gates met.** Zero specs outside D0 have empty gold. Enumeration is
deterministic under a seed and draws differently under a different one. The
published neutral query round-trips to the published gold. Gold agrees exactly
with `gold_bank` on every single-hop shape it covers and on the federated
CAPEC → technique → mitigation chain — two derivations, no shared code.

**Four things the build surfaced that were not in the plan:**

1. **The federation join had to be made explicit.** CAPEC-declared technique ids
   are placeholder nodes carrying no ATT&CK edges, so every cross-source path
   dead-ended at the bridge — silently, with an empty gold set that looked like
   a data gap. `RawGraph.aliases` performs the join in the gold computer, which
   is correct: the gold *is* the joined answer, and the system under test has to
   reproduce it.
2. **Gold splits into retrievable and declared-but-dangling.** 10 of CAPEC's
   189 technique ids have no live ATT&CK object (see EXP-2026-09-001 A-1 M-1).
   Keeping them would grade federated chains against answers no system can
   produce; dropping them silently would hide the catalogues' version skew
   inside a gold set.
3. **D5 constraints must discriminate.** A filter that removes nothing lets a
   system that ignores it score full marks. Specs where filtered gold equals
   unfiltered gold are rejected; 8 of the 12 census facets survive that.
4. **D0 needs a plausibility rule.** Without one the tier filled with category
   errors — "which attack patterns can this ATT&CK analytic also be" — where
   abstaining is not a judgement call. The predicate must be one some label in
   the same catalogue carries.

### Step 2 — Difficulty as a structural fact

| tier | shape |
|---|---|
| D0 | unanswerable / abstention probe |
| D1 | property read on one named entity |
| D2 | one hop, forward, narrow fan-out |
| D3 | one hop, reverse |
| D4 | two hops, one source |
| D5 | hop + facet filter, count, or comparison |
| D6 | cross-source, two or more hops |

D5 is entirely new — 12 facets available, 0 used. D0 needs real n; abstention
held 4/4 on a sample too small to mean anything.

**Implemented in Step 1**; every spec carries its tier as a structural
consequence, and tests assert each tier is what it claims (D2 forward, D3
reverse, D4 two hops with no bridge, D5 has a discriminating filter, D6
traverses the bridge).

**Gate, still open:** tiers must *predict* score. That cannot be checked until
Step 8. If D4 does not score below D2, the tiers are decoration and the plan
says so rather than shipping them.

### Step 3 — Width as a measured variable ~~cap~~

**Done 2026-09-01, and it changed this step.** Q29 is answered negatively:
gold width does not predict judged score (within-cell r = −0.0068, sign-stable
in 16/38 cells). There is no cap to set.

What survives is the finding underneath: the corpus contains **6 questions
above width 20 and 3 above 50**, so it could not have detected a width effect
if one existed. Stratify the new bank across width bands — including wide ones —
so this is answered at n rather than assumed.

### Step 4 — Fable 5.1 renders, and only renders

Spec in, question text out. The model sees entity names and relation semantics
in domain terms; never a query, a template, or the label vocabulary. Three
renderings per spec at different registers (analyst-casual, formal, indirect),
which buys paraphrase robustness as a by-product.

**Gate:** measure lexical overlap between question text and schema labels, and
reject renderings that merely echo the label. Our own record says a question set
avoiding the schema's words would have found the vocabulary problem immediately
— so enforce it rather than hope for it.

### Step 5 — Validation before anything is graded

Recompute gold from the rendered question independently. Drop specs with
ambiguous referents or empty results. Hand-review a stratified sample of ~40.

**Gate:** the reject rate is reported, not hidden. A 60% reject rate is fine; an
unreported one is not.

### Step 6 — Capability probe on the never-asked shapes

~60 questions across the 21 never-asked edge types, deterministic arm, no judge.
Purely: can the builder express these at all?

Per decision 5 this **reports rather than gates**. If the builder cannot express
half the new shapes, that is a finding — "the system covers a third of its own
graph" is a real result — and it goes in the record before the large bank is
generated, so a later low score has a cause already on file.

### Step 7 — Generate at scale, split before fitting

400–600 questions, stratified across tier, source, shape and width. Dev/blind
split drawn by hash **before anyone looks at a score**. Banks frozen and hashed
like the existing ones.

**Gate:** the blind half stays sealed until Step 8 is written.

### Step 8 — Re-run the headline comparisons at real n

Set-F1 against computed gold as the **primary** metric; judged score secondary.
At 400+, question-sampling noise falls from roughly ±0.06 to ±0.02 and the arm
differences the 30-question banks could not resolve become resolvable.

### Step 9 — Release

Bank, gold, executable queries, census, and the generation code. This is what
turns decision 4 into the benchmark the paper ships with.

## What this plan does not cover

- **The identity graph.** Generated from a blueprint, not a raw catalogue; its
  census needs a different entry point (EXP-2026-09-001 I-4). Any "we cover N%"
  statement must say which graphs.
- **Baselines.** A stronger bank makes a baseline comparison worth running; it
  does not supply one. Separate work.
- **Human grading.** Still not done, still the study's largest gap. Set-F1
  reduces how much rests on it; it does not close it.
