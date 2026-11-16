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
