# PROTOCOL — EXP-2026-09-004

**Written before the run.** EXP-2026-09-003 predicted 47 and delivered 2, so the
prediction below is recorded first and scored afterwards whichever way it goes.

## Question

The ladder picks a template by which labels a question mentions rather than by
what it asks. Does gating it on the question's actual shape recover the ATT&CK
property reads and the CAPEC containment questions?

## Independent variable

Two changes, landed together:

1. `utils/specialists/cypher/builder.py` — the Group and Tactic branches fire on
   technique intent instead of on the label's presence, so a property read
   reaches `describe`.
2. `utils/specialists/gremlin/builder.py` — containment is added to the
   neighbour vocabulary, with the edge chosen by the container's kind
   (`MEMBER_OF` for a Category, `IN_VIEW` for a View) and the direction by which
   end anchors. No target label on the edge.

## Held constant

Same 32 questions, same bank hash, same arm, deterministic composer, no model in
the loop. Dev half only; the 288-question holdout stays sealed.

## Selection

Dev-half questions scoring below 1.0 in EXP-2026-09-002 whose spec either steps
across a membership predicate or is a D1 property read on a Group or Tactic
anchor. 32 questions.

## Prediction, recorded in advance

**23 of 32 move; 9 do not.**

| group | n | prediction | why |
|---|---:|---|---|
| containment anchored on a Category or View, forward | 20 | **move** | the traversal now exists and runs the right way; verified live returning 6 members for CAPEC-156 and 9 for CAPEC-1000 |
| ATT&CK property reads (Group 2, Tactic 1) | 3 | **move** | now reach `describe`, which returns the record |
| containment anchored on a member, reverse | 6 | **do not move** | only 67 of 6,374 CAPEC nodes sit in any view, so most of these have no edge to traverse and an empty answer is correct |
| `Technique`-anchored containment | 3 | **do not move** | an ATT&CK label on the CAPEC side; these route elsewhere entirely and this change does not touch them |

The reverse-direction handling is expected to be **right and to move nothing**,
because the data is sparse rather than because the traversal is wrong. That
distinction is the one to check in the results: an unmoved question whose query
is now correct is a different outcome from an unmoved question whose query is
still wrong, and EXP-2026-09-003 showed the two look identical in the score.

## Measurement

`deterministic_scores.coverage.coverage` per question, before from the
EXP-2026-09-002 artifacts and after from this run, plus the recorded template
and traversal direction so an unmoved question can be attributed.
