# RESULTS — EXP-2026-08-006 The template bridges as outer joins

## 1. Headline

Blind-holdout retrieval for the **default cascade** reaches **1.0000** — 30/30
fully covered, zero gold identifiers missing — from 0.8952, with the
120-question development catalogue reporting **0 improved, 0 regressed**.

All five identifiers `EXP-2026-08-005` named in advance are recovered, and only
those five.

**Nothing here is judged.** See §5.

## 2. The progression, on one bank

From [`data/metrics.json`](data/metrics.json). Same arm, same 30 blind
questions, same live fixtures.

| Tree | Blind `gold_in_evidence` | Fully covered |
|---|---|---|
| Template cascade as the holdout measured it | 0.7688 | 22/30 |
| + binding check and direction resolution (`EXP-2026-08-005`) | 0.8952 | 26/30 |
| + outer-join bridges (this) | **1.0000** | **30/30** |

Development catalogue: 1.0000 before and after, 0 improved, 0 regressed.
Evidence records rise 216 → 221 on the blind set: the unmapped anchors now
returned rather than dropped.

The two defects were independent and are now both closed. The 0.7688 figure was
never one problem.

## 3. The regression this exposed, which is the real result

An outer join changes what "nothing found" looks like, and the abstention
machinery was keyed on the old shape. `_empty_ok_results` defined an honest
empty as *no records*. Once the producer returned the anchor with an empty
mapping list, it stopped abstaining — and the answer to "which ATT&CK techniques
does CAPEC-16 map to?" became two supported claims about CAPEC-16's abstraction
and status, with **no statement about mappings at all**.

Nothing was fabricated. The unsupported-claim rate stayed at 0.0 and no
correlation was invented. But the answer quietly stopped answering, and the
project's headline property — abstain with the executed query as proof — had
been deleted by a recall fix.

The repair: a sub-question that declared a join key and came back with no join
values is an honest empty *for that join*, whatever else its records describe.
The statement now reads

> the executed query ran cleanly and returned CAPEC-16 with no linked records

rather than the false *"returned no matching records"* — the record exists, and
saying otherwise would misdescribe the evidence the answer cites.

This is the argument for keeping adversarial negatives in a golden bank. The
retrieval metric rose at every step of this experiment; the honesty defect was
invisible to it and was caught only because seven committed negative cases
asserted the old contract and failed.

## 4. The gold contract moved, deliberately

Recorded as [D-015](../../DECISIONS.md). A negative answer may now carry
supported, cited claims describing the anchor and **must** still carry the
query-proof abstention. `expect_no_join` replaces `expect_empty` on the seven
cases where the anchor genuinely exists.

Two disciplines on that change, because moving gold is what this project
distrusts everywhere else: it is made in the bank *generators* rather than the
compiled JSON, and it altered seven assertions and **zero gold values**. An
early draft wrongly flipped `A-NEG-01` — a lookup of a nonexistent technique,
which is a true empty — and corrupted its gold from `[]` to `["T9999"]`. That
was caught by diffing the recompiled bank, and it is recorded here rather than
quietly fixed, because it is precisely the accident this discipline exists to
catch.

## 5. Threats to validity

* **Nothing is judged**, and `gold_in_evidence` is now saturated at 1.0000 on
  **both** banks for this arm as well as the generic one. The metric has no
  headroom left and cannot see the precision cost of returning strictly more.
  A second 1.0000 is not twice the evidence.
* **A post-fix v1 figure is a diagnostic, not a headline** — v1 diagnosed both
  defects this arm now repairs.
* **Arm F is not re-run.** The local LLM server was restarting; only the
  deterministic arm is measured here.
* **Arm-figure comparability is now generational.** Figures before
  `freeze/arm-baseline-2` and after are comparable only with the label attached.
* **n = 30**, single run, seeds unrecorded.

## 6. Follow-ups

1. **Re-run Arm F** on both banks when the LLM server is back, and label both
   arms as generation 2.
2. **Judge** this arm and Arm H. Every remaining question about either is a
   precision question and retrieval cannot answer it.
3. **Holdout v2**, before any blind figure is quoted.
4. The composer's `under_enumeration` defect, unchanged by this work.
