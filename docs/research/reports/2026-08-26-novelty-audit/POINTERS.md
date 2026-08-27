# Novelty audit — 2026-08-26

**This report was not produced by this repository's pipeline.** Unlike
[`../2026-08-20-ariadne-project-briefing/`](../2026-08-20-ariadne-project-briefing/),
no number in it comes from `data/collect.py`, and it cites no experiment of ours.
It is an **external adversarial literature audit**: a deep-research agent was
given the brief in [`PROMPT.md`](PROMPT.md) and instructed to refute nine
candidate novelty claims rather than support them.

| | |
|---|---|
| Audit date | 2026-08-26 |
| Instrument | deep-research agent, brief in `PROMPT.md` |
| Queries run | 95 across three field vocabularies (report Part 6) |
| Documents read in full | 41 |
| Documents at abstract only | 15 |
| Verdict | 1 claim killed, 2 partially scooped, 5 narrowed, 1 clear |

## Why it is filed here rather than in `experiments/`

It reads across the whole project and says what the *literature* adds up to,
which is the reports directory's job. It has no manifest and no
`supports_claims`, because it supports no claim — it **constrains** several. The
constraints it imposes are recorded where they bind: `CLAIMS.md` (C-008, C-011,
C-016, C-017, C-021, C-022, C-023, and the new C-024/C-025), `RELATED_WORK.md`
(scoop watch, rebuilt), `OPEN_QUESTIONS.md` (Q23–Q26) and `DECISIONS.md`
(D-026, D-027).

## Reading it with the right suspicion

The report's own evidence convention is load-bearing and is preserved in every
downstream citation:

- ✅ **READ** — full text retrieved and read
- 📄 **ABSTRACT** — abstract or landing page only; **not** evidence about a
  results section
- ⚠️ **SNIPPET** — known only from a search result; a lead, not a finding
- **UNVERIFIED** — a specific field could not be confirmed from a fetched page

**Do not promote a 📄 or ⚠️ entry to a citation without opening the paper.**
That is the same discipline `RELATED_WORK.md` already enforces, and this report
is the largest single injection of external citations the project has taken.

## Independent verification performed on 2026-08-26

The single most damaging finding — that Q8 is fully scooped — was checked
against primary sources rather than accepted:

| Field | Status |
|---|---|
| Szlobodnyik, *Analytics* 5(3):25, DOI 10.3390/analytics5030025, 28 July 2026, single author, CC-BY | **confirmed** via DOI resolution and Semantic Scholar |
| Six injection categories (instruction override, role confusion, output-format manipulation, misleading prompts, chained instructions, obfuscation) | **confirmed verbatim** |
| Attack Success Rate + Unsafe Operation Rate | **confirmed** |
| Validator model flagging malicious/unsafe/divergent Cypher with corrective feedback | **confirmed** |
| Models: GPT-4o, DeepSeek R1, Claude 3.5 Sonnet, Qwen 2.5 Coder 32B | **confirmed** |
| **Role/attribute-based access control restricting execution to the authorised portion of the schema** | **NOT CONFIRMED** — mdpi.com and SSRN both return 403 to our fetcher |

The unconfirmed row is the one that matters, and it is why **Q23** exists: it is
the mechanism that maps onto our own schema-boundary refusal, and it decides
whether C-008's territory is fully occupied or only mostly. An SSRN version
exists (`abstract_id=5669662`) whose posting date could not be established — if
it predates 28 July 2026, the "four weeks" framing in the executive summary is
wrong and the work was findable earlier.

## One place the report overstates on our behalf

Its recommended novelty sentence (Part 4) claims we contribute *"the first
question set over MITRE ATT&CK and CAPEC that pairs natural-language questions
with executable gold queries scored by execution-based correctness."*

**We do not have gold queries.** A bank entry carries `question`,
`expected_template` (a template *name*), `task.seed_ids`, and computed gold
**answers** (`ex_gold.expected`, `assertions.must_include_related`) parsed from
raw STIX and CAPEC XML. No entry carries an executable Cypher or Gremlin string.
The gold query is *constructible* — template name plus seed identifiers
determines it — but it is not emitted, so the sentence as written is not
currently true. See **C-025** (`unsupported`) and **Q26**.
