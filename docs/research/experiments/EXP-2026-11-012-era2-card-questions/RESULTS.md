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
- **E2, fluency: met by the proxy; the person's read is pending.** The blind proxy reader
  (Claude Sonnet 5.5, not a person) found:
  - 50 of 50 sampled questions fluent;
  - 10 of 10 ambiguous ones truly ambiguous.

  That is above the 70–90% band expected, on a sample of 10. No ambiguous question was
  rejected, so none was dropped from the clarification sets. The person's read of the same
  sheet, `data/review-sheet.md`, is still pending.
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
- **The proxy reader is a model, and it read only 50 questions.** Its 10 of 10 on ambiguity is a
  small sample; the person's read is the plan's check.
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
- **The person's read** of `data/review-sheet.md`: fluency, and whether each ambiguous question
  really is ambiguous. Questions it rejects come out of the clarification sets.

## 8. Reproduction

```bash
uv run python scripts/era2_card_bank.py --out docs/research/experiments/EXP-2026-11-012-era2-card-questions/data --banks docs/evaluation/banks
# blind proxy reader (Claude Sonnet 5.5, medium effort) reads data/review-sheet.json and writes data/proxy-read.json
uv run python scripts/era2_card_metrics.py docs/research/experiments/EXP-2026-11-012-era2-card-questions/data
```
