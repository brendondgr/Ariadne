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

## AMENDMENT A-1 (2026-09-09) — Pointers filled, supersession recorded, reproduction stated

Written during the 2026-09-09 record audit. No number in §1–§6 changes.

**What was wrong.** `data/POINTERS.md` was the blank scaffold (one empty row,
no artifact, no hash), so nothing in the record tied the figures above to the
raw runs they were computed from. The manifest also carried
`supersedes: null` although this experiment replaces EXP-2026-08-005's blind
headline (0.8952 → 1.0000 on the same 30 questions, same arm, same bank), and
RESULTS has no reproduction section.

**What is now correct.**

* `data/POINTERS.md` lists the five raw directories with tree hashes taken
  2026-09-09: `outerjoin-holdout` (after, blind), `outerjoin-dev` (after,
  development), `binding-fix-holdout` and `binding-fix-dev` (before, from
  EXP-2026-08-005) and `binding-baseline-holdout` (the 0.7688 origin of
  `progression_blind`). The two `outerjoin-*` directories have gained
  `*.judgment*.json` sidecars since the run (EXP-2026-08-007's grading passes,
  2026-08-19); the answer files are unchanged and every figure in §1–§2 and in
  `data/metrics.json` reproduces exactly from them once the sidecars are
  excluded (audit recomputation with `utils/evaluation/retrieval_coverage.py`:
  blind 1.0000 / 30 / 0 missing / 221 records; before 0.8952380952 / 26 / 5 /
  216; paired 4 improved (H-CHN-02 +2, H-CHN-01, H-CTM-01, H-CTM-02 +1),
  0 regressed; dev 1.0 / 1.0, 1079 / 1061 records; original 0.7687675, 22/30).
  See ISSUES 2026-09-09 for the n = 90 trap in the committed scorer.
* Manifest `supersedes`: `null` → `EXP-2026-08-005`. EXP-2026-08-005's
  manifest carries the matching `superseded_by` and `status: superseded`. Its
  0.8952 remains valid as the "before" row here.
* Manifest `related`: EXP-2026-08-007 added — the judged follow-up §6 asks for,
  which graded these very answer files.

**Reproduction (the §8 the contract asks for).** Entrypoint as in the manifest:
`uv run python -m utils.evaluation.experiment_untruncated --arm deterministic`
for the development catalogue and the same with
`--bank utils/specialists/tests/golden/holdout_questions.json` for the blind
set, at commit `c10caaad2c5f6bbbde4ddee93a8e9ec2383ddedb`, against the live
Neo4j + Gremlin stores (ATT&CK 19.0 / CAPEC 3.9). Score with
`utils/evaluation/retrieval_coverage.py` against the directories in
`data/POINTERS.md`.
