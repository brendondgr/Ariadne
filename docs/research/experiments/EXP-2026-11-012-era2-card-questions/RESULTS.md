# RESULTS — EXP-2026-11-012 Era 2 Step 6: questions with gold answers, generated from a card alone

## 1. Headline

**Every gate passes on the fourth recorded run**: 837 questions from the ATT&CK and CAPEC cards
alone.

| Gate | Result |
|---|---|
| G1, every gold answer re-executes identically through a second fetch path | 483 / 483 (ATT&CK) and 354 / 354 (CAPEC), every ambiguous reading included |
| G2, tuning and held-out share no anchor | 0 shared, over both datasets together |
| G3, leak audit on the synonym and schema tiers | 0 of 232 |
| G4, fixture tests | 18 of 18 pass |

**Three earlier runs were not kept.** Each was stopped by a defect that its own checks
surfaced (PROTOCOL amendments 1–3, ISSUES).

- **Run 1: CAPEC relation names (void).** Every CAPEC hierarchy question was silently labelled
  "insufficient". The cause was a mismatch between the card's relation names and the
  store's edge labels.
- **Run 2: ambiguity budget.** It produced 8 and 1 ambiguous questions, where 16 each were
  budgeted.
- **Run 3: id-format hints.** Id formats such as "T-ID.NNN" leaked into the schema tier.

**The scored banks are Sonnet-worded (PROTOCOL amendments 5–7, §8).** The operator chose a
second writer, so the agent is not scored on questions its own planner model wrote (Q61).

- **What was rewritten:** all 805 model-written questions, by Claude Sonnet 5.5. No question
  was dropped.
- **What stayed the same:** ids, anchors, gold and splits.
- **Gates:** they pass again.
- **Fluency:** a blind Opus read finds 47 of 50 fluent and 10 of 10 ambiguous questions truly
  ambiguous.
- **Banks:** later steps score on `card-sonnet-2026-11-16-*`. The Qwen-worded `card-2026-11-16-*`
  banks stay as the paired comparison.

## 2. Results table

From `data/metrics.json` and `data/card_bank.json`. This is one run. The anchors, splits and
choices are seeded (20261116); the writer is not, so survivor counts move by a question or two
between runs (ISSUES).

| Kind | ATT&CK | CAPEC |
|---|---:|---:|
| answerable | 433 | 310 |
| insufficient (empty by construction, diagnosed) | 24 | 24 |
| ambiguous (with a gold clarification) | 14 (entity) | 8 (relation) |
| out of coverage | 12 | 12 |
| **total** | **483** | **354** |
| tuning / held-out | 228 / 255 | 205 / 149 |

| Rewording tier: kept / attempted (yield) | ATT&CK | CAPEC |
|---|---:|---:|
| identifier | 75 / 75 (1.00) | 57 / 57 (1.00) |
| name | 75 / 75 (1.00) | 57 / 57 (1.00) |
| reworded name | 75 / 75 (1.00) | 57 / 57 (1.00) |
| description | 69 / 75 (0.92) | 46 / 57 (0.81) |
| paraphrased schema | 75 / 75 (1.00) | 57 / 57 (1.00) |
| synonym relation | 64 / 75 (0.85) | 36 / 57 (0.63) |

- **Description-tier drops:** mostly anchors without a usable description (6 for ATT&CK, 10 for
  CAPEC), plus 1 CAPEC leak.
- **Synonym-tier drops:** questions that still leaked after one retry.

**Twelve banks**, one per dataset × decision step × split, under
`docs/evaluation/banks/card-2026-11-16-*`. They are hashed in `data/POINTERS.md`, and the
held-out banks are sealed.

| Decision step | ATT&CK tuning / held-out | CAPEC tuning / held-out |
|---|---:|---:|
| grounding (identifier, name, reworded, description tiers) | 138 / 156 | 130 / 87 |
| relation choice (synonym, schema tiers) | 63 / 76 | 53 / 40 |
| exit (ambiguous, out of coverage, insufficient) | 27 / 23 | 22 / 22 |

**Expectations:**

- **E1, yield: met.** The identifier, name and schema tiers keep everything (1.00), and the
  synonym tier is lower. CAPEC's synonym yield is lowest (0.63), as the dry run predicted: its
  relations carry long paraphrase lists, which forbid most everyday verbs.
- **E2, fluency (Qwen-worded sheet): met by the proxy.** The blind proxy reader
  (Claude Sonnet 5.5, not a person) found:
  - 50 of 50 sampled questions fluent;
  - 10 of 10 ambiguous ones truly ambiguous.

  That is above the 70–90% band expected, on a sample of 10. No ambiguous question was
  rejected, so none was dropped from the clarification sets. The person read the scored,
  Sonnet-worded sheet instead (§8).
- **E3, sizes: ATT&CK met (483 against about 450); CAPEC above (354 against about 220).** The
  CAPEC estimate came from the dry run, which carried the relation-name defect: there, every
  hierarchy slot was empty. Ambiguous questions fell short of the 16 budgeted, at 14 and 8:
  - **ATT&CK:** its card has no two relations joining the same pair of labels, so all its
    ambiguity is by shared name. Its same-split shared names (at least 4 characters) ran out
    at 14.
  - **CAPEC:** its names are all distinct, and only one label pair has several relations, so
    its 8 are all relation ambiguity.

## 3. Figures

None.

## 4. Interpretation

Era 2 now has evaluation questions whose gold comes from the card and the graph, not from a
person's authoring.

- **What it covers:** every rewording tier, including the synonym tier where era 1 was weakest,
  and the three exit kinds that Steps 10–12 need: ask (ambiguous), cannot (out of coverage) and
  nothing there (insufficient).
- **Where they go:** the banks are split by decision step, so tuning a step never sees its
  held-out anchors.
- **What it does not show:** that an agent scoring well on these banks answers people's
  questions. That depends on Q61 (the writer is the agent's own model) and on the person's
  read.

**The relation-name defect matters beyond this step.** Any era-2 component that walks
Ariadne's CAPEC Gremlin store by card names must use the loader's edge-label map. Otherwise
every CAPEC hierarchy question comes back empty, and with an honest-looking "nothing there".

## 5. Threats to validity

- **Writer = planner model (Q61).** The questions are worded by Qwen 3.8 27B, the model era 2's
  agent will plan with. Rewording difficulty may be understated.
- **Small gold sets.** 383 of 743 answerable questions have one answer, and the largest has 46.
  Large-set enumeration is covered by Step 5's hubs, not by these banks.
- **Fifty questions were read, 10 of them ambiguous.** Both the person's read and the proxies'
  reads cover the same small samples.
- **The phrasing is expert phrasing.** In the operator's judgement, the questions read like those
  of a seasoned cybersecurity specialist. The banks therefore test expert-style wording, not a
  novice's loose or misspelled questions.
- **Out-of-coverage assumes Step 9's catalogue.** The four missing operators (path search,
  temporal trend, median, similarity) are assumed absent from Step 9's retrieval operators. If
  Step 9 adds one, its questions must move to answerable.
- **"Insufficient" means empty in the graph today.** Several are diagnosed `relation_absent` at
  that anchor, which a later data release could fill. The banks are tied to today's graphs.
- **G1 checks consistency, not vocabulary.** Run 1 showed that both fetch paths can share one
  wrong relation name. The absent-slot guard now covers that case: every card slot has at least
  one edge in the store.

## 6. What surprised us

- **The one defect that mattered was invisible to every gate.** G1 passed, the leak audit
  passed, the split check passed, and still every CAPEC hierarchy question had the wrong gold.
  It surfaced only when asked why one kind came out empty, and the vocabulary leak only when a
  reader stumbled on one question.
- **The ATT&CK card offers no relation ambiguity.** Every label pair has at most one relation,
  so "ask which link you mean" never arises there; only name collisions do.

## 7. Follow-ups

- **Q61:** re-word a held-out sample with a different writer and report the gap.
- **The person's read: done** (§8). It rejected nothing, so the clarification sets keep all 10
  sampled ambiguous questions.

## 8. The second writer: Sonnet-worded banks (amendments 5–7)

From `data/sonnet/metrics.json` and `data/sonnet/card_bank.json`.

| Gate or measure | ATT&CK | CAPEC |
|---|---:|---:|
| G1, gold re-executes through the keyset path | 483 / 483 | 354 / 354 |
| G2, anchors shared between splits | 0 | 0 |
| G3, leak audit (synonym and schema tiers, joined-label stems included) | 0 | 0 |
| G4, fixture tests | 21 of 21 pass | |
| questions rewritten / dropped | 471 / 0 | 334 / 0 |
| failed the first check, passed on the one retry | 6 | 4 |
| template questions, rendered in plain words | 12 | 20 |

**Paired wording, over the 805 rewritten questions:**

| | Qwen 3.8 27B (run 4) | Claude Sonnet 5.5 (round 2) |
|---|---:|---:|
| names the asked-for kind by its exact schema label ("DetectionStrategy entries") | 237 | 0 |
| median length, in words | 9 | 8 |
| identical text | 56 (both writers) | |

**E2, the blind proxy read (Claude Opus 5.5, not the writer's model, not a person):**
- 47 of 50 fluent; 10 of 10 ambiguous questions truly ambiguous.
- The three not fluent are written answerable questions. As pre-registered, they are reported,
  not dropped:
  - a garbled description reference;
  - a reworded name whose long clause strands "a member of";
  - a stilted schema paraphrase.

**E2, the person's read (the operator, via the review-sheet artifact; `data/sonnet/person-read.json`):**
- 50 of 50 fluent; 10 of 10 ambiguous questions truly ambiguous. Nothing is dropped.
- It accepts the three questions the Opus proxy rejected.
- The operator's remark: the phrasing reads like that of a seasoned cybersecurity specialist.
- The read was not blind to the study, and the proxy reads had been summarised in conversation
  beforehand.

**E4, yield: met, with a caveat.** Sonnet kept all 805 questions it was given, 10 of them after
a retry. Its yield is measured over Qwen's survivors, not over every attempt, so it is not
directly comparable to Qwen's 0.85 and 0.63 synonym-tier yields.

**Three rounds led here:**

1. **Round 1** (in `data/sonnet/v1/`, not used) passed every check on the first try. But 98% of
   its non-schema questions named the kind by its exact label, because the shared rule said
   "name the asked-for kind directly". Amendment 6 added a plain-wording rule and a checked
   style problem, and closed a gap in the leak check for joined labels.
2. **Round 2** fixed this. Its first blind read (kept as `data/sonnet/v2-proxy-read-raw-templates.json`)
   found 38 of 50 fluent, and 9 of the 12 rejects were template questions that no writer
   touches. Amendment 7 renders the templates in plain words.
3. **A fresh blind read** of the final sheet gives the figures above.

**What it means for Q61:** the scored banks are no longer worded by the agent's planner model.
The gap between the two wordings is measured the first time the agent is scored on both. Part
of any gap may come from Qwen's 237 label-literal questions, which are easier to ground, rather
than from authorship. Report the two together.

## 9. Reproduction

```bash
uv run python scripts/era2_card_bank.py --out docs/research/experiments/EXP-2026-11-012-era2-card-questions/data --banks docs/evaluation/banks
# blind proxy reader (Claude Sonnet 5.5, medium effort) reads data/review-sheet.json and writes data/proxy-read.json
uv run python scripts/era2_card_metrics.py docs/research/experiments/EXP-2026-11-012-era2-card-questions/data
# NOTE: amendments 6-7 changed card_generator's rules and templates. Re-running the line above at a later
# commit gives different text; the Qwen-worded run 4 was generated by the tree of commit dac6b8e4.
# second writer (amendments 5-7): export jobs, 20 Sonnet 5.5 writer subagents fill data/sonnet/answers/,
# check (writes retry jobs), retry subagents, assemble banks, blind Opus proxy read, metrics
uv run python scripts/era2_card_reword.py export   --data docs/research/experiments/EXP-2026-11-012-era2-card-questions/data --batches 20
uv run python scripts/era2_card_reword.py check    --data docs/research/experiments/EXP-2026-11-012-era2-card-questions/data --retry-batches 2
uv run python scripts/era2_card_reword.py assemble --data docs/research/experiments/EXP-2026-11-012-era2-card-questions/data --banks docs/evaluation/banks
uv run python scripts/era2_card_reword.py metrics  --data docs/research/experiments/EXP-2026-11-012-era2-card-questions/data
```
