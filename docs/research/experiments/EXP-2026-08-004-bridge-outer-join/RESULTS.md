# RESULTS — EXP-2026-08-004 The bridge as an outer join

## 1. Headline

Making the generic cross-source bridge an **outer join** takes blind-holdout
retrieval to **1.0000** — 30/30 fully covered, zero gold ids missing — from
0.8952 before the fix and **0.7688** for the hand-written template cascade.
The development catalogue holds at 1.0000 with **0 regressions**.

Every one of the five residual identifiers `EXP-2026-08-003` left outstanding
was the same defect, and all five are recovered.

**Nothing here is judged.** See §5.

## 2. Results table

From [`data/metrics.json`](data/metrics.json); per-set summary in
[`tables/tab-outer-join.md`](tables/tab-outer-join.md).

| Set | Template cascade | Arm H inner join | **Arm H outer join** |
|---|---|---|---|
| Blind `gold_in_evidence` | 0.7688 | 0.8952 | **1.0000** |
| Blind fully covered | 22/30 | 26/30 | **30/30** |
| Development `gold_in_evidence` | — | 1.0000 | **1.0000** |
| Development fully covered | — | 120/120 | **120/120** |

Paired, blind set: 4 improved, **0 regressed**. Paired, development set: 0
improved, **0 regressed** — it was already saturated, so that run could only
detect harm, which is why it was worth running.

Evidence records rise 950 → 966 on the development set and 51 → 56 on the blind
set: the unmapped anchors now being returned instead of dropped.

## 3. What the fix actually is

`.out(edge)` is an inner join — an anchor with no edge on the far side produces
no row, so it disappears from the evidence entirely. The bridge now projects one
row per anchor with its mappings folded into a possibly-empty list.

The CWE-anchored chain is deliberately **asymmetric**: the first hop stays an
inner join, because only patterns that genuinely exploit the weakness belong in
the answer, and only the second becomes outer. Making both outer would return
patterns unrelated to the weakness; making both inner is what was deleting
`CAPEC-116`.

This is not only a recall fix. *"This pattern has no ATT&CK mapping"* is a real
analyst answer, and an inner join cannot return the record needed to ground it.
Three of the four affected blind questions are `expect_no_correlation` cases the
judge already scored 1.00 or 0.50 on Arm F — the abstention was right, and is
now grounded in a retrieved record rather than in nothing. The dependent hop
still correctly stands down, because an anchor with no mappings contributes no
join values.

## 4. The loss that retrieval cannot reach

`EXP-2026-08-003` found 45% of Arm F's blind loss sitting on questions that
retrieved completely. `utils/evaluation/answer_gap.py` decomposes it:

| Class | Questions | Loss share of total | Ids |
|---|---|---|---|
| `under_enumeration` | 3 | **0.0883** | `H-ABS-01`, `H-CSQ-01`, `H-PRE-01` |
| `judge_nuance` | 19 | 0.0417 | spread thinly |

So "45% is answer shaping" resolves to **one named defect worth 0.0883**,
concentrated in three questions, plus small deductions elsewhere that are
presentation rather than bug. In all three the answer names the anchor and drops
the neighbours the query already returned — 1 of 4, 1 of 2, 1 of 3.

Classes are chosen by the **magnitude** of each observable deficit, not by a
fixed precedence. `H-PRE-01` carries a 0.1 faithfulness deduction alongside a
0.75 enumeration shortfall; a ladder ranking faithfulness first would file it
under the symptom and point the fix list at the wrong thing.

## 5. Threats to validity

* **No arm here is judged.** Every figure is retrieval. `1.0000` may not be
  printed beside Arm A's 0.689 or Arm F's 0.708. The `answer_gap` block reuses
  `EXP-2026-08-002`'s Arm F judgments and describes **Arm F**, not Arm H.
* **`gold_in_evidence` saturates, and is now saturated on both sets.** It has no
  remaining headroom and cannot distinguish a good answer from an over-broad
  one. Arm H's two deliberately over-returning primitives stay invisible to it.
  This metric has done its job and further work needs a judged measurement.
* **An outer join returns strictly more.** Precision was already the known cost
  of this arm; this change adds empty-mapping records to the evidence and can
  only increase what a narrator might over-state.
* **The templates still have the inner-join defect.** `capec_maps_to` and
  `cwe_chain` lose the same ids. Fixing them would break the byte-identical
  isolation test and make every arm figure in the 2026-07-26 study
  non-comparable, so it was deliberately not done — see `ISSUES.md`.
* **n = 30** on the blind set, single run, one model, seeds unrecorded.

## 6. What surprised us

That the development catalogue moved not at all. The same defect existed there —
966 vs 950 records shows unmapped anchors are now returned — but no gold
assertion in that catalogue ever required an anchor with an empty mapping. The
blind author wrote four such questions in thirty. That is the co-authoring
effect visible in miniature: the development set does not ask the question that
exposes the bug.

## 7. Follow-ups

1. **Judge Arm H** on both banks. Retrieval is saturated; every remaining
   question about this arm is a precision question, and precision needs a judge.
2. **Fix `under_enumeration` in the composer** — 3 questions, 0.0883, one defect:
   state the neighbours that were retrieved, not just the anchor.
3. **Decide on the templates.** The same outer-join fix applies to
   `capec_maps_to` and `cwe_chain`; the cost is arm-figure comparability.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin

uv run python -m utils.evaluation.experiment_untruncated --arm generic \
  --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/holdout-v1-generic-outer --workers 4
uv run python -m utils.evaluation.experiment_untruncated --arm generic \
  --root docs/evaluation/experiments/untruncated-generic-outer --workers 4

uv run python -m utils.evaluation.retrieval_coverage \
  --root docs/evaluation/experiments/holdout-v1-generic-outer --arm generic \
  --reference-root docs/evaluation/experiments/holdout-v1 --reference-arm gold_loop_llm
uv run python -m utils.evaluation.answer_gap \
  --root docs/evaluation/experiments/holdout-v1 --arm gold_loop_llm \
  --judgment-root docs/evaluation/experiments/holdout-v1 --judgment-arm gold_loop_llm
```

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — PROTOCOL.md was the blank scaffold; the commit field named the record commit

**What was wrong.** `PROTOCOL.md:1–52` was the unfilled template
(`# PROTOCOL — EXP-2026-08-004 <title>` and placeholder prose); this
experiment ran with no recorded protocol. It has been replaced by a
retrospective protocol, marked as such in its first line, reconstructed from
`docs/plans/arm-h-generic-primitives.md`, `manifest.yaml`'s hypothesis,
`EXP-2026-08-003` §4/§7, the six "Bridge outer join" commits and this file.
It records no prediction that was not already in the manifest.

`manifest.yaml:29` recorded `code.commit: 93da6d4…` ("(5/6): Development
catalogue shows no regression", 23:53), a record-side commit made after both
runs. The manifest's own `dirty:` comment names the run commits: the blind run
at `618bc20` (23:20; artifacts 23:28) and the development run at `1e8e16f`
(23:34; artifacts 23:51), both verified with `git cat-file -e`. **Old:**
`93da6d4…` → **new:** `618bc20e7faea6bcd12df553e442c447dcbdfff7`, the commit of
the run behind the primary metric; the development run's commit is named in
the comment beside it. `manifest.yaml:56` `llm.model` "local/skynet (Gemma 4
31B)@unknown" → `relay/gemma-4-31B@2026-08-10`, the format
`docs/evaluation/README.md` prescribes, as recorded at run time (the relay's
August repoint date is unknown).

## AMENDMENT A-2 (2026-09-09) — Both artifact directories gained judgment files on 2026-08-19; the answers are unchanged

**What was wrong.** `data/POINTERS.md:3–9` recorded the two run directories at
657 289 and 4 850 928 bytes with digests `e24f8d9e…` / `8e15ac27…` and stated
"No judgment files exist for either run". Since 2026-08-19 the blind directory
holds 30 `*.judgment.json` + 1 `*.judgment.error.txt` and the development
directory 120 + 1, written by `EXP-2026-08-007`, which judged Arm H on exactly
these outer-join artifacts (its POINTERS rows 38 and 40 point at
`…-outer/generic/answers`). The directories are now 683 755 and 4 953 549
bytes and hash differently.

**What is now correct.** On 2026-09-09 the §8 recipe restricted to
non-sidecar files (`find … -name '*.json' ! -name '*.judgment*'`) gives
exactly `e24f8d9e…` / 657 289 bytes and `8e15ac27…` / 4 850 928 bytes — **the
answer files are byte-identical to what was recorded**. Both rows are
re-recorded with the tree hash of the directory as it now stands
(`sha256:055240fd…`, `sha256:ba22ed41…`), the sidecars are named, and the
exclusion recipe is kept in the file. The B2 audit re-ran
`retrieval_coverage` (both sets, both pairings) and `answer_gap` over these
directories and reproduced every number in §2 and §4.

## AMENDMENT A-3 (2026-09-09) — Supersedes EXP-2026-08-003; the templates were fixed after all; Arm H has been judged

**Supersession.** `manifest.yaml` now records `supersedes: EXP-2026-08-003`:
this experiment replaced that one's blind headline (0.8952 → 1.0000) on the
same arm and bank the same day, which `EXP-2026-08-003`'s own amendment
already acknowledges. The reverse link is set there.

**Stale prose.**

* §5 fourth bullet and §7 item 3 ("The templates still have the inner-join
  defect … deliberately not done"; "Decide on the templates") and
  `ISSUES.md:3–17` ("Not fixed. This is an operator decision"): the decision
  was taken eight days later. `EXP-2026-08-006` (2026-08-18) ported the same
  outer join to `capec_maps_to` and `cwe_chain` on the default cascade and
  measured blind retrieval 0.8952 → 1.0000 there too, re-cutting the
  comparability baseline that this experiment declined to touch. Added to
  `related`.
* §5 first bullet, §7 item 1 ("Judge Arm H on both banks") and `ISSUES.md:26`
  ("Arm H has never been judged on either bank"): done. `EXP-2026-08-007`
  (2026-08-19) judged Arm H on these artifacts at **0.8483** blind (n = 30) and
  **0.9692** on the development catalogue (n = 120) — its manifest's
  `blind_correctness_generic` / `dev_correctness_generic` — against the
  repaired cascade's 0.8367 / 0.9839. The precision cost the saturated
  retrieval metric could not see (§5 second bullet) turned out not to
  separate the arms under a judge. Added to `related`.
* §7 item 2 (fix `under_enumeration` in the composer, 3 questions, 0.0883):
  addressed by the composer fix in `EXP-2026-08-008` (2026-08-19), by that
  experiment's title and scope; its figures are its own.

**Numbers here: unchanged.** 1.0000 / 1.0000, 4 improved / 0 regressed, 950 →
966 and 51 → 56 records, and the 0.0883 / 0.0417 decomposition stand as
measured on 2026-08-10.
