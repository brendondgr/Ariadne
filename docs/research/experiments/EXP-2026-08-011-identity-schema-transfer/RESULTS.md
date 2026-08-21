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
