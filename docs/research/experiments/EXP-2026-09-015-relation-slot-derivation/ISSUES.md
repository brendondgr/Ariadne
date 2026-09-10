# ISSUES — EXP-2026-09-015

## I-1 — The metric this experiment was designed around is partly measuring the gold

**Found:** 2026-09-09, after A2 run 1, before any conclusion was drawn.

`EXP-2026-09-014` reported `slot_relation` as the rewrite stage's worst slot at
every tier, and this experiment's hypothesis was built on that. Rescoring the
saved rows shows a large part of it is a property of `slot_gold.json`.

Of the 36 gold records carrying a full `(anchor_label, relation, target_label)`,
**11 name a relation that does not exist between their own two labels** in the
canonical snapshot:

| dataset | anchor label | target label | gold relation | the graph has | n |
|---|---|---|---|---|---|
| attack | Group | Technique | `HAS_TECHNIQUE` | `USES` | 4 |
| attack | Campaign | Technique | `HAS_TECHNIQUE` | `USES` | 3 |
| attack | Software | SubTechnique | `HAS_TECHNIQUE` | `USES` | 3 |
| attack | DataComponent | Analytic | `HAS_ANALYTIC` | `MONITORS` | 1 |

`HAS_TECHNIQUE` is a real ATT&CK relation, but the snapshot declares it only
from `Tactic`. A question about the techniques a Group *uses* is gold-labelled
with an edge that pair does not have, so a system answering `USES` — the only
edge the graph offers — is scored wrong for being right.

**This was already known one layer up.** `canonical.form_from_slot_gold` marks
such a relation `unbound` rather than rendering a question from it, and its
comment names the cause: 39 of the 120 gold relations were matched from the
template name, and a template called `group_techniques` yields `HAS_TECHNIQUE`.
But `variant_harness.score_slots` reads `gold["relation"]` straight from the raw
record, so that protection never reaches the scorer.

**Effect on the numbers**, `scripts/rescore_slot_relation.py`, A2 run 1:

| tier | strict (as EXP-2026-09-014 scored it) | graph-consistent |
|---|---|---|
| T3 | 0.3684 | 0.6842 |
| T4 | 0.2143 | 0.5714 |
| T5 | 0.2500 | 0.6000 |
| pooled | 0.4286 | 0.7273 |

**Handled by reporting both, and repairing nothing.** The gold is not edited:
the strict column keeps this experiment comparable to `EXP-2026-09-014`, and the
gap between the columns *is* the finding. `EXP-2026-09-014` carries no
`slot_relation` value in its manifest, so no published figure is withdrawn; its
`RESULTS.md` prose about the relation slot is amended by pointer rather than
rewritten, per the append-only rule.

Filed as `Q44`.

## I-2 — The hypothesis was falsified by its own pre-registered test

The protocol's falsifier reads: *if `slot_relation` rises but `form_exact` does
not, the relation slot was not the binding constraint and the label slots are.*
What happened is weaker still — `slot_relation` did not rise at all. Under both
readings the derivation and the model's own pick are indistinguishable
(strict 0.4359 → 0.4286; graph-consistent 0.7179 → 0.7273, A2 run 1 against
`EXP-2026-09-014` R2 run 1).

The mechanism does work: the derivation fires on 116 of 128 model-rung rows,
abstentions fall from 80 to 67, and the model rung rises from 115 to 128. It is
simply not where the loss was. The label slots are, and they were visible all
along: `slot_anchor_label` 0.2201 and `slot_target_label` 0.4118 at T4.
