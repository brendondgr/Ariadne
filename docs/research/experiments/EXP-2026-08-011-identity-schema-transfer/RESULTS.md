# RESULTS — EXP-2026-08-011 Identity-schema transfer

## 1. Headline

**Both arms retrieve nothing. 0.0000 on 27 of 27 questions, on a schema neither
was written for.**

C-010 says the dataset-specific surface is bounded and countable and the
schema-agnostic machinery transfers. On the first non-MITRE schema this codebase
has ever been pointed at, it does not transfer at all — and the failure is not
in the layer the audit measured.

| Arm | n | Retrieval | Questions at 0 | Anchor label ever queried |
|---|---|---|---|---|
| `generic` (schema-derived primitives) | 27 | **0.0000** | 27 | **1 / 27** |
| `deterministic` (25-template cascade) | 27 | **0.0000** | 27 | **1 / 27** |
| **Arm gap** | | **0.0000** | | |

Generated from [`data/metrics.json`](data/metrics.json).

## 2. What actually happens

The arms are identical because they fail *upstream of where they differ*. The
template-versus-primitive choice is made inside the specialist; the failure is in
the planner, before a specialist is reached. On 26 of 27 questions the anchor
label is never queried at all.

The mechanism is entity extraction. The deterministic planner matches question
words against the source card's schema vocabulary. On ATT&CK that vocabulary is
11 labels and 9 relationship types of distinctive jargon — *technique*,
*mitigation*, *sub-technique*. On this schema it is **72 labels and 779 attribute
names drawn from ordinary IT English**, and ordinary question words collide with
it constantly:

> **Q:** *"What can Database Admins generically write?"*
> **entities extracted:** `GCP_SQL_INSTANCE`, `GENERIC_WRITE`,
> `WRITE_ACCOUNT_RESTRICTIONS`, `WRITE_DACL`, `WRITE_GP_LINK`, `WRITE_OWNER`
> **query:** `MATCH (n:GCP_SQL_INSTANCE) RETURN … LIMIT 1000`

"Database Admins" is an Active Directory `GROUP` and is the anchor. It never
becomes one. `GCP_SQL_INSTANCE` wins because the word *database* appears in its
declared attribute `gcp__database_uid`. The five `WRITE_*` relationship names
match on *write*.

What the planner scanned instead, across the 27 questions:

| Label scanned | Times |
|---|---|
| `ENTRA_APP_ROLE_ASSIGNMENT` | 54 |
| `AWS_ACTION` | 30 |
| **`Technique`** | **12** |
| `AD_ISSUANCE_POLICY` | 12 |
| `AWS_EC2_SECURITY_GROUP` | 12 |
| `GCP_SQL_INSTANCE`, `ENTRA_APPLICATION`, `ENTRA_CONDITIONAL_ACCESS_POLICY` | 6 each |

`Technique` is queried **twelve times against a graph that has no such label**.
That is MITRE vocabulary surviving into a source whose card never mentions it.

## 3. Hypotheses

| | Prediction | Outcome |
|---|---|---|
| **H1** | generic ≥ 0.90 retrieval | **Falsified.** 0.0000. |
| **H2** | cascade < 0.40, and the arm gap measures the dataset-specific surface | **Not evaluable as written.** The cascade is below 0.40, but so is the generic arm, so the gap is 0.0000 and measures nothing. The surface cannot be priced by an arm difference when both arms floor. |
| **H3** | homogeneous triples ≥ 0.20 below heterogeneous | **Not evaluable.** Both populations are at 0.0000. The predicted defect may still be real; this run cannot see it, because nothing reaches the direction resolver. |
| **H4** | >50% of properties learn as *open*; zero false mismatches | **Split.** Zero false mismatches — the safety property holds. But only **3.7%** (22 of 594) learn as open, far from the predicted majority, and **this number should not be believed** — see §5. |

## 4. The abstention result

Both `unanswerable` questions — anchored on labels with no declared relationship
of any kind — produced queries and records rather than an abstention. The system
did not decline, and did not carry query proof of an honest empty. On this
source, the property C-017 describes is not observed at all.

## 5. Threats to validity

**The instances are synthetic.** Stated in advance and unchanged. The schema is
real and unmodified; the tenant conforming to it is generated. Nothing here
speaks to detection quality.

**H4's 3.7% is an artifact of the generator, not a fact about identity data.**
The generator fills undeclared-shape attributes with formulaic values
(`gcp-sql-instance-zone-417`), which collapse to a single scheme and learn
cleanly. Real tenants carry free text there. The prediction that identity data is
mostly unlearnable was not tested by this run; it was answered by a generator
that made the data more regular than reality. **Do not quote the 3.7%** as a
property of identity graphs. What does survive is the zero-false-mismatch
half — that was tested against 72 labels and held.

**The catalog is permanently truncated.** An inner join dropped every
attribute-less edge type: 58 of 72 labels have no declared relationship, and
`USER -MEMBER_OF-> GROUP` is absent. Three edges are inferred by this project and
carry 1,115 of the tenant's 3,814 relationships (29%). No corrected export is
coming. Full detail in [ISSUES.md](ISSUES.md) I-4 and the
[dataset card](../../datasets/cards/reliaquest-identity-catalog.md).

**One defect was fixed mid-experiment, before any arm was scored.** `label_scan`
emitted `n.attack_id` against a schema with no such property (I-1). Fixing it did
not burn the bank — it was found by a hand-written smoke query, not by a holdout
question failing. Everything found *after* the bank was drawn is recorded and
left alone.

**Two harness defects of my own were found and corrected before these numbers
were taken**, and both had produced plausible-looking wrong results first. The
sweep serialised the evidence bundle with `default=str`, flattening it so every
query and record id vanished — which yielded an apparent 0.0741 and an apparent
"0/27 correct routing" that were artifacts. And the source card under-declared
`name`, which ATT&CK's card declares on every label. Correcting the card changed
nothing, which is itself the evidence that the routing failure is real and not a
card gap.

**Judging was not run.** The secondary correctness metric requires an LLM judge
over persisted answers. With retrieval at 0.0000 on every question, a judge can
only confirm that answers containing no gold evidence are not correct. Running it
would consume a contended shared server to produce a foregone number. Recorded as
a scoping decision, not an omission.

## 6. What this does to C-010

C-010 is `supported` on the strength of [EXP-2026-07-011](../EXP-2026-07-011-portability-audit/),
an audit that counted 19 of 25 templates as MITRE-specific and classified
orchestration, planning, synthesis and evaluation as portable. That audit's own
threats section says: *"This is an audit, not a measurement. No non-MITRE dataset
was ever loaded. The portability verdict is a code reading, and code readings
miss coupling that only shows up at run time."*

It was right, and the miss is larger than "some templates need re-authoring" in
two distinct ways:

1. **The audit measured the wrong unit.** It counted template *identifiers* by
   AST parse and classified them by question shape. `label_scan`'s shape is
   generic; its MITRE-specificity was in the property name it emitted
   (`n.attack_id`). That class of coupling is invisible to an identifier count,
   and it is not one template — it is a pattern.

2. **The planner was classified as portable and is not.** Entity extraction is
   card-driven in the sense that it reads the card's vocabulary, so it looks
   portable. It is not *schema-scale-independent*: it degrades from usable at 11
   labels to unusable at 72, with no code change and no error. Nothing in a code
   reading reveals that, because there is no MITRE string to find.

C-010 should move from `supported` to `partial`, with the qualification that
"bounded and countable" was established by a method that cannot see the two
largest couplings this run found. The honest re-statement is narrower: *the
orchestration, safety and evaluation layers transfer; the planner and the query
builders do not, and their re-authoring cost is not yet bounded.*

## 7. What would make this measurable

The experiment cannot price the template surface (H2) or test direction
resolution (H3) until anchors resolve. The obvious next step is a planner that
binds a named entity before matching schema words — the card already declares
`name` on every label, and 26 of 27 questions name their anchor in plain text.
That is a change to the system under test, so it belongs in a new experiment
with a freshly drawn bank; this one's bank has now seen the arms and is burned.

---

# AMENDMENTS

## A-1 (2026-08-22) — the failure was five fixable defects, not a wall

Everything above is the **pre-fix** measurement and stands as recorded: pointed
at a foreign schema with no changes, both arms retrieved nothing. What §7 called
"what would make this measurable" was then done, and the answer changed.

Five structural fixes (commit `74d027e`), none of which names a label, a group,
or a question. Against the **same 27 questions, now used as a development set**:

| Arm | Pre-fix | Post-fix |
|---|---|---|
| `generic` (schema-derived primitives) | 0.0000 | **0.8519** (23 of 27 perfect) |
| `deterministic` (25-template cascade) | 0.0000 | **0.2778** |
| Arm gap | 0.0000 | **+0.5741** |

By question kind, generic arm: reverse-direction `facet-in` **0.0 → 1.0**,
same-label-both-ends `homo-in`/`homo-out` **0.0 → 1.0**, `multihop` **0.0 → 1.0**,
abstention **0.0 → 1.0**. `facet-out` reaches 0.5 and `describe` 0.667; four
questions still fail.

**What the fixes were, and why each is structural rather than local:**

1. The name-lookup guard was eight hard-coded ATT&CK labels, so on any other
   source it matched nothing however well the name had been extracted. Now
   derived from labels that declare `name`.
2. Deriving that required the schema registry to record `name` at all. It never
   had — on any dataset — because it scanned each node's `properties` dict and
   `name` is a top-level column.
3. A name-resolved anchor could not be traversed from: walking a relationship
   was gated on having an id, so a source with no analyst-facing identifier
   could never traverse anything and every relationship question collapsed to
   facet counts.
4. The only route onto the name path was a "what is X" phrasing, so a question
   that names its subject but asks something else fell to a bare label scan.
5. The resolver shredded dotted identifiers (`corp.corp.example` → `corp` +
   `example`), and the validator's relationship regex could not parse
   alternation — so `[r:A|B]` had **no** type checked against the card, a
   validator silently declining to validate.

1,250 tests pass, identical to the pre-change baseline: MITRE is unmoved.

## A-2 — status of the hypotheses, restated

**H1 is still falsified as pre-registered** (it predicted ≥0.90 with no changes)
and that is the honest reading of the pre-fix run. What the post-fix number
shows is different and narrower: the schema-agnostic path *can* reach a foreign
schema, but not as it stood — it needed five defects removed first, four of
which were invisible to a code reading.

**H2 becomes evaluable for the first time.** The arms have separated: 0.8519
against 0.2778. On a schema nobody wrote templates for, the schema-derived
primitives are worth **+0.5741** over the template cascade. That is the
measurement H2 asked for and the pre-fix run could not supply, because an arm
gap of zero between two floored arms measures nothing.

**H3 is now testable and did not reproduce.** Homogeneous triples score 1.0,
level with heterogeneous. The predicted direction defect did not appear once
anchors resolved — the `PlausibleFacet` reasoning that motivated it was sound
about the data model but the direction was recoverable anyway.

## A-3 — this is a development-set number, not a blind one

The 27 questions have now been iterated against. **0.8519 must never be quoted
as a blind result.** A second bank was drawn with a different seed and an
explicit anchor exclusion (zero overlap with bank 1, verified), authored by the
same blind protocol, and it is the honest test of whether these fixes
generalised. Its result is recorded separately.

## A-4 — C-010

The downgrade to `partial` stands, and the reasoning in §6 is unchanged: the
audit measured question shapes and could not see coupling that lives in emitted
column expressions or in schema scale. The post-fix number does not restore the
claim, it prices it — the schema-agnostic machinery transfers *after* five
defects that only a run could find.

## A-5 (2026-08-22) — the fixes generalised: 0.7857 on a bank they never saw

Bank 2: 28 questions, drawn at seed 20260822 with all 24 bank-1 anchors
excluded, **verified at zero anchor overlap**, authored by the same blind
protocol (four fields of one anchor, never the expected answer), gold computed
from the blueprint before any question text existed. No code changed between the
two runs.

| | Development bank (n=27) | **Blind bank (n=28)** | Drop |
|---|---|---|---|
| `generic` | 0.8519 | **0.7857** | 0.0662 |
| `deterministic` | 0.2778 | **0.1964** | 0.0814 |
| **Arm gap** | +0.5741 | **+0.5893** | — |

**The fixes hold.** A development-to-blind drop of 0.0662 is close to the
project's own measured co-authorship bias (0.0483, C-021) and nowhere near the
collapse that would indicate the five changes had been fitted to 27 particular
sentences. Nothing in them names a label, a group, a relationship or a question;
the blind number is the evidence that this was not merely an intention.

**The arm gap widened rather than narrowed** — +0.5893 blind against +0.5741 on
the development set. If the schema-derived primitives' advantage were an artifact
of tuning against bank 1, the gap would shrink when the questions changed. It did
not. On a schema nobody wrote templates for, the primitives are worth roughly
+0.59 retrieval over the template cascade, and that figure is now blind.

**Where it is weaker, and it is not where the development set suggested.**
`facet-out` *improved* on the blind bank (0.5 → 0.8333) while the homogeneous
kinds fell (1.0 → 0.6 and 0.667) and `multihop` fell (1.0 → 0.5). The 1.0s on the
development set were partly small-sample luck rather than solved problems; five
questions per homogeneous kind cannot distinguish 1.0 from 0.7. The honest
reading of both banks together is that the homogeneous and multi-hop cases sit
somewhere around 0.6–0.8 and are the remaining weakness — which is a different
conclusion from either bank alone, and the reason two banks were run.

`facet-in` holds at 1.0 across both, so the reverse-direction failure that
motivated H3 is genuinely fixed rather than sampled away. Abstention holds at 1.0
across both.

**What this does not establish.** Both banks are drawn from one synthetic tenant
under one real schema, so this measures transfer to *this* schema, not to
schemas in general. The instances remain generated. And nothing here is judged
for correctness — it is retrieval only.

## A-6 (2026-08-22) — judged: the answers are faithful, and the templates fabricate

§5 recorded that judging was skipped because retrieval was 0.0000 and a grader
could only confirm a foregone number. With retrieval now at 0.7857 blind, that
reasoning no longer applies, so the blind bank's answers were graded.

Both arms, **one judging session, same grader instance**, on the 28 blind
questions:

| | `generic` | `deterministic` |
|---|---|---|
| Faithfulness | **0.9821** | 0.8893 |
| Groundedness | **0.9893** | 0.8500 |
| Evidence sufficiency | 0.6786 | 0.3036 |
| **Unsupported-claim rate** | **0.1071** | **0.8214** |
| Cross-source conflicts | 0 | 0 |

**The unsupported-claim rate is the finding.** The template cascade asserts
something its evidence does not support in **82%** of blind answers; the
schema-derived path does so in 11%. Retrieval already showed the templates
finding almost nothing on a foreign schema (0.1964) — this shows what the
composer then does with nothing, which is to keep asserting. Retrieving badly
and answering anyway is a worse failure than retrieving badly and abstaining,
and only the judged pass could distinguish them.

By question kind, the generic arm's unsupported claims are confined to two
places: `describe` at 0.50 and `homo-in` at 0.20. Every other kind is **0.000**,
including the abstention cases. The template arm is above 0.5 on every kind and
at 1.0 on `facet-in` and on `unanswerable` — it fabricates most reliably exactly
where it should decline.

**Evidence sufficiency of 0.6786 is the known composer ceiling, not a retrieval
gap.** The deterministic composer renders a claim as an id-line, so a judge
scoring "is there enough here to answer" marks attribute and compound questions
down however complete the retrieval was. That ceiling is a property of the
composer this project already has on record; it is not evidence about this
schema.

### Caveats that travel with these numbers

**The generic arm's grader is `mixed`: 25 of 28 answers got the real judge and 3
fell back to the deterministic proxy**, so its mean blends two graders while the
template arm's does not. That asymmetry favours neither side predictably and it
is not repaired by re-running — a second session recovered only 1 of the 3.

**Judge variance is measured, not assumed.** The same generic answers graded in a
second session returned faithfulness 0.9786 against 0.9821 — a spread of
**0.0035**, with the unsupported rate identical at 0.1071. The arm difference of
0.71 in unsupported-claim rate is two orders of magnitude larger than the
grader's own spread, so it is not grader noise.

**The reported figures come from the single session covering both arms.** A
second session graded the generic arm slightly better-covered (26/28), and it was
deliberately *not* substituted in: comparing arms graded in different sessions
folds grader variance into the arm difference, which is the confound
EXP-2026-08-009's protocol exists to avoid.

## A-7 (2026-08-22) — cross-model judging: the local judge overstates by 0.43

A-6's figures came from the local `skynet` relay. C-009 already established that
self-judged evaluation materially overstates quality and that the primary
evaluation must be cross-model. The same answers were therefore graded again by
**ten independent Claude Sonnet judges**, using the existing rubric **verbatim**
— `build_messages` composed the payloads, so only the *model* differs between
the two gradings and nothing about the prompt does.

**Blind bank, the same 28 answers, two judges:**

| | skynet | **Sonnet** | Overstatement |
|---|---|---|---|
| `generic` faithfulness | 0.9821 | **0.5500** | **0.4321** |
| `deterministic` faithfulness | 0.8893 | **0.3500** | **0.5393** |

The local judge overstates faithfulness by **0.43 on the schema-derived arm and
0.54 on the template arm**. For scale, C-009's original cross-model gap on the
MITRE pipeline was 0.1054. This is four to five times that.

**What survives, and it is the conclusion rather than the level.** The arm
ordering is preserved under both judges — the schema-derived path beats the
template cascade either way, by +0.20 faithfulness under Sonnet and +0.09 under
skynet. So *"schema-derived primitives transfer to a foreign schema better than
hand-written templates"* stands. What does not stand is any claim that the
answers are near-ceiling faithful: under an independent judge they are middling.

Development bank, same treatment: `generic` 0.6135, `deterministic` 0.3140.
Both banks agree that skynet's near-ceiling figures do not reproduce.

**Quote the Sonnet figures, not A-6's**, wherever a correctness number is
reported for this source. A-6 is kept because the disagreement between the two
is itself the measurement.

### What the independent judges found that the local one did not

Multiple judges, independently and without seeing each other's slices,
identified the same concrete defect — see [ISSUES.md](ISSUES.md) I-9. Answers
over an identity graph are rendered as *"Found N **ATT&CK record(s)** …"*
regardless of what the records actually are (`GROUP`, `GPO`,
`AWS_EC2_SECURITY_GROUP`, `ENTRA_APP_ROLE_ASSIGNMENT`, `DOMAIN`). The local judge
scored straight past it. One judge also flagged a genuine hallucination: five
enumerated group ids in `generic__ID-FACETIN-04` appear nowhere in the evidence,
with no truncation disclosure.

### Caveats

**Six of 108 verdicts could not be attributed to a bank and are excluded from
the per-bank split** (they are included in the pooled figures). The cause is an
instruction defect of mine: the agents were not asked to record which bank a
payload came from, and question ids repeat across banks, so six cases where the
same `(arm, question_id)` occurred twice inside one slice are ambiguous. The
remaining 102 were recovered by joining each slice's results back to its input.

**The two judges are not calibrated against each other.** EXP-2026-08-007
calibrated its grader at r = 0.9275 against Sonnet judgments; no such calibration
was run here, so the 0.43 is a raw difference between two instruments, not a
corrected one.

**Ten agents, one rubric, no cross-talk.** Each judged its own slice with no
sight of the other slices, the other arm's aggregate, or any expected answer.
Slices were balanced by payload size, not by arm or kind, so no judge saw only
one arm.
