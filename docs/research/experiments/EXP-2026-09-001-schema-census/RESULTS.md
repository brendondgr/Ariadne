# RESULTS — EXP-2026-09-001 Schema census

**Status: complete, 2026-09-01.** Deterministic enumeration; no model, no
database, no network. Re-running reproduces the artifact byte-for-byte.

## Headline

**The 16 hand-written question categories reach 12 of the 33 edge types the
sources support — 36.4%.** Twenty-one edge types have never carried a question.

| Measure | Value |
|---|---:|
| Node types | 23 |
| Nodes (after exclusions) | 10,098 |
| Edge types | 33 |
| Edge instances | 34,954 |
| Edge types reached by the 16 categories | 12 (36.4%) |
| Edge instances reached | 23,294 (66.6%) |
| Node properties reached | 23 of 74 (31.1%) |
| Facet properties available | 12 |
| Facet properties used by any bank | **0** |
| Cross-source edge types | **1** |

The instance figure (66.6%) is higher than the shape figure (36.4%) for an
unflattering reason: the categories concentrate on the three highest-volume
edges in the graph — `Software -uses-> Technique` (11,213),
`Group -uses-> Technique` (4,546) and `Mitigation -mitigates-> Technique`
(1,448). Coverage looks broader by instance count than it is by shape.

## The hypothesis held, and understated the result

Predicted before the run: the shortfall would be concentrated in Campaign,
Analytic and DataComponent relations, and in CAPEC's non-`ChildOf` natures. All
five of those appear in the never-asked list. What the prediction missed is
**how much of the graph they add up to**.

Top never-asked edge types by instance count:

| Triple | n | fwd med/p90 | rev med/p90 |
|---|---:|---:|---:|
| `Analytic -[log_source]-> DataComponent` | 4,170 | 2/4 | 7/109 |
| `DetectionStrategy -[x_mitre_analytic_refs]-> Analytic` | 1,745 | 2/5 | 1/1 |
| `AttackPattern -[HAS_MITIGATION]-> CapecMitigation` | 1,170 | 2/6 | 1/1 |
| `Campaign -[uses]-> Technique` | 1,146 | 18/34 | 2/9 |
| `Group -[uses]-> Software` | 1,144 | 5/17 | 1/3 |
| `AttackPattern -[HAS_PREREQUISITE]-> Prerequisite` | 746 | 1/3 | 1/1 |
| `AttackPattern -[HAS_EXAMPLE]-> Example` | 387 | 1/2 | 1/1 |
| `AttackPattern -[REQUIRES_RESOURCE]-> Resource` | 289 | 1/1 | 1/1 |

Three findings fall out of this table.

**F-1 — the detection subgraph is almost entirely untested.** ATT&CK v19
restructured detection into DetectionStrategy → Analytic → DataComponent, and
those two edges alone carry 5,915 instances — 17% of the whole graph. The banks
reach that subgraph through exactly one shape,
`DetectionStrategy -detects-> Technique` (697 instances), because that is the
one the `detection` category was written for. The two-hop and three-hop
detection questions a detection engineer would actually ask have never been
asked once.

**F-2 — CAPEC mitigations are invisible while ATT&CK mitigations are the most
asked shape in the record.** `AttackPattern -HAS_MITIGATION-> CapecMitigation`
carries 1,170 instances, comparable to `Mitigation -mitigates-> Technique`'s
1,448, and no bank has ever touched it. Nobody chose this asymmetry; it is an
artifact of which categories someone thought of.

**F-3 — every one of the 21 never-asked edge types is forward-askable** (p90 ≤
50), and 13 of them carry 50 or more instances. They are absent because no
category was written for them, not because they are unanswerable. This is the
finding that matters for expansion: the missing shapes are *usable*.

## Direction, measured rather than assumed

Fan-out is recorded in both directions because reverse-direction asks are where
the blind holdout collapsed. Two asked shapes turn out to be marginal:

| Triple | fwd p90 | rev p90 | note |
|---|---:|---:|---|
| `Group -[uses]-> Technique` | **63** | 26 | the `groups` category asks *both* directions |
| `Technique -[kill_chain_phase]-> Tactic` | 2 | **113** | forward only, correctly |
| `Software -[uses]-> Technique` | 27 | **53** | reverse is marginal |
| `Mitigation -[mitigates]-> Technique` | **79** | 5 | asked in reverse, correctly |

`ATTACK_CATEGORIES["groups"]` reads *"The techniques a named group uses, or the
groups using a technique"* — it licenses the direction whose p90 answer is 63
items. That is a live risk in banks we already hold, not a hypothetical: a
question drawn on that side has an answer no grader can score well, and it would
show up as a system failure rather than as a question defect. Recorded as I-2.

## Federation rests on 271 edges

**There is exactly one cross-source edge type in the entire census**:
`AttackPattern -[MAPS_TO[ATTACK]]-> Technique`, 271 instances, median fan-out 1.

Every federated question in every bank, every claim about cross-store
correlation, and the whole merged-vs-federated comparison traverse that single
edge type. It is not wrong — it is what the sources declare — but it needs
saying plainly in any write-up, because "federated graph QA" implies a richer
join surface than one taxonomy mapping with 271 rows.

## Twelve facets, zero used

The census finds 12 properties whose values are shared widely enough to carry a
filter — `Technique.x_mitre_platforms` (11 values, 100% coverage),
`AttackPattern.Abstraction` (3), `AttackPattern.Typical_Severity` (5),
`AttackPattern.Likelihood_Of_Attack` (3), `Software.x_mitre_platforms` (14),
and 7 more, plus two date properties on Campaign that carry range filters.

No bank contains a single constrained question. "Which techniques targeting
Linux have no listed mitigation" is answerable from the pinned snapshot today
and has never been asked.

## Agreement with the independent derivation

The census and `gold_bank` parse the same two files by different routes and
share no code. They agree exactly:

| Quantity | census | gold_bank |
|---|---:|---:|
| Live ATT&CK objects | 4,369 | 4,369 |
| Techniques (incl. sub-techniques) | 697 | 222 + 475 |
| CAPEC patterns | 558 | 558 |
| CWEs | 336 | 336 |
| `Mitigation -mitigates-> Technique` | 1,448 | 1,448 |
| `Group -uses-> Technique` | 4,546 | 4,546 |
| `Software -uses-> Technique` | 11,213 | 11,213 |
| `AttackPattern -MAPS_TO[ATTACK]-> Technique` | 271 | 271 |
| `AttackPattern -EXPLOITS_WEAKNESS-> Weakness` | 1,211 | 1,211 |

Enforced by `test_node_counts_match_gold_bank` and
`test_edge_counts_match_gold_bank`. When these diverge, one of the two parsers
has a bug and nothing else in the repository would say so.

## What this does and does not license

**Does.** It sets the denominator for bank expansion, and it names 21 specific
shapes and 12 specific facets to expand into. It replaces "the categories were
written from memory" with a number.

**Does not.** It says nothing about whether Ariadne can *answer* the 21
never-asked shapes. Coverage here is coverage of the question space, not of
system capability, and the two must not be conflated — a shape the banks never
asked may be one the builder handles perfectly or one it cannot express at all.
Establishing which is a separate experiment, and it should be run before any
large generated bank is graded, so that a low score on new shapes can be
attributed to the right cause.

Coverage is also an **upper bound on what was asked**: it measures what the 16
categories *could* reach, not what any 30-question bank did reach. A given bank
asks fewer shapes than this, never more.

## Reproduce

```
uv run python -m utils.specialists.evalset.schema_census
uv run pytest utils/specialists/evalset/tests/test_schema_census.py -q
```

---

# AMENDMENTS

## A-1 — Census v2 (2026-09-01): three corrections and one new measure

Step 1 of the expansion plan needed the instances behind the shapes, not just
the counts, so the parse moved into `utils/specialists/evalset/raw_graph.py` and
both the census and the enumerator now consume it. The refactor was held to
reproducing the v1 numbers; where it did not, the difference was a v1 defect.
All four differences are below. None changes the headline — **12 of 33 edge
types, 36.4%** — and one changes a supporting figure materially.

### C-1 — Two node types were missing (23 → 25)

v1 created a node type for referenced-but-undefined **CWEs** (`Weakness`, 336)
but not for referenced-but-undefined **taxonomy entries**. `TaxonomyEntry:WASC`
(33) and `TaxonomyEntry:OWASP Attacks` (39) had edges pointing at them and no
row of their own.

v2 states the rule instead of leaving it implicit: *a referenced-but-undefined
node counts toward its label's population only when nothing else in the graph
defines that label.* CWEs count (no CWE catalogue is loaded). CAPEC-declared
technique ids do not (ATT&CK defines Techniques). `Technique` stays 697.

### C-2 — 21 View members were typed as attack patterns and are categories

**This entry was first written with the wrong cause and is corrected here.** It
originally said the 21 edges pointed at patterns the load policy excludes. They
do not. Counted exactly, the 67 `View` member references are **46 live attack
patterns and 21 categories**, and **zero** retired patterns. The check that
produced the wrong explanation tested membership against the live *attack
pattern* set alone, so every category read as "retired".

The real defect is a typing one, and it was v1's: CAPEC views contain both
categories and attack patterns — `capec_graph.py:333` says so in as many words —
and v1 typed all 67 as `View -[HAS_MEMBER]-> AttackPattern`.

`View -[HAS_MEMBER]-> AttackPattern` is therefore **46**, and
`View -[HAS_MEMBER]-> Category` (**21**) is a new edge type; see C-4 for why it
took a second pass to appear. Total edge instances: 34,954 → **34,933** →
**34,954** again, the same total for a different reason.

### C-3 — Property coverage was too generous: 31.1% → **19.3%**

v1 counted a property as reached if *any* category reads a property of that
name, so `Campaign.description` counted as covered although no category has ever
reached a Campaign. v2 restricts to labels a category can actually reach — 11 of
25 — giving **16 of 83**. `text` was also added to the reachable set, because
the execution/consequence/skill categories do surface it.

This is the largest correction in the amendment and it moves in the unflattering
direction, which is the direction a self-serving bug would not have taken.

### C-4 — Categories and views were given identifiers CAPEC does not use

v2's first pass keyed categories and views as `CATEGORY-118` and `VIEW-1000`.
Those are inventions. CAPEC allocates attack patterns, categories and views from
**one number space** — verified here: 615 / 78 / 13 ids with no collision in any
pair — and addresses all three as `CAPEC-<n>`.

Two things followed from the invented scheme, and the second is the one that
mattered:

1. The renderer's first pilot rejected 30 of 126 questions because the model
   would not put `VIEW-703` in a sentence. That was the model behaving
   correctly and the identifier being wrong.
2. **A whole edge type was missing.** Views reference their category members by
   CAPEC id, so with categories keyed as `CATEGORY-118` those references
   resolved to nothing and the census dropped them silently — which is what
   produced the mistaken C-2 explanation above.

Fixed by keying both as `CAPEC-<n>`, with an assertion that raises if a future
snapshot ever collides the number space rather than silently merging a category
into an attack pattern.

**Census totals after C-4: 34 edge types, 22 of them never asked**, and category
coverage 36.4% → **35.3%** — the denominator grew, the numerator did not.

### M-1 — Dangling cross-source references: **10**

New measure, and the sharpest federation finding so far. CAPEC v3.9 declares 189
distinct ATT&CK technique ids; the pinned Enterprise bundle has a live object
for **179**. The 10 that fail split into two causes:

- **9 are revoked in ATT&CK v19** — `T1562.001` … `T1562.009` and `T1574.002`,
  the Impair Defenses and Hijack Execution Flow restructures. CAPEC still maps
  to the old ids. This is **version skew between independently released
  catalogues**, and it is the ordinary condition of federating them, not an
  accident of this snapshot.
- **1 is out of domain** — `T1513` is a Mobile technique, and we load
  Enterprise.

5.3% of the join surface is dangling. The single cross-source edge type carries
271 instances and 10 of its targets do not exist, which needs stating in any
write-up that describes the system as federated.

The consequence for question generation is recorded in the composition
enumerator: gold is split into **retrievable** and **declared-but-dangling**.
Keeping dangling ids in a federated chain would grade against answers no system
can produce; dropping them silently would hide the skew inside a gold set.

### What did not change

Facets (12), facets used (0), cross-source edge types (1), and every population
figure the `gold_bank` cross-check covers. The 13 tests that hold the census to
`gold_bank` all still pass unchanged.

### Headline after all four corrections

**12 of 34 edge types — 35.3%.** The finding is unchanged in substance and
slightly worse in magnitude than first reported: the categories reach one fewer
share of a graph that turned out to have one more shape in it.

---

## AMENDMENT A-2 — The load holds less than the sources support (2026-09-01)

Step 6 was designed to ask *can the builder express the shapes no bank has ever
asked?* It could not answer that, because it failed on its own controls. Chasing
the failure produced a better question and a firmer answer.

### What the probe did

78 questions covering **all 22 never-asked edge types**, authored by Opus 5
subagents from briefs, run through the deterministic arm and scored with **no
judge** — the arm's own answer files carry recall of the snapshot-derived gold.

**Overall recall 0.0706. Controls 0.1944.** The controls are shapes the
committed banks answer at 1.0, so the probe measured the harness, not the
system.

Two design faults, both mine:

* **Every control was multi-hop.** The control pool required all of a spec's
  shapes to be already-asked, and the sampler drew D4/D5/D6 exclusively — 5 D5,
  4 D4, 3 D6, and not one single-hop control. The committed banks never put a
  two-hop question in a single `task`.
* **The bank used the census's edge vocabulary.** Confirmed by running the
  committed bank 19 through the identical runner: **recall 1.0000**. The harness
  is sound; the bank was not.

### What that surfaced

The census names an edge the way the *source* declares it. The loaded graph names
it its own way, sometimes reversed, sometimes collapsing several census edge
types into one — and sometimes not loading it at all. Nothing had ever compared
the two. `scripts/reconcile_graph.py` now does, and requires every census
predicate to be mapped explicitly to a graph relationship or to `None`; an
unmapped predicate fails the run, because a silent default is how "we cannot ask
this" becomes "the system got it wrong".

**Five edge types the sources declare are absent from the load — 1,545 instances:**

| triple | instances |
|---|---:|
| `AttackPattern -[HAS_PREREQUISITE]-> Prerequisite` | 746 |
| `AttackPattern -[HAS_EXAMPLE]-> Example` | 387 |
| `AttackPattern -[REQUIRES_RESOURCE]-> Resource` | 289 |
| `AttackPattern -[HAS_INDICATOR]-> Indicator` | 96 |
| `AttackPattern -[HAS_ALTERNATE_TERM]-> AlternateTerm` | 27 |

All five are in the never-asked set, and now the reason is known: **no arm can
answer them, because the rows are not there.** A question about a CAPEC
prerequisite is not hard, it is unanswerable — and the census alone would have
recorded it as a coverage gap in the *question set* rather than in the *ingest*.

**Eleven census edge types collapse into three graph relationships.** `USES`
carries five (`Software/Group/Campaign -uses-> Technique/Software`), `MAPS_TO`
carries three, `MEMBER_OF` carries three. A question that distinguishes
`Group -uses-> Software` from `Group -uses-> Technique` is asking for something
the stored relationship type does not by itself express.

### Two defects the reconciliation found in the census

* **The exclusion policy was not applied to categories.** The census reported 78
  CAPEC categories where the load holds 21; **57 are `Deprecated`**. The policy
  was written for attack patterns and quietly never extended. Fixed; the census
  now excludes retired categories and views and counts the exclusion.
* **ExecutionStep: census 815, graph 794.** Not retirement — all 815 belong to
  live patterns. **Unexplained, and reported as unexplained.** Everything else
  that differs is a known modelling choice (the graph splits `Technique` from
  `SubTechnique`; it keeps one `TaxonomyEntry` label where the census splits by
  taxonomy) and is annotated as such.

### What this licenses

**Does.** It separates three things the census had merged: shapes nobody asked,
shapes nobody *can* ask, and shapes the graph renames. Any future statement that
the system "fails" on a shape must first check that the shape is loaded.

**Does not.** It still says nothing about whether the builder can express the 29
edge types that *are* loaded. The probe has to be re-run with the graph's
vocabulary and with single-hop controls before Step 6's original question has an
answer.
