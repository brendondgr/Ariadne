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

---

# AMENDMENT A-1 (2026-09-09) — The model-free metrics span the sealed holdout, the score pin broke, and this experiment is superseded

Written from the 2026-09-09 audit (`verify-b5.md`), `bank.json`,
`score.json`, `anomalies.json`, `direction.json`, the judged sidecars and
`git log`. Nothing here changes the three judged arm figures, which the audit
recomputed from the sidecars exactly (0.6576 / 0.4934 / 0.3712, gap 0.1642).

## 1. The manifest says `split: dev`, `n_examples: 284`; the model-free metrics were computed over all 572 questions

`data/POINTERS.md` names the same `score.json`, `direction.json` and
`anomalies.json` that EXP-2026-09-001 A-5 produced from the **full** 572-question
model-free run (`expansion-2026-09-01/deterministic/answers`, 572 files). Those
files carry no split filter, and the populations behind four manifest metrics
prove it:

| metric | recorded n | what the n is | dev | holdout |
|---|---:|---|---:|---:|
| `abstention_rate` (37 of 61) | 61 | every D0 question in the bank | 36 | **25** |
| `property_read_empty_query_rate` (63 of 63) | 63 | every D1 question in the bank | 35 | **28** |
| `containment_empty_query_rate` (68 of 68) | 68 | every question on a `CONTAINMENT` shape (`scripts/anomaly_triage.py`) with recall < 1 | 35 | **33** |
| `direction_paired_mean_delta` (20 shapes, 237 + 97 = 334 questions, ISSUES I-8) | 20 | every single-shape non-D0 question | 166 | **168** |

Of the 24 abstention failures listed in `anomalies.json`, 14 are dev ids and
10 are holdout ids. PROTOCOL.md `:80-82` lists tier counts of 61 / 63 / 77 /
89 / 117 / 105 / 60 — which sum to **572**, not 284; the dev half is 36 / 35 /
40 / 44 / 55 / 47 / 27.

**What this does and does not change.** The three judged arm figures and the
0.1642 gap are dev-only (568 judgments per arm over 284 cases) and are
unaffected. The direction, anomaly and abstention findings are correct as
computed, but their population is the whole bank, and the sentence at
`RESULTS.md:191` — *"288 questions were sealed and stay sealed"* — and
`PROTOCOL.md:78-79` are too strong in the same way EXP-2026-09-005 A-1 later
conceded for the deterministic arm's model-free look: no holdout question was
ever **judged** here, but the deterministic arm's model-free answers to all 288
were read by these three analyses. The manifest's `data.split` now says so, and
each affected metric carries its dev/holdout denominators in a comment.
`n_examples` stays 284 because it describes the judged population the primary
metric is computed over.

## 2. The `score.json` pin

`score.json` was rewritten on 2026-09-08 by `a460fa2` (Hybrid Rewrite Stage
6/8): every row gained `rung` / `model_consulted` / `cache_hit` /
`served_model` columns and the report gained a `rewrite` block. The file grew
from 233,633 B (`sha256:6fb4eaf1…`, the `eeef322` blob this experiment read)
to 302,627 B (`sha256:a3f779fc…`). The `report` values — 0.4522 / 0.506 / dev
0.435 / holdout 0.4683 / 37 of 61 — are unchanged, and the audit reproduced
37/61 from the `eeef322` rows. The row is re-hashed and records the original
blob (ISSUES I-10).

## 3. Superseded by EXP-2026-09-005

EXP-2026-09-005's manifest has declared `supersedes: EXP-2026-09-002` since
2026-09-03 and this manifest carried no back-link. Set on 2026-09-09:
`superseded_by: EXP-2026-09-005`, `status: superseded`. The reason is the one
005 states: *"The 0.1642 gap was measured against a baseline carrying three
retrieval defects; repaired, the gap is 0.1623."* The three defects were sized
by EXP-2026-09-003 (CAPEC anchor identity, 0.0816 → 0.1081 over 37 questions)
and EXP-2026-09-004 (template routing, 0.0787 → 0.4059 over 32). EXP-2026-09-003
ISSUES I-1 also records that the *"63 of 63"* property-read figure here *"was
an artifact of a classifier with one reachable branch"*: every D1 failure was
classified `query_built_returned_no_rows` because that was the only cause the
triage could assign. The quotable arm comparison is now 005's 0.6569 / 0.4946 /
0.1623 (dev) and EXP-2026-09-007's 0.6546 / 0.4862 / 0.1684 (holdout).
`related` gains 09-003, 09-004 and 09-005.

## 4. Smaller corrections

- **Aggregation.** PROTOCOL.md `:96-97` defines the arm figure as *"the mean
  over all judgments (568 per arm)"*. The recorded figures are means of
  per-case means (both positions averaged per case, then across cases). The
  two coincide for `deterministic` and `generic` (every case has two judgments)
  and differ for `llm_query`: per-case **0.3712** (recorded) vs over-judgments
  0.3723. The recorded convention is the one every later experiment uses.
- **ISSUES I-7 ("283, not 284 … cause unexplained")** is explained by the
  sidecars: two *different* cases failed in the two passes —
  `D1-Campaign-description-C0005…::indirect` (p1) and
  `D3-subtechnique-of-T1589…::formal` (p2) — so 282 + 282 = 564 judgments cover
  283 cases with at least one judgment and 281 with two. The four
  `.judgment.p{1,2}.error.txt` files are in the pointed directory.
- **RESULTS.md `:57`** says *"16 826 / 16 326 reasoning chars"*;
  `budget-probe.json` records **16,844** / 16,326.
- **`environment.lockfile`**: `env/requirements.lock` → `null` (never written;
  ISSUES I-9).

## 5. Manifest changes, old → new

`status` complete → superseded · `superseded_by` null → EXP-2026-09-005 ·
`data.split` "dev" → the two-population statement above · `environment.lockfile`
env/requirements.lock → null · `related` + [09-003, 09-004, 09-005] · comments
on four metric lines. No metric value changed. `data/metrics.json` created.
