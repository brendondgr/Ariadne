# ISSUES — EXP-2026-08-011 Identity-schema transfer

Recorded as they were found, before any arm was scored. Two of these are
**findings**, not merely defects: they are run-time couplings that
[EXP-2026-07-011](../EXP-2026-07-011-portability-audit/) could not have seen,
and that audit's own threats section predicted exactly this — *"code readings
miss coupling that only shows up at run time."*

---

## I-1 — `label_scan` emitted a MITRE property name against a foreign schema

**Status:** fixed before any arm ran. **Bears on:** C-010.

The first real query put through the identity source was *"Which groups does the
Helpdesk group own?"*. The Cypher builder produced:

```cypher
MATCH (n:AWS_EC2_SECURITY_GROUP) RETURN n.attack_id AS id, n.name AS name
```

This schema has no `attack_id` property anywhere. Every row therefore returned a
null id, the normalizer rejected all five for `provenance missing 'record_id'`,
and a syntactically valid query against a correctly loaded graph returned
nothing.

**Why this matters beyond the fix.** EXP-2026-07-011 counted 19 of 25 templates
as MITRE-specific by parsing the source for template identifiers, and classified
the rest as portable. `label_scan` is one of the six it did *not* flag — because
its MITRE-specificity is not in its question shape, which is generic ("scan a
label"), but in the **property name it emits**. An AST count of template
identifiers cannot see that, and no amount of re-reading the code would have,
because the code looks correct until a schema without `attack_id` arrives.

So C-010's "bounded and countable" surface was undercounted, and the
undercounting is systematic rather than incidental: the audit measured
*question shapes*, and this class of coupling lives in *emitted column
expressions*.

**Fix:** `coalesce(n.attack_id, n.id)`, which is the same idiom the merged build
already uses (D-017). Byte-identical on ATT&CK, where `attack_id` is never null
on a scannable label; correct on any source whose public id is `id`.
`utils/specialists/cypher/builder.py::_label_scan`. 794 passed, 2 skipped across
`utils/specialists` after the change.

**Why fixing it now does not burn the bank.** The blind-bank trap that
`make_bank.py` documents is fixing something *in response to a holdout question
failing*, which converts a test set into a second development set. This defect
was found by a hand-written smoke query before the bank was drawn against any
arm, so the bank is still blind. Any defect the bank itself finds must be
recorded and left, or the bank burned.

---

## I-2 — The planner routes "group" to `AWS_EC2_SECURITY_GROUP`

**Status:** open, and **deliberately not fixed**. **Bears on:** the T4
label-disambiguation reading.

The same query — *"Which groups does the Helpdesk group own?"* — was routed to
`AWS_EC2_SECURITY_GROUP`, an EC2 network firewall rule set, rather than to
`GROUP`, the Active Directory security group the question is obviously about.

This is not a bug to fix inside this experiment. It is one of the things the
experiment exists to measure, and it is the predicted consequence of a schema
seven times wider than ATT&CK's: six labels contain the token `GROUP`
(`GROUP`, `ENTRA_GROUP`, `OKTA_GROUP`, `GCP_GROUP`, `AWS_SSO_GROUP`,
`AWS_EC2_SECURITY_GROUP`), and one of them is not an identity principal at all.

The source card's `entity_descriptions` were authored specifically to give the
planner a disambiguation signal here, and every one of those six glosses says
what it is distinct from. That the routing still lands on the firewall label
suggests label matching is not consulting the glosses, or is matching on
substring before meaning. Recorded now; it will be quantified over the bank
rather than anecdotally.

---

## I-3 — Seven of thirty questions initially returned empty from the author

**Status:** retried with a larger budget. **Bears on:** nothing in the results.

The served model is a reasoning model: it spends tokens on a reasoning trace
before emitting content, so a small `max_tokens` truncates mid-trace and returns
an empty string. At 4,096 tokens, 23 of 30 authored and 7 came back empty. An
empty reply reads as "the model declined" when it actually means "the budget was
too small".

`author_all` refuses to record an empty string as a question — recording `""`
would manufacture an unanswerable question by accident and quietly depress the
score — and checkpoints per question, so the retry at 16,384 re-attempts only
the seven.

---

## I-4 — Two truncations in the delivered catalog, both permanent

**Status:** permanent limitation, handled and reported. **Bears on:** every
result.

Recorded in full in the
[dataset card](../../datasets/cards/reliaquest-identity-catalog.md). In short:
the delivered export inner-joined to the attribute catalog, so every edge type
with no attributes was dropped before the file was written. Seen from the edge
side there is no `USER -MEMBER_OF-> GROUP` and 48 of 60 triples start at `GROUP`;
seen from the node side, **58 of 72 declared node types appear in no declared
triple at all**.

The operator confirmed on 2026-08-21 that no corrected export will be supplied.
Three inferred edges are therefore carried in a separate marked block, never
merged into the declared set, and every result splits declared-vs-inferred.
Inferred edges are 1,115 of 3,814 in the generated tenant (29%), essentially all
of them group membership, so any user-anchored question traverses this project's
reconstruction and is confounded to that extent. Questions in the `homo-*` kinds
— H3's population — are guaranteed free of it by a test.

---

## I-5 — The generator wrote an edge twice; the store MERGEd it away

**Status:** fixed during step 5. **Bears on:** methodology, not results.

A planted attack chain re-created two edges the random passes had already made
(`USER -MEMBER_OF-> GROUP` and `GROUP -DC_SYNC-> DOMAIN`). Neo4j MERGEd each
pair back to one, so the blueprint claimed 3,816 edges against a store holding
3,814 — precisely the blueprint-versus-graph divergence the whole spec-derived
gold design exists to prevent.

Worth recording because it is evidence the design earns its cost: the divergence
was caught by a count check at load time rather than surfacing later as an
unexplained gold mismatch on individual questions. `_Builder.edge` is now
idempotent on `(source, edge, target)`.

---

## I-6 — Concurrent-session accident: the shared Docker project was taken down

**Status:** resolved, no data lost. **Bears on:** nothing in the results, but
recorded because it touched stores other work depends on.

While recreating the identity container with the correct credentials, a
`docker compose --profile identity down -v` was issued. `down` acts on the whole
compose project rather than the named profile, so `ariadne-neo4j` (ATT&CK) and
`ariadne-gremlin` (CAPEC) were stopped and removed alongside it.

No data was lost. Neo4j's store is a bind mount, so ATT&CK came back at exactly
4,369 nodes. Gremlin is an in-memory TinkerGraph with no volume and never
survives a restart — a pre-existing property of this setup, already noted in the
EXP-2026-08-009 changelog — so CAPEC was reloaded, returning 4,769 vertices and
6,972 edges.

`EXP-2026-08-010` was running concurrently in another session. Its last artifact
was written at 16:52; the containers went down at ~17:34, so it had already
finished writing and was not affected.

The correct command is `docker compose stop <service>` or `down` naming the
service explicitly. Never `down -v` on a shared project.

---

## I-7 — The development-bank judging run is unusable (server contention)

**Status:** failed, recorded not deleted. **Bears on:** nothing — no figure from
it is reported.

After the blind bank was judged successfully (A-6), the same pass was run over
the 27-question development bank so correctness could be compared
development-vs-blind the way retrieval already had been. It failed.

The LLM judge reached **12 of 27** generic answers and **0 of 27** deterministic
answers. The deterministic arm was therefore graded entirely by the fallback
proxy, and the two arms were scored by different instruments — which is exactly
the confound A-6 refused to introduce by substituting a second grading session.

Its numbers (generic faithfulness 0.9519, deterministic 0.1111) are **not a
correctness comparison** and must not be quoted or aggregated. The file is kept
and flagged `UNUSABLE` in its own metadata rather than deleted.

**Cause is environmental, not a defect.** The shared relay stopped answering: a
one-line completion that returned in about two seconds earlier in the session
did not return within 90 seconds when checked immediately afterward. Nothing in
the judge stage changed between the successful blind run and this one.

**What it does not affect.** The blind judged result (A-6) was taken in a single
earlier session with 25/28 and 28/28 coverage and stands. The
development-vs-blind *retrieval* comparison (A-5) involves no language model at
all and is unaffected.

**To retry:** re-run `--stage judge --out docs/evaluation/identity-2026-08-21`
when the relay is idle, and check `source` is `llm` for **both** arms before
reporting anything from it.

---

## I-8 — Bank 3 drawn at 117 questions; `multihop` cannot be scaled

**Status:** open, awaiting authoring. **Bears on:** every per-kind figure.

A-5 and A-6 both rest on kinds of two to six questions, and A-5 records that the
development set's 1.0s on `homo-*` and `multihop` were partly small-sample luck
— five questions cannot distinguish 1.0 from 0.7. Bank 3 exists to fix that.

117 questions drawn at seed 20260823, excluding every anchor used by banks 1 and
2 (49 of them), **verified at zero overlap**, across 86 distinct anchors. Gold is
computed and committed; only authoring remains, and that needs the relay.

| Kind | Bank 1 | Bank 2 | **Bank 3** |
|---|---|---|---|
| `facet-out` | 6 | 6 | **24** |
| `facet-in` | 5 | 6 | **24** |
| `homo-out` | 5 | 3 | **20** |
| `homo-in` | 5 | 5 | **20** |
| `describe` | 3 | 4 | **16** |
| `unanswerable` | 2 | 2 | **12** |
| `multihop` | 1 | 2 | **1** |

**`multihop` is the exception and cannot be fixed without invalidating the other
two banks.** The generator plants exactly five attack chains, and banks 1 and 2
consumed four of them; only one anchor remains. Planting more chains means
regenerating the tenant, which changes node ids and therefore every gold answer
in banks 1 and 2 — so the three banks would no longer be measuring the same
graph and could not be compared.

The multi-hop figure therefore stays at n=1 for now and **must not be quoted as
a rate**. Raising it properly means a fresh tenant with more planted chains and
a re-run of all three banks against it, which is a new experiment rather than an
amendment.

---

## I-9 — Every answer is labelled an "ATT&CK record", whatever the source

**Status:** open, located, **deliberately not fixed yet**. **Bears on:** A-7 and
every faithfulness figure for this source.

`utils/specialists/cypher/normalizer.py:885,888` hardcodes the source name into
the evidence summary:

```python
return f"Found ATT&CK record {rec.primary_id}: {rec.name}."
f"Found {total} ATT&CK record(s) including {id_text}"
```

There is no card lookup and no dataset branch. Every answer from every source is
described as an ATT&CK record, so an identity graph returns *"Found 54 ATT&CK
record(s)"* about `GROUP`, `GPO`, `DOMAIN`, `AWS_EC2_SECURITY_GROUP` and
`ENTRA_APP_ROLE_ASSIGNMENT` objects that have nothing to do with MITRE.

**How it was found is the point.** Several of the ten independent Sonnet judges
flagged it without seeing each other's work, and it is a substantial part of why
they scored faithfulness 0.43 below the local judge — an answer that misstates
what its records *are* is unfaithful even when every identifier in it is
correct. The local judge scored past it entirely.

This is the third member of the same family as I-1 (`n.attack_id` emitted
against a schema without it) and the `Technique` label scanned against a graph
that has none: MITRE vocabulary baked into code that presents itself as
source-agnostic, invisible to a code reading because there is no schema
dependency to spot — only a string.

**Why not fixed now.** The answers currently under measurement were produced by
the present code. Fixing the summariser mid-flight would leave the judged
figures describing a system that no longer exists. The fix is a one-line
card lookup, and it belongs with a re-run and a fresh judging pass.

**When fixed, re-judge rather than re-quote.** A-7's numbers are a measurement of
this defect as much as of the retrieval path, so they do not carry over.

**RESOLVED 2026-08-22.** `summarize()` now reads the source name from each
record's own `provenance.source`, which `emit_record` already fills from the
source card — so the label is whatever the card declares rather than a literal.
Four branches were hard-coded, not two. Two further corrections came with it:

* The source name is rendered after "in", never welded into a noun phrase. A
  card may legitimately call itself "the ReliaQuest identity graph", and
  *"Found 5 the ReliaQuest identity graph record(s)"* is not a sentence.
* A record with no `primary_id` rendered as *"Found record : Database Admins"* —
  a dangling colon that reads as a missing citation, which is how the judges
  scored it. The identifier is now included only when one exists.

```
before:  Found 54 ATT&CK record(s) including unknown and more.
after:   Found 1 record in the ReliaQuest identity graph: Database Admins.
```

**This is not a cosmetic change and must not be filed as one.**
`utils/synthesis/composer.py:181` uses the specialist summary as *claim text*,
so the false "ATT&CK record" statement was being promoted into an asserted
claim. That is why independent judges marked it unfaithful, and why the fix is
expected to move the number rather than tidy the prose.

**It changes ATT&CK's claim text too**, which is a consequence the operator
should weigh rather than something to ship quietly:

```
before:  Found ATT&CK record T1055: Process Injection.
after:   Found 1 record in MITRE ATT&CK: Process Injection (T1055).
```

Recorded MITRE answers will therefore no longer match byte-for-byte on a re-run.
**The MITRE golden banks have NOT been re-run to quantify this** — that touches
other experiments' committed artifacts and is not this experiment's to do. The
one ATT&CK branch that already read "in MITRE ATT&CK" is unchanged.

Retrieval is unmoved by the fix (0.7877 / 0.3177 before and after), which
confirms it altered prose and not what was found. 999 tests pass.

**Still latent:** the Gremlin normalizer carries the same hard-coded "CAPEC"
phrasing. It is not wrong today because CAPEC is the only Gremlin source, but it
is the identical trap waiting for the next one.
