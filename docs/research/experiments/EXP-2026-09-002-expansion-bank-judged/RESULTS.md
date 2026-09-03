# RESULTS — EXP-2026-09-002 The expansion bank, judged

**16 of 16 phases completed.** 2026-09-02T22:55:52Z → 2026-09-03T09:49:42Z,
10.9 hours unattended. Every number below was read from a file in
[`data/POINTERS.md`](data/POINTERS.md).

---

## Headline

**On the schema the templates were written for, the template cascade loses to
queries assembled from the schema at run time — by 0.1642.**

| arm | judged correctness | cases | judgments |
|---|---:|---:|---:|
| **`generic`** — assembled from the schema | **0.6576** | 284 | 568 |
| `deterministic` — the template cascade | 0.4934 | 284 | 568 |
| `llm_query` — a model writes the query | 0.3712 | 283 | 564 |

Both leading arms contain **no language model at all**. The comparison is
between *authored* structure and *derived* structure, and derived wins on the
home schema.

**Why this matters more than the number.** C-023 currently rests on two
measurements that bracket the interesting case without landing in it:

| population | template − generic | source |
|---|---:|---|
| the 120-question catalogue | **0.0000** (both saturated, sd 0) | EXP-2026-08-015 + Q22 fix |
| a foreign identity schema | **−0.6121** [−0.6720, −0.5530] | EXP-2026-08-015 |
| **this bank, same schema as the catalogue** | **−0.1642 (judged)** | here |

The catalogue said *level*; the foreign schema said *catastrophic*. The natural
reading was that the boundary is the **schema** — templates hold where they were
written, and fail where they were not. **This experiment says the boundary is
not the schema.** Same stores, same catalogues, same templates — and templates
lose as soon as the questions leave the 12 shapes they were authored against and
reach the 34 the sources actually support.

**The condition on C-023 is vocabulary, not schema.** That is the amendment this
experiment makes, and it is a stronger and more general claim than the one it
replaces: a template library's advantage is bounded by the question shapes its
authors thought of, on any schema, including its own.

---

## Read the `llm_query` row as confounded, and do not cite it as a baseline

**153 of 284** of that arm's questions returned an empty query, and the gate
correctly refused it. That is only a baseline if the model wrote *bad* queries.
It is not one if the model never emitted anything.

`builder_budget_probe.py` put the identical request to the same model again:

| budget | outcome |
|---:|---|
| 4096 (as run) | 2 of 2 replies `finish_reason: length`, `content_chars: 0`, **16 826 / 16 326 reasoning chars** |
| 32768 | 1 of 2 produced an actual `MATCH (s:Software {attack_id: $id}) …`; the other 502'd at the relay after 603 s |

The served model reasons before answering; chain-of-thought lands in a separate
`reasoning` field and `content` stays empty until it stops thinking. A budget
spent entirely on reasoning returns `finish_reason=length` with `content=''` —
**downstream indistinguishable from a model with nothing to say.**

So **0.3712 measures how much room the model was given to think**, not whether
it can write a query. It is recorded here and it must not be quoted against
C-012. C-012's supporting figure remains EXP-2026-08-008's 0.9467 vs 0.5000,
which was not budget-limited in this way.

**A second defect, found by reading the run's own records.** `.env` sets the
builder budget to **2048**; the arm never read it and used a built-in default of
**4096**. Neither was large enough, so it changed nothing tonight — but a setting
that is written down, looks correct, and is silently ignored is worth fixing
before it matters. See ISSUES.md I-3.

---

## Direction: the contradiction is resolved, and the answer is "it depends"

EXP-2026-09-001 A-4 found forward easier; A-5's aggregate found reverse easier
(0.5165 vs 0.4302). **A-5's comparison is invalid** — its forward and reverse
questions are about *different edges*, so it may only be reporting that the
reverse questions landed on easier subject matter.

Paired on shape, 20 shapes, 237 questions:

| | |
|---|---:|
| mean delta (positive = forward easier) | **−0.0797** |
| sd / se | 0.4865 / 0.1088 |
| forward higher | 3 shapes |
| reverse higher | 10 shapes |
| tied | 7 shapes |

**The interval spans zero, and that is the finding.** There is no global
direction effect. But the per-shape spread is enormous — the sd is six times the
mean — and that is what matters:

| shape | easier direction | gap |
|---|---|---:|
| `AttackPattern -[CanPrecede]-> AttackPattern` | forward | 0.9815 |
| `AttackPattern -[ChildOf]-> AttackPattern` | forward | 0.8688 |
| `Campaign -[uses]-> Technique` | reverse | 0.6620 |
| `Analytic -[log_source]-> DataComponent` | reverse | 0.5833 |
| `Category -[HAS_MEMBER]-> AttackPattern` | reverse | 0.3333 |

**Direction matters a great deal, and which direction is harder depends entirely
on the edge.** Averaging over shapes destroys the effect; that is why both prior
readings were wrong in the same way. 97 questions were excluded because their
shape was asked from only one end.

---

## The property-read anomaly has one cause, and it is not comprehension

A-5 flagged D1 (read one property) scoring below both single-hop tiers, which
the difficulty ordering does not predict. Classified by cause, without a model:

| tier | failures | cause |
|---|---:|---|
| D1 property read | **63 of 63** | `query_built_returned_no_rows` |
| containment | **68 of 68** | `query_built_returned_no_rows` |

**One cause, 131 cases, zero exceptions.** This rules out most explanations: the
question is understood, a query is built, the gate passes it, and it executes
cleanly against a live store. It is looking somewhere the answer is not.

And it is **specific, not general** — recall by anchor label:

| anchor | recall |
|---|---:|
| Group | **0.0000** |
| Tactic | **0.0000** |
| View | **0.0000** |
| Analytic / AttackPattern / DataComponent / Mitigation | 0.5000 |
| Software | 0.4688 |
| Technique | 0.4179 |
| Campaign | 0.4861 |

Three node types fail completely while everything else works about half the
time. That shape — total failure on a few types, partial success elsewhere —
is what a **property-name or storage-location mismatch** looks like, not what a
capability limit looks like. It is the cheapest open defect in the project.

---

## Abstention, tested at 15× the previous scale

Previously evidenced on **4** questions. The bank carries **61**.

| outcome | n | share |
|---|---:|---:|
| correctly returned nothing | 37 | 60.7% |
| returned the anchor only | 18 | 29.5% |
| returned unrelated neighbours | **6** | **9.8%** |

The 18 anchor-only cases are a mild failure — the subject echoed back with no
fabricated relationships. The **6 unrelated-neighbour cases are the serious
kind** and are the clearest weakness this bank found.

This bears directly on C-023's abstention half, which is the part of that claim
that has held across every prior setting. **It still holds relatively** — the
mechanism diagnosed in EXP-2026-08-007 A-1 (the generic path never emits the
source-side abstention when a query ran cleanly and returned the anchor but no
linked records) predicts exactly the `returned_the_anchor_only` class, and 18 of
24 failures are that class. **But 60.7% absolute is much weaker than the 95%
query-carrying abstention rate the cascade shows on the catalogue**, and the gap
is the same story as the headline: the catalogue never asked these shapes.

---

## What this does and does not license

**Licensed.**

- Amending C-023's condition from *schema* to *vocabulary*, with this as the
  evidence. This is the strongest form of the study's primary result.
- Quoting 0.6576 / 0.4934 as a **ranking** of the two model-free arms on this
  bank, by an **identified** grader (`qwen38-27B-v2`, probed at preflight),
  which is what X2 in the 2026-08-31 audit exists to obtain.
- Reporting the direction result as "no global effect, large per-edge effects".
- Reporting the empty-query diagnosis as a single localised defect.

**Not licensed.**

- **Comparing these judged figures to EXP-2026-09-001 A-5's recall.** Different
  instrument, different population, different question.
- **Comparing them to the 0.95–1.00 the committed banks score.** Those cover 12
  shapes in the direction they were written for.
- **Quoting 0.3712 against C-012.** Budget-confounded; see above.
- **Any claim about the holdout.** 288 questions were sealed and stay sealed.
- **A significance test.** `n_runs: 1` per arm; D-010 is still in force. The
  0.1642 gap is 16× the grader's measured 0.0050 spread and 16× the ~0.01 order
  effect, which is why it is reported — but that is an argument from magnitude,
  not a test.

---

## Reproduce

```bash
uv run python scripts/expansion_overnight.py     # resumes from overnight-state.json
uv run python scripts/builder_budget_probe.py    # the llm_query confound
```

The `deterministic` and `generic` arms are byte-reproducible. The `llm_query`
arm and both grading passes are not — they depend on a locally served model.
