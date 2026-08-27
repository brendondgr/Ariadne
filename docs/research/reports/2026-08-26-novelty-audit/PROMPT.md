# Deep research task: what can this architecture actually claim as novel?

> **Provenance.** This is the brief given to the deep-research agent on
> 2026-08-26, as sent. The agent's answer is
> [`novelty-audit-report.md`](novelty-audit-report.md); its executed queries are
> that report's Part 6. Written before execution, following the search
> discipline in §2.2 of [`../../audit-2026-08-03.md`](../../audit-2026-08-03.md).

You are auditing the novelty of a research system. Your job is **not** to help us
look new. Your job is to find the work that scoops us, and to tell us precisely
which of our candidate claims survive contact with the literature. Treat every
claim below as a hypothesis to be **refuted first**. A verdict of "clear" is only
credible if you can show what you searched to try to kill it.

---

## 1. The system under audit

Natural-language question answering over cybersecurity knowledge graphs.

- **Three live sources, never merged.** MITRE ATT&CK Enterprise in Neo4j
  (queried in Cypher), CAPEC in an Apache TinkerPop store (queried in Gremlin),
  and a customer Active-Directory-style identity graph in a second, separate
  Neo4j. Each runs as its vendor ships it; nothing is copied into a common store.
- **No language model writes a query.** A deterministic planner classifies the
  question, resolves entity identifiers, chooses source(s), and routes to a
  library of roughly 25 hand-written, parameterised, read-only query templates.
  A second path builds queries from the database's own declared schema
  (generic "describe this node" / "expand this relation" primitives) for
  questions no template covers.
- **Cross-source answers use a declared join key** with identifier
  reconciliation between STIX-derived and CAPEC-XML-derived identifier schemes.
- **A plan-level safety gate** rejects any query that is not read-only, not
  bounded, or that touches a label not declared on the source's schema card.
- **Answers are composed mechanically from retrieved records.** A claim-level
  verifier checks every claim is cited, resolvable, grounded in a retrieved
  record, and correctly correlated across sources. When evidence is
  insufficient the system **abstains and returns the executed query as the
  proof of insufficiency**.
- **An optional LLM narrator** writes prose, bound to the verified claim set
  and never given the raw retrieved evidence.
- **Evaluation.** A 120-question catalogue whose gold answers are computed
  independently from the raw source files rather than through the ingest
  pipeline; blind question banks authored without sight of the templates; two
  external published benchmarks; graded by a model from a different family than
  any model in the pipeline.

---

## 2. Prior art we already found — go past it, and verify it

Do not spend budget rediscovering these. **Do** check whether each is described
accurately, and whether anything has superseded it.

| Work | What it is | Why it matters to us |
|---|---|---|
| **AgCyRAG** — Kurniawan, Ardian, Kiesling, Ekelhart, RAGE-KG workshop @ ISWC 2025 | Agents in LangGraph over a Neo4j property graph *and* the SEPSES RDF store via SPARQL, security domain, ATT&CK grounding, **predefined rather than generated queries** | Our closest known match. Believed to report **no quantitative evaluation at all** — *verify this against the actual paper, not the abstract.* |
| **FinAI Data Assistant** | Routes requests to a small library of vetted parameterised queries rather than generating SQL | Same design thesis, different modality (SQL), single-source. Its results section was **never retrieved** — retrieve it. |
| Bast & Haussmann (CIKM 2015); Zheng et al. (PVLDB 2018); Abujabal et al. (WWW 2017); Gu et al. (AKBC 2022) | The "templates instead of semantic parsing" family in KBQA | Establishes the mechanism is 10+ years old and not ours to claim |
| PICARD (EMNLP 2021), grammar-constrained decoding (EMNLP 2023), GCR/KG-Trie (**ICML** 2025, often miscited as ICLR) | Constrained generation | The obvious reviewer objection: why *eliminate* generation rather than *constrain* it |
| FedX, SPLENDID, HiBISCuS, CostFed, FedShop, FedUP | SPARQL endpoint federation | All **same-language** federation. Ours is cross-*language* across engines |
| BigDAWG (SIGMOD Record 2015) | Seminal polystore | The cross-engine idea long predates us |
| LinkQ | KGQA with a stated faithfulness guarantee | Closest known prior art to our verifier |
| Sikos (2023) §7 | Survey that *names* cross-KG federation for security | **Cites nothing for it** — this absence is the current basis of our novelty claim. Confirm the section says what we think it says. |

---

## 3. The claims to adjudicate

For each, return one of: **fully scooped** / **partially scooped** / **narrowed
but standing** / **clear**. Name the single closest published work and state the
delta in one sentence. If a claim is scooped, say what the *surviving* narrower
version would be.

### Tier 1 — these decide what the paper is about. Spend most of your budget here.

**Q1. Cross-*language* federation.**
Is there any published system that answers natural-language questions by
querying two or more graph stores **in different query languages** (e.g. Cypher
and Gremlin, or Cypher and SPARQL) without materialising them into a common
store? Security domain or not. Include: does *any* system generate or route to
**Gremlin** from natural language at all?

**Q2. Federation versus merging, measured.**
Has anyone built both a federated and a merged/materialised version of the same
knowledge-graph QA system and compared **answer accuracy** head to head? Note
that the data-integration literature has compared virtual versus materialised
integration for decades — but on query *performance* and *freshness*. We want
comparisons on **answer correctness**. Our own result is a null (federation is
not more accurate), so we need to know whether that null is already published.

**Q3. Stage-wise failure attribution in an LLM knowledge-graph QA pipeline.**
Our strongest empirical finding is that when such a pipeline fails, the loss is
concentrated in **planning** — deciding what to look up — rather than in query
generation or in answer synthesis, and that faithfulness failures are a small
minority of failures. Is there prior work that mechanically localises the last
pipeline stage at which the correct answer was still recoverable? Look for
ablation studies, error taxonomies, and failure-mode analyses in KGQA,
text-to-SQL, GraphRAG, and agentic retrieval. Also check the routing literature,
which reports high routing accuracy alongside low answer accuracy.

**Q4. Hand-written templates versus schema-derived generic query construction.**
We measured these head to head and found templates are **not** more accurate;
they buy precision on the schema they were written for and reliable abstention,
and they cost coverage — and the precision advantage **reverses** on a schema
nobody wrote templates for. Has this trade been measured before? Look for
template-based KBQA compared against schema-guided or ontology-driven query
construction, and for any paper reporting a precision/recall crossover between
them across schemas.

### Tier 2 — supporting. Answer as well as budget allows; flag any you could not cover.

**Q5. Abstention that carries its proof.**
Systems that decline to answer are common. Is there a published system whose
abstention returns **the executed query** as the artifact justifying the refusal,
so a reader can check that the absence is real rather than a hedge? Search
attribution, verification, selective prediction, and "I don't know" work in
QA/KGQA — and specifically anything using provenance as the abstention warrant.

**Q6. Benchmark authorship bias, measured.**
We quantified how much a question set written alongside the system that answers
it inflates the score — same system, same grader, same session, ~5 points. This
is **not** training-data contamination, which is well covered. It is bias from
the benchmark being *authored by the developers of the system under test*. Is
this effect named and measured anywhere? Check benchmark-integrity, construct
validity, and evaluation-methodology literature.

**Q7. A graph-query benchmark over ATT&CK or CAPEC.**
We believe none exists — existing ATT&CK question sets are flat text or
text-with-retrieval, and the text-to-Cypher benchmarks cover Wikidata and
enterprise graphs, not security taxonomies. Verify or refute. Extend the check
to CVE, CWE, D3FEND and ATLAS. Also: is there any ATT&CK/CAPEC question set with
**human-written** questions, as opposed to template- or LLM-generated questions
with humans validating?

**Q8. Security of natural-language interfaces to graph databases.**
Text-to-SQL has a small literature on injection and on unsafe generated queries.
Is there a graph-query equivalent — read-only enforcement, schema-boundary
refusal, adversarial probe suites against NL-to-Cypher or NL-to-Gremlin systems?

**Q9. Cross-source leakage in multi-source retrieval.**
When a system retrieves from several sources for one question, records from a
source the question was not about can reach the answer. In a multi-tenant
deployment that is a confidentiality failure that a per-query safety check
cannot see, because each individual query is legal for the store it was sent to.
Is this measured anywhere — multi-tenant RAG, federated retrieval, or
access-control-aware KGQA?

---

## 4. How to search

**Search each question in the vocabulary of at least three fields.** Getting
scooped by a paper you never found is almost always a terminology failure. For
each question, run the KGQA/NLP phrasing, the databases/data-integration
phrasing, and the security/SOC phrasing. Examples of the split:

- *NLP/KGQA*: knowledge graph question answering, KGQA, GraphRAG, text-to-Cypher,
  text-to-SPARQL, semantic parsing, query templates, schema linking, tool
  routing, agentic retrieval
- *Databases*: federated query processing, mediator-wrapper, polystore,
  multistore, virtual integration, ontology-based data access, query
  translation, cross-model query, data virtualisation
- *Security*: cyber threat intelligence, ATT&CK, CAPEC, security knowledge
  graph, SOC copilot, threat-intelligence question answering, CTI automation

**Cover, for each question:** the seminal/canonical work; the last 24 months
including **arXiv preprints and workshop papers** (our closest known match is a
workshop paper — the scoop risk lives there, not in the main proceedings);
surveys and position papers; and **negative-result and critique papers**, which
are load-bearing here because several of our own findings are nulls.

**Venues worth targeting directly:** ISWC (and its workshops), ESWC, VLDB,
SIGMOD, ICDE, EDBT, ACL, EMNLP, NAACL, NeurIPS Datasets & Benchmarks, AAAI,
WWW, CIKM, CCS, USENIX Security, NDSS, IEEE S&P, ACSAC, RAID, and the
LLM-for-security and RAG workshop circuit.

---

## 5. Standard of evidence — this part is not optional

1. **Never cite a paper you have not opened.** A plausible reference to a paper
   nobody retrieved is the fastest way to lose a reviewer, and it is the specific
   failure this audit exists to prevent.
2. **Mark every unverified field.** If you could not confirm a venue, a year, an
   author list or a number from a fetched page, tag it and say so. Do not
   silently drop the caveat.
3. **Do not accept an abstract as evidence about a results section.** If a claim
   turns on what a paper *measured* — especially "it reports no evaluation" —
   read the results and limitations sections or state that you could not.
4. **Distinguish peer-reviewed from preprint, and name the venue.** A workshop
   paper and a main-track paper carry different weight against us, and we need
   to know which we are facing.
5. **State negatives honestly.** Write "not found in a search of X, Y, Z on
   [date]", never "does not exist". Give the exact query strings you ran for
   every negative finding, so the null is reproducible.
6. **Report what contradicts us most prominently.** If one paper collapses a
   claim, lead with it.

Three real errors from our own record, as a calibration of the standard:
a widely repeated statistic turned out to be absent from the paper it was
attributed to; a benchmark's `human_question` column means *a human wrote the
generator script*, not that a human wrote the question; and a frequently cited
2025 paper is routinely attributed to the wrong conference. All three survive
casual checking and fail on retrieval.

---

## 6. Deliverable

1. **Verdict table** — one row per question Q1–Q9: verdict, closest work
   (full citation, venue, year, peer-reviewed or preprint), one-sentence delta,
   and your confidence in the check itself.
2. **Scoop watch** — every work that partially overlaps, with what it covers and
   what it leaves open. Rank by threat.
3. **The surviving claim** — write, in one paragraph, the strongest novelty
   statement this system can honestly make given everything above. Then write
   the sentence a hostile reviewer would use to dismiss it, and say whether we
   can answer that sentence.
4. **What we should stop claiming** — any claim above that the literature kills.
5. **Search log** — queries run per question, per field vocabulary, with dates
   and result counts, so that the negatives can be re-run.
6. **Annotated bibliography** — every work retrieved, with a one-line
   *how it differs from us*. An entry without that line is a bookmark, not
   related work.
