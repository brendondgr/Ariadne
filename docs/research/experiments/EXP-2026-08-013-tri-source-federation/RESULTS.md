# EXP-2026-08-013 — Three sources at once: the routing floor

**Status:** phase 1 complete, and the defect it found is fixed. Three live
sources now retrieve **identically** to one. Phase 2 (cross-source correlation)
not started.

## The question

Every result this project has ever recorded was measured with **one relevant
source live at a time**. ATT&CK and CAPEC have been federated, but they sit on
different backends and answer disjoint questions. The claim that a customer
could point this at their own graph *alongside* the threat catalogues, and ask
one question that touches both, had never been run.

Phase 1 asks the narrowest honest version of it, and supplies no knowledge of
its own: **what does adding two irrelevant sources cost?** The bank, the gold
and the code are identical between the two conditions. Only the number of live
sources changes.

## Two defects had to be fixed before the question could be asked at all

**A URI was resolved by backend, not by source.** `endpoint_for(backend)` returns
one address per backend, so two Neo4j-backed sources in a process share it. The
planner reported

    [DOWN] identity (neo4j) — backend up with 4369 nodes but none of the
           expected labels present

and 4369 is *ATT&CK's* node count: `identity` had probed ATT&CK's store. This
was invisible for the life of the project because the stack held exactly one
Neo4j source and one Gremlin source, so the two variables could never collide,
and the merged-graph counterfactual sidestepped it by putting both catalogues in
a single store. Fixed with an explicit per-source override,
`ARIADNE_ENDPOINT_<DATASET>`, unset for every dataset today so no existing runner
moves.

**A source is not its card.** The first composed directory held the three cards
and nothing else, and every schema-driven primitive silently reverted to a
hardcoded MITRE fallback: a question routed *correctly* to `identity` was
answered with a query over `n:Technique OR n:SubTechnique OR …`. The schema
registry is built from `graphs/<dataset>/canonical/`, and `discover_datasets`
finds a dataset only when that tree exists, so an absent registry is
indistinguishable from a MITRE-shaped one at the call site. **The first run of
this experiment was therefore invalid and its numbers are discarded** — they
showed `describe` collapsing 0.812 → 0.438 and read exactly like a routing
defect. `scripts/tri_compose.py` now copies the canonical tree and `--check`
refuses a composition without one.

Recording that mistake matters more than the number it produced: a missing
artifact and a routing failure are indistinguishable from the answer alone.

## Result

Three sources live in one process — attack 4369 (Neo4j), capec 4769 (Gremlin),
identity 1339 (Neo4j) — against bank 3's 117 questions, both arms, same gold.

| kind | n | generic 1 src | generic 3 src | template 1 src | template 3 src |
|---|---|---|---|---|---|
| describe | 16 | 0.812 | **0.812** | 0.812 | **0.812** |
| facet-in | 24 | 0.583 | **0.583** | 0.000 | **0.000** |
| facet-out | 24 | 0.750 | **0.750** | 0.000 | **0.000** |
| homo-in | 20 | 0.700 | **0.700** | 0.000 | **0.000** |
| homo-out | 20 | 0.550 | **0.550** | 0.000 | **0.000** |
| multihop | 1 | 1.000 | **1.000** | 0.667 | **0.667** |
| unanswerable | 12 | 1.000 | **0.167** | 1.000 | **0.083** |
| **overall** | 117 | 0.7094 | **0.6239** | 0.2194 | **0.1254** |

**Every kind that has an answer is unchanged. Exactly.** Not close — identical,
on both arms, across six kinds and 105 questions. Adding two catalogues costs
nothing at all on the questions the system can answer.

**Every question that moved was an abstention.** 10 of 12 on the generic arm and
11 of 12 on the template arm, and none moved the other way. Where the correct
behaviour is to say "there is no such relationship", the system now returns
catalogue records instead.

**The mechanism is routing, not retrieval.** 80 of 117 identity questions were
routed beyond identity, and evidence volume rose accordingly:

| | generic | template |
|---|---|---|
| ids per question | 8.24 → **180.36** | 1.95 → **391.47** |
| worst question | 54 → **2234** | 2 → **2608** |

A 22× and 200× increase in evidence for zero additional correct retrieval. One
abstention question returned 558 CAPEC records beside the single identity record
that was the whole honest answer.

## The fix

The selection rule was `id_hits > 0`, evaluated for each card independently — an
absolute threshold with no comparison between sources. With one Neo4j source and
one Gremlin source that was adequate, because their vocabularies barely overlap.
Add a customer graph and a single shared, generic word drags in a whole
catalogue.

The replacement is comparative: **a secondary source must bring evidence the
leader does not already have.** The leader is whichever source matched the most
request tokens; any other source is selected only if it matched a token the
leader did not. A source whose entire case is a word the leader also matches has
said nothing to distinguish itself.

One refinement was needed. A source's own name is the strongest routing signal a
request can carry, and it was being counted for the wrong source: "What
mitigations does ATT&CK list for T1047?" contributes the token `att` (the
ampersand splits it), which no label in either catalogue contains, so the word
ATT&CK was worth nothing to ATT&CK — the question scored 1 to CAPEC's 2 and a
purely ATT&CK question pulled in CAPEC. Source-name tokens now count for their
own source, *except* where another live card uses the word in an identifier:
`attack` is also the first word of CAPEC's `AttackPattern`, so it names neither,
and "attack patterns and their weaknesses" stays CAPEC vocabulary.

### After the fix

| | generic | template |
|---|---|---|
| overall, 1 source | 0.7094 | 0.2194 |
| overall, 3 sources | **0.7094** | **0.2194** |
| unanswerable, 3 sources | 0.167 → **1.000** | 0.083 → **1.000** |
| routed beyond identity | 80/117 → **0/117** | 80/117 → **0/117** |
| ids per question, 3 sources | 180.36 → **8.24** | 391.47 → **1.95** |
| worst question | 2234 → **54** | 2608 → **2** |

**Zero questions differ between one source and three**, on either arm, in either
direction. The single-source baseline is unmoved (0.7094 / 0.2194), which is the
check that the new rule is inert when there is nothing to choose between.

It is also strictly better on the two-catalogue configuration it was not written
for. Across the 120 golden entries, the number whose *owning* source is not
routed falls from **14 to 2**, and the two that remain are the `A-AST` boundary
cases, which ask for an entity type ATT&CK does not have and are supposed to
refuse. The eight "What mitigations does ATT&CK list for …" questions now route
to ATT&CK alone instead of dragging in CAPEC on the shared word "mitigation".

## What this says

The capability is real and the discipline is not. The system **can** hold three
databases across two query languages and still retrieve exactly what it
retrieved with one. What it cannot do is stay quiet about the two that are
irrelevant — and because the keyword router matches a request against 72 identity
labels and 779 property names of ordinary IT English, "irrelevant" is the common
case, not the edge case.

That was the state before the fix, and it was a precise prerequisite for phase 2:
correlating a customer finding with ATT&CK is not worth building on top of a
router that pulls in ATT&CK for 68% of questions that have nothing to do with it,
because a correct correlation would be indistinguishable from the noise already
arriving.

With the router fixed, that prerequisite is met. Three live sources across two
query languages now cost exactly nothing, so phase 2 has a clean floor to be
measured against: any cross-source retrieval it produces is attributable to the
bridge rather than to noise, because there is no longer any noise to confuse it
with.

## Limits

- The identity records are synthetic. The schema is the customer's; the
  instances are generated, so this measures navigation, not operational utility.
- One bank, drawn against the identity schema. There are no questions here that
  *should* route to three sources, by design: phase 1 measures the cost of
  irrelevant sources, not the benefit of relevant ones.
- Retrieval only. The conditions were not judged, so nothing is claimed about
  answer quality beyond what retrieval and evidence volume show.
- The identity bank contains no question that *should* route to more than one
  source, so this measures that irrelevant sources are correctly excluded. It
  does not measure that relevant ones are correctly included — the golden set's
  14 → 2 improvement is the only evidence on that side, and it comes from a
  two-source configuration.
- The baseline condition was run before the abstention-wording fix and the
  tri-source condition after it. That fix changes narrative text only; retrieval
  is computed from evidence records, so the comparison is unaffected.
