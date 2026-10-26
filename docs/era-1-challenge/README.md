# Era 1 — the Innovation Challenge: what we started with (finished)

**June 8 to October 19, 2026. Complete.** Nothing in this era is being extended. Where
Ariadne goes next is [era 2](../era-2-expansion/README.md); why the documents are split
this way is [`REORGANIZATION-2026-10.md`](../REORGANIZATION-2026-10.md).

## What era 1 was

The year-one ReliaQuest Innovation Challenge award (Challenge Three, Knowledge Graph
Integration; award period June 8 to October 23, 2026) funded a prototype that answers an
analyst's question across live cybersecurity knowledge graphs that do not share a query
language, with every claim citing the record and the query behind it. The
[proposal](proposal.md) set the scope, and the [year-one roadmap](../goals.md) tracked it.

Around the prototype ran a research programme built for the pitch: arm comparisons, sealed
question banks, model judging, and the experiments `EXP-2026-07-001` to `EXP-2026-09-029`.
It ended with the September showcase and the October pitch at FSU Discovery Days on
**2026-10-19**.

## Where everything from era 1 lives

Some of it moved into this folder. The rest stays at its old path because experiment
manifests, hash pins, tests or scripts cite it there; it is listed here so the whole era
can be found from one page.

| What | Where | Note |
|---|---|---|
| The October pitch: deck, script, preview, plan, numbers audit | [`pitch/`](pitch/october-pitch-plan.md) | Moved from docs/pitch/ |
| The September showcase: deck, technical brief, figures | [`showcase/`](showcase/README.md) | Moved from docs/showcase/. Its "open item" (re-record a clip) was overtaken by the pitch |
| The funded year-one proposal | [`proposal.md`](proposal.md) | Moved from docs/proposal/ |
| The year-one roadmap and deliverables | [`../goals.md`](../goals.md) | In place; every row is done |
| The results, as the record stood at the pitch | [`../RESULTS.md`](../RESULTS.md) | In place; linked from the root README |
| Implementation plans, 2026-08-05 to 2026-09-16 | [`../plans/`](../plans/) | In place; closed |
| Raw evaluation artifacts | [`../evaluation/`](../evaluation/README.md) | In place; hash-pinned by the experiments |
| The experiments, `EXP-2026-07-001` to `EXP-2026-09-029` | [`../research/INDEX.md`](../research/INDEX.md) | In place; the research record serves both eras |
| Synthesis reports, 2026-08-20 to 2026-09-14 | [`../research/reports/INDEX.md`](../research/reports/INDEX.md) | In place; the era-1 table |
| The paper draft and venue analysis | [`../research/paper/`](../research/paper/OUTLINE.md) | In place |
| The external audits (3 and 31 August) and the September top-tier plan | [`../research/audit-2026-08-31.md`](../research/audit-2026-08-31.md), [`../research/top-tier-programme-2026-09.md`](../research/top-tier-programme-2026-09.md) | In place. The plan's title says "Phase 2"; that is a paper plan inside era 1, not era 2 |
| Positioning and venue-selection prompts | [`../prompts/`](../prompts/) | In place; the era-1 section |

## Quoting its figures

Every figure era 1 produced is quoted from [`../research/CURRENT.md`](../research/CURRENT.md),
which is generated from the experiment manifests and lists every withdrawn value with its
replacement. Decks, plans and reports in this era quote the figures that were current on
their own dates; do not lift a number from them.

## What carries into era 2

- **The system.** The pipeline described in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) is
  what era 2 starts from, and the reference documents (commands, source cards, interfaces,
  query safety, the migration guide) remain in force.
- **The record.** [`../research/`](../research/README.md) stays the single record. Its
  claims, decisions and open questions were written in era 1; era 2 adds to them.
- **The starting figures.** Era 2 quotes the measurements it starts from in its own
  [README](../era-2-expansion/README.md).
