# SEAL — variants-holdout-2026-09

*Sealed 2026-09-15 before any rule or threshold in `docs/plans/2026-09-15-open-question-correctness.md` was set. Append-only.*

## What this is

An **entity-held-out** bank: 40 gold questions whose anchor entities appear in no
variant of `docs/evaluation/variants-2026-08-29` (the exposed bank), with four
authored variants each — T3 (exact name, no id), T4 (paraphrased name), T5
(description only), T6 (invented id and name, negative control). It exists so a
rule chosen on the exposed bank can be *confirmed* here, never *chosen* here.

## How it was drawn

- Gold questions come from the composition banks `bank-dev.json` (12) and
  `bank-fresh-2026-09-12.json` (28), filtered to: a single seed id, a real entity
  name, a label in {Technique, SubTechnique, Group, Software, Campaign, Mitigation,
  AttackPattern, Tactic, Category}, deterministic recall 1.0 on the recorded run,
  `d_tier` D1–D5, and the seed absent from every exposed-bank anchor.
- Stratified 20 ATT&CK / 20 CAPEC across D1–D5, at most four questions per
  census shape, `random.seed(20260915)`; four HAS_MEMBER questions whose
  reference extracted nothing, one whose gold set is verifiably empty, and one
  contributors question whose reference was a 747-record dump were replaced
  (seeds 20260916–18) before any variant was written.
- No federated questions: the composition banks carry none.
- Variants authored by the Claude session that wrote the plan, from
  `authoring/inputs.json` (anchor name, description, per-bank avoid list),
  then passed through `scripts/author_variants.py gate`: **160 kept, 0 rejected**.
- The reference is the shipped tree's own capture of each gold question
  (`scripts/variant_harness.py capture --gold`), taken twice at 32 workers:
  `reference.json` and `reference_check.json` are byte-identical.

Gold questions: 40 (20 attack, 20 capec); d_tier {'D1': 7, 'D2': 13, 'D3': 5, 'D4': 4, 'D5': 11}. Variants: 160 ({'T3': 40, 'T4': 40, 'T5': 40, 'T6': 40}).

## Hashes (SHA-256)

| file | sha256 |
|---|---|
| `gold.json` | `df479c6024930a78cbed70027dab30892dc976e84e087dcc22bf36201f83c9f8` |
| `slot_gold.json` | `d96fa70688f78635ffd988db3bf599df5dc8d5a055e7b2557eea5910ae2a209f` |
| `variants.json` | `f50ddaa628f892ee2498c19662a4a42bf1c4589dad6361d4003233011ab578ce` |
| `reference.json` | `2ab12ae417ff15b4831d17a551bfebbdeb30312c333d325d8d7cd8ec42e6f917` |
| `reference_check.json` | `2ab12ae417ff15b4831d17a551bfebbdeb30312c333d325d8d7cd8ec42e6f917` |
| `authoring/inputs.json` | `7f0d2e283474451d252093622e8564eeb91ecf3f3593e2c6f177162520824f05` |

## Rules of use

1. Open it once per plan step, for confirmation of a rule already fixed on the exposed bank.
2. Never choose or move a threshold on it. If a rule needs adjusting to pass here, the step records a failure.
3. `utils/planner/tests/test_holdout_bank.py` asserts the hashes, the zero-overlap property and the reproducible reference.
