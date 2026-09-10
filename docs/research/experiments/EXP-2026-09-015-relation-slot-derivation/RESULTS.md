# RESULTS — EXP-2026-09-015, relation-slot derivation

**Status:** the intervention is refused by its own pre-registered ship rule. The
flags stay off, exactly as `D-032` left them. The experiment's value is not the
intervention; it is `I-1`.

---

## A-1 — The headline

The relation slot can be read from the schema instead of being asked of the
model, and now is. It changes nothing, because the model was already picking a
graph-consistent relation about as often as the schema does — and because a
third of what that slot was graded on was graded against an edge the graph does
not have.

| | value |
|---|---|
| relation derived from the label pair | 116 of 128 model-rung rows |
| abstentions | 80 → 67 |
| model rung | 115 → 128 |
| `slot_relation`, strict | 0.4359 → 0.4286 |
| `slot_relation`, graph-consistent | 0.7179 → 0.7273 |

Both readings say the same thing: no effect. The mechanism fires; the accuracy
does not move.

## A-2 — The controls hold

`A0` (rewrite off) and `A1` (deterministic fill) reproduce `EXP-2026-09-014`'s
`R0` and `R1` exactly on `records_exact` at every tier. The change is invisible
when the model rung is off, which is what a flag that ships off has to be.

| tier | A0 | EXP-014 R0 | A1 | EXP-014 R1 |
|---|---|---|---|---|
| T1 | 0.4921 | 0.4921 | 0.4921 | 0.4921 |
| T2 | 0.4921 | 0.4921 | 0.4603 | 0.4603 |
| T3 | 0.2745 | 0.2745 | 0.3529 | 0.3529 |
| T4 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| T5 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| T6 | 0.1111 | 0.1111 | 0.1111 | 0.1111 |

## A-3 — Against the ship rule

The rule was fixed before the first run. All three clauses had to hold.

| clause | outcome |
|---|---|
| 1. `slot_relation` rises on T3, T4, T5 | **failed** — unchanged on T4 and T5, down 0.0318 on T3 |
| 2. `form_exact` rises on two of three | **failed** — unchanged on T4 and T5, down 0.0131 on T3 |
| 3. `wrong_entity` does not rise anywhere | **failed** — T4 0.2642 → 0.3019, T5 0.2453 → 0.2830 |

Clause 3 failing is the one that was pre-registered as mattering. The derivation
turns a relation the model would have got wrong into a relation the schema pins
from two labels the model may *also* have got wrong, and so it manufactures a
confident wrong answer out of a pair of label errors. That is exactly the
mechanism the protocol warned about, and it is now measured rather than feared.

## A-4 — The falsifier fired, one step earlier than written

The protocol's falsifier read: *if `slot_relation` rises but `form_exact` does
not, the relation slot was not the binding constraint and the label slots are.*
`slot_relation` did not rise at all, which says the same thing more strongly.

The label slots were visible all along and are where the loss is:
`slot_anchor_label` 0.2201 and `slot_target_label` 0.4118 at T4. A label-side
intervention is the next thing to try, and this experiment says nothing about
whether it would work.

## A-5 — What the experiment is actually for

See `ISSUES.md` `I-1`. Eleven of the 36 gold records that name a relation name
one undeclared between their own two labels, and `score_slots` grades against
the raw record. Pooled, the slot reads 0.4286 against the gold and 0.7273
against the graph. `EXP-2026-09-014`'s reading of the relation slot — and this
experiment's entire hypothesis — rested on the first number.

Nothing was repaired. `Q44` carries the decision.
