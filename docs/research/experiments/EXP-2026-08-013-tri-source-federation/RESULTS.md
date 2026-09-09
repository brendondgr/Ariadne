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

---

# Phase 2 — the declared bridge

**Status:** the bridge is built, wired and demonstrated. It has **not** been
measured on a bank: there is no blind tri-source question set yet, so what
follows is a capability demonstration and a no-regression result, not a score.

## What had to be built, and why it is a different kind of thing

ATT&CK and CAPEC bridge on a **shared value**: both graphs contain the technique
id, and the planner compares strings it read out of them. The identity graph
admits no such bridge — it contains no ATT&CK identifier anywhere, in no
property, label or edge attribute. There is nothing to join *on*.

What exists instead is a correspondence in **meaning**: a `DC_SYNC` edge *is*
the technique ATT&CK calls T1003.006. That is a claim about the world, supplied
by us, derivable from neither graph. It is declared in
`utils/planner/edge_correspondence.py`, in one reviewed place, exactly as the
canonical join keys require.

**13 of 21 edge types carry a technique. The other 8 explicitly do not**, each
with its reason recorded. `MEMBER_OF` is not Account Manipulation — being a
member of a group is how every directory in the world works, and mapping it
would report a technique for every user in the tenant. `GP_LINK` is a policy
deployment; `WRITE_GP_LINK`, the ability to *change* it, is T1484.001 and is
mapped. A test fails if the schema ever grows an edge nobody classified, because
absence from both tables is indistinguishable at the call site from "carries no
technique" — which is a claim nobody made.

Every mapping cites the customer's own description of the edge from the catalog
they supplied. `ADD_KEY_CREDENTIAL_LINK` maps to T1649 because their text says
"allowing a certificate to be attached and the target impersonated", not because
we assumed it. That grounding is what makes the table reviewable **by them**.

The partial/whole distinction is theirs too, and it is enforced rather than
noted: `GET_CHANGES` is marked partial because the catalog says "Alone it is
insufficient; combined with GET_CHANGES_ALL it is DCSync", so a lone half-right
produces **nothing**, and the pair produces T1003.006 through a declared
composite rule. Seeding ATT&CK with DCSync from a single replication right would
assert a technique the customer's own description denies.

## What it does

*"Which ATT&CK technique corresponds to what the Domain Admins group can do with
DC_SYNC, and what mitigates it?"*

| | before the bridge | with the bridge |
|---|---|---|
| join declared | none | `identity-edge-technique` |
| execution order | independent | identity **before** attack |
| ATT&CK seeds | `[]` | `['T1003.006']` |
| ATT&CK records | 7 (keyword noise) | **1** (exact) |

*"The App Access 070 group can WRITE_DACL on objects. Which ATT&CK technique is
that and how is it mitigated?"* seeds `['T1098', 'T1222.001', 'T1484.001']` from
the edges that anchor actually holds, and ATT&CK returns exactly those three.

Before, ATT&CK reached T1003.006 by string coincidence — the token "sync"
matching `SyncAppvPublishingServer` and `Asynchronous Procedure Call` — and
returned six wrong records beside the right one. Now it is *driven*: the
identity record emits the technique id as a join value because of the edge type
it walked, and ATT&CK consumes it as a seed.

## Three defects surfaced on the way, and one of them is the gate working

**The gate refused the bridge**, and was right to. Its producer/consumer check
keyed on `via_edge` alone, saw `producers=[]`, and rejected the join rather than
shipping one it could not validate. Both it and `dependency_map` now ask the
endpoint whether it `produces`, which covers both ways of deriving a key —
walking a mapping edge, and holding an edge whose *type* is the key.

**A leading article was being absorbed into every name.** The Title-Case run for
*"The App Access 070 group can …"* begins at "The", so the extracted name was
`The App Access 070`, and the lookup is an unanchored `CONTAINS` against a stored
name of `App Access 070` — which matches **nothing**. The anchor resolved, looked
reasonable in a trace, and retrieved zero records. Latent until a question began
with its subject: every question in banks 1–3 phrases it mid-sentence, where the
article is lowercase and no Title-Case run reaches it. Trimming leading articles
also fixed `Describe Phishing for Information` → `Phishing for Information` and
returned `List ATT&CK software entries` to the label-scan path the builder's own
docstring says that gate exists to protect.

**The correlation pull-in overrode the router.** With a bridge declared between
identity and ATT&CK, any identity question the intent classifier reads as
correlational pulled in ATT&CK to "close the join" — *"Which containers is the
group policy object GPO-13-baseline linked to?"* routed to both. The pull-in now
declines to re-add a source the selector deliberately **shed**: shedding is a
judgement that the source's evidence was subsumed, while the pull-in exists for
a partner with no keyword evidence at all that is nonetheless needed to close a
declared join.

## No-regression

The 117 identity-only questions, three sources live, bridge declared:

| | generic | template |
|---|---|---|
| 1 source | 0.7094 | 0.2194 |
| 3 sources + bridge | **0.7094** | **0.2194** |
| questions differing | **0** | **0** |
| routed beyond identity | **0/117** | **0/117** |
| ids per question | 8.24 → **8.24** | 1.95 → **1.95** |

The bridge is **inert for questions that do not invoke it** and fires for those
that do. That is the property that matters: a declared correspondence that
leaked into unrelated questions would be worse than no bridge at all.

---

# Phase 2 measured — the tri-source bank

64 questions, blind, authored by Fable from a five-field view of one anchor and
nothing else. Gold comes from the generator blueprint and the declared
correspondence, with the ATT&CK side read from the canonical export rather than
the live store. Audited before any run: **0 of 64 questions contain a gold
identifier**, 64 of 64 name their anchor, 0 use SCREAMING_CASE relationship
names, and 0 identity-control questions mention ATT&CK.

Half the bank is negative on purpose. A run that scored well on the positives
while failing the negatives would have learned to attach ATT&CK to everything,
which is the failure a recall-only metric cannot see.

| kind | n | schema-derived | templates |
|---|---|---|---|
| bridge-technique | 24 | **0.8333** | 0.0000 |
| bridge-mitigation | 16 | 0.3398 | 0.2081 |
| bridge-refusal | 12 | **1.0000** | 0.4167 |
| identity-control | 12 | **1.0000** | 1.0000 |
| **overall** | 64 | **0.7724** | 0.3176 |

**The bridge works and it does not lie.** The schema-derived arm names the right
technique on 20 of 24, and on the twelve anchors that no mapped edge touches it
names **no technique at all** — 12 of 12, zero false claims. The template arm
scores **zero** on the same technique questions and falsely names a technique on
7 of those 12 negatives, which is the shape this project has seen throughout: a
cascade with no template for the question does not abstain, it answers with
whatever a keyword reached.

**identity-control is 1.0000 with 0 of 12 reaching ATT&CK at all.** The bridge
is inert unless invoked. That property matters more than the positive score: a
declared correspondence that leaked into unrelated questions would be worse than
no bridge.

**The mitigation hop is the weak kind and it is not the bridge's fault.** The
technique itself arrives on 11 of 16; the mitigations arrive on 4. Once ATT&CK is
seeded, whether it then walks `MITIGATES` depends on the planner resolving
"Mitigation" from the question's wording — an existing limitation of the second
hop, unchanged by anything here, and visible now only because the first hop
started working.

## The multi-join defect this found

Three sources mean a consumer can sit at the end of two declared joins at once.
ATT&CK is the consuming end of both `attack-technique-id` (CAPEC produces) and
`identity-edge-technique` (identity produces), and a plan routing to all three
declares both. `dependency_map` returned `dict[str, str]` and assigned by
last-write-wins, so whichever join came second silently replaced the first:
identity produced `T1649` **correctly**, ATT&CK was assigned to CAPEC instead,
CAPEC yielded no join values, and ATT&CK ran unseeded and returned nothing.

The bridge worked and the wiring discarded it. A consumer is now seeded from the
union of its producers. `bridge-technique` went 0.3333 → 0.8333 on that fix
alone.

## Two gold defects, caught before they were reported

Both would have read as the system inventing techniques, which is the most
damaging thing this bank could get wrong.

**The negative anchors were dirty.** The sampler indexed *outgoing* edges only,
while the runtime walk is direction-agnostic. `dc202` was selected as a refusal
control on its lone outgoing `RUNS_AS`, then correctly produced T1098 from a
`WRITE_ACCOUNT_RESTRICTIONS` edge held **over** it by something else. The
declaration was right, the system was right, the gold was wrong. Negative
anchors are now clean in both directions, and `bridge-refusal` went 0.8333 →
1.0000 — the difference was entirely the gold.

**The partial-right control is not drawable from this tenant and has been
removed rather than reported.** Every anchor holding `GET_CHANGES` is also
touched by another mapped right, usually `ALL_EXTENDED_RIGHTS`, which the
declaration maps to T1003.006 in its own right on the customer's wording that it
includes "on a domain, the replication rights". A T1003.006 in the evidence
cannot be attributed to the half-right rather than the whole one, so the control
cannot distinguish the behaviour it exists to test. Its first draw scored 0.8889
and that number is discarded. Testing the partial discipline needs a tenant
generated with an isolated replication right — a separate experiment.

## What is not claimed

- **The mapping is ours.** This measures whether the system *uses* the declared
  bridge correctly — routes to both sources, walks the right edge, produces the
  right technique ids, seeds ATT&CK with them, and stays silent where the
  declaration says there is nothing to assert. It does **not** measure whether
  the mapping is right. Nothing here can, and a figure quoted without that
  sentence is quoted wrongly.
- **Retrieval, not correctness.** These are set comparisons against gold. The
  answers were not judged, so nothing is claimed about how well they read.
- **The identity records are synthetic.** The schema is the customer's; the
  instances are generated.
- **Scoping is not measured.** Gold is scoped to the edge the question names,
  but the runtime walks every edge its planner resolves, so an anchor holding
  several mapped rights yields several techniques. That inflates nothing in
  recall and is invisible here; it would show up in a precision-weighted or
  judged reading.
- **One direction only.** Identity produces technique ids and ATT&CK consumes
  them. The reverse — "which of our groups could perform T1003.006" — needs the
  inverse lookup and is not built.
- CAPEC is reachable from ATT&CK by the existing key, so identity → attack →
  capec is expressible in principle. It has not been run.

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — Phase 2 status corrected, provenance fixed, manifest metrics completed, pointers hashed

Written during the 2026-09-09 record audit. **No figure above changes.** Every
phase-1, phase-1a, bridge no-regression and tri-bank figure was recomputed on
2026-09-09 from the sweep states now hashed in `data/POINTERS.md` and
reproduces exactly (one-source 0.7094 / 0.2194; pre-routing 0.6239 / 0.1254,
80 of 117 routed beyond identity; post-routing and with-bridge 0.7094 / 0.2194
with 0 differing; tri-bank 0.7724 / 0.3176 and every per-kind cell; 0 of 64
gold leaks). Not recomputed: `golden_owning_source_not_routed` 14 → 2 and the
7 → 1 bridge demo.

**1. Stale status prose.** The opening status line ("Phase 2 (cross-source
correlation) not started") and PROTOCOL "Phase 2 — cross-source correlation
(not started)" were overtaken the same day by "Phase 2 — the declared bridge"
and "Phase 2 measured — the tri-source bank" above. The current state is:
phase 1 complete and its router defect fixed; phase 2 bridge declared, seeded
and **measured** on the 64-question blind tri-source bank. The manifest status
comment already said so.

**2. Provenance (ISSUES 2026-09-09).** `code.commit`
`544f978b56593a198bc5f9ccf9878d4e748d857e` → `4a97053d3756179f966a11e8bb90d38833ddecf2`;
`code.dirty` false → true. Per-figure trees, from commit times against artifact
mtimes: pre-routing 0.6239 / 0.1254 at 544f978 (artifacts 13:52–13:58); routing
fix 9841b859… (14:45; sweeps 14:42–14:43); bridge declaration 95b8c91d… (15:53)
and seeding 484bf0cb… (16:22; bridge sweeps 16:13–16:20); tri-bank 4a97053d…
(16:54; sweep 16:42). Every post-fix run used a working tree committed minutes
after it. `compute.hardware` "unknown — recorded at run time" → "unknown";
`config.hash` null → `sha256:b06881859b847f9a984cf00f26110b55502ce2377d2737ac022f570f32f22d01`.

**3. Manifest metrics.** Keys renamed to the `data/metrics.json` names (old →
new, values unchanged): `retrieval_{generic,deterministic}_tri_source[ _<kind>]`
→ `…_tri_source_prerouting[ _<kind>]`; `ids_per_question_*_tri_source` and
`max_ids_*_tri_source` → `…_tri_source_prerouting`. Added from
`data/metrics.json`: `retrieval_*_tri_source_postrouting` (0.7094 / 0.2194),
`questions_differing_tri_vs_one_postrouting_*` (0 / 0),
`routed_beyond_identity_*_postrouting` (0.0 / 0.0),
`golden_owning_source_not_routed_{before,after}` (14 / 2 of 120),
`retrieval_*_tri_source_bridge` (0.7094 / 0.2194),
`questions_differing_tri_vs_one_with_bridge_*` (0 / 0),
`edge_types_mapped_to_a_technique` 13 and `…_explicitly_not_a_technique` 8 (of
21), `tribank_*_overall` (0.7724 / 0.3176, n 64), `tribank_*_bridge_technique`
(0.8333 / 0.0, n 24), `…_bridge_mitigation` (0.3398 / 0.2081, n 16),
`…_bridge_refusal` (1.0 / 0.4167, n 12), `…_identity_control` (1.0 / 1.0, n 12),
`tribank_gold_identifier_leaks` 0. `metrics.primary`:
`gold_in_evidence_retrieval` (a prefix, not a key) →
`retrieval_generic_tri_source_postrouting`.

**4. Discarded numbers now in ISSUES** (they were in RESULTS prose only): the
invalid first run (`describe` 0.812 → 0.438, composition without the canonical
tree), the removed partial-right control (first draw 0.8889), and the
negative-anchor gold defect (`bridge-refusal` 0.8333 → 1.0000 on the gold fix
alone).

**5. `data/POINTERS.md`** was the blank scaffold and now hashes the five
`identity-bank3-*-2026-08-22` sweep directories, the `tri-bank-2026-08-22`
directory with its bank, gold and sweep state, and `data-tri/tri_manifest.json`.
