# ISSUES — EXP-2026-09-014

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-09-08 — `default-model-2` is a second *instance* of the same weights, not a second model
**Impact:** Step 7's arm **R3** is a **cross-instance repeatability** arm, not a
model comparison. Nothing in this experiment can support a claim about one model
versus another; what R2 vs R3 measures is whether two vLLM instances of the same
checkpoint, on different GPUs, give the same answers.
**Cause:** probed twice, six minutes apart, from response envelopes rather than
the advertised alias (`data/model_identity_2026-09-08.json` holds the second):

| alias | probe 1 (16:06) | probe 2 (16:12) | advertised upstream |
|---|---|---|---|
| `default-model` | qwen38-27B-v2 | qwen38-27B-v2 | qwen38-27B-v2 |
| `default-model-2` | HTTP 502 | qwen38-27B-v2 | qwen38-27B-v2 |
| `default-model-3` | HTTP 502 | HTTP 502 | qwen38-27B-v2 |
| `default-model-4` | HTTP 502 | HTTP 502 | qwen38-27B-v2 |

Both healthy aliases returned the same `served_model` **and** the same
`system_fingerprint` (`vllm-0.21.0-bf3a75db`). The operator confirmed on
2026-09-08: `default-model` and `default-model-2` are two instances of
`qwen38-27B-v2`, each on a different GPU. `default-model-2` also flapped between
the two probes, so it was down for at least part of the window.
**Resolution:** R3 runs as written and is *reported* as a cross-instance
repeatability block. Every arm re-probes identity at run time rather than
trusting this record, because the endpoint demonstrably flaps.
**Paper implication:** variance from this experiment is within-model variance for
one checkpoint. R2-vs-R3 is a serving-instance comparison and must be labelled
as one. No cross-model claim may be made from it.

## 2026-09-08 — the shipped `reference_arm6.json` no longer reproduces on current `main` (records do; queries and claims do not)
**Impact:** R0 is scored against a **fresh** capture,
`docs/evaluation/variants-2026-08-29/reference_2026-09-08.json`, not against the
2026-08-29 file. `records_exact` comparisons against the published Arm 0–6
figures remain valid; `queries_exact` comparisons against them do not and are
not made.
**Cause:** three shipped changes and one data refresh land between the Arm 6
capture and today. Of 120 cases: **0 differ on `entity_ids`** (the primary
`records` metric), 60 differ on `queries`, 15 on `claims`, 11 on `abstentions`.
Every query diff is Gremlin-side — the emitted traversal lost its
`hasLabel("AttackPattern")` prefix when universal node extraction replaced the
per-template lookups — and every abstention diff is the sub-question *wording*
inside an abstention statement, never whether the case abstained (all 11 still
abstain). The claim diffs are ATT&CK 19 property drift, e.g. T1047 now carries
`x_mitre_remote_support`.
**Resolution:** Re-captured on 2026-09-08 and committed as the R0 reference; the
2026-08-29 file is left untouched as the dated historical record.
**Paper implication:** the "byte-identical retrieval" claim (EXP-2026-09-010) is
about repeated runs of one build, not across builds. Say so where the reference
is cited.

## 2026-09-08 — `--graph verify --dataset attack` failed on a runtime manifest for a store that no longer holds ATT&CK
**Impact:** None on any number; a precondition check only.
**Cause:** ATT&CK was loaded into Gremlin at 17:45Z for a side experiment, and
the CAPEC load at 18:07Z replaced the Gremlin graph. The ATT&CK Gremlin
`load-manifest.json` survived, so `verify` kept checking a backend whose 6374
nodes / 8582 edges are entirely CAPEC (`AttackPattern`, `Weakness`,
`Prerequisite`, …) against ATT&CK's expectations. Neo4j held ATT&CK exactly:
4369 nodes, 27669 edges, every label at its manifest count.
**Resolution:** the stale manifest was retired (kept out-of-tree; the file is
git-ignored local state). Both datasets then verify clean. Nothing was reloaded
and no graph content changed.
**Paper implication:** none.

## 2026-09-08 — `slot_gold.json` does not specify the federated bank, and the five-slot form cannot express a chain
**Impact:** 25 of the 29 round-trip misses. The gold forms round-trip
**89/118** overall, but **74/78** on the single-source banks and only **15/40**
on the federated bank. Every federated figure in this experiment is bounded by
this, and the ceiling is the gold's, not the renderer's.
**Cause:** two things at once, and they compound.
1. `slot_gold.json` records `relation_source: "no template declared"` for
   exactly the 40 federated cases: the federated bank declares its template per
   *sub-question*, not at the top level, so those records carry an anchor and an
   anchor label and nothing else — no relation, no target labels. There is no
   hop to render.
2. Even fully specified they could not be rendered. A federated question is a
   *chain* — CAPEC-150 →MAPS_TO→ techniques →MITIGATES← mitigations — and the
   form this plan specifies (§2: anchors, labels, relation, direction, mode) has
   one relation slot. It can say what a question is about; it cannot say what to
   do next with the result.
**Resolution:** Not resolved, and deliberately not patched. Extending the form
with a second hop is a design change to §2, and it could not be *scored* today
because the gold has no second-hop slots to score against. Recorded here for the
operator: either the federated bank is excluded from the slot-accuracy metric
and reported separately, or the form grows a `then` and the gold grows a hop.
**Paper implication:** report single-source and federated round-trip separately.
Quoting 89/118 as one number hides a 74/78 and a 15/40.

## 2026-09-08 — two gold questions round-trip "wrong" because the reference under-enumerates
**Impact:** `A-SUB-01` and `A-SUB-02` count as misses and should not be read as
renderer defects.
**Cause:** the rendered form returns *more* than the gold question does, and what
it returns is right. `A-SUB-01` asks for the sub-techniques of T1021; the gold
question retrieves `['T1021']` alone, while the rendered form retrieves T1021
plus T1021.001–.007. `A-SUB-02` asks which technique T1055.012 is a sub-technique
of; the gold retrieves only T1055.012, the rendered form also retrieves T1055 —
the answer. This is the composer under-enumeration already on the record, seen
from the other side.
**Resolution:** Recorded, not reconciled (the 2026-08-30 "disagreement is a
finding" rule). The round-trip scores against the incumbent's behaviour, so a
case where the incumbent is wrong scores as a miss by construction.
**Paper implication:** `records_exact` against a captured reference measures
*agreement with the incumbent*, not correctness. Where the two diverge, say which
one was checked against the source.

## 2026-09-08 — two gold relations are null where the question names an edge; two gold records are empty
**Impact:** `C-PRE-01`/`C-PRE-02` miss; `A-SCN-01`/`C-SCN-01` do not render at all
and are excluded from the round-trip denominator (118, not 120).
**Cause:** `C-PRE` asks "which patterns can CAPEC-98 precede", which is the
`CanPrecede` edge, but the gold's `relation` is null because its template
(`capec_neighbors`) does not name one — so the form can only ask for neighbours
in general and gets the anchor back. `A-SCN-01` and `C-SCN-01` are bounded label
scans and their gold records carry **no slots at all**: empty anchors, empty
labels, null relation. There is nothing to build a form from.
**Resolution:** Not resolved. Both are gold gaps; filling them is an edit to the
understanding-gold and would need the same from-the-raw-source derivation that
built it.
**Paper implication:** the understanding-gold covers 116 of 120 questions in a
form this stage can act on. State the denominator.

## 2026-09-08 — the renderer's *function words* cost more than its nouns
**Impact:** none on the reported numbers — it was found and fixed inside Step 1 —
but it is the load-bearing finding of the step and belongs in the write-up.
**Cause:** the first renderer got every noun from the card and still round-tripped
only 61/118. Three scaffolding words, none of them catalogue vocabulary, caused
almost all of it:
- `related to` is a **correlation** cue in `utils/planner/intent.py`, so a
  single-source question read as cross-source, the drafter pulled in the declared
  join partner, and 748 techniques or 558 attack patterns came back attached.
- `list` is a **bulk-scan** cue, so "list the attack patterns for CAPEC-98"
  asked for the whole label.
- `describe` reaches CAPEC's `AttackPattern` through the stem of "describing" in
  its gloss, so an ATT&CK lookup scored CAPEC a hit.
- appending the card's relation *gloss* imported whatever labels it mentioned:
  ATT&CK glosses `HAS_TECHNIQUE` as "A Tactic contains a Technique", so a
  question about a **group's** techniques arrived talking about tactics.
**Resolution:** the renderer now emits several candidate sentences that differ
only in function words, classifies each with the router's own cue rules, and
keeps the one misread least; the gloss is no longer appended. 61 -> 89.
**Paper implication:** "canonical form in the source's vocabulary" is not
sufficient on its own. The sentence must also *read* to the router as the
intent it encodes, and that is a separable, checkable property.

## 2026-09-08 — `USES` is unreachable from the word "use", because `uses` is a router stopword
**Impact:** the deterministic fill binds the relation slot on only **43/120**
gold questions (T0). A large share of the misses are the single most common
ATT&CK question shape — "which techniques does group G0016 **use**?" — where the
edge that answers it is literally named `USES`.
**Cause:** `utils/planner/drafter.py::_STOPWORDS` contains `use`, `used` and
`uses`, so the token never reaches the concept index and `USES` is never a
matched entity. The words are reasonable stopwords in general and are exactly
the relationship's name in this catalogue.
**Resolution:** Not changed. Removing them from the stopword list is a routing
change to the shipped drafter and would have to go through the recorded-answer
regression on both banks before it could ship — out of scope for a plan whose
premise is that nothing behind the rewrite stage changes. Recorded so the number
is not read as a defect of the fill.
**Paper implication:** the deterministic bind rate is a property of the shipped
router's vocabulary, not a ceiling on what deterministic filling could do.

## 2026-09-08 — the deterministic fill reports ambiguity where two edges both fit, and this is most of the residue
**Impact:** context for the T0 bind rate, not a defect.
**Cause:** "How is T1047 detected, and via which analytics?" matches both
`DETECTS` and `HAS_ANALYTIC`; "which analytics monitor data component DC0084"
matches both `MONITORS` and `HAS_ANALYTIC`. The contract is that an unbound slot
is reported rather than filled with the best available match, so two candidates
means the slot is reported unbound with the reason recorded in `form.sources`.
**Resolution:** By design. This is precisely the slot the gated model fill exists
to close, and the recorded reason is what its prompt is built from.
**Paper implication:** report the deterministic bind rate per slot, not only per
question. "Anchor bound, relation ambiguous" and "nothing bound at all" are
different states and only the second is a failure to understand.

## 2026-09-08 — F-PART-04 stopped round-tripping when a nonsense sentence was removed
**Impact:** gold-form round-trip 89 -> 88 between Step 1 and Step 2. The change
is an improvement recorded as a regression.
**Cause:** Step 1's renderer emitted a sentence per dataset unconditionally, so a
CAPEC-anchored federated form produced "In ATT&CK, summarise CAPEC-555" — not a
question about anything. For F-PART-04 that stray sentence happened to drag the
right records in through the join. Step 2 requires a card to *recognise*
something in the form before it gets a sentence, and the accident goes with it.
**Resolution:** Kept. A right answer reached by asking a meaningless question is
not a result. The footing test asks the resolver's own per-dataset identifier
ladder, which is why the six reverse-direction federated cases — where a `T`-id
legitimately IS CAPEC's business, through its TaxonomyEntry seeds — still render
both sentences.
**Paper implication:** none, but it is a clean example of why `records_exact`
alone cannot be the only reported metric.
