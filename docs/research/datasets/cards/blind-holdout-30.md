# Dataset Card — Ariadne Blind Holdout (30 questions)

**Version:** `holdout-v1` · **Size:** 30 questions · **Authored by:** Claude Fable 5 (high reasoning effort), blind
**Used by:** EXP-2026-08-002

---

## What it is

The held-out question set that exists to answer one question the
[120-question catalogue](golden-catalogue-120.md) structurally cannot: is the
deterministic pipeline's near-ceiling correctness a capability, or an artifact of
questions co-authored with the templates that answer them?

Thirty questions, each anchored on an entity drawn mechanically and uniformly
from the pinned snapshot, written by an author who could not see the template
inventory, with gold computed independently from the raw MITRE sources.

Ids carry an `H-` prefix and a category segment (`H-MIT-01`, `H-CTM-03`). Every
entry carries `split: "holdout"` — the field the three development banks lack,
which is the gap this set closes.

## How it was built

The three roles were kept apart, and one agent never held two.

**Sampler** — `utils/specialists/evalset/holdout_protocol.py`, committed, with a
fixed seed (`20260805`) recorded as a module constant. Populations are the live
id space of the pinned snapshot, not a curated subset:

| Population | Size | Source |
|---|---|---|
| ATT&CK Technique + SubTechnique | 697 | live ids in ATT&CK 19.0, 157 revoked and 251 deprecated excluded at load |
| CAPEC AttackPattern | 558 | live patterns in CAPEC 3.9 — **including the 381 with no ATT&CK mapping** |
| Bridged CWE | 336 | `gold_bank.json` `capec.cwe_to_capec`, unfiltered |

Stratified 12 ATT&CK / 8 CAPEC / 10 federated to match the development bank's
46/34/40 source proportions, sampled **uniformly within stratum**. There is no
weighting by degree, mapping count, fame, or category — the development set's
federated anchors were explicitly chosen for richness, and reproducing that here
would have reproduced the bias this set exists to detect. The population SHA256s
are recorded in `docs/evaluation/holdout-v1/anchors.json` so a reviewer can
confirm the draw was made against the snapshot claimed.

**Author** — one fresh Claude Fable 5 subagent at high reasoning effort per
anchor, no shared context between spawns, no repository access. Each prompt
carried exactly: the anchor id, its entity type, its catalogue name, one category
description, and the reference-discipline rule. No repository path, file name,
template identifier, example question, or second entity appears in any prompt —
`test_holdout_protocol.py` asserts this. All 30 prompts are reproduced verbatim
in `docs/evaluation/holdout-v1/author-prompt.md`.

**Compiler** — gold computed by `utils/specialists/evalset/gold_bank.py`, which
parses the raw STIX bundle and CAPEC XML directly rather than reading the loaded
graph. Zero anchors were discarded.

## The federated partition

Uniform CAPEC sampling means most patterns carry no ATT&CK mapping. Those were
not filtered out — they are the most informative anchors in the set — but they
are not blended into one number either, because "correctness" means something
different for each:

| Partition | n | Correct behaviour | Scored on |
|---|---|---|---|
| Answerable | 6 | An answer | Answer correctness |
| Abstention-expected | 4 | An **honest empty carrying the executed query** | Did it abstain, did the abstention carry the query, did it avoid fabricating a mapping |

## Reproducibility

Unlike a human-authored holdout, this one can be regenerated. `anchors.json`
carries the seed, the populations, their SHA256s, the full draw order and the 10
over-draws; `author-prompt.md` carries every prompt verbatim; the sampler is
committed. A reviewer can re-run the draw and confirm the anchors really were
sampled uniformly rather than selected.

## ⚠️ Limitations

1. **It controls co-authorship bias, not distribution bias.** The author had no
   knowledge of the template inventory, so the questions cannot have been shaped
   to fit it. But they are still *a model's idea of what an analyst asks*. A
   human-authored set remains the stronger test; a further 15–20 questions would
   be a cheap secondary check.
2. **`expected_template` is derived, not gold.** The Author never saw the
   template inventory and could not supply it, so the Compiler inferred it from
   the anchor's type and category. Every entry carries
   `expected_template_is_derived: true`. **Template-routing accuracy may not be
   reported from this set.**
3. **n=30.** Wilson score intervals are wide. Quoting a bare point estimate from
   this set overclaims, and per-category cells hold 1–4 questions each.
4. **One authored question is malformed and was kept.** `H-SW-01` asks what
   techniques a *sub-technique* implements, because the `software` category
   description is phrased for a Software anchor while the stratum's population
   is techniques. Editing it would have converted a blind question into a
   co-authored one, so it stands and results are reported with an n=29
   sensitivity alongside.
5. **Single-source categories require the relation to exist.** Category is drawn
   first and the anchor uniformly within that category's feasible
   sub-population, conditioned only on "the relation exists at all" — never on
   how many neighbours there are. Honest-empty behaviour is measured in the
   federated abstention stratum instead.
