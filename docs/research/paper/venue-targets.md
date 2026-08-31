# Venue Targets

Deadlines, page limits, anonymisation, and artifact requirements — kept in the
repository so they are checkable rather than remembered.

> ⚠️ **Every date below was read on 3 August 2026** and is carried over from
> [`../audit-2026-08-03.md`](../audit-2026-08-03.md) §8. Some are
> aggregator-sourced and flagged there. **Re-verify any date before planning
> around it.** Dates marked *pattern* are historical patterns, not published
> calls.

> 🛑 **Superseded as an assessment, stale as a calendar — 2026-08-31.**
> Every deadline in this file was read on 3 August and several have passed
> (ARTMAN 31 Aug, IEEE Big Data demo 21 Aug). **Do not plan against a date here
> without re-reading the call.** A venue report dated 31 August exists outside
> the repository at `~/Downloads/ariadne-venue-report.md` and has not been
> imported; it independently assesses the ladder and reaches L3 on a stricter
> reading of "baseline" (external *systems* only). Import it or replace this
> file before the next submission cycle.

**Readiness as assessed 2026-08-03:** L3 — near from workshop/demo; blocked by
positioning; critical path 2–3 weeks. Far from applied conference (10–13 weeks);
far from top-tier archival (26–40 weeks, not recommended).

**Readiness as assessed 2026-08-31** ([`../audit-2026-08-31.md`](../audit-2026-08-31.md)):
**L4 — ready for workshop/demo; near from applied conference; blocked by novelty
defensibility; critical path 3–5 weeks.** Far from top-tier archival (20–30
weeks, still not recommended). Positioning moved 0 → 3 and baseline coverage
1 → 3, so the axis that blocked everything in August is no longer the binding
one.

---

## Current position: no venue is being targeted (decided 2026-08-23)

Both near-term deadlines below are **dropped**, by the operator's decision:

| Venue | Deadline | Status |
|---|---|---|
| ARTMAN 2026 @ IEEE ACSAC | 31 Aug 2026 | **Dropped.** Eight days out at the time of the decision, and viable only as a write-up of standing results with an experiment freeze. |
| EACL 2027 System Demonstrations | 22 Sept 2026 | **Dropped.** Was the recommended first move below; the recommendation stands on its merits and is simply not being taken on this cycle. |

**The reasoning is not schedule slippage.** The record has an open backlog that a
submission would have to be written around rather than through: C-003's plain
reading is contradicted by three of its own measurements, the verifier's central
property is asserted rather than ablated, no arm figure carries a confidence
interval, and the safety claim rests on 17 hand-written probes. Writing to a
deadline would have frozen all four in their current state. The decision is to
close them first and select a venue afterwards, from a stronger position.

> **Update, 2026-08-31: all four are closed, and the reason for dropping the
> deadlines no longer applies.** C-003 was resolved by refutation
> (`EXP-2026-08-007`, `-008`, `-011`; superseded by C-023); the verifier was
> ablated over 888 claims and again against LLM-proposed claims
> (`EXP-2026-08-014`, `-018`); every judged cell now carries a bootstrap
> interval; and the safety claim rests on 240 generated probes after 15 live
> bypasses were found and fixed (`EXP-2026-08-016`). The blocking backlog is now
> a different and shorter one — `Q24`, a cross-model re-grade, and `Q26` — and
> it is listed in [`OUTLINE.md`](OUTLINE.md).

**What this does not change.** Re-verify every date in this file before planning
against it; they were read on 3 August 2026 and some are aggregator-sourced.

**Blocking prerequisites: all three are now closed.** LICENSE and attribution
shipped 2026-08-18; the blind holdout ran as `EXP-2026-08-002`; the LLM-planning
delta was recomputed within one judge run at −0.1185 and has since been
superseded as a headline. The remaining release constraints are **archival
identity (a DOI)** and **the non-redistributable identity catalog** — see
[`../datasets/DATASETS.md`](../datasets/DATASETS.md).

**When to revisit:** the trigger has fired. `EXP-2026-08-017` completed on
2026-08-23 and the record-hardening plan is done; twelve further experiments have
run since. **This file is overdue for replacement rather than revisit** — see the
banner at the top.

---

## Blocking prerequisites — all three closed

| # | Item | Cost | Status |
|---|---|---|---|
| 1 | Add a LICENSE file and a MITRE attribution notice | ½ day | ✅ **Done 2026-08-18.** Apache-2.0 + `NOTICE`. The remaining release constraints are a DOI and the non-redistributable identity catalog |
| 2 | Run the blind holdout (Q1) — 30 questions authored by someone else against frozen templates | ~4 days | ✅ **Done.** `EXP-2026-08-002`: 0.689 / 0.708 against a development 0.9972. C-013 refuted, C-001 narrowed. The bank has since been burned and three fresh ones drawn |
| 3 | Recompute the LLM-planning delta within one judge run | hours | ✅ **Done.** −0.1185 within the final table, and the figure has since been superseded as a headline. `−0.196` is retired (C-018, cut) |

**The current blocking set is different and shorter:** `Q24` (one day of
writing), a cross-model re-grade of the judged comparisons, and `Q26`. They are
listed in [`OUTLINE.md`](OUTLINE.md) and estimated in
[`../audit-2026-08-31.md`](../audit-2026-08-31.md) §8.5.

---

## Recommended first move

**EACL 2027 System Demonstrations — 22 September 2026.** Treat this as the
correct first submission, not a consolation.

| Field | Value |
|---|---|
| Deadline | **22 Sept 2026** (opens 18 Aug; notification 18 Dec) |
| Conference | 9–14 Mar 2027, Athens |
| Length | 6 pages + unlimited references |
| Anonymity | **Single-blind** |
| Mandatory | ≤2.5-min screencast **and** a live demo URL or installable package — missing either is a **desk reject** |
| Evidence of validity | Required: user study, benchmark, case study, or usage statistics |
| Fit | The workbench exists, the video is a day's work, and the 120-question benchmark satisfies "evidence of validity". **Demo tracks do not require baselines** — which is exactly the gap this work has (D-005). |

### In parallel

**ARTMAN 2026 @ IEEE ACSAC — 31 August 2026.** Four pages excluding references,
IEEE two-column, **anonymous (desk reject otherwise)**, mandatory LLM Usage
Statement, IEEE CPS proceedings. Its scope explicitly covers trust in intelligent
systems and interpretable/accountable AI agents. Strategically valuable: its
chair leads one of the three research groups closest to this work. Cheap route
into that community.

---

## Other tier-3 options

| Venue | Track | Deadline | Length / anonymity | Note |
|---|---|---|---|---|
| IEEE Big Data 2026 | Demo | 21 Aug 2026 | 4 pp incl. refs; not anonymous | Under three weeks. Tight but feasible. |
| EACL 2027 | Industry | 11 Sept 2026 | 6 pp; **double-blind**; mandatory Limitations | Welcomes "evaluation practices as deployments shift from deterministic automation toward LLM-based components" — nearly a literal description of the Path 1 framing. Only pursue alongside the demo if two genuinely distinct papers are possible; the >25% overlap rule bites. |
| ACM SAC 2027 | ACE / ST / KNLP | 2 Oct 2026 | Mandatory presentation; APC may apply | ST is the better fit for the federation framing. |
| ACL-family workshops | Workshop | EACL 15 Dec 2026 · COLING 5 Jan 2027 · NAACL 5 Feb 2027 (*tentative*) | — | Watch for a KG+LLM / GraphRAG / agentic-retrieval workshop; historically at least one per cycle. |
| ACL Rolling Review | Rolling | Oct 2026 cycle: 12 Oct 2026 | 8 pp long / 4 pp short; two-way anonymised; Responsible NLP checklist; mandatory Limitations; **all authors must register as reviewers** | Moderate as a short paper. |

## Tier 2 — target (the baselines this heading waited for now exist: `EXP-2026-08-008`, `-009`)

| Venue | Deadline | Note |
|---|---|---|
| **IAAI-27** Emerging Applications | *Not announced.* AAAI states papers due "no earlier than July 27th"; pattern suggests September — **pattern, not fact** | **Best conceptual fit in this tier.** 6 pp for pilot-stage results with a path to deployment — precisely this project's status. Single-blind, no rebuttal, shepherding possible. **Check weekly.** |
| **ESWC 2027** In-Use | *Not announced.* Pattern: abstracts mid-December | If the pattern holds, lands inside the window. Source cards fit the schema-description conversation; both closest groups publish there. **Monitor.** |
| SIGMOD 2027 Demo | 15 Jan 2027 | 4 pp incl. everything; not double-blind; **template violations are desk rejects**; ORCID + CMT per author; optional ≤5-min video counted in selection. |
| WWW 2027 poster/demo | *Not announced* (research track 18 Oct 2026) | Research track too early — no baseline. |

## Tier 1 — reach, and honestly unlikely

| Venue | Deadline | Why low |
|---|---|---|
| PVLDB / VLDB 2027 | Rolling, 1st monthly; final 1 Mar 2027 | Requires the missing baselines. Lead with cross-engine federation as a **data management** contribution, not with LLMs. Caps: 12 papers/year, 2/month per author. |
| NDSS 2027 | 19 Aug 2026 | CFP explicitly warns that papers with contributions primarily in AI/ML may be desk-rejected. This is a data-integration paper wearing a security hat. |
| USENIX Security '27 | Cycle 1: 25 Aug 2026 · Cycle 2: 26 Jan 2027 | Same topic-fit problem, plus a **mandatory Open Science Appendix** — acceptance conditional on public artifact availability, currently blocked by the missing LICENSE. |
| IEEE S&P 2027 | ⚠️ 17 Nov 2026 (aggregator-sourced; official site shows TBA) | Very low. |

## Shared tasks worth considering

- **SemEval-2027 Task 11 — VAKRA-Advanced** (IBM): multi-hop, multi-source
  tool-calling in executable environments. Sample data 8 Aug 2026, training data
  1 Sept 2026, evaluation 10–31 Jan 2027, system papers Feb 2027. **Maps almost
  exactly onto the multi-source planning problem**, participation is open, sits
  inside the window, and a system paper is a low-cost publication.
- **TEXT2SPARQL Challenge**: no 2027 edition announced. The 2026 framing is
  language-agnostic and the winning entry names Cypher and GQL as siblings —
  **pitching a Cypher/Gremlin track to the organisers is a credible, cheap move
  that creates a venue rather than competing for one.**

## Artifact evaluation

Most ACM/USENIX venues award three badges:

| Badge | Requirement | Status |
|---|---|---|
| **Available** | Artifact deposited in a **public archival repository with a DOI** | ❌ **GitHub alone does not satisfy this.** Needs Zenodo, Figshare, or Dryad. Blocked on the LICENSE. |
| **Functional** | Documented, consistent, complete, exercisable | 🟡 Plausible — the record's `PROTOCOL.md` + entrypoints cover most of it. |
| **Results Reproduced** | Independent committee re-obtains main results within tolerance | 🟡 Arm A is byte-reproducible. The judged arms are not (`n_runs: 1`, no seeds, LLM judge). See Q2. |

[`ARTIFACT_APPENDIX.md`](ARTIFACT_APPENDIX.md) assembles mostly from
`manifest.yaml` + `PROTOCOL.md` and is started early by design.
