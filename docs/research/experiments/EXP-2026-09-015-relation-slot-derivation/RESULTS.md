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

The ablation (`A-7`) is sharper still. Holding the model's own picks fixed and
changing only how they are read, **three cells move out of twenty-four** and
`records_exact` is identical at every tier. The intervention is very nearly a
no-op on the answers.

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

## A-3 — Against the ship rule, judged on the ablation

**The before/after against `EXP-2026-09-014` is confounded and must not be used
to judge the rule.** `A-7` shows why: on identical model picks the derivation
moves `wrong_entity` at T4 by **−0.0189**, while the gap to `EXP-2026-09-014`'s
run of the same arm is **+0.0503** in the other direction. Something other than
the intervention moved between the two sessions, and the ablation is the only
comparison that holds the model's choices fixed. It is what the protocol
pre-registered as the causal claim, and it is what the rule is judged on here.

| clause | outcome on the ablation |
|---|---|
| 1. `slot_relation` rises on T3, T4, T5 | **failed** — T3 falls 0.3810 → 0.3333; T4 and T5 identical |
| 2. `form_exact` rises on two of three | **failed** — T3 falls 0.2549 → 0.2353; T4 and T5 identical |
| 3. `wrong_entity` does not rise anywhere | **passed** — T4 falls 0.3208 → 0.3019; every other tier identical |

**The change is still refused, but for the honest reason.** It fails on clauses
1 and 2: it does not improve what it was built to improve. It does *not* cost
what an earlier reading of these numbers suggested — clause 3, the one the
protocol singled out as mattering most, passes.

`records_exact` is identical at every tier under the ablation. The intervention
is very nearly a no-op on the answers, which is the cleanest possible statement
of the result.

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

## A-6 — The shipped path is byte-for-byte untouched

Required before any builder-, normalizer- or router-adjacent change ships, and
required here specifically because `utils/llm/client.py` is a module every model
call in the repository passes through.

```
changed 0 of 120  |  better 0  worse 0  same 0  |  0 changed with no recorded gold
gold recall over 66 scorable questions: 0.9161 -> 0.9161  (+0.0000)
```

Captured 2026-09-10 against `reference_2026-09-08.json`, scored independently on
both sides against gold parsed from the pinned STIX and CAPEC bundles rather
than against the earlier capture. Raw output in
`data/recorded_answer_regression.txt`.

Two changes were in scope. The rewrite-stage derivation is inert because it
lives inside the model rung and both flags ship off — `A-2` already showed the
flag-off arms reproducing exactly. The token meter is inert because it
accumulates usage from replies that have already been parsed and returned, and
no branch reads it.

## A-7 — The ablation, and why it is the only comparison that counts

`A4` replays `A2` run 1's **own cached model choices** with the derivation
switched off. The model is not consulted again; the same 191 picks are folded
into a form twice and interpreted differently. Any difference is the
derivation and can be nothing else.

| tier | `slot_relation` on / off | `form_exact` on / off | `wrong_entity` on / off | `records_exact` on / off |
|---|---|---|---|---|
| T1 | 0.2400 / 0.2400 | 0.4603 / 0.4603 | 0.1270 / 0.1270 | 0.4444 / 0.4444 |
| T2 | 0.2400 / 0.2400 | 0.4921 / 0.4921 | 0.1111 / 0.1111 | 0.4603 / 0.4603 |
| T3 | **0.3333 / 0.3810** | **0.2353 / 0.2549** | 0.0980 / 0.0980 | 0.4118 / 0.4118 |
| T4 | 0.1304 / 0.1304 | 0.0755 / 0.0755 | **0.3019 / 0.3208** | 0.0943 / 0.0943 |
| T5 | 0.2174 / 0.2174 | 0.0943 / 0.0943 | 0.2830 / 0.2830 | 0.1698 / 0.1698 |
| T6 | 0.7500 / 0.7500 | 0.0000 / 0.0000 | 0.0556 / 0.0556 | 0.1111 / 0.1111 |

Three cells move out of twenty-four. The derivation costs 0.0477 of relation
accuracy at T3, buys 0.0189 of `wrong_entity` at T4, and changes **nothing
else, anywhere** — `records_exact` is identical at all six tiers.

### The confound this exposes

`wrong_entity` at T4 reads 0.2516 in `EXP-2026-09-014` and 0.3019 tonight, a gap
of +0.0503 across sessions. The ablation says the derivation accounts for
−0.0189 of movement, in the opposite direction. So something *between the two
sessions* moved that figure, and it is not the intervention.

The known difference is that the CAPEC Gremlin fixture was found empty at the
start of this session and reloaded before the arms ran. Preflight verifies node
and edge counts against the pinned manifest and passed, so the *contents* agree;
traversal ordering after a fresh load need not. That is a hypothesis, not a
finding, and it is filed as `Q46`.

**The operational lesson stands regardless.** A before/after across sessions is
not a controlled comparison in this system, however stable the within-session
spread looks — and tonight's within-session spread was 0.0000 on the very cell
that moved 0.0503 between sessions. Had the ablation not been pre-registered,
this experiment would have reported a cost the intervention did not cause.
