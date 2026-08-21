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
