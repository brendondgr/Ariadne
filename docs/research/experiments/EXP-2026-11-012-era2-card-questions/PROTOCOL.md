# PROTOCOL — EXP-2026-11-012 Era 2 Step 6: questions with gold answers, generated from a card alone

Written 2026-11-16, before the recorded run. **Disclosed:** the generator and its fixture tests
exist, and a small dry run was done (1 anchor per slot; 229 ATT&CK and 106 CAPEC questions).
Reading 20 of its questions led to two changes:
- CAPEC public ids (`CAPEC-n`, `CWE-n`) are now threaded through, because the dry run first
  produced no CAPEC anchors;
- ambiguous-by-name questions now need names of at least 4 characters ("at" made an
  unreadable question).

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
