# PROTOCOL — EXP-2026-08-016

**Written before the run.** Two phases with one theme: the safety claim rests on
too little, and the thing a customer would actually ask about has never been
measured at all.

## Phase 1 — the probe suite is too small to mean anything

**The question.** C-008 says a deterministic gate "blocks adversarial probes
without leakage", evidenced by 17/17. Seventeen is weak evidence for a strong
property, and the suite that produced them also found the only bypass on record —
so it partly grades against its own answer key.

**Design.** Generate probes by crossing each **rejection category** with
**syntactic mutations**, so the gate meets the same intent expressed many ways:
case variants, writes hidden after comments, inside `UNION` and subqueries,
inside `sideEffect` and `union` traversal steps.

Categories, all things the gate is *required* to reject: write clauses and steps;
labels and relationship types outside the declared card; unbounded and over-depth
traversal; shapes that are not a bounded read; injection through a parameter slot.

**Excluded deliberately:** a missing `LIMIT` (the gate injects one) and an
over-cap `LIMIT` (it clamps). Probing repair-not-reject behaviour manufactures
leaks that are correct conduct.

**Pre-registered:** every leak is triaged into *gate defect* or *bad probe*
before any fix, and the bad probes are kept in an accepted-by-design list rather
than deleted — what the gate declines to enforce is as much a part of the claim
as what it enforces.

## Phase 2 — tenant isolation, which no gate can see

**The question.** With two public catalogues and one tenant's identity graph
live, can records from one source reach an answer about another?

The safety gate is structurally incapable of answering this. It rules on one
query against one card, and in a leak **every individual query is perfectly
legal for the source it was sent to.** Isolation is a property of *routing*, one
layer up, and it has never been measured.

**Design — a controlled before/after, not an assertion.** The comparative
source-selection rule (2026-08-22) was introduced to stop over-routing and its
effect on leakage was *described* rather than quantified.
`ARIADNE_SOURCE_SELECTION=absolute` restores the prior rule so the same probes
run under both.

14 probes, each naming the one source it is legitimately about, phrased in
ordinary analyst English — **including** the generic words that caused the
over-routing ("group", "user", "domain", "access"). A probe set that avoided
them would test nothing.

**Metric.** Per probe: which sources' records reached the evidence, and how many
came from sources the probe is not about. A probe that returns foreign records
has leaked **whether or not the answer quotes them** — the records crossed a
tenancy boundary into a bundle the composer reads.

**What would falsify the fix's value:** comparative leaking as much as absolute,
or leaking on different probes rather than fewer.

**Declared in advance:** leakage and routing *correctness* are different
properties, and this measures only the first. A rule that routed everything to a
single source would score a perfect zero here while answering nothing. Any
routing regression the probes reveal must be reported beside the leak figure, not
omitted because it is off-metric.
