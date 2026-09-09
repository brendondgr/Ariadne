# EXP-2026-08-010 — Results

Every figure here is computed by `scripts/external_results.py` from
`data/metrics.json`, which is the sweep's own output. Nothing is transcribed.
The tables are in `tables/results.md`; the plain-language version for a
non-specialist reader is `docs/evaluation/external-2026-08-21/REPORT.md`.

**No language model participates in any score below.** Answers are compared to
the benchmarks' gold as sets of ATT&CK identifiers.

## The headline

| arm | n | recall | precision | precision as read | exact |
|---|---:|---:|---:|---:|---:|
| ceiling — direct graph read | 182 | 0.9863 | 0.8100 | 0.8095 | 0.7033 |
| `deterministic` (templates) | 182 | 0.6836 | 0.7701 | 0.7266 | 0.4451 |
| `deterministic`, same 60 as below | 60 | 0.7170 | 0.7815 | 0.7086 | 0.4833 |
| `generic` (no templates + narrator) | 60 | **0.9953** | 0.8100 | **0.4182** | 0.7333 |
| `llm` (plan-free) | 60 | 0.6132 | 0.7670 | 0.5242 | 0.4500 |

"Precision as read" drops the label filter that both other columns apply. The
filter is right for a recall comparison — every arm gets it — but it is generous
to an arm that returns every neighbour and lets the filter select the requested
type. The `generic` arm does exactly that, and the two precision columns
differing by 0.39 is the measurement of it.

## Pre-registered hypotheses

**H1 — plan-given Ariadne recall within 0.05 of the ceiling. Split.**
`deterministic` scores **−0.303** against the ceiling: refuted, decisively, for
the arm the paper leads with. `generic` scores **0.9953 against a ceiling of
0.9953** on its 60 items — a gap of 0.000, held exactly. The hypothesis was
written as though the arms would behave alike. They do not.

**H2 — external questions score below the internal 0.92–1.00 band. Split, same way.**
`deterministic` at 0.684 is far below. `generic` at 0.995 is inside it. Whether
this project's numbers survive external questions depends entirely on which arm
is being defended.

**H3 — precision is low for everyone, the ceiling included. Held.**
A direct graph read scores **0.810** precision overall and **0.607** on
CTIBench's `cti-ate`, where it returns 466 identifiers against 283 in gold. The
benchmark is older than ATT&CK 19.0 and the graph has grown. No precision figure
in this experiment should be read against 1.0, and any published `cti-ate`
result that does not say this is overstating its own headroom.

**H4 — plan-free below plan-given. Held, −0.104**, on the same 60 questions
(0.6132 against 0.7170). It must be reported with the qualification in
ISSUES.md I7: a "given" plan supplies a source name and three entity strings.
The anchor is not among them — it reaches the specialist only because the
benchmark's own wording contains it. So 0.104 is the value of *that*, not the
value of a fully specified plan.

## The finding the experiment was not looking for

Templates lose to no templates by **+0.278 recall** on identical questions
(0.7170 → 0.9953), and the template-free arm hits the ceiling exactly.

The per-family table says why. Eight of fourteen question types match the
ceiling to three decimals. **Four return nothing at all**, and they are exactly
the four that traverse Group↔Software and Campaign↔Software. Two more lose about
70%.

Both failure modes are specific and both were traced.

**The four zeros are a missing template.** Asked "what software are used by
attack group G0003?", the builder emits
`MATCH (g:Group)-[:USES]->(t:Technique) WHERE g.attack_id IN $ids`. It answers
with the group's *techniques* because `group_techniques` is the only template
anchored on a Group. There is no `group_software`. The question is not answered
wrongly; it is answered as though a different question had been asked.

**The two partials are one label.** `_group_techniques` pins its target as
`(t:Technique)`. Three of G0020's four gold answers are sub-techniques, so it
returns one of four. The builder already carries a comment about widening that
target — and widens it, but only when the *anchor* is a sub-technique. The
group-anchored direction never got the fix.

**Why the internal banks never caught either.** Across both generated banks,
every `group_techniques`, `campaign_techniques` and `software_techniques`
question is **technique-anchored**: "Which groups use T1012?", "Which software
implements T1222.002?". Eight of eight. The reverse direction — "which
techniques does this group use?" — is never asked, and neither is
Group↔Software in any direction. The banks were drawn from the shapes the
templates support.

That is co-authorship bias, located precisely and for the first time. It did not
show up as a wrong answer on an internal question. It showed up as a question
the internal bank does not contain.

## By benchmark

| benchmark | n | recall | precision | exact |
|---|---:|---:|---:|---:|
| cti-ate | 45 | **1.0000** | 0.6073 | 0.6667 |
| attackqa | 137 | 0.5971 | 0.8778 | 0.3723 |

`cti-ate` asks one question shape, and it is the shape Ariadne's best template
covers: recall is perfect, equal to the ceiling. Its precision of 0.607 is the
ceiling's own precision — pure benchmark staleness, not an Ariadne result. A
paper that evaluated only on `cti-ate` would report a flawless system.

## Limits

- **Nothing here addresses human phrasing.** Both benchmarks are
  machine-generated. A search on 2026-08-21 found no human-authored ATT&CK or
  CAPEC question set anywhere public. **Q16 remains open.**
- **Enterprise ATT&CK only.** 14 of 60 `cti-ate` rows were excluded, 13 of them
  Mobile.
- **CAPEC is untouched.** Neither benchmark covers it.
- **Enumerating questions only.** Every gold answer here is a list. Q4 is
  unaddressed.
- **60 items for the two slow arms**, one run each. The `generic` and `llm` arms
  have a model in the loop and would vary if re-run; no conclusion rests on a
  small difference between them.
- **The plan derivation was corrected mid-experiment** (ISSUES.md I9). The first
  run's numbers are superseded and appear nowhere.

---

## Superseding note, 2026-08-21 (appended, nothing above edited)

Two of the defects measured above have since been acted on. The figures in this
document stand as the measurement of the system **as it was when measured**.

**Fixed — EXP-2026-08-012.** The four families scoring 0.000 (`groups_for_software`,
`software_for_group`, `campaigns_for_software`, `software_for_campaign`) now
score **1.000**, matching the ceiling. Overall external recall for
`deterministic` moved 0.6836 → **0.7633**, and families at the ceiling 8 → 12 of
14. The internal banks were unaffected: 60 of 60 answers byte-identical, no
query string moved.

**Fixed — D-024.** The composer defect visible in §6 — naming a Group or a piece
of software a "used technique" — is closed, along with two grammar bugs found
beside it. External scores are unchanged by it to four decimals (recall 0.7633,
exact 0.6593), because it altered prose and not one identifier.

**Not fixed, and deliberately so — D-023 / EXP-2026-08-012 ISSUES I1.** The two
partial families (`techniques_for_group` 0.295, `techniques_for_campaign` 0.326)
remain. Widening the pinned `(t:Technique)` target would take overall recall to
**0.9825**, but `evalset/questions.py::_top_level` filters the gold to parent
techniques for exactly those templates on purpose, and the two external
benchmarks disagree with each other about which reading is right. A tested patch
is kept at EXP-2026-08-012 `data/proposed-fix1-widen-target.patch`.

## AMENDMENT A-1 (2026-09-09) — Manifest placeholders filled, pointers hashed, refinement by EXP-2026-08-012 recorded

Written during the 2026-09-09 record audit. **No figure above changes**: all
17 manifest values, the headline table, the by-benchmark table and the four
zero families were re-scored offline from the stored answer files with
`scripts/external_validation.py::score_cell` and reproduce exactly.

**Manifest fields corrected in place (old → new), ISSUES I10:**

| field | old | new | established by |
|---|---|---|---|
| `code.commit` | `fa4c941` | `fa4c94183832b0857dd8b83a7ac0c8f7cefa8d7f` | `git log` (2026-08-21 16:37:51 −0400); artifacts 16:38–17:21 |
| `compute.hardware` | `<cpu/gpu, ram>` | `unknown` | never recorded |
| `llm.model` | `<provider>/<model>@<version-or-date>` | `relay/unknown@2026-08-21` | `generic` and `llm` arms ran the relay alias `skynet`; served model unrecorded |
| `llm.max_tokens` | 2048 | 16384 | `scripts/external_validation.py:155` |
| `llm.nondeterminism_note` | template text | one run per arm, no std; model arms not repeated | this record |
| `seeds` | `[]` | `[20260821]` | `metrics.json` `sample_seed` (the 60-item AttackQA draw) |
| `related` | 007, 008, 009 | + `EXP-2026-08-012` | see below |

**`data/metrics.json`** is a byte-identical copy of the sweep's `metrics.json`;
it now also carries a top-level `manifest_metrics` object (the 17 manifest
values, including `ariadne_minus_oracle_recall` −0.3027 = 0.6836 − 0.9863,
which was previously only in `data/manifest_metrics.json`).

**`data/POINTERS.md`** was the blank scaffold and now hashes the run directory,
`state.json`, `metrics.json`, `REPORT.md` and the four answer directories
(nothing has been added since the run).

**Refinement, not supersession.** The "Superseding note" above already says
EXP-2026-08-012 closed the four dead families (deterministic external recall
0.6836 → 0.7633, families at ceiling 8 → 12 of 14). The figures here stand as
the measurement of the system as it was on 2026-08-21 16:38 and remain the
"before" side of every EXP-2026-08-012 delta; this experiment therefore keeps
`status: complete` and names EXP-2026-08-012 in `related`.
