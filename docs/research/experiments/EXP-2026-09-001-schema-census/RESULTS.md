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

---

## AMENDMENT A-3 — The gap is closed (2026-09-01)

A-2 reported five edge types the sources declare and the load did not hold.
They are now loaded, along with two more defects of the same family that the
reconciliation surfaced on the way.

### What changed in the ingest

| | before | after |
|---|---:|---:|
| CAPEC nodes | 4,769 | **6,374** |
| CAPEC relationships | 6,972 | **8,582** |
| census edge types loaded | 29 of 34 | **34 of 34** |
| census node types loaded | 20 of 25 | **25 of 25** |

**1. The five missing sub-element kinds (1,545 instances).** Prerequisites
(746), examples (387), resources (289), indicators (96) and alternate terms
(27) are parsed, materialized as nodes, and edged from their pattern. Touching
four layers — parser, id scheme, schema registry, materializer — plus the
loader's edge-pattern allow-list, which rejected them until it was told they
were legal.

**2. Execution steps: 794 loaded where the source declares 815.** Not a
filtering rule. **CAPEC restarts `<Step>` numbering at 1 in each phase**
(Explore / Experiment / Exploit), and a few patterns repeat a number inside one
phase as well, so the number is not unique within a flow. The id scheme keyed on
it, `add_node` returns early on a duplicate, and **21 steps across 11 patterns
were silently dropped — systematically biased toward Exploit-phase steps**, the
terminal and highest-value part of each flow.

Two further corruptions followed from the same root: `previous_step_id` was
assigned even when the node had been deduped away, producing **9 `NEXT_STEP`
self-loops** and, where the collision was non-adjacent, **2 back-edges that
turned a flow chain into a cycle**.

Fixed by keying on **document position**, which is unique by construction and
stable under re-parse, with step number and phase kept as node properties so a
question can still ask about them. `gold_bank` mirrors the scheme and was
changed in lockstep — its comment had described the collapse as intended
behaviour.

**3. The entire OWASP taxonomy was absent — 39 entries, 40 `MAPS_TO` edges.**
The materializer required `Entry_ID`; OWASP entries carry only `Entry_Name`.
`TaxonomyEntry` is now 261 (ATTACK 189, WASC 33, OWASP 39) where it was 222 with
OWASP at zero.

**This is the third instance of one bug**, and worth naming as a class: *a
keying field that most of a collection carries and a minority does not.* The
census hit it (I-1, OWASP dropped), the ingest hit it here, and the execution
steps are the same shape — a key assumed unique that is not.

### Two accounting fixes

* The five new groups now count as *mapped*, so the quarantine figure stops
  reporting 1,545 materialized rows as dropped.
* They are excluded from `AttackPattern` node properties, as skills and
  consequences already were. Carrying them as list properties *and* as nodes
  would give a retrieval path two representations of one fact and no rule for
  which is authoritative.

### Regression check

Both committed banks re-run through the deterministic arm and diffed against the
recorded answers, clock keys stripped:

* **54 of 60 byte-identical.**
* **Recall 1.0000 → 1.0000** on both banks.
* 3 lookup answers gained facet rows for the five new relationship types — the
  entities genuinely have those neighbours now.
* 3 chain answers reordered with **identical retrieved id sets**, an artifact of
  a freshly rebuilt store.

Fixture-QA passes 12/12 for CAPEC and 14/14 for ATT&CK.

### Still absent, and deliberately out of scope

An audit of every child element of `Attack_Pattern`, `Category` and `View`
found more that neither the census nor the load models: `Content_History`
(2,706 modification records — every provenance and currency question about the
catalogue), pattern `Notes` (29), **`View/Filter` (9 of 13 views define
membership by XPath and have zero members in both representations)**, and
category/view `References`. None is required for the expansion; all are recorded
here so the next person does not rediscover them.

---

## AMENDMENT A-4 — Step 6, answered (2026-09-01)

The probe re-run with the graph's vocabulary, single-hop controls, and the
routing defects fixed. 80 questions, deterministic arm, **no judge** — recall of
snapshot-derived gold from retrieved evidence.

| | first run (A-2) | corrected |
|---|---:|---:|
| recall, all | 0.0706 | **0.4029** |
| recall, controls | 0.1944 | **0.7037** |
| recall, never-asked shapes | 0.0481 | **0.3391** |
| fully answered | 2 / 78 | **14 / 80** |

### The finding is direction, and it is stark

The same edge, asked from each end:

| shape | anchored on | recall |
|---|---|---:|
| `Technique -[kill_chain_phase]-> Tactic` | Technique | **1.00** |
| | Tactic | **0.26** |
| `DetectionStrategy -[detects]-> Technique` | Technique | **1.00** |
| | DetectionStrategy | **0.50** |
| `Mitigation -[mitigates]-> Technique` | Mitigation | **0.17** |

The committed banks ask `Mitigation -mitigates-> Technique` **from the
Technique** and score 1.0 on it. Nothing has ever asked it from the mitigation.
This is the same axis the blind holdout collapsed on
(EXP-2026-08-005), measured now on a shape-by-shape basis rather than as an
aggregate — and it is the strongest argument the expansion has for existing.

### The newly loaded shapes are reachable

`AttackPattern -[REQUIRES_RESOURCE]-> Resource` retrieves at 0.50, and the
OWASP and WASC taxonomy mappings at 0.50 each. Before A-3 all three were
**structurally zero**: the rows were not in the store. The ingest change is
doing what it was meant to.

### Three harness defects the controls caught, each of which would have been read as a system failure

1. **Census vocabulary in the bank.** The store names edges differently; the
   probe asked for `kill_chain_phase` where the graph holds `HAS_TECHNIQUE`.
   `spec_bank` now translates through the reconciliation's map rather than
   duplicating it.
2. **A single bridge hop routed as federated.** "Which techniques does CAPEC-66
   map to" is answered entirely inside CAPEC — CAPEC is what declares the
   mapping. Routing it as a two-store plan sent it to the store that has never
   heard of CAPEC-66. Recall on that shape: 0.00 → **1.00**.
3. **`MAPS_TO` targets are `TaxonomyEntry` nodes, not `Technique` nodes.** The
   census says CAPEC-66 maps to a Technique, because that is what CAPEC
   declares; the store materializes the target as a taxonomy entry. A global
   label map cannot express an edge-specific difference, so the override is
   keyed on the edge.

### What is still open

`Matrix -[tactic_refs]-> Tactic` from the Tactic end, and
`View -[HAS_MEMBER]-> Category` from either end, retrieve nothing. Those are
three of the 34 shapes and they are genuinely unreached, not mis-routed as far
as this probe can tell. Recorded rather than chased.

The probe carries no D0 items — the selection is shape-first and D0 specs have
no shape to select on. Abstention behaviour on the new shapes is therefore
unmeasured and must be covered in the full bank.

---

## AMENDMENT A-5 — The expansion bank, built and scored (2026-09-01)

**572 questions, 492 distinct specs, all 34 census edge types.** Authored by 20
Opus 5 subagents from briefs, 98.6% kept. Split dev/holdout by `sha256(spec_id)`
parity **before anything was run**, 284/288. Scored with **no grader** — recall
of snapshot-derived gold from retrieved evidence.

### The headline needs two numbers, not one

| | |
|---|---:|
| pooled recall | 0.4522 |
| **reweighted recall** | **0.5060** |
| dev / holdout | 0.4350 / 0.4683 |

The pooled figure is an artifact of the draw: the bank deliberately
over-samples the corners of the graph nothing has ever asked about. The
reweighted figure weights each shape by the instances the census says it has,
and is the one comparable to a naturally-drawn set. **Neither is comparable to
the 0.95–1.00 the committed banks score**, which cover 12 shapes in the
direction they were written for and are graded by a different instrument.

Dev and holdout agree to within 0.033, which is what a blind split should look
like and is the first evidence that this draw is not fitted to anything.

### Five results the 30-question banks could not have produced

**1. Difficulty tiers partly work, and D4 is the floor.**

| tier | recall |
|---|---:|
| D3 one hop, reverse | 0.6013 |
| D5 constrained | 0.5499 |
| D2 one hop, forward | 0.5345 |
| D1 property read | 0.3958 |
| D6 cross-source | 0.3893 |
| D4 two hop | 0.2594 |

Two hops is the hardest tier by a wide margin, which the structural hypothesis
predicted. D1 scoring below both single-hop tiers is **not** predicted and needs
explaining before the tiers are reported as a difficulty ordering.

**2. Reverse beats forward — 0.5165 against 0.4302 — and this contradicts
Step 6.** A-4 found the system answering the forward side of an edge and failing
the reverse. At n=511 the sign is the other way. The two are not measuring the
same thing: A-4 compared *the same shape* asked from each end, and this compares
*different shapes* that happen to be forward or reverse. The paired comparison
is the trustworthy one and this aggregate is confounded by shape composition.
**Recorded as a tension, not resolved.** A paired forward/reverse contrast over
this bank is the experiment that settles it.

**3. Gold width does predict retrieval recall**, monotonically: 0.5223 (width 1),
0.4292 (2–5), 0.3135 (6–20), 0.2858 (21+).

This does **not** overturn Q29, which found width does not predict *judged
score*. Different metric on a different population: Q29 measured what a grader
thinks of an answer over a corpus with six questions above width 20, and this
measures how much of a gold set was retrieved over a bank with 39 questions in
the top band. Both can be true — a system that retrieves half a wide answer may
still be judged well on it. Whether they are is now testable.

**4. Abstention is weak, and this is the first time it has been measured at
n > 4.** On 61 questions whose correct answer is "nothing", the system returned
nothing **37 times — 60.7%**. It retrieved something for the other 24. Previous
evidence was 4 of 4.

**5. Phrasing matters slightly, and the indirect register is easiest.** 0.4808
indirect, 0.4388 formal, 0.4378 analyst, over 40 specs rendered in all three.
The spread is small; the direction is the opposite of the intuition that
conversational phrasing is harder.

### The weakest shapes are containment

`Category -[HAS_MEMBER]-> AttackPattern` at 0.04 over 32 questions,
`View -[HAS_MEMBER]-> Category` at 0.03, `Matrix -[tactic_refs]-> Tactic` at
0.12. All three are loaded — the reconciliation confirms the rows exist — so
this is a retrieval gap, not a data gap. They are also all shapes no bank had
ever asked, which is what the expansion was for.

Five `D1` property reads score 0.00 (`Group.description`, `Tactic.description`,
`Group.aliases`, `Group.x_mitre_contributors`, `View.Type`). Property reads on
non-Technique entities look systematically unsupported.

### What this does not license

The bank is one arm (`deterministic`) on one metric (retrieval recall). It says
nothing yet about the judged comparisons, about the LLM-planned arms, or about
answer quality. Those are the next runs, and the holdout half stays sealed until
the dev half has been written up.

---

## AMENDMENT A-6 (2026-09-09) — Record repair: the headline is superseded by A-1/A-2, eight pointers were stale, and the commit predated the code

Written from the 2026-09-09 audit (`verify-b5.md`), the current
`census.json`, `git log`/`git diff`, and `utils.research_record.hashing`. No
number in this amendment is new; every one is read from an artifact named in
`data/POINTERS.md`.

### 1. The Headline section still quotes v1

`RESULTS.md:8-9` and the table at `:11-22` were written before A-1 and A-2 and
never updated: *"12 of the 33 edge types — 36.4%"*, *"Twenty-one edge types"*,
23 node types, 10,098 nodes, 33 edge types, 34,954 edge instances, 23 of 74
properties (31.1%). F-3 (`:67-68`) says *"every one of the 21 never-asked edge
types … 13 of them carry 50 or more instances"*. A-1 C-1/C-3/C-4 and A-2
corrected each of these lower down in this file. The current figures, read
from `census.json` (`sha256:e2f55f82…`, `census_version: 2`):

| Measure | Headline (v1) | Current (v2) | Where corrected |
|---|---:|---:|---|
| Edge types | 33 | **34** | A-1 C-4 |
| Edge types reached | 12 (36.4%) | **12 (35.3%, 0.3529)** | A-1 C-4 |
| Never-asked edge types | 21, 13 with ≥50 instances | **22, 12 with ≥50 instances** | A-1 C-4; this amendment |
| Node types | 23 | **25** | A-1 C-1 |
| Nodes (after exclusions) | 10,098 | **10,113** | A-2 (category/view exclusion, regenerated at `1dd69d9`) |
| Edge instances | 34,954 | **34,952** | A-2 |
| Edge instances reached | 23,294 (66.6%) | **23,294 (66.65%, 0.6665)** | this amendment |
| Node properties reached | 23 of 74 (31.1%) | **16 of 83 (19.3%, 0.1928)** | A-1 C-3 |

The reading at `:24-28` (instance coverage exceeds shape coverage because the
categories sit on the three highest-volume edges) is unchanged. The text above
is left as written; this table is the correction.

### 2. Manifest values changed (old → new)

- `metrics.values.edge_instance_coverage`: **0.6664 → 0.6665**. The recorded
  value was the v1 ratio 23,294 / 34,954; the v2 census holds 34,952 instances
  and its own `coverage.edge_instance_coverage` field says 0.6665.
- `data.n_examples`: **10098 → 10113** (v2 node total).
- New keys: `edge_instances_total` 34,952, `edge_instances_reached` 23,294,
  `nodes_after_exclusions` 10,113, `never_asked_edge_types` 22,
  `never_asked_edge_types_with_50_plus_instances` 12.
- `metrics.withdrawn` added for the v1 figures this file's own A-1/A-2 retired:
  `edge_type_coverage_v1` 0.3636, `edge_types_total_v1` 33, `node_types_v1` 23,
  `nodes_after_exclusions_v1` 10,098, `property_coverage_v1` 0.3108,
  `edge_instances_total_v1` 34,954 — each `replaced_by` the current key of the
  same name.
- `code.commit`: **8ab0d2ba… → eeef3228bcc51bd032a7246017f26f0830591cdc**;
  `code.dirty`: **true → false**. The recorded commit (2026-08-31 21:49,
  *"Fix the grading-order bias…"*) predates every line of census code — the
  module first appears at `7812d54` (2026-09-01 16:01) — and could regenerate
  nothing in this folder. `git diff --stat eeef322 -- <every present pointer
  path>` is empty, so the tree at `eeef322` (Step 7, 2026-09-01 23:33, the
  commit that also produced A-5's bank and scores) regenerates every artifact
  listed. The intermediate states are `7812d54` (v1), `caec889`/`a61dedb`
  (A-1), `1dd69d9` (A-2), `e2dbb64` (A-3), `eeef322` (A-5).
- `environment.lockfile`: **env/requirements.lock → null** — the file was never
  written (ISSUES I-9).
- `related`: EXP-2026-09-002 added (see §5).

### 3. Pointers: 8 of 17 stale, 1 missing, 9 rows added

Eight hashes were the blobs at `a61dedb` (census.json, CENSUS.md,
raw_graph.py, composition.py, test_composition.py, specs.json, report.json) or
`585e7dc` (prepare_briefs.py). A-2's category-exclusion fix at `1dd69d9`
regenerated the census and the spec pool; `eeef322` touched composition.py and
prepare_briefs.py again. All eight are re-hashed as they stand (identical at
`eeef322` and HEAD); the old hashes are kept in each row's description.

`docs/evaluation/composition/authored/ingested.json` — the 42-brief Opus 5
pilot the table pinned at 37,581 B, `sha256:659c1cd5…` — is gone. That hash is
the `585e7dc` blob; the file was regenerated at `1dd69d9` and `e2dbb64` and
**deleted at `eeef322`** when the full-bank ingest replaced it at
`docs/evaluation/composition/bank/ingested.json` (5,836 lines, different
content). EXP-2026-09-003 ISSUES I-5 describes this path as *"committed at
eeef322"*; it was deleted there. The row now points at the successor, labelled
as such, and ISSUES I-7 records where the pilot survives.

Rows added for artifacts the amendments used and never pinned: the A-2/A-4
probe (`docs/evaluation/composition/probe/{selection,bank,probe-report}.json`
and the gitignored `probe-2026-09-01/deterministic/answers`, 80 files, from
which the audit reproduced A-4's 0.4029 and 14 fully answered exactly);
`scripts/reconcile_graph.py`; A-5's `bank.json`, the gitignored
`expansion-2026-09-01/deterministic/answers` (572 files) and `score.json`; and
`scripts/score_bank.py`. `score.json` was rewritten on 2026-09-08 by `a460fa2`
(Hybrid Rewrite Stage 6/8 added a `rewrite` provenance block); its `report`
block still carries 0.4522 / 0.5060 / 37 of 61 unchanged, and the row records
the `eeef322` blob (`sha256:6fb4eaf1…`) as the file A-5 was computed from.

A-2's *first* probe — 78 questions, recall 0.0706, controls 0.1944 — was
overwritten in place by the corrected 80-question run and cannot be reproduced
(ISSUES I-8). A-4's corrected figures reproduce.

### 4. What did not change

Every other manifest value reproduces from the current `census.json`
(`edge_type_coverage` 12/34, `property_coverage` 16/83, 25 node types, 12
facets, 1 cross-source edge type, 10 dangling references) and from
`score.json@eeef322` (0.4522 / 0.5060 / 0.6066 over 572 questions). The
conclusion is unchanged: the 16 categories reach 12 of 34 edge types.

### 5. Stale prose overturned later

A-5 §2 reports reverse easier than forward (0.5165 vs 0.4302) and records it as
*"a tension, not resolved"*. EXP-2026-09-002 paired the contrast on shape (20
shapes, 237 questions, mean −0.0797, sd 0.4865) and found no global sign; its
RESULTS states that A-5's aggregate comparison is confounded by shape
composition, which is what A-5 itself suspected. The paired figure is the one
to quote. EXP-2026-09-002 also judged this bank (0.6576 / 0.4934) and
EXP-2026-09-005 re-measured it after the retrieval repairs; A-5's model-free
0.4522 remains the correct figure for what it measures and is not the quotable
arm comparison.

### 6. `data/metrics.json`

Did not exist. Created 2026-09-09 from the manifest's `metrics.values`.
