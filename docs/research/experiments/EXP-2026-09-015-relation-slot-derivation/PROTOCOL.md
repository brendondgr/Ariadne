# PROTOCOL — EXP-2026-09-015, relation-slot derivation

**Pre-registered 2026-09-09, 23:30 EDT, before any run of this arm.**
Written against `14944a9d` plus the working-tree change described in §2. The
LLM instances are withdrawn at 08:00 EDT, so §6 states what is dropped first.

---

## 1. The question

`EXP-2026-09-014` put a model in front of the deterministic engine and let it
choose values for the slots the deterministic pass left unbound. It did not meet
its ship rule. This asks whether one of its four slots was carrying the loss,
and whether that slot needed a model at all.

Per-slot accuracy from that experiment's `data/metrics_R2.json`, instance A,
mean of three runs:

| tier | anchor | anchor label | target label | relation | whole form |
|---|---|---|---|---|---|
| T3 | 0.5098 | 0.5098 | 0.5938 | 0.3651 | 0.2484 |
| T4 | 0.1761 | 0.2201 | 0.4118 | 0.1304 | 0.0818 |
| T5 | 0.2516 | 0.3711 | 0.4706 | 0.2174 | 0.0943 |

Relation is the worst slot at every tier. It is also the only slot with no
retrieval bottleneck: the complete list is printed in the prompt. And 24 of the
80 abstentions in that run were the model returning a relation index past the
end of the list it was given.

Meanwhile the schema already knows the answer. Counting distinct
`(source_label, rel_type, target_label)` triples in the canonical snapshot:

| dataset | declared label pairs | pairs where the relation is unique |
|---|---|---|
| capec | 17 | 16 |
| attack | 19 | 19 |

## 2. The intervention

`utils/planner/canonical.relations_between(anchor_label, target_label, dataset)`
returns the relations the declared schema allows between two labels, in either
direction. It is the mirror of the existing `neighbour_labels`.

In `rewrite_llm.apply_choice` the target label is now resolved **before** the
relation, and the relation is then decided in this order:

1. If the label pair pins exactly one relation, take it. The model is not
   consulted and its relation index is discarded, in range or not.
2. If the pair allows several, the model's index must name one of them.
3. If the pair is undeclared, the model's index is read exactly as before.

This is the rule `direction` has followed since `EXP-2026-08-005`, applied one
slot over. Nothing else about the prompt, the candidate lists, the cache key or
the gate changes. `PROMPT_VERSION` is deliberately **not** bumped: the prompt is
byte-identical, so a cache written by one arm is legitimately replayable by the
other, which is what makes §3 a controlled comparison rather than a re-run.

## 3. Arms

The unit of comparison is the frozen 579-variant bank, **tune half only** (301
questions). The `report` half and `bank-holdout.json` stay unread.

| arm | rewrite | derive relation | runs | purpose |
|---|---|---|---|---|
| A0 | off | n/a | 1 | flag-off control; must be byte-identical to `EXP-2026-09-014` R0 |
| A1 | det | n/a | 1 | deterministic fill only; must be byte-identical to that experiment's R1 |
| A2 | model | **yes** | 3 | the intervention, instance A (`:9090`) |
| A3 | model | **yes** | 3 | the intervention, instance B, cross-instance repeatability |
| **A4** | model | **no** | 1 replay | **the control**: A2's own cache, re-applied with the derivation off |

A4 is the causal claim. It replays the choices A2's model actually made and
changes only how they are interpreted, so any difference between A2 and A4 is
the derivation and cannot be model variance. A2-versus-`EXP-2026-09-014`-R2 is
a weaker before/after and is reported as such.

## 4. Pre-declared outcome

**Primary:** `slot_relation` on tiers T3, T4, T5, instance A.

**Ship rule, fixed before the first run.** The change is kept only if all three
hold on the tune half:

1. `slot_relation` rises on all three of T3, T4, T5.
2. `form_exact` rises on at least two of the three.
3. `wrong_entity` does not rise at any tier, and `T6` (the invented-entity
   negative control) does not get worse on either `records_exact` or
   `wrong_entity`.

Rule 3 is the one that matters. The derivation converts a relation the model
would have got wrong into a relation the schema pins from two labels the model
may also have got wrong, so it can manufacture a confident wrong answer out of
a pair of label errors. `EXP-2026-09-014` already doubled `wrong_entity` at
T4/T5 and that is the open concern in Q35; an intervention that doubles it
again is not an improvement whatever the record identity does.

**Falsifier.** If `slot_relation` rises but `form_exact` does not, the relation
slot was not the binding constraint and the label slots are. Say so and stop.

## 5. Held fixed

- `--llm-timeout-s 900` and `--pipeline-timeout-s 900`. Both confounded
  `EXP-2026-09-014` before they were raised; the relay's own timeout was raised
  on 2026-09-09, which removes a third clock but does not license lowering
  these.
- 64-way concurrency, 32 per instance, two instances.
- Cache cleared between A2's and A3's runs, so what varies is the model and not
  the cache. A4 deliberately reuses A2 run 1's cache.
- Served weights read from the response envelope per D-028, never from the
  alias. Recorded in `data/model_identity.json`.

## 6. What is dropped if the clock runs out

In order, first dropped first: A3 run 3, A3 runs 2 and 1 (cross-instance
repeatability becomes a stated gap), A2 run 3. **A0, A1, A2 run 1 and A4 are
not droppable** — without A4 there is no controlled comparison and the
experiment reports nothing.

## 7. Recorded regardless of outcome

A negative result is written up with the same care as a positive one and the
manifest keeps `status: complete`. If the ship rule fails the flags stay off,
exactly as `D-032` left them, and the finding is that the relation slot was not
the binding constraint.
