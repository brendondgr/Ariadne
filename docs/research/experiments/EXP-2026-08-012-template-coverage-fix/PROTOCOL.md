# EXP-2026-08-012 — Fixing the two template defects EXP-2026-08-010 found

**Written 2026-08-21, before either fix was written.** Hypotheses in §3 are
pre-registered.

## 1. What is being changed

EXP-2026-08-010 ran 182 questions from two published benchmarks and found six
of fourteen question types below the ceiling. Two distinct causes were traced.

**Defect A — sub-techniques dropped when the anchor is a Group or Campaign.**
`_group_techniques` and `_campaign_techniques` widen their target label only
when the *anchor* is a sub-technique:

```python
target = "(t)" if bound and bound.label == "SubTechnique" else "(t:Technique)"
```

When the anchor is the Group — that is, whenever the question is "what
techniques does this group use" — the target stays `(t:Technique)` and every
sub-technique result is dropped. `_software_techniques`, which scores 0.998 on
the same benchmark, widens unconditionally and is the model for the fix.

**Defect B — no template for the Software↔Group and Software↔Campaign edges.**
Nineteen templates exist; none covers them. Worse, the dispatcher's `if
has_group:` branch is unconditional, so "what software does group G0003 use?"
is routed to `_group_techniques` and answered with the group's *techniques*.

## 2. The changes

1. Both `_group_techniques` and `_campaign_techniques` always emit `(t)` with
   the `(t:Technique OR t:SubTechnique)` predicate.
2. A new builder for Group↔Software and one for Campaign↔Software, either end
   anchorable, following `_software_techniques`.
3. Two dispatch branches placed ahead of the branches that currently capture
   those questions.

Nothing else. In particular the generic path is untouched: `build()` returns
`self._build_generic(resolved)` before any changed line, so the `generic` arm
cannot move and is not re-run.

## 3. Pre-registered hypotheses

**H1 — the four dead families come alive.** `campaigns_for_software`,
`groups_for_software`, `software_for_campaign` and `software_for_group` rise
from 0.000 to their ceiling of 1.000. Refuted if any stays below 0.95.

**H2 — the two partial families close.** `techniques_for_group` (0.295 against
a 0.990 ceiling) and `techniques_for_campaign` (0.326 against 0.988) come
within 0.01 of their ceilings.

**H3 — overall external recall rises to at least 0.95**, from 0.6836 against a
ceiling of 0.9863.

**H4 — no internal answer changes. This is the one that can stop the fix.**
Re-running the deterministic arm over `bank-2026-08-19` and `bank-2026-08-20`
must reproduce the committed answers exactly, excluding clock readings
(`wall_s`, `timing_ms`). Every published figure in this project rests on those
answers. Refuted if any answer differs — and a refutation here outweighs H1–H3,
because a coverage gain bought by moving a recorded number is not a gain.

**H5 — the plan-free arm improves by less than the plan-given arm.** It must
still infer the entity types from the question text, and the new dispatch
branches key on those, so a share of the gain should not reach it.

## 4. What would make this wrong

- **The dispatch order.** Adding branches to a long `if` chain can silently
  re-route a question that already worked. H4 is the guard, and it is checked
  against committed bytes rather than against a score.
- **Same benchmarks, same limits as EXP-2026-08-010.** Enterprise ATT&CK only,
  enumerating questions only, CAPEC untouched, machine-authored phrasing.
- **A fix measured on the benchmark that found it.** These six families are no
  longer a blind test — the fix was written knowing exactly which questions
  score it. What this experiment can honestly show is that the diagnosis was
  right and the change is safe. It cannot show that the system now generalises;
  only a benchmark nobody has optimised against could.
