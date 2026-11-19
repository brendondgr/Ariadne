# RESULTS — EXP-2026-11-015 Era 2 Step 8: the tool catalog, generated from the card

## 1. Headline

**All four gates fail,** judged on T-lazy against the English hand-off (E) on one commit
(67607f55).
- **G1** synonym tier: 0.6167 against a bar of 0.80 (E 0.5500).
- **G2** empty retrievals: 56 against a bar of 25 (E 51).
- **G3** original wording: 0.5167 against a bar of 0.98 (E 0.6667).
- **G4** confidently wrong: 61 against E's 33 on the variants, and 12 against E's 1 on the dev
  bank.

**By the pre-registered decision rules, the typed hand-off does not ship** on the planned path.
- **What ships.** The catalog, coercion, error envelope and tools ship for the agent loop
  (E1–E5 pass).
- **What doesn't.** The planned path keeps the English hand-off.

**Two findings beside the verdict:**
- **The typed plan answers more of the hard paraphrases.** On T4 it gains +0.096 records_exact,
  interval [+0.010, +0.173]. On T5 it gains +0.164, interval [+0.096, +0.231].
- **Most of its new confidently-wrong answers on the dev bank come from one defect.** 11 of
  T-lazy's 12 are an anchorless whole-label scan. It is emitted when an anchor id cannot be
  resolved in the graph being asked.

## 2. Results table

Generated from `data/metrics.json` by `scripts/era2_catalog_score.py`. The full table is
`tables/scoreboard.md`.
- **One run per arm** (`n_runs: 1`). Every figure below is a single run, not a mean.
- **Intervals** are paired bootstraps against E: 2,000 resamples, seed 20261118. Variants are
  resampled with each gold question and its variants as one cluster.

### Gates (T-lazy against E)

| Gate | Bar | T-lazy | E | Pass |
|---|---|---|---|---|
| G1 synonym tier (T1 records_exact) | ≥ 0.80 | 0.6167 | 0.5500 | no |
| G2 empty retrievals (dev lost) | ≤ ⌊51 / 2⌋ = 25 | 56 | 51 | no |
| G2, reported: the old bar | ≤ 38 | 56 | | no |
| G3 original wording (T0 records_exact) | ≥ 0.98 | 0.5167 | 0.6667 | no |
| G4 confidently wrong, variants T0–T5 | ≤ E | 61 | 33 | no |
| G4 confidently wrong, dev | ≤ E | 12 | 1 | no |

### records_exact per tier

| Arm | T0 | T1 | T2 | T3 | T4 | T5 | T6 | CW T0–T5 |
|---|---|---|---|---|---|---|---|---|
| R (rules only) | — | 0.3917 | 0.3667 | 0.1782 | 0.0000 | 0.0000 | 0.0667 | 51 |
| E (English) | 0.6667 | 0.5500 | 0.5583 | 0.4257 | 0.1154 | 0.0385 | 0.0667 | 33 |
| T-lazy | 0.5167 | 0.6167 | 0.5000 | 0.5248 | 0.2115 | 0.2019 | 0.1000 | 61 |
| T-full | 0.5500 | 0.5750 | 0.5250 | 0.5446 | 0.2500 | 0.2308 | 0.1000 | 55 |
| T-lazy-G (Gemma) | 0.5500 | 0.6000 | 0.5167 | 0.6436 | 0.2788 | 0.2596 | 0.1000 | 37 |

### T-lazy minus E, paired

| Tier | Difference | Interval |
|---|---|---|
| T0 | −0.1500 | [−0.2500, −0.0583] |
| T1 | +0.0667 | [−0.0417, +0.1750] |
| T2 | −0.0583 | [−0.1583, +0.0500] |
| T3 | +0.0990 | [−0.0099, +0.1980] |
| T4 | +0.0962 | [+0.0096, +0.1731] |
| T5 | +0.1635 | [+0.0962, +0.2308] |
| CW T0–T5 (count) | +28 | [+9, +47] |
| dev lost (count) | +5 | [−11, +21] |
| dev CW (count) | +11 | [+4, +18] |

### Dev bank (284) against the authored plan

| Arm | lost | gained | both empty | confidently wrong |
|---|---|---|---|---|
| E | 51 | 1 | 8 | 1 |
| T-lazy | 56 | 0 | 9 | 12 |
| T-full | 49 | 0 | 9 | 7 |
| T-lazy-G | 60 | 0 | 9 | 7 |

E's lost count is 51, not EXP-2026-11-009's 45. Amendment 2 changed its token cap, thinking
budget and deadline, and amendment 1 gates on the measured figure.

### Typed-path health

| Arm | set | valid first | fixed by coercion | fixed by repair | still refused | catalog calls/q | prompt tokens/q |
|---|---|---|---|---|---|---|---|
| T-lazy | variants | 0.6366 | 0.2518 | 0.2446 | 0.1001 | 3.878 | 9,447 |
| T-lazy | dev | 0.7394 | 0.2570 | 0.1972 | 0.0493 | 3.933 | 9,813 |
| T-full | variants | 0.7282 | 0.2632 | 0.1903 | 0.0629 | 3.799 | 27,823 |
| T-full | dev | 0.7958 | 0.2465 | 0.1408 | 0.0563 | 3.743 | 30,588 |
| T-lazy-G | variants | 0.5665 | 0.2203 | 0.3104 | 0.1130 | 1.571 | 5,654 |
| T-lazy-G | dev | 0.6056 | 0.2887 | 0.2430 | 0.1514 | 1.261 | 5,762 |

**No harness errors.** Every variant row has `errors` 0, and every dev arm wrote 284 of 284
answers. The model identity was verified by token id before and after every arm: Qwen ended on
248046 and Gemma on 106 (`*.identity.json`).

## 3. Figures

None. The tables above carry every comparison.

## 4. Interpretation

### The verdict

The typed hand-off, as built, is not better than the English one on the planned path, and it
is more often confidently wrong. The decision rules settle it: G3 and G4 each block shipping
on their own.

### What the gates measured, and what they did not

**G3's bar could not be met by any language-model planner.**
- **What the reference is.** It is the rules pipeline's own capture of each gold question, so
  R's T0 is 1.0 by construction. The protocol's 0.98 carried that over.
- **What E scores.** The English control, the planner in use today, scores 0.6667 on the
  same 120 questions.
- **What T0 means for a model planner.** It measures how closely a planner reproduces the
  rules plan, not the original wording. The protocol named this threat in advance
  ("a typed arm can be right where the reference is wrong").
- **The relative reading still fails.** T-lazy is 0.15 below E, and the interval excludes 0.

**Where G3's paired loss comes from.** There are 27 T0 questions where E is exact and T-lazy is
not (`scripts/era2_catalog_score.py` diagnosis, with the per-question pairing in §6):
- **10 differ only by the anchor id.** The typed answer lists the anchor (for example the group
  G0016) beside its 17 techniques, and the reference leaves it out. This is a difference of
  form, not of retrieval.
- **4 are anchorless scans.**
- **13 are real retrieval differences.** Of these, 5 are refused or empty, 4 are supersets, 3
  are subsets and 1 is mixed.

With the anchor ids ignored, T-lazy's T0 is 0.6000 against E's 0.6667.

**G1 moved in the right direction, but not near the bar.** T-lazy beats E by +0.067 on T1, and
the interval includes 0. Rules-only R scores 0.3917.

**G2 is no different from E.** The difference is +5, interval [−11, +21]. The typed path
neither halves the empty retrievals nor adds to them.

### G4 has two causes

**1. The anchorless scan (a defect).**
- **What happens.** When the planner cannot resolve an anchor, it emits a `scan` step with no
  anchor ids. That step returns every member of the label: 222 techniques, 558 attack
  patterns or 261 CAPEC taxonomy entries.
- **When the anchor fails to resolve.** It happens in two situations:
  - **The id does not exist.** These are the A-NEG-01, A-EXC-01/02 and C-NEG-01 questions,
    which test that the system returns nothing.
  - **The id belongs to another graph.** An ATT&CK id asked against CAPEC, as in F-PART-01/02
    and the dev bank's D6 family, is stored there as a `TaxonomyEntry` id
    (`capec:taxonomy:ATTACK:…`).
- **What E does instead.** The English arm hands the raw id over, and the federated join
  resolves it.
- **How much of G4 it accounts for.**

  | Arm | anchorless-scan answers among confidently wrong: variants T0–T5 | dev |
  |---|---|---|
  | T-lazy | 16 of 61 | 11 of 12 |
  | T-full | 11 of 55 | 6 of 7 |
  | T-lazy-G | 6 of 37 | 5 of 7 |

- **Where the scan comes from.** Across all tiers there are 18 anchorless scans for T-lazy.
  - **9 follow the repair turn.** The anchor refusal's own `fix` text ends "or use kind
    \"scan\" for a whole label" (`utils/planner/typed.py:483`). All 6 of Gemma's follow the
    repair turn.
  - **The other 9 are first emissions.** In these, `resolve_entity` failed and the plan
    format offered no way to say "this entity is not in the graph".

**2. Answering what E abstains on (a trade, not a defect).**
- **Where it shows.** On T4 and T5, E abstains on 38 and 48 questions; T-lazy abstains on 15
  and 22.
- **What T-lazy does with them.** It turns these into 10 and 17 more exact answers, and into
  10 more confidently wrong answers on each tier.
- **What is left without the scans.** Even with every anchorless scan removed, T-lazy's
  variant count (45) is above E's (33). E's own count includes 12 catalogue dumps from its
  own path.

### Arms beside the gate

**T-full against T-lazy.**
- **G1.** T-full is lower on G1, 0.5750 against 0.6167, so the "load the whole card" rule
  (more than +0.05) does not fire.
- **Validity.** T-full is valid more often at first emission (0.73 against 0.64).
- **Cost.** It costs about three times the prompt tokens.

**Gemma (T-lazy-G).**
- **Same direction as Qwen on the tiers:** T0 0.55, T1 0.60, T3 0.64, T5 0.26.
- **Fewer confidently-wrong variant answers.** It has 37, which is +4 over E with an interval
  of [−12, +20]. It uses fewer catalog calls (1.6 per question) and more repairs.
- **It does not replicate a pass,** because there is none to replicate.

**R re-anchors at 0.3917, not 0.4667.**
- **It matches September exactly.** Today's rules-only T1 is 0.3917, the same as the
  2026-09-15 baseline capture (`docs/evaluation/variants-2026-09-15/scored_baseline.json`).
  The two reference captures are identical on all 120 questions.
- **Where 0.4667 comes from.** It is EXP-2026-08-020's August figure. The change happened
  between August and mid-September, before this step. CLAIMS C-014 still quotes 0.4667 (see
  ISSUES).

### Claims

No claim moves. The experiment was engineering for the era-2 agent, and `supports_claims` is
empty.

## 5. Threats to validity

- **One run per arm.** There is no repeat, so run-to-run spread is unmeasured. The paired
  intervals cover question sampling only.
- **Exact-set scoring against the rules capture.** `records_exact` penalises a typed answer
  that lists its anchor, and any answer that is right where the rules plan is wrong. The
  diagnosis separates the first case; the second needs a judge or gold sets, and neither was
  run.
- **Different engines in the two harnesses.** The variant arms run the template cascade with
  typed steps ahead of it. The dev arms run the generic engine (amendment 2, item 5). The two
  sets cannot be pooled.
- **The planner's catalog tools have no store** (amendment 2, item 6). `describe` of an id is
  refused, and `resolve_entity` answers from the entity index. A planner with store access
  could resolve cross-graph ids differently.
- **Step 9's operators are absent** (amendment 2, item 7). Questions that need set operations,
  aggregates or ranking become `unsupported` on the typed path. This lowers the typed arms'
  exact rate on those questions.
- **The diagnosis is post hoc.** The outcome classes, the anchor-insensitive score and the
  anchorless-scan counts were defined after seeing the results. They are reported and do not
  gate.
- **The T1 variants cover only ATT&CK, CAPEC and the federated pair.**

## 6. What surprised us

- **E scores 0.6667 on the original questions.** The planner in use today already differs from
  the rules plan on a third of the gold questions: 21 supersets, 12 refusals, 4 subsets and 3
  mixed. The variant set has been read as "1.0 on the originals", but that holds only for
  the rules pipeline.
- **The error envelope taught the wrong fix.** The refusal written to help the model recover
  ("or use kind scan") produced half of the dumps. A teaching error is part of the planner's
  prompt and needs the same care as the prompt.
- **A typed plan had no way to say "not found".** Questions built to test that the system
  returns nothing (T9999, retired techniques) became whole-label dumps. In English the same
  case falls through to an empty retrieval.
- **The gains are where E was weakest.** The typed plan helps most on the hardest paraphrases
  (T4, T5) and on T3, where E abstains. It hurts on the original wording, where E's English
  sub-question already names the relation.

Paired E-exact → typed-miss flips, by the typed answer's class (diagnosis code, recomputed from
the run files):

| Arm | tier | E exact, typed not | anchor only | anchorless scan | refused/empty | superset | subset | mixed | typed exact, E not |
|---|---|---|---|---|---|---|---|---|---|
| T-lazy | T0 | 27 | 10 | 4 | 5 | 4 | 3 | 1 | 9 |
| T-lazy | T1 | 17 | 1 | 1 | 4 | 10 | 0 | 1 | 25 |
| T-full | T0 | 28 | 8 | 2 | 1 | 11 | 3 | 3 | 14 |
| T-lazy-G | T0 | 26 | 7 | 1 | 8 | 6 | 3 | 1 | 12 |

## 7. Decision rules applied

| Rule (PROTOCOL) | Condition | Applies | Consequence |
|---|---|---|---|
| All of G1–G4 pass | — | no | — |
| G1 or G2 fails while E1–E5 pass | G1 and G2 fail; E1–E5 pass | **yes** | The catalog ships for the agent loop. The planned path keeps the English hand-off. The failures are diagnosed per question (§4, §6), and the plan is revised before Step 9. |
| G3 fails | 0.5167 < 0.98 | **yes** | The typed path does not ship on the planned path. |
| G4 fails | 61 > 33 and 12 > 1 | **yes** | It does not ship, whatever G1–G3 say. |
| T-full beats T-lazy on G1 by > 0.05 | −0.0417 | no | The prompt stays names-only. |

**What stays in the tree.** The typed planner mode stays in the tree, off by default. A
`SubQuestion` with no `step` gives the same plan JSON and answers as before (E5).

**What the plan revision before Step 9 should address** (the operator decides; recorded in
the private plan §9):
1. **Remove the scan hint** from the anchor refusal's `fix`.
2. **Add a typed "not found" outcome.** A written id that `resolve_entity` cannot find gives
   an empty, explained answer, not a refusal or a scan.
3. **Resolve cross-graph anchor ids through the declared join** (ATT&CK id to CAPEC
   `TaxonomyEntry`), or route the step to the anchor's own graph.
4. **Refuse a scan** whose label is larger than the view cap unless the plan says so
   explicitly.
5. **Re-gate G3 against E, or against judged gold,** not against the rules capture, and score
   with the anchor ids excluded. Either change is a new protocol, not an amendment of this
   one.

## 8. Phase 1 engineering checks (E1–E5), on 67607f55 and its parent a695b869

| Check | Result | Pass |
|---|---|---|
| **E1** text boundary (`utils/specialists/tests/test_typed_boundary.py`) | 120 of 120 identical with nonsense text | yes |
| **E2** catalog generation (`utils/agent/tests/test_catalog.py`) | 13 cards (ATT&CK, CAPEC, 11 CypherBench); 364 parameter schemas valid under Draft 2020-12; enums equal the card's sets; no graph or label names in `utils/agent/`. 6 cards skipped, stores not loaded (ISSUES) | yes |
| **E3** error contract (`utils/agent/tests/test_error_fuzz.py`) | 1,000 of 1,000 refusals carry a `fix` naming a valid option | yes |
| **E4** coercion (`utils/agent/tests/test_coerce.py`) | kill-test replay: 6 fixed, 0 fixed wrongly | yes |
| **E5** recorded answers (`data/phase1/run_arms.sh`, `diff_arms.py`) | 30/30, 30/30, 284/284 identical against a same-tree baseline (`data/phase1/e5-phase1-final-diff.json`) | yes |
| Test suite | 1,607 passed, 21 skipped | — |

**Commands:**

```bash
uv run pytest -q utils/specialists/tests/test_typed_boundary.py utils/agent/tests
bash docs/research/experiments/EXP-2026-11-015-era2-tool-catalog/data/phase1/run_arms.sh <out>
uv run python docs/research/experiments/EXP-2026-11-015-era2-tool-catalog/data/phase1/diff_arms.py <before> <after>
uv run python scripts/era2_catalog_score.py --data docs/research/experiments/EXP-2026-11-015-era2-tool-catalog/data \
    --runs docs/evaluation/experiments/tool-catalog-2026-11-18
```

**Phase 2 ran unattended** in 2.77 hours (20:56 to 23:42 EST, 2026-11-18). The chain was
`logs/phase2.sh` (gitignored). Qwen and Gemma ran at the same time, at 16 concurrent requests
each. The rules-only reference was captured twice, and the two captures were byte-identical.
