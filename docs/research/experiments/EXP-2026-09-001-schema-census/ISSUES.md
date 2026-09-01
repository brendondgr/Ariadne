# ISSUES — EXP-2026-09-001 Schema census

## I-1 — the first implementation silently dropped a whole taxonomy

CAPEC `Taxonomy_Mapping` elements were keyed on `Entry_ID`. All 272 ATTACK
mappings and all 38 WASC mappings carry one; **all 39 `OWASP Attacks` mappings
carry only `Entry_Name`**, so the entire taxonomy was dropped and the first run
reported 32 edge types instead of 33.

The direction matters: a dropped shape makes coverage look *better* than it is
(37.5% before, 36.4% after). This is the same failure family the project has now
recorded four times — a procedural artifact that moves a number in a consistent,
flattering direction and is invisible in a single pass.

**Fixed.** `Entry_ID` falls back to `Entry_Name`, and
`test_every_taxonomy_is_present` asserts all three taxonomies appear. Two
sibling tests were added for the same class of failure: all five declared CAPEC
natures, and every live STIX relationship type.

## I-2 — an existing category licenses a question in an ungradeable direction

`ATTACK_CATEGORIES["groups"]` is *"The techniques a named group uses, or the
groups using a technique"*. The first of those directions has a p90 fan-out of
**63** — a question drawn on that side has an answer too large to grade well.

This is not hypothetical: the categories are what the committed banks were drawn
from, so bank questions on that side already exist. **The failure mode is
attribution** — an answer that scores badly because the question has 63 gold
items reads as a system failure, not a question defect.

Not fixed here; fixing it means editing a generator that frozen banks were drawn
from, which is a decision, not a bug fix. Raised as Q29.

## I-3 — sub-element node counts are instance counts, not entity counts

CAPEC execution steps, consequences, skills, mitigations, prerequisites,
indicators, examples, resources and alternate terms have no identifiers in the
XML. The census synthesises ids the way the loaded graph does, so
`ExecutionStep: 815` means 815 step *instances* across 239 patterns, not 815
distinct steps. Stated in the protocol; noted here because the node table reads
like an entity count and is not one.

## I-4 — the identity graph is out of scope

The third graph is generated from a blueprint rather than parsed from a
catalogue, so nothing in this module applies to it. Its census needs a different
entry point. Any statement of the form "we cover N% of our graphs" must say
which graphs — this experiment covers two of three.
