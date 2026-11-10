# Ariadne documentation

The project has two eras, split at the October 2026 pitch. Every document belongs to one of
them or to the reference set that both rely on. The full repository map:
[`structure.md`](structure.md).

| | Era 1 — what we started with | Era 2 — where we're going |
|---|---|---|
| **Dates** | June 8 to October 19, 2026. **Finished.** | From 2026-10-20 (the ReliaQuest year-two award onward). **Current.** |
| **What it is** | The ReliaQuest Innovation Challenge: a federated, provenance-checked query prototype over ATT&CK and CAPEC, and the research programme that measured it for the pitch | Ariadne as an embeddable, graph-universal, exact retrieval agent that other systems call |
| **Start here** | [`era-1-challenge/README.md`](era-1-challenge/README.md) | [`era-2-expansion/README.md`](era-2-expansion/README.md) |
| **In its folder** | An index of everything from era 1 kept in this repository | The goal, its starting figures and the operator's requirements |
| **Elsewhere, at paths other records cite** | [`goals.md`](goals.md), [`RESULTS.md`](RESULTS.md), [`plans/`](plans/README.md), [`evaluation/`](evaluation/README.md), experiments `EXP-2026-07-001` to `EXP-2026-09-029`, the reports to 2026-09-14 | The latency probe in [`research/reports/`](research/reports/INDEX.md) |

## Reference for both eras

These describe the system as it is built and how to run, extend and trust it. Era 2 starts
from this system.

| Document | What it covers |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The pipeline stage by stage, with the settings each stage reads |
| [`commands.md`](commands.md) | Every command on `setup.py`, `app.py`, `main.py` and the Makefile |
| [`source_cards.md`](source_cards.md) | The source-card format |
| [`agent-interfaces.md`](agent-interfaces.md) | The four frozen seams as public contracts |
| [`query-safety.md`](query-safety.md) | The safety model and the adversarial audit |
| [`migration-guide.md`](migration-guide.md) | Adding a new query-language specialist |
| [`CHANGELOG.md`](CHANGELOG.md), [`changelog.jsonl`](changelog.jsonl) | How to read the change log; the log itself, both eras |
| [`skills/`](skills/global-project-rules/SKILL.md) | Canonical agent instructions |

## Kept outside this repository

Paper drafts, venue research, publication and research plans, research prompts, novelty
audits, proposals and the pitch decks are kept privately. [`../AGENTS.md`](../AGENTS.md)
says where.

## The research record

[`research/`](research/README.md) is the single record for both eras: experiments, claims,
decisions, open questions and reports. Quote any figure from
[`research/CURRENT.md`](research/CURRENT.md) and nowhere else. Its README says which parts
belong to which era.
