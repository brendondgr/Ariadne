# Self-verification — overnight pass, Plan 01

Written after Tasks 1–11. Everything here is checked against files, not against
the run log or the plan.

## 0. Do the independent re-derivations agree?

**Yes — all three, exactly.** Task 12 requires re-deriving three figures from the
raw files rather than from `numbers.json`, and saying so prominently if any
disagrees. None does.

Each was recomputed with a *different* method from the one that produced
`numbers.json` — plain `grep` over the raw file text instead of the JSON/AST
parsers — so the check is not the same code run twice.

| Figure | `numbers.json` says | Re-derived | Method | Agree |
|---|---|---|---|---|
| Arm G mean correctness | 0.638833 | 0.6388333… (sum 76.66 over n=120) | `grep '"correctness"'` across the 120 judgment files, averaged | ✅ |
| Arm A evidence records | 1,061 | 1,061 over 120 answer files | `grep -A3 '"evidence_volume"'` → `"records"`, summed | ✅ |
| Distinct template identifiers | 25 (17 Cypher + 11 Gremlin, 3 shared) | 25 (17 + 11) | `grep -o 'template="…"' \| sort -u \| wc -l`, no AST | ✅ |
| Templates exercised by the bank | 19 | 19 | regex over `expected_template` in the three banks, intersected with the literal set | ✅ |

The `expected_template` scan turns up one value that is not a builder template:
`boundary_refusal`. It is a sentinel for the abstention path, not a query
template, and is excluded from the 19 in both derivations.

---

## 1. Every number changed

Old value → new value, and the file the new value came from. Nothing here was
carried forward from prose.

### Arm A cost (Task 6)

| Location | Was | Now | Derived from |
|---|---|---|---|
| `README.md` results table | 2.6 s | **1.6 s** | `untruncated-fixed/deterministic/manifest.json` → `wall_s` |
| `docs/evaluation/2026-07-26/README.md` cost table | 2.6 s / 1,840 records | **1.6 s / 1,061** | same manifest; records summed over the 120 answer files' `evidence_volume.records` |
| `docs/evaluation/2026-07-26/README.md` §5 | 2.6 s | **1.6 s** | same |
| `docs/pitch/checkin-pitch.md` | "2.6 seconds" | **"1.6 seconds"** | same |
| `docs/research/audit-2026-08-03.md` C1 | 2.6 s | dated note giving **1.6 s / 1,061** | same |
| `docs/research/audit-2026-08-03.md` G10 | 392× | dated note giving **637×** | 1,019.7 / 1.6 = 637.31 |

Speedup arithmetic, shown rather than asserted:

```
pre-fix    1,019.7 s (Arm B) / 2.6 s = 392.19   the recorded 392x
post-fix   1,019.7 s (Arm B) / 1.6 s = 637.31   637x
Arm F        533.4 s          / 1.6 s = 333.37   333x
```

Arm A's related-neighbour count (839) and coverage (1.0000) are byte-identical
between the pre- and post-fix runs, as the plan states, so nothing else in that
row moved.

### Coverage cells (Task 6, beyond the plan's list — see Q7)

| Location | Was | Now | Derived from |
|---|---|---|---|
| Cost table, Arm B coverage | 0.7989 | **0.8074** | `untruncated-fixed/llm` answers; 0.7989 is the pre-fix `untruncated/llm` value |
| Cost table, Arm E coverage | — (blank) | **0.8819** | `untruncated-loop2/llm_loop` answers |

Both are macro means over the 66 scorable cases, matching the repository's own
aggregation in `utils/evaluation/summarize_untruncated.py:81,99`.

### Arm G, newly reported (Task 5)

Every cell derived from the 120 judgment files, the 120 answer files, and
`manifest.json` in `untruncated-generic/generic/`.

| Metric | Value |
|---|---|
| correctness | 0.6388 |
| completeness | 0.6802 |
| faithfulness | 0.9658 |
| groundedness | 0.9788 |
| C/P/I | 64 / 14 / 42 |
| hallucinations | 7, in 7 cases |
| wall clock | 915 s (`wall_s` 914.8) |
| evidence records | 252 |
| related | 1,749 |
| answer coverage | 0.8979 |

### Deltas (Task 5)

| Delta | Value | Arithmetic |
|---|---|---|
| G − F | **−0.3568** | 0.638833 − 0.995667 = −0.356834 |
| B − C | **−0.1185** | 0.850500 − 0.969000 = −0.118500 |
| Ratio | **3.01×** | 0.356834 / 0.118500 |

The plan labels the first "F − G (−0.357)". F − G is **+0.356834**; the quoted
sign is G − F. Recorded as Q6; the tables print G − F so both deltas read in the
same direction.

### Template count (Task 7)

| Location | Was | Now |
|---|---|---|
| `README.md:39` | 16 Cypher + 11 Gremlin | **25 distinct, 19 exercised** |
| `README.md:186` | "19 of the 24 distinct query templates" | **25 distinct** |
| `docs/evaluation/README.md` | "the 24 query templates" | **25 distinct** |
| `docs/evaluation/2026-07-26/portability.md:72` | "24 total" | **25 distinct, 19 exercised, 19 MITRE-specific** |
| `docs/evaluation/2026-07-26/portability.md:73` | generic templates: 5 | **6** (adds `generic_neighbors`) |
| `docs/research/audit-2026-08-03.md:22` | 17 + 11, implying 28 | dated clarification: **25 distinct** |
| `utils/specialists/cypher/builder.py` | "fifteen intent templates" | **seventeen declared, fifteen reachable from `build()`** |
| `utils/specialists/gremlin/builder.py` | 5-step order naming two dead templates | the actual 6-branch cascade |

The old 24 and 16 were *correct before Arm G landed*: `generic_neighbors` is the
17th Cypher template and was uncommitted until commit 1/12. The 28 came from
adding the two per-builder counts without noticing that `describe`,
`describe_by_name` and `expand` are declared in both.

### Judge-agent count (Task 5)

"840 agents across seven runs" → "840 across the seven study runs, plus 120 for
the Arm G control run added afterwards". 7 × 120 = 840; Arm G adds one more arm
of 120.

### Model and context window (Task 10)

| Location | Was | Now |
|---|---|---|
| `docs/evaluation/README.md` | model unnamed | **Gemma 4 31B**; quantisation and window recorded as **unknown** |
| `docs/evaluation/2026-07-26/README.md` limitations | "skynet's 64k window" | "the served window", with a dated note that 64k was an unverified estimate |
| `docs/plans/answer-truncation-fix-plan.md:51` | "unknown from the client side" | unchanged, with a dated line confirming it is still the settled reading |
| `.env:139,159` (`48000`) | — | **not modified** — gitignored operator state, prohibited by the plan. Described in the record instead. |

### `.env.example` (Task 9)

| Key | Was | Now |
|---|---|---|
| `ORCH_MAX_HOPS` | absent (code default 5) | **1**, with both values documented in a comment |
| `EVAL_LLM_MAX_TOKENS` | 1024 | **32000**, matching what the evaluations used |
| pipeline comment | "probe → plan → specialists → bundle → synthesize" | the real graph including `bundle → assess → (synthesize \| replan → specialists)`, plus the two inertness caveats |

---

## 2. Is the freeze clean?

```
$ git diff freeze/holdout-v1 -- utils/specialists/
(no output — 0 lines)
```

**Nothing has changed under `utils/specialists/` since the tag.** The tag is the
last substantive commit, so this is the expected state and the strongest form of
the check the morning review asks for.

The more informative check is what happened to `utils/specialists/` *between the
session's starting commit and the tag*, which splits cleanly in two:

| Range | Files | What |
|---|---|---|
| `45ac6e5 → a509f63` (Task 1) | `cypher/builder.py`, `cypher/normalizer.py`, `gremlin/builder.py` | The Arm G code, committed **exactly as found on disk**. Not authored here; not edited in that commit. |
| `a509f63 → freeze/holdout-v1` (Task 8) | `cypher/builder.py`, `gremlin/builder.py` — 42 insertions, 14 deletions | **Docstrings and comments only.** |

The Task 8 range was verified mechanically, not by reading the diff: both files
were parsed before and after, every docstring stripped from the AST, and
`ast.dump()` compared. Both compare **identical**. No statement, expression or
signature moved.

---

## 3. Test suite

Same invocation every time: `ORCH_MAX_HOPS=5 .venv/bin/python -m pytest -q`.
`ORCH_MAX_HOPS` is passed explicitly because the repository `.env` pins it to 1,
under which an unrelated orchestration event-order test fails.

| When | failed | passed | skipped |
|---|---|---|---|
| Baseline (before Task 8) | 4 | 1308 | 213 |
| After Task 8 (docstrings) | 4 | 1308 | 213 |
| After Task 9 (`.env.example`) | 4 | 1308 | 213 |

The same four tests fail in all three runs, and none is related to this work:

- `utils/conversation/tests/test_graph.py::test_graph_path_llm_off_default_order`
- `utils/conversation/tests/test_graph.py::test_graph_path_anchors_entity_free_followup_with_llm_off`
- `utils/evaluation/tests/test_score_e2e.py::test_score_e2e_live_subset`
- `utils/setup_wizard/tests/test_steps.py::test_inference_step_run_disable_keeps_deterministic`

Three of the four assert LLM-off behaviour while a local inference server is
reachable on `localhost:4000`; the fourth needs the live graph subset. All four
fail identically on the session's starting tree.

The documentation-accuracy regression test
(`utils/specialists/tests/test_docs_contracts.py`, 9 tests) passes after every
documentation change made here.

---

## 4. Files touched

245 files in Task 1 (241 of them Arm G artifacts) plus 24 others. Excluding the
Arm G artifact directory:

```
 .env.example                                       |  57 +-
 NOTICE                                             | 113 +   (new)
 README.md                                          |  15 +-
 docs/evaluation/2026-07-26/README.md               |  67 +-
 docs/evaluation/2026-07-26/portability.md          |  15 +-
 docs/evaluation/README.md                          |  35 +-
 docs/evaluation/experiments/README.md              |  33 +-
 docs/pitch/checkin-pitch.md                        | 278 +   (newly tracked)
 docs/plans/answer-truncation-fix-plan.md           |   3 +
 docs/plans/branch-a-publication-readiness-plan.md  | 670 +   (newly tracked)
 docs/plans/robustness/*.md                         |         (newly tracked)
 docs/plans/robustness/_overnight/*                 |         (new — this audit trail)
 docs/research/audit-2026-08-03.md                  |  30 +-
 utils/evaluation/experiment_untruncated.py         |  13 +-
 utils/specialists/cypher/builder.py                |  98 +-
 utils/specialists/cypher/normalizer.py             |  64 +
 utils/specialists/gremlin/builder.py               |  53 +-
```

plus `docs/evaluation/experiments/untruncated-generic/` — 241 files.

**Not touched, deliberately:** `.env`; anything under
`utils/specialists/tests/golden/` or `utils/specialists/evalset/`; the
`.gitignore` hunk (Q1); `_node_lookup` and `_capec_lookup`, which are marked and
kept.

### Prohibitions, checked

| Prohibition | Status |
|---|---|
| No behavioural change under `utils/specialists/` | ✅ Task 1 committed existing changes verbatim; Task 8 verified AST-identical |
| Question banks untouched | ✅ no file under `tests/golden/` or `evalset/` appears in any diff |
| Dead code marked, not deleted | ✅ both methods present, both commented |
| No experiment, arm or evaluation run | ✅ nothing under `*/answers/` or `*/judgment*` was written; Task 4 only read |
| `.env` not modified | ✅ |
| No `git push` | ✅ 12 overnight commits sit local, ahead of `origin/main` (which is also behind by 7 pre-existing commits) |
| No history rewrite | ✅ no rebase, amend or force |
| No `LICENSE` file, no `license` field | ✅ `ls LICENSE*` finds nothing; neither `pyproject.toml` nor `web/package.json` gained the field |
| Related work / holdout / pitch not written | ✅ Plans 02 and 04 untouched except the freeze SHA in 02 §2, which Task 11 requires |

---

## 5. Commits

| # | SHA | Subject |
|---|---|---|
| 0 | `ed9ce8d` | Track the robustness plans and open the overnight audit trail |
| 1 | `a509f63` | Commit the Arm G generic-only control code path and its 120-case artifacts |
| 2 | `a9e514f` | Track `docs/pitch/` |
| 3 | `7cbc7c0` | Add the MITRE ATT&CK and CAPEC attribution notice |
| 4 | `1f98e1a` | Recompute all arm statistics from the committed judgment files |
| 5 | `feb9298` | Report Arm G in both arm tables with the F−G delta |
| 6 | `a38f424` | Correct the Arm A cost figures and the derived speedup to 637× |
| 7 | `f87d145` | Reconcile the template count across all five locations |
| 8 | `3e3ebab` | Correct the stale template docstrings in both builders |
| 9 | `fa26268` | Close the `.env.example` divergences and correct the pipeline comment |
| 10 | `974e85a` | Record the evaluation model as Gemma 4 31B |
| 11 | `623a047` | Tag `freeze/holdout-v1` ahead of the blind holdout |

**`freeze/holdout-v1` → `974e85a494f020e218e8b73f193543c11ea0d292`**

---

## 6. Open questions, restated

Full text in [`questions.md`](questions.md). Nothing below was decided here.

| # | Question | Why it needs a human |
|---|---|---|
| **Q1** | An uncommitted `.gitignore` hunk adds `docs/evaluation/experiments`, which would have hidden the Arm G artifacts. Left uncommitted; artifacts committed. | Whether new experiment output should be ignored is a policy call, and 2,657 files there are already tracked |
| **Q2** | `cypher/normalizer.py` was a fourth modified file the plan did not list. Judged part of the generic-only gating and committed with it. | If that reading is wrong, the Arm G commit needs splitting before the freeze is trusted |
| **Q3** | The local model's **quantisation** is unknown. | Only the operator knows; it is a property of the serving stack, not the repo |
| **Q4** | The local model's **served context window** is unknown; three inconsistent figures exist and none is authoritative. | Needs reading off the model server |
| **Q5** | `checkin-pitch.md` was committed verbatim (Task 2) then corrected (Task 6). | Whether a pitch document should be corrected in place or annotated is the author's call |
| **Q6** | The plan's "F − G delta (−0.357)" is signed as G − F. | Sign convention; magnitude is confirmed either way |
| **Q7** | Arm B's coverage cell was spliced from the pre-fix run too — a wider splice than the plan assumed. | Worth knowing before quoting any other post-fix figure |
| **Q8** | `.env.example` now pins `ORCH_MAX_HOPS=1`, so a fresh clone defaults to single-pass. | That is a shipping-default decision |
| **Q9** | A latent test-isolation bug in the setup-wizard tests, exposed by Q8's key. Full suite unaffected. | Fixing it is a code change, out of scope here |

**Read Q1 and Q2 first.** They are the two that touch the freeze.
