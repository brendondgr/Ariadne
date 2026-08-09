# Blind holdout v1 — results

**Experiment:** [`EXP-2026-08-001`](../../research/experiments/EXP-2026-08-001-blind-holdout-v1/)
**Protocol:** `docs/plans/robustness/02-holdout-question-generation.md` (normative),
`04-holdout-execution-brief.md` (execution), `05-holdout-execution-plan.md` (this run)
**Frozen at:** `freeze/holdout-v1` = `974e85a494f020e218e8b73f193543c11ea0d292`
**Every number here is produced by `utils/evaluation/holdout_report.py` from the
per-case judgment files.** None is transcribed from prose.

---

## The result

30 questions, written by an author that could not see the query templates,
anchored on entities drawn uniformly by a committed seeded sampler, gold computed
independently from the raw MITRE snapshot, graded by one independent Sonnet 5
agent per case.

| | Arm A (deterministic) | Arm F (loop + claim-bound writer) |
|---|---|---|
| **Blind correctness** | **0.689** (95% CI 0.550 – 0.817) | **0.708** (95% CI 0.565 – 0.838) |
| Development-set correctness | 0.9972 | 0.9957 |
| **Blind − development** | **−0.308** | **−0.287** |
| CORRECT-verdict rate | 17/30 = 0.567 (Wilson 0.392 – 0.726) | 19/30 = 0.633 (Wilson 0.455 – 0.781) |
| Verdicts (C / P / I) | 17 / 6 / 7 | 19 / 4 / 7 |
| Faithfulness | 0.977 | 0.970 |
| Groundedness | 0.993 | 0.973 |
| Completeness | 0.751 | 0.758 |
| Hallucinations | 1 (in 1 answer) | **0** |
| Wall clock, 30 questions | 1.0 s | 554.0 s |

Correctness is a mean of continuous judge scores, so its interval is a
percentile bootstrap (2000 resamples, seed 1729). The CORRECT-verdict *rate* is
a genuine binomial and carries the Wilson score interval plan 02 §10 asks for.
At n=30 both are wide; **do not quote a point estimate from this set without its
interval.**

Excluding the one malformed question (see *Deviations*) the figures are 0.709
(Arm A) and 0.729 (Arm F) over n=29 — the conclusion does not turn on it.

### What this means

The 0.9972 development figure **does not survive a blind question set.** It was
substantially a property of the questions, not only of the system. C-001 cannot
be promoted on the strength of the catalogue alone, and the catalogue figure must
never again be quoted without this one beside it.

But the drop is **not uniform**, and that is the finding worth having.

---

## Per-category breakdown

A uniform drop and a concentrated one mean very different things. This one is
sharply concentrated.

| Category | n | Arm A | Arm F |
|---|---:|---:|---:|
| `mitigations` | 2 | 1.00 | 1.00 |
| `tactics` | 1 | 1.00 | 1.00 |
| `execution` | 1 | 1.00 | 1.00 |
| `weakness` | 1 | 1.00 | 1.00 |
| `mapping` | 2 | 1.00 | 1.00 |
| `pattern-to-mitigation` | 4 | 1.00 | 1.00 |
| `reverse-mapping` | 3 | 1.00 | 1.00 |
| `detection` | 2 | 0.93 | 0.95 |
| `subtechnique` | 1 | 0.75 | 1.00 |
| `cwe-chain` | 3 | 0.63 | 0.68 |
| `lookup` | 3 | 0.55 | 0.62 |
| `hierarchy` | 1 | 0.15 | 0.10 |
| `consequence` | 1 | 0.15 | 0.15 |
| `prerequisite` | 1 | 0.10 | 0.10 |
| `software` | 2 | 0.06 | 0.05 |
| `groups` | 2 | **0.00** | **0.00** |

Seven of sixteen categories score a clean 1.00 on both arms. The loss is
concentrated in four failure modes, each diagnosable from the executed query
rather than from judge prose:

**1. Reverse direction is unserved (`groups`, `software` — 4 questions, ~0.03).**
`group_techniques` emits `MATCH (g:Group)-[:USES]->(t:Technique) WHERE
g.attack_id IN $ids` and the holdout binds `$ids` to a *technique* id. The query
is structurally unsatisfiable — it filters `Group.attack_id` against `T1550.002`
— so it returns nothing, every time. The development bank never exposed this
because it only ever asks Group → techniques. The blind author, given "the
groups using a technique", asked the other direction, and there is no template
for it. `software_techniques` fails the same way and falls through to `describe`.

This is a genuine coverage boundary, not a scoring artifact: the system answers
*A → B* and is asked *B → A*.

**2. Facet counts instead of neighbours (`consequence`, `prerequisite`,
`hierarchy` — 3 questions, ~0.13).** Retrieval frequently succeeded and
synthesis did not use it. `H-PRE-01` retrieved all three `REQUIRES_SKILL`
neighbours into the record's `related` array; the composer reported only the
pattern's own metadata. `H-ABS-01` retrieved the full chain CAPEC-606 → 620 →
212 and reported only CAPEC-606's own abstraction level. The evidence was
there and the answer did not carry it.

**3. Metadata instead of substance (`lookup` — 3 questions, 0.55 / 0.62).**
Every `lookup` case satisfied its formal gold — the right node, the right name,
one record — and was still graded PARTIAL, because the blind questions ask *"how
does this technique actually work?"* and the answers returned STIX bookkeeping
(`revoked`, `stix_type`, `x_mitre_version`) while the description sat unused in
the same record. The gold assertion was too weak to notice; a human reading the
answer notices immediately.

**4. Chain incompleteness (`cwe-chain` — 3 questions, ~0.65).** `H-CHN-01`'s
`cwe_chain` query returned one of the two patterns gold requires.

**Arm F − Arm A = +0.019.** The facet-chasing loop and the claim-bound writer
buy almost nothing here, because the dominant failures are *retrieval-shape*
failures — a query that cannot match, or a composer that ignores what was
retrieved — and neither is a thing the loop chases. Arm F's one clear win is
`subtechnique` (0.75 → 1.00). Its one clear cost is 554 s against 1.0 s.

---

## The two federated strata, reported separately

Per plan §2.4 these are never averaged. "Correctness" means answer correctness in
one and abstention behaviour in the other.

| | n | Arm A | Arm F |
|---|---:|---:|---:|
| **Answerable** (anchor has ≥1 live ATT&CK mapping) | 6 | 1.00 | 1.00 |
| **Abstention-expected** (anchor has none) | 4 | 0.83 | 0.88 |
| — abstained | | 4/4 | 4/4 |
| — abstention carried the executed query | | 4/4 | 4/4 |
| — **fabricated a mapping** | | **0/4** | **0/4** |

Reported across the whole set, the answerable partition (n=26, which includes
the single-source strata) scores 0.668 / 0.683 and the abstention partition
0.825 / 0.875.

**This is the strongest result in the run.** On anchors with no live mapping —
the case a system is most tempted to hallucinate through — both arms abstained
every time, carried the executed query as proof every time, and invented a
correlation zero times. The abstention machinery
(`utils/synthesis/verifier.py:_enforce_abstentions`) does what it claims,
on questions it has never seen. The 0.83/0.88 rather than 1.00 comes from one
case, `H-CHN-02`, where the judge held that the CAPEC-side pattern list should
still have been surfaced before the ATT&CK join came back empty.

By stratum: federated 0.890 / 0.905, CAPEC single-source 0.619 / 0.656, ATT&CK
single-source 0.568 / 0.579. **The federated path — the project's actual
contribution — is the part that generalises best.**

---

## Discards

**Zero.** No anchor failed gold computation, so `anchors.json`'s `discards`
array is empty. The draw needed 10 over-draws to fill the federated partitions
to 6 answerable / 4 abstention-expected; those are recorded in `anchors.json`
under `overdraw`.

---

## Deviations

Both are recorded here rather than folded in silently.

**1. A missing `join_key` on the CAPEC `mapping` category (fixed, re-run).**
The Compiler emitted `join_key: null` for `H-MAP-01` and `H-MAP-02`. The Gremlin
builder gates `capec_maps_to` on the declared join, so both questions fell
through to `describe` and returned facet counts instead of the mapped
techniques — while all three committed `C-MAP-*` entries carry the key. That
meant the holdout was being compared against a *different plan* than the
development set gets for the same category, which is not the comparison this
experiment makes. This is a harness defect, not a wrong answer from the system,
so §9's crash rule applies: fixed, logged, both cases re-run and re-judged on
both arms. **The authored question text was not touched.** Both cases moved from
INCORRECT (0.10 / 0.05) to CORRECT (1.00) on both arms, which moved Arm A from
0.627 to 0.689.

**2. One malformed authored question (kept, not repaired).** `H-SW-01` asks
what techniques a *sub-technique* implements, because the §5 `software` category
is phrased for a Software anchor while the stratum's population is techniques.
Editing it would have converted a blind question into a co-authored one. It
stands verbatim, and every figure is also reported excluding it (0.709 / 0.729
at n=29).

Three judgment files were not written by their grading agents even though the
agents returned the verdict; each was recovered verbatim from the workflow
journal rather than re-graded.

---

## Reproducibility

A human-authored holdout cannot be re-run. This one can.

| Artifact | What it pins |
|---|---|
| [`anchors.json`](anchors.json) | Seed `20260805`, the three population sizes and their SHA256s, the full draw order, the 10 over-draws, the federated partition, the (empty) discard log |
| [`author-prompt.md`](author-prompt.md) | The template and all 30 filled prompts, verbatim as sent |
| [`authored.json`](authored.json) | The 30 returns, unedited, checked against the workflow journal |
| [`results.json`](results.json) | Every per-case verdict, rationale and rollup |
| `utils/specialists/evalset/holdout_protocol.py` | The sampler and the prompt builder |
| `docs/evaluation/experiments/holdout-v1/` | Raw answers, full evidence, and judgments for both arms |

A reviewer can regenerate the draw and confirm the anchors were sampled
uniformly rather than selected — which is the property that makes "blind" a
checkable claim rather than an assertion. `anchors.json` was committed
(`fb3db45`) before any question existed; the questions landed in `b2fa95c`.

`expected_template` is present on every entry but is **derived** by the Compiler
from the anchor's type and category — the Author never saw the template
inventory and could not supply it. **Template-routing accuracy may not be
reported from this holdout.**

---

## The gate

`docs/plans/branch-a-publication-readiness-plan.md` §6, recovered verbatim from
git history (the plan was deleted in the 2026-08-06 trim; the rule is quoted as
written and was not renegotiated after seeing the result):

> **If blind correctness < 0.70** — the 120-question result is substantially a
> coverage artifact and the paper changes. Do not proceed to Steps 6 and 7 as
> written. The finding becomes *"a validated template library achieves
> near-ceiling correctness on covered questions and degrades sharply
> off-coverage, and here is the coverage boundary"* — legitimate, arguably more
> interesting, but a different paper needing its own plan. Stop and re-plan
> rather than continuing on momentum.

**Arm A blind correctness is 0.689. That is below 0.70, so this branch applies.**

Two facts are recorded alongside it, as facts and not as grounds for choosing a
friendlier branch:

- The margin is 0.011 and the 95% CI (0.550 – 0.817) spans three of the gate's
  four bands. At n=30 this gate cannot be resolved sharply, and the plan's
  thresholds were set without that being obvious.
- Arm F is 0.708, inside the 0.70 – 0.85 band, whose instruction is "drop
  ARTMAN, re-scope Step 7 to the reduced form".

The gate's standing kill criteria are both satisfied: the seed, sampler and
anchor list are committed, so the sample is auditable, and no material
disagreement with the original verdicts arose.

**Consequence:** Steps 6 and 7 of the Branch A plan do not proceed as written.
The re-plan should take the coverage-boundary framing, for which this run
already supplies the boundary: the system is at ceiling on the relation
directions its templates serve and at zero on the reverse ones, and that
statement is now measured rather than asserted.

---

## Limitation

Stated in the terms plan 02 §10 requires:

> An LLM-authored holdout controls co-authorship bias — the author had no
> knowledge of the template inventory — but does not control for the question
> distribution being a model's idea of what an analyst asks. A human-authored
> set remains the stronger test; a further 15–20 questions would be a cheap
> secondary check.

Two further limits specific to this run. Per-category cells hold 1–4 questions,
so no single category figure carries weight on its own — the pattern across them
does. And the `lookup` result exposes a limitation of the *gold*, not of the
system: every `lookup` case satisfied its computed assertions and was still
judged PARTIAL, which means computed gold from an id-and-name parse cannot
express "answer the question the analyst asked".
