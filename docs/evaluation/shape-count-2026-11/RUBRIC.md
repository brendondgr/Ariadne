# Question-shape rubric (Era 2, Step 9, Phase A)

This rubric says which retrieval operations a question needs. Both labellers use it, and so do
the deterministic classifiers in `scripts/count_question_shapes.py`. It was written before any
external question was labelled.

## How to label

Give each question the **set of operations its answer needs**, using the codes below. Read the
question as a request to a knowledge graph of MITRE ATT&CK (techniques, sub-techniques, tactics,
groups, software, campaigns, mitigations, detection strategies, analytics, data components) and
CAPEC (attack patterns, categories, views, weaknesses, mitigations, and their text sections).

- Label what the **answer** needs, not how the question is worded. "Name them all" adds nothing.
  "How many … ? Name them all." needs `T.count`.
- An entity named in the question by id or name is an **anchor**. Finding it is grounding, not an
  operation, so do not label it.
- Use the **fewest** codes that produce the answer. A one-hop walk from a named entity is `T.walk`
  alone.
- If the answer is not in the graph at all, use one `X.*` code and nothing else.
- Write a rationale of at most 15 words. Do not quote the question.

## Codes

### Today's operations (what Ariadne already does)

| Code | Means | Example |
|---|---|---|
| `T.describe` | Return one named entity and its properties, including its description text. Also covers a fact stated inside that entity's own description. | "Describe software S1018." "What language is DropBook written in?" |
| `T.walk` | Follow relationships from one or more named anchors: one or more hops, fixed or bounded depth, across ATT&CK and CAPEC through their mapping. | "Which techniques does G0016 use?" "Which tactics do the techniques mapped from CAPEC-98 belong to?" |
| `T.count` | The number of results of a walk from named anchors. | "How many mitigations apply to T1021.003?" |
| `T.scan` | List members of one type, with no anchor and no condition. | "List ATT&CK software." |
| `T.common` | What several named anchors all link to, or the overlap of two walks. | "Which techniques in TA0006 are mitigated by M1027?" |
| `T.eqfilter` | One condition "property equals value" on the walked or scanned items. | "Which meta-level attack patterns are children of CAPEC-x?" |
| `T.refuse` | The graph has no such concept, and the right answer is an honest "not held". | "What assets does T1047 target?" (assets are ICS-only) |

### New operators (Step 9)

| Code | Operator | Means | Example |
|---|---|---|---|
| `O1.filter` | 1 | A condition beyond one equality: comparison, range, text contains, not-equal, several conditions, or "has this property". | "Which patterns with high likelihood and low severity…" |
| `O2.aggregate` | 2 | A number computed over a set that is not one walk from named anchors: catalogue-wide counts, sum, average, min, max, median. | "How many techniques are in the catalogue?" |
| `O3.rank` | 3 | Order and take the top or bottom: most, least, top k, largest, first by count. | "Which group uses the most techniques?" |
| `O4.verify` | 4 | Yes/no, or "how is A related to B", about a specific link between two named entities. The answer is the link (and its text) or its absence. | "Does G0016 use T1566?" "How does S0623 use T1611?" |
| `O5.typescan` | 5 | List or count every member of a type that meets a condition, with no anchor. | "Which software runs on Linux?" |
| `O6.groupby` | 6 | A result per member of a type, keeping members with none. | "For each tactic, how many techniques?" "Median techniques per group" (also `O2`) |
| `O7a.edgefilter` | 7 | A condition on a relationship's own properties. | "Techniques G0016 used, per the 2023 report" (if the edge holds the source) |
| `O7b.time` | 7 | Dates: since, before, first, last, changed over time. | "Which campaigns started after 2020?" "When was DEADEYE first used?" (if a date property is asked for) |
| `O7c.union` | 7 | Either of two **different** patterns. Several anchors of the same pattern are `T.walk`. | "Techniques that are either mitigated by M1027 or detected by DET0010" |
| `O7d.absence` | 7 | Items lacking a link or a property. | "Which techniques have no mitigation?" |
| `O8.path` | 8 | Unbounded reach (all ancestors, all descendants) or the shortest chain between two entities. | "What is the shortest chain linking T1071 and T1546.016?" |

### Mind the Query's three gaps (built only if the count shows them)

| Code | Means | Example |
|---|---|---|
| `G1.multiagg` | Several aggregates in one result row. | "For each group, the number and the share of techniques…" |
| `G2.groupbyvalue` | Grouping by a property's **value**, not by a related entity. | "How many attack patterns at each abstraction level?" |
| `G3.twovars` | Rows that pair columns from two variables. | "List each technique with its tactic." |

### Outside retrieval (the answer is not a graph read)

| Code | Means | Example |
|---|---|---|
| `X.textsearch` | The answer is in description text, but the question names no entity to anchor on. It needs search across descriptions. | "What methods do adversaries use to package data for exfiltration?" |
| `X.extract` | Extract facts from text supplied with the question (a report, a description). | CTIBench cti-ate rows |
| `X.similar` | Semantic similarity or nearest neighbour. | "Which analytic is most similar to AN0269?" |
| `X.knowledge` | Needs knowledge, judgement or advice the graph does not hold. | "Why might an adversary create cloud-only accounts?" |
| `X.other` | Anything else. Say what in the rationale. | |

## Coverage, as the count reports it

A question is **covered after operator k** when every code it needs is a `T.*` code or an
operator 1 to k. The count reports, per source:
- the share covered by today's operations;
- the share covered after each operator in order (1, 2, …, 8);
- the share after the gaps;
- the share outside retrieval.

The single label used for labeller agreement (Cohen's κ) is the **stage** at which a question
becomes covered: `today`, `1` … `8`, `gaps`, or `outside`.

## Deterministic labels (Ariadne's own banks)

These sources carry structure, so they are labelled by code, not by a model:
- **dev 284 (`spec`):**
  - 0 steps → `T.describe`;
  - 1 or more steps → `T.walk`;
  - each `eq` filter adds `T.eqfilter`; any other filter op → `O1.filter`.
- **gold 120 (`expected_template`):**
  - `describe` → `T.describe`;
  - `label_scan` and `capec_scan` → `T.scan`;
  - `tactic_technique_mitigations` → `T.common`;
  - `boundary_refusal` → `T.refuse`;
  - every other template, and the federated cases (no template), → `T.walk`;
  - `capec_hierarchy_chain` → `T.walk`, since the ancestors sit at a bounded depth.
- **Step 6 tuning banks (`card_gen`):** a slotted question is one hop, so `T.walk`. Slotless
  questions (out-of-coverage) are labelled by hand like the external ones.
