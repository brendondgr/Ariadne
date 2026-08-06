# Related Work

Running bibliography with a one-line **how it differs from us** per entry, plus a
scoop watch. Update it whenever a relevant paper surfaces — not the week before
submission.

**The full bibliography lives in [`audit-2026-08-03.md`](audit-2026-08-03.md)
§9** — roughly 100 entries across seven areas, every one retrieved during that
session, with `⚠️` marking any field that could not be confirmed from a fetched
page. **Do not cite a `⚠️` field without re-checking it.** This file curates the
entries that bear directly on a claim in [`CLAIMS.md`](CLAIMS.md); it does not
replace that bibliography.

Citation keys below match the audit's, so `[C-AGCY]`, `[T-TQA]`, etc. resolve
there.

---

## 🚨 Scoop watch

Papers that partially overlap the contribution. Re-check these before every
submission.

### `[C-AGCY]` — AgCyRAG (Kurniawan, Ardian, Kiesling, Ekelhart), RAGE-KG @ ISWC 2025

**Threat: highest.** Six named agents in LangGraph over a Neo4j property graph
*and* the SEPSES CSKG RDF store queried by SPARQL via MCP, with a reflection
loop. Two stores, two query languages, one agentic loop, security domain, ATT&CK
grounding — **and predefined rather than generated queries.** Its own limitations
section states that restricting agents to predefined queries *"helps manage
complexity and guide the analytic process"*. That is Ariadne's design thesis, in
print, from a peer group.

**How it differs from us:** it reports **no quantitative evaluation whatsoever.**
Ariadne adds a declared cross-source join key with identifier reconciliation, a
plan-level gate with schema-boundary refusal, a deterministic claim verifier with
enforced abstention carrying executed-query proof, a 120-question catalogue with
computed gold, and the controlled seven-arm study.

**Consequence for positioning:** AgCyRAG scoops the *architecture*. It does not
scoop the *result*. C-011 must therefore be framed around measurement, not around
novelty of design — see [`DECISIONS.md`](DECISIONS.md) D-004.
⚠️ The paper enumerates six agents but its prose says "five"; hedge if quoting a count.

### `[T-FIN]` — FinAI Data Assistant

**Threat: high, and under-verified.** Its stated design is ours: *"Rather than
synthesizing complete SQL via text-to-SQL, our system routes user requests to a
small library of vetted, parameterized queries."* Its RQ3 asks exactly the
question C-012 asks, and the abstract claims lower latency and cost and higher
reliability than a text-to-SQL baseline.

**How it differs from us:** different modality (SQL, not graph query languages)
and single-source rather than federated.

**Action required:** ⚠️ **the results body was never retrieved.** Read it before
relying on the claim that no template-vs-generation ablation exists. Cite the
existence of the comparison, not numbers.

---

## The mechanism is not novel — and that is fine

These establish that "use templates rather than free generation" is a recognised
family, which is why the contribution must be the *measurement*, not the idea.

| Key | Work | How it differs from us |
|---|---|---|
| `[T-AQQU]` | Bast & Haussmann, CIKM 2015 | Three query templates covering almost all of Free917 and WebQuestions. Seminal, single-source, Freebase, no LLM anywhere. Establishes the family is 10+ years old. |
| `[T-TQA]` | Zheng et al., PVLDB 2018 | The most explicit "templates rather than semantic parsers" argument in the literature. Single KG; no cross-engine federation and no LLM comparison. |
| `[T-QUINT]` | Abujabal et al., WWW 2017 | Mined templates rather than hand-written. ⚠️ Its own figures could not be verified. |
| `[T-C2F]` | Dong & Lapata, ACL 2018 | Sketch generation as classification over a fixed set — only 35 distinct sketches on WikiSQL. The same insight in a neural setting. |
| `[T-SURV]` | Gu et al., AKBC 2022 | Survey establishing templates as a named family, and stating the structural limit: templates *"typically impose a maximum length limit of 2 for relation paths."* This is the coverage cliff C-014 must measure. |

## Constrained generation — the obvious reviewer objection

A reviewer will ask what *eliminating* generation adds over *constraining* it.
The answer has to be the coverage–reliability trade measured explicitly (C-014),
not asserted.

| Key | Work | How it differs from us |
|---|---|---|
| `[T-PIC]` | PICARD, EMNLP 2021 | Constrains decoding rather than replacing it. Spider 69.9→74.1; unusable predictions 12%→2%. The strongest form of the objection. |
| `[T-GCD]` | Geng et al., EMNLP 2023 | Grammar-constrained decoding without finetuning. Same objection, different mechanism. |
| `[T-GCR]` | GCR / KG-Trie, **ICML 2025** | Graph-constrained reasoning; WebQSP Hit 92.2. ⚠️ Frequently miscited as ICLR — it is ICML. |
| `[T-OZS]` | Ozsoy, preprint | **The best quantified evidence of the cost of constraining:** execution success 63.8→86.7% while empty predictions rise 11→36. Directly supports framing the paper around a trade. |

## Text-to-graph-query is genuinely hard — this is our strongest supporting context

These make the deterministic design look informed rather than timid.

| Key | Work | How it differs from us |
|---|---|---|
| `[T-PIPE]` | PIPE-Cypher, preprint | **Zero-shot execution accuracy 0.000–0.203 (mean 0.036) across 11 models** on enterprise graphs; 0.189 for a strong local baseline. The single most useful number for our positioning. |
| `[T-GQL]` | Text2GQL-Bench, preprint | **≤4% zero-shot EX on ISO-GQL**; grammatical validity <70% at 3-shot. Gremlin is named but excluded from experiments — a gap we sit in. |
| `[T-GQLB]` | GQLBench, ACL 2026 | 35.40% average execution accuracy across two dialects. Peer-reviewed, unlike most of this row group. |
| `[T-EIC]` | EICopilot, preprint | The **only** system found that generates Gremlin. Execution correctness up to 82.14%. Closest thing to the baseline C-012 needs. |
| `[T-CB]` | CypherBench, preprint | 11 property graphs, >10,000 questions. Single-engine; no federation. ⚠️ Leaderboard figures search-derived. |

## Federation and routing

| Key | Work | How it differs from us |
|---|---|---|
| `[F1]`–`[F7]` | FedX, SPLENDID, HiBISCuS, CostFed, FedShop, FedUP | The SPARQL-endpoint federation lineage. All **same-language** federation across endpoints; ours is cross-*language* across engines. Mediator-wrapper federation is 25 years old — the architecture is not the contribution. |
| `[F8]` | BigDAWG polystore, SIGMOD Record 2015 | Seminal polystore. Establishes the cross-engine idea long predates us. |
| `[F21]` | Agentic SPARQL, preprint | Federated KGQA benchmark, 118 endpoints, 5,814 runs. **GPT-5.2 accuracy 42.1–45.4%.** Strong evidence that federated agentic KGQA is unsolved. ⚠️ Preprint; abstract independently verified. |
| `[F19]`, `[F20]` | Emonet et al.; SPARQL-LLM | LLM-generated SPARQL over federated KGs with validation-and-repair. The generation-side counterfactual, in SPARQL rather than Cypher/Gremlin. |
| `[R-PLAT]` | The Routing Plateau, preprint | 21 routing methods, 5 benchmarks: a predictability bottleneck, not an architecture problem. Supports not over-investing in the planner. |
| `[F28]` | WorkSurface-Bench, preprint | **Route F1 98.7–99.8 but answer accuracy only 56.1–75.3%.** Good routing is not good answering — worth citing beside our own planner metrics. |

## Benchmark integrity — read before defending our gold set

| Key | Work | How it differs from us |
|---|---|---|
| `[G-KGQAGEN]` | Zhang et al., **NeurIPS 2025 D&B** | The most important benchmark-integrity paper in the area. **Average factual correctness across 16 KGQA datasets: 57%.** SOTA systems drop from 85.7–92.2 Hit@1 to 21.3–54.0 on a clean benchmark. Our computed-gold approach is a partial answer to this — but it also means our own gold needs auditing. |
| `[G-ZENG]` | Zeng et al., preprint | Position bias swings LLM-judge win rates **>30%**; a 72-vs-28 result fully reverses after debiasing. Directly relevant to Q6 and to every judge-scored number we report. |
| `[E32]` | Sun et al., ACL-IJCNLP 2021 | Entity alignment with dangling cases. Relevant to our declared-join-key design. |

## GraphRAG critiques — why our abstentions are well-placed

| Key | Work | How it differs from us |
|---|---|---|
| `[G-XIANG]` | GraphRAG-Bench | 5 of 12 graph methods score below plain RAG; medical fact retrieval RAG 64.73 vs MS-GraphRAG 38.63. |
| `[G-HAN]` | RAG vs. GraphRAG | NQ at 70B: RAG 68.18 vs KG-only 28.50, root-caused to *"only about 65.8% of answer entities appear in the constructed KG."* ⚠️ Venue unverified. |
| `[G-MS]` | Microsoft GraphRAG | Seminal. ⚠️ **No peer-reviewed venue**, and its evaluation is LLM-as-judge head-to-head **with no ground truth** — worth noting when it is cited at us as a standard. |

> ⚠️ **Provenance warning, carried forward from the audit.** The widely
> circulated claim that *"GraphRAG achieves 13.4% lower accuracy on Natural
> Questions compared to vanilla RAG"* appears in `[G-XIANG]`'s introduction
> attributed to `[G-HAN]`, **but the number is not in `[G-HAN]`**, which scores
> NQ with P/R/F1 rather than accuracy. **Do not repeat it.**

## Cybersecurity knowledge graphs

The domain framing. Sikos (2023) §7 names cross-KG federation for security as an
idea and **cites nothing for it** — which is the shape of a genuine gap, and the
basis for C-011. Full entries in the audit §9.6.

---

## Maintenance

- **Add an entry the day you read the paper**, with its how-it-differs line. An
  entry without that line is a bookmark, not related work.
- **Anything that could scoop us goes in the scoop watch**, not the tables, and
  gets re-checked before each submission.
- **Preserve the `⚠️` markers.** They record what was verified against a fetched
  page and what was not. Silently dropping one converts a caveat into a false
  citation.
- **Never add a citation that has not been retrieved.** A plausible-looking
  reference to a paper nobody opened is the fastest way to lose a reviewer.
