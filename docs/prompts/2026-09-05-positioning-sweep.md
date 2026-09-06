# Overnight positioning sweep — prompt

*Paste everything below the line into a capable LLM with web access. It is
self-contained. Target venue: a full conference paper or JMLR — not a demo — so
the standard is "would a reviewer find this first", not "is it plausible".*

---

You are doing a **novelty and positioning audit** for a systems paper. Your job
is to try to **falsify four claims** by finding prior work that already does what
they say is unoccupied. You are not writing a survey and you are not summarising
the field. Finding one paper that kills a claim is worth more than fifty that
don't.

## The system, in four sentences

It answers natural-language security questions over **two live, unmerged
knowledge graphs in different query languages** — MITRE ATT&CK in Neo4j/Cypher
and CAPEC in Apache TinkerPop/Gremlin. A planner decomposes a question, routes
sub-questions to per-source specialists, and each specialist emits a **native
query in its own language**; results are joined on shared identifiers. Three
arms are compared: hand-written parameterised templates, a schema-derived
template-free path, and a language model writing the query. **No language model
writes a query on the shipped paths**, and the two graphs are never merged.

## The four claims to attack

**C-023 (partial).** *Hand-written query templates do not hold the system's
correctness — a schema-derived generic path matches them. What templates hold is
precision on the schemas they were written for, plus provable abstention; what
they cost is coverage.*
→ **Kill it by finding**: any template-based KGQA system reporting a
precision-versus-coverage comparison against a schema-derived or template-free
path on the same graph.

**C-024 (partial).** *This is the first implemented and benchmarked system that
answers natural-language questions by dispatching native queries in two
different graph query languages to live, unmerged, independently-governed
stores.*
→ **Kill it by finding**: any system that federates across **two different graph
query languages** (Cypher/Gremlin/SPARQL/GQL in any pairing) at query time,
against live stores, and reports answer accuracy. Virtual/materialised
integration work that reports only latency or source-selection efficiency does
**not** kill it — say so explicitly if that is all you find.

**C-025 (unsupported).** *No benchmark pairs natural-language questions with
executable gold queries in a standard graph query language, against a live graph
store, scored by execution-based correctness, over MITRE ATT&CK, CAPEC, CVE,
CWE, D3FEND or ATLAS.*
→ **Kill it by finding**: any such benchmark. Text-to-Cypher/SPARQL benchmarks on
general-domain graphs (Spider-style, LC-QuAD, QALD) do not kill it unless they
cover one of those six security catalogues — but **list them anyway** as the
nearest neighbours.

**C-022 (partial).** *Federating across separate engines is accuracy-neutral
against merging both sources into one store, and its advantage is structural.*
→ **Kill it by finding**: any paper that builds **both** a federated and a merged
version of the same KGQA system and reports a head-to-head **answer-accuracy**
comparison.

## Five specific gaps — this is the actual task

A prior audit disclosed exactly where its own search was thin. Work these in
order; 1 and 2 are the only ones that can change a claim.

1. **CEUR-WS workshop volumes, enumerated directly.** General web search indexes
   them poorly and **the closest known competitor is a CEUR workshop paper.**
   Sweep **ESWC 2026** and **ISWC 2026** workshop proceedings by hand at
   `ceur-ws.org`. **Watch RAGE-KG 2026 specifically** — the
   **Kurniawan / Kiesling / Ekelhart** group has stated in *two consecutive
   papers* that comprehensive evaluation is future work, which is exactly
   C-025's artifact, promised publicly, by an active group. If they have
   published it, C-025 is dead and that is the single most valuable thing you
   can find tonight.
2. **Four primary systems never opened.** Read the **results sections**, not the
   abstracts: **QUINT**, **TeBaQA**, **QAnswer/WDAqua**, and **SG-KBQA** (EMNLP
   2025). **TeBaQA is the priority** — it claims portability "to a new domain…
   partially proven by evaluation over different KGs." If that evaluation
   contains a precision-versus-coverage table across knowledge graphs,
   **C-023 narrows**. Report the actual table if it exists.
3. **arXiv systematic field search.** A previous attempt got empty bodies from
   the full-text API. Use the search UI or API with field queries —
   `abs:Gremlin AND abs:Cypher`, `abs:"graph query language" AND abs:federat*`,
   `all:TinkerPop AND all:"question answering"` — and report what the query
   space actually contains. This is the main structural gap under C-024.
4. **Two circulating statistics that could not be traced to any document**:
   *"planning… 33% of total errors"* and *"29% planning / 47% reasoning / 10%
   retrieval"*. Probably search-engine synthesis. **Either find the primary
   source or confirm it does not exist** — this is recorded so nobody re-finds
   and cites them.
5. **arXiv PDFs with no machine-readable text.** The workaround that works is
   `arxiv.org/html/<id>v1`. Note any paper you could not open at all.

## Rules

- **Primary sources only.** A claim you cannot open is `📄 abstract-only` and is
  labelled as such. Never infer a results table from an abstract.
- **Verify every citation independently**: title, authors, venue, year, DOI. A
  previous audit cited a paper for something it did not say, and that cost more
  than the gap it was filling.
- **Distinguish "not found" from "does not exist."** Write *"we are not aware
  of"*, never *"no one has done"*. Say where you looked and where you could not.
- **Watch for two known traps.** *Federated learning* is a homonym that floods
  any "federated accuracy" search and is unrelated. And at least one preprint
  uses *"federation"* to mean *loading everything into one store* — i.e. our
  **merged** condition — so read what a paper does, not what it calls itself.
- **A negative result is a real deliverable.** If a claim survives, say what you
  searched and why the negative is credible.

## Output

One markdown document:

1. **Verdict per claim** — `killed` / `narrowed` / `survives`, with confidence
   and the one citation that decides it.
2. **RAGE-KG 2026 status** — published, not published, or cannot determine.
   Answer this explicitly even if the answer is "cannot determine".
3. **The four systems**, one paragraph each: what the results section actually
   reports, and whether it touches C-023.
4. **Nearest neighbours** — the 5–10 papers a reviewer would ask "how is this
   different from X?" about, with a one-sentence differentiator each.
5. **Search log** — engines, databases, query strings, dates. Enough that
   someone can tell how thin the negative is.
6. **Untraceable statistics** — resolved or confirmed phantom.

Sources worth hitting beyond web search: arXiv, ACL Anthology, ACM DL, IEEE
Xplore, Springer, ScienceDirect, DBLP, Semantic Scholar, CEUR-WS, and the
ESWC/ISWC/VLDB/EDBT proceedings directly.
