# PROTOCOL — EXP-2026-11-012 Era 2 Step 6: questions with gold answers, generated from a card alone

Written 2026-11-16, before the recorded run. **Disclosed:** the generator and its fixture tests
exist, and a small dry run was done (1 anchor per slot; 229 ATT&CK and 106 CAPEC questions).
Reading 20 of its questions led to two changes:
- CAPEC public ids (`CAPEC-n`, `CWE-n`) are now threaded through, because the dry run first
  produced no CAPEC anchors;
- ambiguous-by-name questions now need names of at least 4 characters ("at" made an
  unreadable question).

## Amendment, 2026-11-16, before the second recorded run

The first recorded run (G1 476/476 and 227/227, 0 leaks, no split overlap) is **void**.
Looking into why CAPEC produced no ambiguous questions turned up two defects:

- **A card/store name mismatch.** The CAPEC card names five relations in CamelCase
  (`ChildOf`, `CanPrecede`, `CanFollow`, `CanAlsoBe`, `PeerOf`). Ariadne's loader stores
  them as `CHILD_OF` and so on. Step 5's Gremlin backend queried the card names, so every
  AttackPattern-to-AttackPattern set read as empty.
  - All 9 of the first run's AttackPattern-to-AttackPattern questions were therefore labelled
    "insufficient" with empty gold, when they had answers.
  - G1 did not catch this because the keyset path used the same wrong name.
  - **Fix:** `GremlinBackend(edge_label=...)` maps card names to stored labels. It is set
    to the loader's `gremlin_edge_label` for Ariadne stores; the kill-test stores keep source
    names, so Step 5's results are unaffected.
  - **New guard:** a slot with no edge anywhere in the store is now reported in `notes` and
    never used. After the fix, neither dataset has one.
  - **New live test:** the mapping is tested on the CAPEC store.
- **Relation ambiguity was never produced.** One random anchor was drawn per label pair. It
  never separated the readings in either dataset. Up to 25 anchors are now tried.

Everything else is unchanged: seed, writer, settings, gates and expectations. The second run
replaces the first, and the proxy read is repeated on its new review sheet.

## Amendment 2, 2026-11-16, before the third recorded run

The second run passed G1–G3 (476/476 and 349/349, no overlap, 0 leaks). It still made only 8
ATT&CK and 1 CAPEC ambiguous questions of the 16 budgeted per dataset. Both shortfalls come
from how the budget was split:

- **ATT&CK's card has no two relations joining the same pair of labels.** A neutral-verb
  relation ambiguity therefore cannot be built from it. Its half of the budget went unused,
  while entity ambiguity was capped at the other half.
- **CAPEC has one usable label pair** (AttackPattern to AttackPattern; ExecutionStep ids are
  not public), and the generator wrote one question per pair. Its names are all distinct, so
  entity ambiguity is impossible.

**Change:** relation ambiguity now runs first, with half the budget spread over the eligible
pairs and several anchors per pair. Entity ambiguity fills whatever budget is left. Two
fixture tests cover this.

The second run is superseded. Its outputs are not kept, apart from the counts above.

## Amendment 3, 2026-11-16, before the fourth recorded run

The third run passed G1–G3 (482/482 and 354/354, no overlap, 0 leaks). It made 14 ATT&CK and
8 CAPEC ambiguous questions. Its blind proxy read found 49 of 50 fluent and 10 of 10 ambiguous
truly ambiguous.

The one rejected question exposed a leak the audit did not define. The writer copies id-format
and version hints from the target label's description ("T-ID.NNN", "DET-IDs", "v19"). These
name the label by its id scheme, which defeats the schema tier.

- **Extent:** the extended audit finds 14 such questions in the third run, all in ATT&CK's
  schema tier.
- **Change:** the schema-tier rule now forbids them. They are leak-checked (`format_hints`)
  and retried once, then dropped. G3's audit includes them, and a fixture test covers this.

The third run is superseded, and the proxy read is repeated on the fourth run's sheet.

## Amendment 5, 2026-11-16, after the fourth run: a second writer (operator decision)

The fourth run's questions are worded by Qwen 3.8 27B, the model era 2's agent will plan with
(Q61). The operator decided that the scored banks are worded by a different, stronger writer,
and that the Qwen wording is kept as a paired comparison. Nothing has read the held-out banks
yet, so they can still be rewritten.

- **What changes: only the text.** The anchors, gold answers, splits, kinds, tiers and ids of
  the fourth run are kept. Every model-written question is rewritten: 805 of 837. This includes
  the reworded-name and description references, which Qwen also wrote. The 32 template
  questions (relation ambiguity and out of coverage) were never model-written, so they are
  copied unchanged.
- **The writer:** Claude Sonnet 5.5 at medium effort, run as 20 Claude Code subagents of about
  40 jobs each (`scripts/era2_card_reword.py export`). Each job carries:
  - the same system prompt, rules and forbidden lists the Qwen writer got
    (`card_generator.question_rules` and the reference prompts);
  - for the reference tiers, the entry's type, name, id and description.

  No job contains the Qwen text. The writers are told to read only their own batch file.
- **Checks:** `check` applies the generator's own checks, `question_problems` and
  `reference_problems`. As with Qwen, a failing job gets **one retry** naming the problems, and
  is then dropped and counted. The writers do not run the checks themselves.
- **Gates:** G1–G4 are re-run on the rewritten set (`assemble`). Gold is unchanged by
  construction, but it is re-executed anyway.
- **Banks:** written as `card-sonnet-2026-11-16-*`, with the held-out banks sealed and hashed.
  - These are the banks later steps score on.
  - `card-2026-11-16-*` (Qwen-worded, same ids) stays as the paired comparison for Q61.
  - A question dropped by either writer is left out of paired comparisons.
- **The fluency proxy read moves to a different model.** It was done by Sonnet, which now wrote
  the text, so a blind proxy read of the new 50-question sheet is done by Claude Opus 5.5 at
  medium effort. The person's read remains the plan's check.
- **Expectation E4 (new):**
  - the synonym-tier yield is at least Qwen's (0.85 ATT&CK, 0.63 CAPEC);
  - the other tiers keep at least 0.9.

  If Sonnet's yield is lower, that is reported, not tuned away.

## Amendment 6, 2026-11-16, before the second Sonnet round

The first Sonnet round passed every check on the first attempt (805 of 805). Reading it showed
two problems the checks did not define.

- **The writer copied schema labels verbatim.**
  - Example: "Which TaxonomyEntry entries does CAPEC-440 map to?"
  - The exact target label appears in 98% of Sonnet's non-schema questions, against 25% of
    Qwen's.
  - The rule "name the asked-for kind directly", together with the direction sentence's
    "the {target} entries", was read literally.
  - A person would not type this, and it hands the agent the schema name.
  - Qwen's run has the same defect in 192 questions.
- **The leak check missed joined labels.** "SubTechnique" written as one word slipped past the
  schema-tier audit, which split the label into "sub" and "technique". No question in either
  run contains one, but planted tests showed the gap.

**Changes, in `card_generator`:**

- `forbidden_label_stems` adds the joined form.
- Every tier's rules now ask for kinds in plain lower-case words ("detection strategy"),
  without "entries" after a kind's name.
- `question_problems` rejects a compound label written as one word in every tier but the
  schema tier, which already forbids the label outright.
- A fixture test covers this.

**What happens to the rounds:**

- The first Sonnet round is kept in `data/sonnet/v1/` for the record and is not used.
- All 805 jobs are re-exported and rewritten from scratch by 20 new writers, with one retry
  per failing job.
- The Qwen-worded run is not rewritten. The paired comparison reports how many of its
  questions carry the copied label.

## Amendment 7, 2026-11-16, before the final assembly and proxy read

The blind Opus read of the round-2 sheet found 38 of 50 fluent and 10 of 10 ambiguous
questions truly ambiguous.

- **Nine of the 12 rejects are template questions.** These are the relation-ambiguity and
  out-of-coverage questions, which code writes and no model rewords. Their templates use the
  schema label with "entries" ("Which AttackPattern entries are connected to CAPEC-17?"), the
  same defect amendment 6 removed from the written questions.
- **The other three are written questions.** One description reads as garbled, one reworded
  name buries its meaning in a long clause, and one schema paraphrase is stilted. As
  pre-registered, rejected answerable questions are reported, not dropped.

**Change:** `plain_template_text` renders the templates in plain words ("Which attack patterns
are connected to CAPEC-17?"). The relation-ambiguity clarification question is rendered the
same way. A fixture test covers this.

**Applied to:** the Sonnet-worded set's 32 template questions. The raw text is kept as
`template_question_raw`. The sealed Qwen-worded banks are not touched. Template questions are
identical in kind across the pair, and they are left out of the paired wording comparison.

**Then:** the banks are re-assembled and re-hashed, and a fresh blind Opus read covers the new
sheet. The earlier read is kept as `data/sonnet/v2-proxy-read-raw-templates.json`.

## Question

Can era 2's evaluation questions be generated from a source card alone, with gold answers known
by construction? This must cover every rewording tier, including the synonym tier where the
system is weakest (today 0.4667), and the three new kinds the agent's exits need: ambiguous,
out of coverage, and insufficient.

## Setup

- **The generator:** `utils/specialists/evalset/card_generator.py`.
  - **Slots** are every (label, relation, direction, target) the card's schema allows, read
    through the registry derived from the card.
  - **Anchors:** 2 per slot, from the lower and upper halves of degree. They must be public
    ids, and anchors used by any existing bank are excluded (`t3.generate.excluded_anchors`).
  - **Gold** is the slot's typed request run through Step 5's exact fetch.
- **The writer:** Qwen 3.8 27B (registry default, `reasoning_effort=medium`), temperature 0.7,
  32 requests at a time.
  - Every question must quote its reference exactly.
  - Every rewording is leak-checked automatically, retried once naming the leaked words, then
    dropped and counted:
    - synonym tier: none of the relation's own words or the card's paraphrases for it;
    - schema tier: none of the target label's words;
    - reworded-name and description tiers: no id, name, or rare name word.
- **Kinds:**
  - **ambiguous:** a shared name with different answers, or a neutral verb where two card
    relations join the same labels. Each carries its readings and the gold clarification answer.
  - **out of coverage:** path search, temporal trend, median or similarity, which are assumed
    absent from Step 9's retrieval operators.
  - **insufficient:** a card-valid relation at an anchor with zero neighbours.
- **Splits:** tuning or held-out by a hash of the anchor. A question touching both splits is
  dropped.
- **Banks:** `docs/evaluation/banks/card-2026-11-16-<dataset>-<decision>-<split>/bank.json`,
  with decision ∈ {grounding, relation_choice, exit}. Held-out banks are marked sealed and
  hashed in POINTERS before anything reads them.

## Gates (from the plan)

- **G1:** every generated question's gold re-executes to the same answer through a second fetch
  path (keyset mode); every ambiguous reading too. **n/n** per dataset.
- **G2:** tuning and held-out share **no anchor**, measured pairwise over all questions of both
  datasets.
- **G3:** the automatic leak audit re-run on the final questions finds **0** leaks in the
  synonym and paraphrased-schema tiers.
- **G4:** `test_card_generator.py` passes on the fixture card.

## Expectations

- **E1, yield.** Above 0.8 of attempts survive in the identifier, name and paraphrased-schema
  tiers, lower in the synonym tier. The dry run's synonym yield was 32 of 38 for ATT&CK and 9
  of 19 for CAPEC, whose relations carry long paraphrase lists.
- **E2, fluency (the plan's reader).** At least 0.9 for the identifier and name tiers, lower
  for description and synonym. Ambiguous questions are judged truly ambiguous 70–90% of the
  time.
  - **The plan calls for a person** to read a random 50. The 50-question sheet is in
    `data/review-sheet.md`, and the person's read is pending.
  - **A blind proxy read** (Claude Sonnet 5.5, medium effort) of the same 50 is recorded now and
    labelled as a proxy, not a person.
  - Ambiguous questions the reader rejects are dropped from the clarification sets.
- **E3, sizes.** About 450 ATT&CK and 220 CAPEC questions, from 2 anchors per slot plus up to 16
  ambiguous, 12 out-of-coverage and 24 insufficient per dataset.

## Procedure

```bash
uv run python scripts/era2_card_bank.py --out docs/research/experiments/EXP-2026-11-012-era2-card-questions/data --banks docs/evaluation/banks
# proxy reader (subagent) reads data/review-sheet.json blind and writes data/proxy-read.json
```

## What would falsify this

- **G1–G3** must hold before the step can be committed.
- **A proxy fluency below 0.7 on the identifier and name tiers** would mean the writer, not the
  rewording, is the problem. The prompts would then be revised and the run repeated.
