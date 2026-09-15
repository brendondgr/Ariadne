# Open-question answering from cards and graphs

## Recommendation

Make **discovery → interpretation → evidence collection → answer** explicit
stages. Keep multiple plausible interpretations until the question and retrieved
evidence distinguish them. Use source metadata to describe capabilities and
graph records to supply facts. Measure each stage independently and then measure
the whole system on new analyst questions.

The desired unit of reuse is a graph operation, such as filtering records or
following a declared relationship. A question template encodes one phrasing;
an operation can serve many phrasings and many datasets.

## What the current code actually limits

- `canonical.deterministic_fill` selects datasets before looking up names and
  returns when source selection fails. The first source with name hits also
  wins the search loop; collisions across sources need an explicit treatment.
- `IntentForm` represents describe/enumerate/count with an anchor and one
  relationship. It is too small for arbitrary combinations of comparisons,
  filters, negation, aggregation, multiple anchors, and multi-hop requests.
- Rendering that form back into English sends interpretation through another
  wording-sensitive router. Preserving IDs alone does not preserve intent.
- `namesearch._canonical_docs` uses catalogue-specific ID normalization and
  excludes identifiers containing a colon. Some graph nodes that carry useful
  descriptions therefore cannot enter its candidate list.
- Schema validity establishes that a query is allowed and structurally possible.
  It does not establish that it expresses the user's question. The same applies
  to a grounded answer about the wrong entity.
- Current source cards do not fully declare portable public-ID formatting or
  preferred searchable fields. Exact public-ID search in the new prototype is
  incomplete where those values are absent from canonical properties.

## Ideas and falsifiable next experiments

| Priority | Idea | Main beneficiaries | Portable mechanism | Test that could reject it |
|---|---|---|---|---|
| First | Source-independent exact lookup | T3; ID/name source routing | Query each authorized live source's identity/name capability, then route from matches | Cross-source name collisions or unrelated name mentions increase wrong binding |
| First | Search names, aliases, and descriptions as separate views | T4/T5 | Card-declared fields; bounded candidate lists with canonical identity | Candidate recall fails to beat pooled text at equal budget |
| First | Interpret intent without rewriting away anchor identity | T1/T2 and all tiers | Bind immutable anchors separately; select operations, roles, filters, and paths from card/schema vocabulary | Exact IDs remain correct but relation/direction or filter accuracy does not improve |
| Next | Rerank candidate–plan pairs using evidence | T4/T5 | Compare original question with candidate properties and a bounded graph neighborhood | Higher answer coverage comes with more wrong entities or constraint violations |
| Next | Collect evidence against an explicit answer checklist | All tiers | Requested properties/relations plus pagination state drive additional queries | Extra hops add irrelevant rows or cost without improving answer recall at matched precision |
| Next | Ask one discriminating clarification | Ambiguous T4/T5 and open questions | Present candidate differences supported by records; carry the reply as a constraint | Users need frequent questions when their original request was already answerable |
| Later | Multi-anchor and global question plans | Questions beyond T1–T5 | Composable select/filter/traverse/join/intersect/aggregate/compare operations; evidence-backed synthesis | A new question shape requires a catalogue-specific template or loses an explicit constraint |

These priorities are a proposal, not a ship decision. The lexical ablations in
this experiment measure only the second row and a candidate-search portion of
the first. [RESULTS.md](RESULTS.md) determines which search arm merits more work.

### 1. Let discovery supply source evidence

Start with all authorized, live sources, not the source whose schema happens to
share the question's words. Preserve `(source, canonical record ID, label)` and
matching evidence. An exact name is an observation about a phrase; it does not
prove that the entity is the subject rather than a comparison target.

Prototype the Q59 change behind an explicit experiment option in
`utils/planner/canonical.py`, compare with D-035 on the same captures, and test
colliding names across sources. Preserve explicitly requested sources, all
anchor mentions, and declared cross-source joins. A lookup in a source does not
authorize adding another source to the plan.

### 2. Separate retrieval recall from acceptance precision

Search name/alias text, descriptive properties, and optionally semantic text
similarity. Fuse candidate lists using ranks, since raw backend scores are not
comparable. A small language model may expand the *description* into several
search queries using source vocabulary; only graph-returned identities may
become candidates. Evaluate expansion separately from candidate reranking.

Use graph context selectively after initial retrieval: attached descriptions,
parent relations, and neighbors can resolve an ambiguity. Flattening all of
those words into every candidate can make a detector, tool, or sibling look like
the requested entity. The graph arm here deliberately tests that simple approach
before recommending it.

Keep a model-free lexical option available. A semantic model would be an
optional adapter, versioned and benchmarked against lexical search on independent
data. It cannot supply facts missing from the source.

### 3. Bind the anchor and interpret the task independently

For a question such as “what stops T1047?”, retain the supplied identifier and
interpret the requested action using the source's relationship glosses. The
model can choose a declared path or say the operation is unknown; it must not
replace the identifier. The current ID gate blocks rewriting wholesale, so
improving this tier needs a more precise separation of those responsibilities.

Build a structured request passed directly to specialist primitives. Its fields
should include anchor roles, target properties, filters (including negation and
time), typed paths, aggregation, and the requested output shape. Preserve spans
from the original request as interpretation provenance. Reject or clarify
unrepresented constraints rather than silently dropping them.

Extension points: `IntentForm`/`requested_slots`, `rewrite_llm.apply_choice`,
`DatasetSchema`, `schema/paths.py`, and the existing generic query builders.
Keep the existing wording path as a comparison arm until direct operation plans
are tested. A structural gate remains necessary but cannot grade semantic fit.

### 4. Test competing interpretations against evidence

Represent a hypothesis as **candidate + requested operation/path + constraints**.
Retrieve a small amount of discriminating evidence for several hypotheses,
then rerank against the original question. For a vague description of Windows
administration, compare the actual mechanisms described by the candidate nodes;
the presence of a mitigation edge alone cannot choose the right one.

Use bounded path exploration with fixed query/time/row budgets, expand promising
paths, and keep “none of these” available. A proposed reranker chooses only among
retrieved candidates and records supporting and contradicting fields. Calibrate
acceptance on independently labeled ambiguous and absent-entity cases. Scores,
score margins, and model self-reported confidence are not calibrated confidence.

An architectural precedent is interactive, bounded graph exploration in
[Think-on-Graph](https://arxiv.org/abs/2307.07697). That mechanism motivates an
Ariadne experiment; the paper does not establish an improvement for this system.

### 5. Make completeness observable

Turn the requested output into explicit obligations: intended entities resolved,
requested relations queried, filters applied, requested properties present,
declared joins checked, and all needed pages retrieved or marked partial.
Drive `assess`/`replan` from unmet obligations rather than generic evidence
presence. Distinguish a verified empty result, an unresolved question, missing
source data, and an exhausted retrieval budget.

Extend `utils/orchestration/agents/assess/policy.py` and the existing
`describe`/`expand` primitives; preserve deadlines, per-source limits, pagination
cursors, and truncation flags. Re-fetch and validate candidate identities against
the live snapshot before treating cached search text as current evidence.

### 6. Treat ambiguity as a useful intermediate result

When several interpretations survive, ask a short question based on their
differences: “Do you mean remote administration or local script execution?”
Offer only alternatives supported by the retrieved records. Where appropriate,
answer both conditionally with separate citations instead of selecting one.

Evaluate successful completion after clarification and the number of turns,
alongside answer correctness. A system that asks on every question has not
solved open-question answering. The experimental API exposes candidate reasons;
the workbench conversation flow is future integration work.

### 7. Give broad questions a different plan shape

“Which controls cover several mechanisms, and where are the gaps?” requires a
set, paths, aggregation, and comparison. It may have no single intended anchor.
Do not force it through entity lookup. Select the relevant subgraph using
declared scope, compute grounded groups/counts, and synthesize with coverage and
omission statements. An unrecorded edge means “not established in this graph,”
not “does not exist in the world.”

[GraphRAG's local/global distinction](https://arxiv.org/abs/2404.16130) motivates
evaluating synthesis questions separately from entity lookup. Its document-to-
graph and community-summary construction is not required for Ariadne, which
already has curated graphs; any summaries here must retain traceable evidence.

## Minimal source onboarding contract

| Source-supplied information | What generic code can do with it |
|---|---|
| Schema labels, properties, edge endpoints, and readable glosses | Construct valid operation/path candidates and interpret vocabulary |
| Canonical identity and explicit public-ID/alias mappings | Find the same record without catalogue-specific normalization |
| Name, alias, and descriptive field roles per label | Build search views without guessing which strings matter |
| Snapshot/version and access scope | Invalidate stale candidates and restrict discovery before search |
| Query limits and supported capabilities | Bound execution and make unsupported tasks explicit |
| Declared canonical join keys | Correlate sources without equating similar names |

Prefer generated structural metadata plus a small authored layer of field roles
and glosses. Source cards alone cannot answer instance-level questions if no
record data is accessible. An opaque graph whose labels and properties have no
meaningful descriptions also needs semantic metadata. Adding a source on an
existing backend should require a card/mapping and registration; a new query
language still needs its executor and validator adapter.

For live Neo4j, full-text indexes support multiple string properties and return
ranked nodes, providing a backend-native implementation option. This is not yet
integrated with Ariadne's query gate or deployed databases.
[Neo4j full-text index documentation](https://neo4j.com/docs/cypher-manual/25/indexes/semantic-indexes/full-text-indexes/).

## Evaluation that can establish portability

1. Keep the existing tier bank as a regression suite. Attribute failures to
   discovery, selection, intent, execution, completeness, or synthesis.
2. Author new questions independently of catalogue templates and gold answer
   wording. Include near-neighbor entities, misleading shared vocabulary,
   multi-entity questions, absent facts, typos, ambiguity, negation, and filters.
3. Hold out entity families and question authors, not just paraphrases of the
   same entities. Split retrieval/reranker tuning from acceptance calibration and
   sealed evaluation. Preserve paraphrase families when bootstrapping uncertainty.
4. Add an unrelated source using only declared metadata and a supported backend.
   Do not permit core retrieval changes after its evaluation bank is exposed.
   The small library tests here verify the interface only.
5. Measure candidate recall, accepted-entity precision and coverage, relation/
   direction/filter fidelity, answer-record precision/recall/exactness, judged
   usefulness and completeness, wrong-entity answers, clarification turns,
   truncation, latency, and query/model cost. Never compare candidate recall with
   the shipped answer-recall column as if they measured the same outcome.
6. Compare systems at matched error rates and matched budgets. Use independent
   evidence-grounded grading plus human checks of disputed/ambiguous examples.
   Any ship rule must be frozen before the sealed run; this exploratory diagnostic
   chooses no new accuracy threshold and makes no claim about reaching the bar.

## Proposed implementation order after this prototype

First test Q59 and immutable-anchor intent interpretation independently. In
parallel as a research track, compare description retrieval plus constrained
reranking with the best lexical arm from this experiment. Next add evidence
obligations and targeted graph exploration. Then test clarification, compound
questions, and transfer to an unrelated source. Each stage earns adoption by
improving end-to-end outcomes under the same wrong-entity and cost constraints.
