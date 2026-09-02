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

## I-5 — An ambiguous brief inverted the question's direction, and the stronger model was the one it fooled

**Found 2026-09-01 by switching the Author from a local relay model to Opus 5.**

The renderer's first frame was `the {plural} it {gloss}`, producing briefs like:

> the CAPEC attack patterns it can happen after

That is correct English and a garden path. It means *patterns X such that CAPEC-98
can happen after X* — i.e. things that come **before** CAPEC-98. Opus 5 read it
the other way and wrote "which patterns can happen **after** CAPEC-98", on two of
seven sampled specs (one D5, one D6). The gold was unchanged, so the pairing was
silently wrong.

**The weaker model did not invert it, and that is not reassurance.** The relay
model produced near-literal restatements of the brief; the stronger one
paraphrased, and paraphrasing is where an ambiguity gets resolved — sometimes the
wrong way. Reading "the weak model got it right" as evidence the brief was fine
would have shipped the defect.

**Why it matters beyond this pipeline.** Direction is the axis the blind holdout
collapsed on (EXP-2026-08-005: 0.7688 → 0.8952 after the binding/direction fix).
A generator that silently inverts direction on some fraction of its questions
would produce a bank that *looks* harder in exactly the place the system is
weakest, and the extra difficulty would be an artifact of the question text.

**Fixed.** Every relation gloss now names its own direction and cannot be read
both ways: each is either subject-first (`{s} uses`) or an unambiguous relative
clause about the object (`that can precede {s}`). Three tests enforce it — every
gloss must match one of those two shapes, directional pairs must be exact
opposites of each other (`CanPrecede` forwards == `CanFollow` backwards), and
only `PeerOf` may gloss identically in both directions.

After the fix, all 12 sampled D5/D6 questions carry the brief's direction
exactly, and re-authoring kept 126/126.

**Not retained:** the pre-fix Opus output was overwritten by the re-run, so the
two inverted questions survive only as the examples quoted above. A future
author-model comparison should keep both passes.

## I-6 — Some D0 items are plausible by construction and odd to a reader

The Author, unprompted, reported writing D0 items "that read oddly for the
subject type (e.g. S0614 asked as 'a sub-technique of', T1568 asked as what it
'detects')".

The plausibility rule requires only that the predicate be one some label in the
same catalogue carries. That removes category errors across catalogues and does
not remove them within one. A D0 question a reader can spot as malformed tests
whether the system parses, not whether it abstains, and the two are different
properties.

Not fixed. Tightening needs a semantic notion of which labels a predicate could
sensibly apply to, which is a judgement call worth making deliberately before the
full bank rather than hastily now.
