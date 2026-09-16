# ISSUES — EXP-2026-09-023

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## 2026-09-15 — Step 0 numbers were first computed outside the record
**Impact:** none on the values; `data/shipped_vs_prototype.py` and
`data/exact_name_probe.py` re-derive them from hash-pinned inputs and the two
agree to four decimals with the scratchpad run that the 2026-09-15 review of
`EXP-2026-09-022` reported in chat.
**Cause:** the review was a reading of another experiment, not an experiment,
and its probes were run in a scratchpad before this folder existed.
**Resolution:** entered here as Step 0, labelled as motivation rather than
result. The reranker half of that review (bge-small over the shipped top 25)
is **not** entered here; it belongs to plan Step 9's experiment.
**Paper implication:** none.

## 2026-09-15 — H1's threshold was seen on the exposed bank
**Impact:** the 1 % document-frequency cut in H1 is a value read off the exposed
bank during the review, so the exposed-bank H1 figures are confirmation of a
fit, not a test. The sealed bank is the test.
**Cause:** the review measured four candidate thresholds (0.5 %, 1 %, 2 %, 5 %)
to see whether *any* rule separated gold from incidental binds.
**Resolution:** the value is fixed in `PROTOCOL.md` before the sealed bank is
opened; if it must move to pass there, H1 is recorded as failed.
**Paper implication:** the rule's generality claim rests on the sealed bank and
on the non-cyber fixture tests, not on the exposed-bank numbers.

## 2026-09-15 — H1 (the 1 % document-frequency rule) falsified at the probe level; AMENDMENT A-1 designed with both banks visible
**Impact:** the shipped distinctiveness rule is not the pre-registered one.
`ARIADNE_EXACT_NAME_DISTINCT=df` reproduces H1 and is never shipped;
`=1` selects A-1.
**Cause:** `data/exact_name_probe.py --arm df` on the sealed bank lost the T3
gold bind on "Hardware" (1 of 40, above the 2 % line), reduced T4/T5 wrong
binds by only 36 % / 43 % (below 60 %) and left 5 T6 binds (above 2); on the
exposed bank it also dropped "Phishing" and "APT29" — common words that are
*also* the names analysts use — and could not see the tool named "at", whose
two-letter name the tokenizer never indexes. The review's 60/60 figure only
counted T3 questions that bound uniquely; the Phishing questions were in the
ambiguous row and were never checked for survival.
**Resolution:** A-1 replaces the frequency cut with a structural test — a
one-word name is a lookup only when the question writes it as a standalone
proper noun (same casing, whole word, not inside a longer capitalised run
after the sentence-initial word, at least one indexable token). No numeric
threshold. It was designed after the probe had been run on **both** banks, so
its probe-level sealed figures are not a blind confirmation; the harness-level
figures (`scored_distinct.json` on the sealed bank) are the first measurement
of it that was not visible during design. Step 10's judged pass and any future
bank are the real confirmation.
**Paper implication:** the exact-name rule must be described as structural
(proper-noun writing), not statistical, and its sealed-bank probe numbers must
carry this caveat.

## 2026-09-15 — the first exposed-bank run of A-1 (`scored_distinct.json`) is contaminated by timeouts and superseded
**Impact:** `docs/evaluation/variants-2026-09-15/scored_distinct.json` (A-1 alone,
no dump guard) shows T3 `records_exact` 0.3069 and `abstained` 0.4257 against the
shipped 0.3267 / 0.3564. Ten of its T3 rows carry `latency_s` 129–179, no
executed query and no abstention statement — the rewrite model call exceeded
the harness's default per-question budget and the row scored as an empty
answer. Those rows had rewrite-cache hits in the shipped arm and none here.
The sealed-bank runs of the same arm have no such row (max latency 87 s).
**Cause:** the run was launched without `--llm-timeout-s 600
--pipeline-timeout-s 600`, the settings EXP-2026-09-021 established for
32-way concurrency (its I-1 / EXP-2026-09-014 record the same failure).
**Resolution:** the file is kept on disk and not pointed to; the `hygiene` and
`anchor_first` arms are run with the 600 s budgets and are the arms reported.
A-1-alone on the exposed bank is therefore measured only through the
`hygiene` arm (A-1 plus the unanchored-relation guard). The sealed
`scored_distinct.json` is valid and is kept as the A-1-alone reading there.
**Paper implication:** none beyond the reporting rule already in EXP-2026-09-021:
a harness figure is only quotable with its timeout settings.

## 2026-09-15 — A-1 unmasked two downstream defects on the sealed bank
**Impact:** interpretation of the `distinct` (A-1 alone) sealed rows.
**Cause:** with the false single-word anchor gone, (a) three T3 questions now
*reach* the rewrite stage's deterministic rung, which renders a describe or a
wrong card-vocabulary relation ("attributed to Tonto Team" → ATTRIBUTED_TO)
for a question the template path was answering correctly — the render
round-trip defect plan Steps 5–6 address; and (b) T4/T5 questions fell
through to seedless relation templates that scan the catalogue (558 CAPEC
rows, 222 tactic→technique rows), so `catalogue_dump` rose from 0.225/0.350
to 0.275/0.475 while `wrong_entity` fell.
**Resolution:** (b) is closed in this step by the unanchored-relation guard
(`ARIADNE_UNANCHORED_RELATION_ABSTAINS`, in the `hygiene` arm). (a) is
recorded here and left for Steps 5–6; it costs 0.05 T3 `records_exact` on the
sealed bank in exchange for `wrong_entity` 0.025 → 0.
**Paper implication:** the exact-name rule's value is in `wrong_entity`, and
its T3 cost is a rendering defect it exposes, not a binding it loses.

## 2026-09-15 — arms were run from the working tree, then committed without change
**Impact:** `code.commit: a0888b33` with `dirty: true`.
**Cause:** the harness arms ran while the Step 3 and Step 4 changes were
uncommitted, so no commit hash existed at run time.
**Resolution:** the two commits (`e055e2bb`, `a0888b33`) captured the tree
that ran; no source file changed between the runs and the commits (only
record files under this folder). The pointers' hashes tie each scored file to
its arm.
**Paper implication:** none.

## 2026-09-15 — a pre-existing, unrelated test failure on the untouched tree
**Impact:** none on this experiment.
**Cause:** `utils/specialists/tests/test_llm_builder.py::test_no_other_arm_turns_the_query_builder_on`
fails on the tree before any of this experiment's changes (verified by
stashing them); it reads the ambient environment, which is the D-029
import-time `.env` leak this repository already records.
**Resolution:** not touched here; every other suite under `utils/specialists`,
`utils/planner` and `utils/orchestration` passes.
**Paper implication:** none.
