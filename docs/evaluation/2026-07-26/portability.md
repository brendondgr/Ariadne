# Portability — What Survives a New Dataset

Written to answer: *if the grant hosts hand us a real dataset, does any of this
transfer, or is it back to zero?*

**Short answer: most of it transfers, and the part that doesn't is well-bounded
and countable.** Roughly 19 hand-written query templates and a handful of
id-shape regexes are MITRE-specific. Everything else — the orchestration, the
retrieval loop, synthesis, verification, provenance, and the entire evaluation
apparatus — is driven by the *source card*, not by MITRE.

The honest caveat up front: **the 0.9957–0.9972 scores in this evaluation came
from those MITRE-specific templates.** A new schema starts on the generic path,
which is real but unmeasured at scale. You would not be at zero; you would not be
at 0.99 on day one either.

---

## 1. Three layers, three different answers

### Layer 1 — Harness and orchestration: **fully portable**

Nothing here knows what MITRE is.

| Component | Why it transfers |
|---|---|
| LangGraph super-graph (probe → plan → specialists → assess → re-plan → synthesize) | Operates on `Plan`/`SpecialistResult`/`FederatedEvidence`, all schema-neutral |
| Sufficiency policy + hop cap + termination guarantee | Reads join closure and facet frontier, both derived from data |
| `append_new` reducers, streaming/SSE contract, timeouts, degradation | Pure plumbing |
| Claim composition, verifier, abstentions, provenance chain | Operates on records and citations |
| **The whole evaluation apparatus** — arm runner, `failure_terminus.py`, the 120-agent judge panel, summarizer | Reads artifacts; only the id regex in `failure_terminus` is MITRE-shaped (one line) |

The evaluation apparatus is, arguably, the most valuable thing built here. The
ability to run a configuration over a catalogue, have it independently graded
per-question, and then mechanically locate *which stage* lost the information —
that is dataset-independent methodology and it is what found all eight defects.

### Layer 2 — Card-driven extraction: **portable, this is the generic path**

The `describe` / `expand` primitives plus the facet loop are the schema-agnostic
answer path, and they are *designed* for an unknown schema:

* `describe(anchor)` returns **every** property on the node plus a **facet
  block** — a count of adjacent nodes grouped by `(relationship, direction,
  neighbour label)`. It needs no template and no prior knowledge of the schema.
* The facet block is an honest, complete map of what exists around a node,
  including **zeros** folded in from the schema registry, so a model can assert
  absence.
* `expand` fetches a facet's members.
* The **facet-chasing loop** built during this evaluation turns those counts into
  content: it ranks facets against the question, emits expansion sub-questions,
  and resolves each relationship **through `card.relationship_types`** rather
  than through hard-coded names. (That indirection exists because CAPEC's own
  card mixes conventions — `ChildOf` beside `HAS_MITIGATION` — which forced the
  generic solution.)

So on a brand-new schema the pipeline can already: resolve an anchor → describe
it → see its real neighbourhood → expand what the question implicates → compose
cited claims → narrate them. That is a working system, not a stub.

**What you must supply per source:** a **source card** — node labels,
relationship types, safety limits, id scheme, connection details — plus the data
loaded into Neo4j or Gremlin. That is the intended extension point and it is
declarative.

### Layer 3 — MITRE-specific assets: **must be re-authored**

Counted, not estimated:

| Asset | Count | Notes |
|---|---|---|
| Named query templates | **24 total**, of which ~**19 are MITRE-specific** | `capec_maps_to`, `technique_mitigations`, `group_techniques`, `cwe_chain`, `subtechnique_parent`, … |
| Generic templates (survive as-is) | **5** | `describe`, `describe_by_name`, `expand`, `label_scan`, `node_lookup` |
| Id-shape regexes | ~6 | `T\d{4}`, `CAPEC-\d+`, `CWE-\d+`, `M\d{4}`, plus the Gremlin composite forms |
| Canonical join keys | 1 | `attack-technique-id` (CAPEC↔ATT&CK bridge) |
| Relationship→noun map (`_REL_NOUNS`) | ~16 entries | Degrades gracefully to the neighbour label if unmapped |
| Golden catalogue | 120 questions | Hand-authored against MITRE |

---

## 2. What actually happens on a new schema, by scenario

### A. Same shape, new content (e.g. a bigger/newer ATT&CK + CAPEC dump)

**Essentially free.** Reload, re-run. The templates, ids and join keys still
apply. The gold catalogue's *expected values* would need refreshing where the
data changed, but the questions and the harness stand. This is the case the
system is already built for — `main.py --dataset … --graph …` plus a bank
recompile.

### B. New domain, similar shape (entities with typed relationships and stable ids)

**Days, not weeks.** You would need:

1. A source card for the new graph — declarative.
2. Id regexes for the new id convention, in `resolve/` and `grounding.py`.
3. A gold set to measure against. *This is the real cost*, and it is unavoidable
   for any evaluation-driven work.
4. Optionally, templates for the high-value traversals.

Without step 4 you get the generic `describe` + facet-loop path. With it you get
the accuracy this evaluation measured.

### C. Genuinely alien schema (no stable ids, free-text keys, hypergraph, …)

**This is where it hurts**, and the specific thing that breaks is *not* the
templates — it is **entity resolution**. The pipeline seeds every question by
extracting an anchor from the question text (`T1047`, `CAPEC-555`). With no
stable id convention there is nothing to extract, and the deterministic planner
already struggles here: on the raw question *"What mitigations does ATT&CK list
for T1047?"* it resolved entities as `['Matrix', 'Mitigation']` — reading
"ATT&CK" as the Matrix node and missing T1047 entirely. The LLM planner is what
rescues that today.

You would need a real resolution layer (alias table, embedding search, or an
LLM resolver) before any of the retrieval machinery could be pointed at it.

---

## 3. The honest risk

The scores in this evaluation are **not** evidence that a new dataset will score
0.99. They are evidence that *this architecture, with hand-authored templates for
the question shapes being asked*, reaches 0.99.

The measurement that bears most directly on the new-dataset case is uncomfortable
and worth stating plainly: **when the router missed a template and fell back to
`describe`, accuracy collapsed** — A-DET scored 0.20 in the LLM-planned arm
because the planner produced a facet-count query instead of the detection
traversal. `describe` alone answers *"how many"*, not *"which"*.

The facet loop built during this evaluation is exactly the fix for that, and it
demonstrably works — C-HIE-01 went from retrieving nothing to coverage 1.0 via a
genuine second hop. But it has only been measured **on top of MITRE templates**,
never as the sole retrieval path. **That is the experiment to run before
committing to a new dataset**, and it can be run today on the existing graphs by
disabling the specific templates and forcing the generic path. It would answer
"what do we score on a schema we have no templates for?" without needing the new
data at all.

---

## 4. Recommended sequence when the dataset arrives

1. **Ask for the schema before the data.** Node labels, relationship types, id
   conventions, and whether ids are stable. That alone determines which scenario
   above you are in, and it is a five-minute conversation.
2. **Run the no-templates experiment now** (§3) so you know the generic floor
   before you are under time pressure.
3. **Write the source card first.** It is the contract; everything downstream
   reads it.
4. **Author a small gold set early — 20–30 questions is enough to steer.** You
   cannot improve what you cannot measure, and the judge harness makes a small
   set genuinely useful.
5. **Add templates only where the generic path measurably falls short.** Let
   `failure_terminus` tell you which stage is losing information rather than
   guessing.
6. **Keep the deterministic path as the reference.** It is the fastest, most
   reproducible configuration and the cleanest baseline against which to judge
   anything new.

---

## 5. One-line answer

Not useless, and not free: **the engine, the loop, and the entire measurement
apparatus port directly; the ~19 MITRE query templates, the id conventions and
the 120-question gold set do not.** The generic `describe` + facet-expansion path
means a new schema gets a working system immediately, at an accuracy that is
currently unmeasured — and measuring it is a one-day experiment you can run
before the data ever arrives.
