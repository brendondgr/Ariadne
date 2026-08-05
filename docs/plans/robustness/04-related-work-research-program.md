# Plan 04 — Related-work research program

**Audience:** a coordinator plus a team of research agents.
**Location:** a **separate, self-contained repository**. Nothing here writes into
the Ariadne tree until the synthesis is delivered and verified.
**Goal:** turn Positioning from 0/4 into 3/4 by producing a related-work section
grounded in papers that were actually retrieved and read, plus the annotated
evidence base behind it.
**Prerequisite:** none. Start immediately, in parallel with everything else.
**Duration:** ~5 days of coordinator time; the six agents run concurrently.

---

## 0. Why this is a research programme and not a writing task

Positioning scored **0/4** in the 3 August audit — the lowest score on any axis
— because there is no related-work engagement anywhere in the Ariadne
repository. `docs/references/` is implementation notes. The only substantial
scholarly material in the tree is the ~90-entry bibliography inside the audit
document, which the project's authors did not write and have not verified. No
non-demo venue will accept a submission without this section.

**The failure mode is specific and it is fatal.** An LLM asked to write a
related-work section will produce fluent, plausible, correctly-formatted
citations to papers that do not exist, or that exist with different authors,
venues, years, or findings. A section like that does not leave Positioning at 0
— it moves the project from *has a gap* to *has a credibility problem*, which is
unrecoverable in review.

Every rule below exists to make that outcome structurally impossible rather than
merely discouraged. The central mechanism is simple: **a citation may only be
written if a corresponding artifact was retrieved and stored.** No artifact, no
citation. Memory is not a source.

---

## 1. Repository bootstrap

Create `ariadne-relatedwork/` outside the Ariadne tree.

```
ariadne-relatedwork/
├── README.md                     # what this is, current status
├── AGENTS.md                     # the shared rules — every agent reads first
├── assignments/
│   ├── A1-federated-query-processing.md
│   ├── A2-text-to-graph-query.md
│   ├── A3-agentic-kg-retrieval-security.md
│   ├── A4-cti-kgs-benchmarks-merged-graphs.md
│   ├── A5-provenance-grounding-abstention.md
│   └── A6-entity-reconciliation-mapping-quality.md
├── papers/
│   └── <citekey>/
│       ├── paper.pdf             # if retrievable
│       ├── meta.json             # always
│       └── notes.md              # always
├── reports/
│   └── A1-federated-query-processing.md   # one per assignment
├── bib/
│   ├── refs.bib
│   └── refs.json                 # machine-checkable mirror
├── synthesis/
│   ├── related-work-draft.md     # the deliverable
│   ├── positioning-matrix.md     # Ariadne vs each close system, axis by axis
│   └── threat-register.md        # ranked scoop risks
└── _audit/
    ├── claims-ledger.csv         # every factual claim → its source
    ├── acquisition-log.jsonl     # every retrieval attempt, success or not
    └── unverified.md             # everything that could not be confirmed
```

`papers/` may be gitignored if size is a problem, but `meta.json` and `notes.md`
must be committed for every entry — they are the audit trail.

---

## 2. `AGENTS.md` — the shared rules

Write this file first. Every agent reads it before its assignment. These rules
are not negotiable and an agent that cannot follow one should report the
blockage rather than work around it.

### 2.1 No citation without an artifact

Before writing any citation, `papers/<citekey>/` must exist and contain a
`meta.json`. If the PDF could not be retrieved, `meta.json` records why and the
entry is marked with a lower read-depth (§2.3). **A citation with no directory
is a fabrication and will be treated as one.**

### 2.2 Acquisition rules

Retrieve openly available PDFs from: arXiv, ACL Anthology, CEUR-WS, USENIX,
NDSS, open-access publisher pages, institutional repositories, and authors'
own copies.

**Do not attempt to circumvent paywalls.** No Sci-Hub, no mirrors of
subscription content, no credential sharing. If ACM DL, IEEE Xplore,
ScienceDirect or Springer blocks retrieval, record the block in
`acquisition-log.jsonl`, capture whatever metadata and abstract are publicly
visible, and mark the entry `metadata_only`. The 3 August audit already hit this
wall — "ACM DL, ScienceDirect and OpenReview returned empty bodies or bot walls"
— so expect it and handle it honestly rather than filling the gap from memory.

Log every attempt, successful or not, one JSON object per line: timestamp,
citekey, URL, method, outcome, bytes retrieved.

### 2.3 Read depth is declared, per paper

Every entry carries exactly one:

| Depth | Means |
|---|---|
| `full` | PDF retrieved and read end to end |
| `partial` | PDF retrieved; specific sections read, named in `notes.md` |
| `abstract` | Abstract read; full text unavailable or not read |
| `metadata_only` | Title/authors/venue/year confirmed from an authoritative index; content not read |

**A `metadata_only` entry may never be the sole support for a factual claim
about what a paper found.** It can support "work exists in this area." It cannot
support "X reports Y."

### 2.4 Every number carries a location

Any figure quoted from a paper — an accuracy, an F1, a dataset size — records
the section, table number or page it came from. `notes.md` stores the quote
verbatim alongside it. A number without a location does not go in the report.

### 2.5 Flag your own uncertainty

If a venue cannot be confirmed, if two sources disagree on a year, if a figure
appears inconsistent within the paper itself — say so inline with a ⚠️ and add it
to `_audit/unverified.md`. The audit being fact-checked found a real instance of
this: CTIArena's prose says "0.99 on ATD" where its own Table II says 0.09.
Catching that is more valuable than a clean-looking report.

### 2.6 The claims ledger

Every factual claim that will appear in the synthesis gets a row in
`_audit/claims-ledger.csv`:

```
claim_id,claim,citekey,location,read_depth,verified_by,confidence,notes
```

The coordinator spot-checks 20% of rows at random before synthesis. Any
unsupported row means that agent's entire report is re-verified.

### 2.7 What you are writing for

Ariadne is a **read-only federated query mediator** over two live property-graph
engines — MITRE ATT&CK in Neo4j/Cypher, MITRE CAPEC in a TinkerPop Gremlin
Server. It answers natural-language analyst questions by routing sub-questions to
per-engine **parameterised query templates** (not LLM-generated queries), joining
results on shared ATT&CK technique IDs, and verifying every claim against the
records actually returned, with enforced abstention carrying the executed query
as proof. **No vector index or embedding store is built over the graph content.**
An LLM optionally rewrites prose from already-verified claims.

Its central measured finding: a validated template library beats free-form LLM
query planning by 0.12 correctness at ~1/600th the wall clock, and beats
schema-primitives-only by 0.36.

Every report answers, for its area: **what does this field already know, what
would a reviewer from it demand, and what can Ariadne honestly claim here.**

---

## 3. The six assignments

Each runs independently. Each produces one report in `reports/`.

### A1 — Federated query processing and source selection

The mature line, largely settled by ~2018, and the one that will produce the
harshest reviewer.

Cover: mediator/wrapper architectures and virtual integration; federated SPARQL
engines (FedX, SPLENDID, HiBISCuS, CostFed, Odyssey); source selection and
triple-pattern-wise selection; cost-based join planning over engines you do not
control; the benchmarks — FedBench, LargeRDFBench, FedShop; and the recent
agentic turn, including the SPARQL-MCP agentic federated KGQA evaluation
(arXiv 2603.06582) reporting ~42–45% on Spider4SPARQL.

Answer specifically: **what does this community consider table stakes?** Ariadne
does source selection by token matching against schema-derived vocabulary and
has a fixed producer-then-consumer execution order with no cost estimation. Name
precisely what is therefore *not* claimable, so the paper can concede it first
rather than have it extracted.

### A2 — Text-to-graph-query

Cover: Text2Cypher (arXiv 2412.10064) and its benchmark and metrics; reported
execution-accuracy ranges on public benchmarks; the ~0.189 figure on an unseen
production graph — **find and verify the primary source for this**; ISO/IEC
39075:2024 GQL and zero-shot text-to-GQL results; Multi-Agent GraphRAG
(arXiv 2511.08274); and the template-based KBQA family — Bast & Haussmann
CIKM 2015, Zheng et al. PVLDB 2018 — which is the named prior art for "use
templates rather than generation."

Answer specifically: **is text-to-Gremlin genuinely empty?** Preliminary
searching found no established benchmark. Confirm or refute it with named
searches, because "no text-to-Gremlin benchmark exists" is a load-bearing claim.
And establish exactly how novel "templates beat generation" is as a *claim*
versus as a *measurement* — the distinction Ariadne's contribution rests on.

### A3 — Agentic KG retrieval in security

The closest prior work lives here. **AgCyRAG is the priority and the report
should lead with it.**

Cover: AgCyRAG (Kurniawan et al., RAGE-KG @ ISWC 2025, `ceur-ws.org/Vol-4079/paper11.pdf`
— openly available); CyKG-RAG; SEPSES CSKG (ISWC 2019); the ATT&CK-KG (ISWC 2021);
ICS-SEC KG; CRAKEN (arXiv 2505.17107); ARCeR (arXiv 2504.12143); CyberGuardian 2;
and the agentic-RAG surveys.

For AgCyRAG specifically, establish and quote: its exact architecture (guardrail,
vector, Cypher, SPARQL, reflection, synthesis agents); which store holds what —
note its Neo4j holds *parsed auth logs*, not a curated catalogue; whether it
reports any quantitative evaluation at all; and its limitations statement about
predefined queries "significantly improving the quality of answers." **Verify
that quote verbatim against the PDF.** It is the hinge of Ariadne's positioning:
a named prior system asserts Ariadne's central claim and never measures it.

Then answer: **how much of the architecture does AgCyRAG scoop, precisely?**
Write the honest version. If the answer is "most of the architecture," that is
what the report says, and the positioning shifts entirely onto measurement.

### A4 — CTI knowledge graphs, benchmarks, and the merged-graph alternative

Cover: CTIArena / CTIConnect (arXiv 2510.11974); CTIBench; SEvenLLM; CyberPal.AI;
the ATT&CK SoK (arXiv 2304.07411); and — importantly — **ATT&CK to CVE: A
Large-Scale Automated Knowledge Graph for Threat Intelligence** (IEEE Xplore
document 11416114), which merges NVD, CWE, CAPEC and ATT&CK into a single Neo4j
with daily sync.

Two jobs. First, **extract the motivation ammunition**: CTIArena's closed-book
results on cross-taxonomy correlation (CAPEC→ATT&CK ≈0.09, CWE→CAPEC ≤0.01
across ten frontier models), its "long-tail enumerated knowledge that is rarely
absorbed during pretraining" diagnosis, its "unsupported correctness" measurement
(3% overall, 7% GPT-4o), and its retrieval-F1 figures. Verify each against the
paper, note the internal inconsistencies, and record the exact locations. These
are the numbers that kill "why not just ask the model."

Second, **characterise the merged-graph alternative fully.** It is the thing a
reviewer will point at and ask why Ariadne did not just do that. What does it
merge, how does it reconcile ids, what does it lose, does it evaluate anything?

### A5 — Provenance, grounding and abstention over structured data

The thinnest area, and the one where Ariadne is strongest.

Cover: provenance models for query results (why/where/how-provenance, the
database-theory line); attribution and citation in RAG and its evaluation;
faithfulness and groundedness metrics; abstention and selective prediction in QA,
including coverage-risk tradeoffs; verification of LLM claims against retrieved
evidence; and LLM-as-judge reliability, including documented bias and
self-preference effects.

Answer specifically: **is there prior work that verifies claim-level identifier
grounding against executed structured-query results and enforces abstention
carrying the query as proof?** If the answer is genuinely no, that is a defensible
secondary novelty claim and needs the negative search documented rigorously —
list the formulations tried. Also establish what the standard evaluation
protocols are, since Ariadne will be judged against them.

### A6 — Cross-source entity reconciliation and mapping quality

The area that supplies Ariadne's biggest threat and, handled well, its most
interesting limitation.

Cover: entity alignment and reconciliation across knowledge graphs; critiques
showing benchmarks measure name overlap and assume bijections that do not hold;
and — the priority — the **empirical literature on CAPEC↔ATT&CK mapping quality**.

Find and verify the sources behind the disputed figures: that only ~25% of
ATT&CK techniques reference CAPEC and ~20% of CAPECs reference ATT&CK; claims
about directional inconsistency; and any published critique of the transitive
CWE→CAPEC→ATT&CK chain.

This matters because Ariadne's own measurements are 177 of 558 live CAPEC
patterns carrying any ATT&CK mapping, 271 mapping edges, 256 resolving. If the
literature independently reports the same thinness, it stops being a weakness of
this project and becomes a **published characteristic of the domain** — which is
simultaneously the strongest argument against eagerly materialising the merge.
Get the citations right; the framing depends on them.

---

## 4. Report structure

Identical for all six. `reports/<assignment-id>.md`.

**1. Scope and search protocol.** Every query string run, every source searched,
dates. Someone must be able to repeat your search. Include the searches that
returned nothing — negative results are evidence.

**2. Landscape map.** ~500 words. What the area is, its main threads, roughly
when each settled or is still contested, who the active groups are.

**3. Annotated bibliography.** Per paper: citekey; full citation; venue and year;
read depth; what it does in two sentences; method; what it evaluates on; **key
numbers with locations**; relevance to Ariadne; and a threat rating —
`scoops | overlaps | adjacent | background`.

**4. The five closest papers.** For each, an explicit verdict: *does this scoop
Ariadne, and if not, what precisely is the difference?* One paragraph each,
written to survive a reviewer who has read the paper and you have not fooled.

**5. Numbers table.** Every citable figure this area offers, with citekey and
location. This is what the Ariadne paper will quote, so it must be checkable at a
glance.

**6. Named gaps.** Gaps the field states about *itself*, quoted. A gap someone
else has named in print is worth more than one you assert.

**7. Claimable and not claimable.** Two lists. What Ariadne can honestly say in
this area, and what it must concede. Be harsh in the second list — conceding
early is what makes the rest credible.

**8. Unverified.** Everything you could not confirm, and what would confirm it.

---

## 5. Synthesis — coordinator only, after all six land

### 5.1 `synthesis/positioning-matrix.md`

A table: Ariadne against every `scoops` or `overlaps` system, on the axes that
actually differentiate — number of stores, whether they are separate engines,
query languages, whether queries are generated or templated, vector index or
not, provenance granularity, abstention, and **whether the system reports a
quantitative evaluation**.

That last column is likely to be the one that matters. Build the matrix before
writing prose; if it does not show a defensible gap, the positioning has to
change and it is better to learn that from a table.

### 5.2 `synthesis/threat-register.md`

Every `scoops` and `overlaps` paper, ranked by how badly it hurts, each with the
one-sentence response the paper will give. If a threat has no good response,
say so — that is a finding the project needs before a reviewer supplies it.

### 5.3 `synthesis/related-work-draft.md`

The deliverable. Four subsections mapping to A1–A2, A3, A4, A5–A6. Roughly
1,200–1,500 words for a 6-page submission.

Written to concede first and claim second. Every citation resolves to
`bib/refs.bib`; every `refs.bib` entry resolves to a `papers/<citekey>/`
directory. Run that check mechanically before delivering.

### 5.4 Delivery into Ariadne

Only after the 20% spot-check passes. Copy `related-work-draft.md` to
`docs/research/related-work.md` and `refs.bib` to `docs/research/refs.bib` in
the Ariadne repository, with a header line recording the source repository, the
commit SHA, and the date.

---

## 6. Definition of done

- [ ] Six reports, all sections present.
- [ ] Every citation in every report resolves to a `papers/<citekey>/` directory.
- [ ] Every `papers/` entry has `meta.json` with a declared read depth.
- [ ] `acquisition-log.jsonl` records every attempt, including failures.
- [ ] `claims-ledger.csv` covers every factual claim in the synthesis.
- [ ] Coordinator spot-check of 20% of ledger rows passed.
- [ ] `unverified.md` is non-empty. **An empty one means the agents were not
      being honest** — the 3 August audit could not verify EDBT 2027 or CIKM 2027
      deadlines at all, and a research pass over a live field that finds nothing
      uncertain has not looked hard enough.
- [ ] Positioning matrix shows a defensible gap, or the coordinator has escalated
      that it does not.
- [ ] Draft is 1,200–1,500 words and concedes before it claims.

---

## 7. Seed set

Give agents this starting list so nobody begins cold. **These are leads, not
verified citations** — every one still needs retrieval and a `papers/` entry
before it may be cited. Where a URL is given it was reachable on 4 August 2026.

| Assignment | Lead | Pointer |
|---|---|---|
| A1 | Agentic SPARQL / federated KGQA benchmark | arXiv 2603.06582 |
| A1 | LLM-based SPARQL generation over federated KGs | arXiv 2410.06062 |
| A1 | Framework for federated SPARQL over heterogeneous LDF | arXiv 2102.03269 |
| A2 | Text2Cypher | arXiv 2412.10064 |
| A2 | Multi-Agent GraphRAG for LPGs | arXiv 2511.08274 |
| A2 | ISO/IEC 39075:2024 GQL | iso.org/standard/76120.html |
| A2 | Bast & Haussmann, CIKM 2015; Zheng et al., PVLDB 2018 | template KBQA prior art |
| A3 | **AgCyRAG** — highest priority | ceur-ws.org/Vol-4079/paper11.pdf |
| A3 | SEPSES CSKG, ISWC 2019 | doi 10.1007/978-3-030-30796-7_13 |
| A3 | ATT&CK-KG, ISWC 2021 | ceur-ws.org/Vol-2980/paper363.pdf |
| A3 | CRAKEN; ARCeR | arXiv 2505.17107; 2504.12143 |
| A4 | **CTIArena / CTIConnect** | arXiv 2510.11974 |
| A4 | **ATT&CK to CVE merged Neo4j** | IEEE Xplore 11416114 |
| A4 | SoK: MITRE ATT&CK in research and practice | arXiv 2304.07411 |
| A5 | Sikos, Cybersecurity knowledge graphs, KAIS 2023 | doi 10.1007/s10115-023-01860-3 |
| A6 | Zhao et al., survey on CSKG construction | doi 10.1016/j.cose.2023.103524 |

One further pointer: `docs/research/audit-2026-08-03.md` §9 in the Ariadne
repository contains ~91 keyed entries assembled by a prior pass. **Treat it as a
lead list only.** It was not verified, it carries its own ⚠️ markers, and
several of its figures are known to be inconsistent. Re-verify anything taken
from it, and record it as your own retrieval — not as inherited truth.
