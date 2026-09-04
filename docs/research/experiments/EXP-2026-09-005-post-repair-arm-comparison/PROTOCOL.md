# PROTOCOL — EXP-2026-09-005

## Question

EXP-2026-09-002 measured `generic` 0.6576 against `deterministic` 0.4934 while
the deterministic arm carried three retrieval defects, so a reviewer could say
the baseline was broken and the 0.1642 gap was not quotable. **Does the gap
survive repairing the baseline?**

## Independent variable

Every repair landed between `0d2934f` and `a1e20f6`, applied to the
deterministic arm's retrieval path and to the graph both arms read:

1. the ATT&CK build's ten-property allowlist, inverted to a shape rule
   (`75a9e74`), plus the two Gremlin loader defects that blocked the reload;
2. CAPEC anchors resolved by identity rather than a guessed label (`2432ce8`);
3. the template ladder gated on what a question asks (`e741f44`);
4. the property-read scoring rule, pre-registered before any figure (`49357f8`).

Both stores were reloaded from the committed exports: Neo4j attack 4,369 /
27,669, Gremlin capec 6,374 / 8,582.

## Held constant

Same bank file (`bank-dev.json`, hash pinned below), same 284 questions, same
grader (`qwen38-27B-v2` at the :4000 relay, `max_tokens=32768`), same
counterbalancing — two passes per arm with the grading position swapped, so the
~0.01 order effect from EXP-2026-08-022 is subtractable rather than baked in.
16 workers.

## What is deliberately absent

`llm_query` is **not re-run**. Its budget defect is fixed (`a1e20f6`) but the
cost of running it at an adequate budget was not measurable — the probe was
sharing a relay with this judging run and was stopped rather than reported from
confounded timings. Re-running or cutting that arm is an operator decision that
needs the cost evidence first.

## Measurement

Two figures that must not be conflated:

* **model-free recall** — snapshot-derived gold found in retrieved evidence, no
  model in the loop, via `scripts/score_bank.py`;
* **judged correctness** — a grader reading each written answer, averaged per
  case across both passes before averaging across cases.

The pre-repair deterministic recall is quoted as **0.4492**, not the published
0.4350: the latter was computed before the property-gold rule existed, and
comparing across scoring rules would credit the repair with the rule's effect.

## The holdout

288 questions, untouched. Asserted by hash and by checking that no answered case
id belongs to the holdout split.
