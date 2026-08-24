# Dataset Card — generated bank, seed 9010

**Size:** 30 questions · **Scale:** 1× · **Authored by:** skynet @ http://localhost:4000/v1
**Snapshot:** ATT&CK 19.0 / CAPEC 3.9
**Excluded before drawing:** 359 previously-used anchors

## What it is

A question set drawn and compiled by
`utils/specialists/evalset/make_bank.py`. Anchors were sampled uniformly from
the live id space of the pinned snapshot — {'attack': 12, 'capec': 8, 'federated': 10} by stratum — with every
anchor used by a previous bank excluded, so this set is disjoint from all of
them.

Gold is **computed, never authored**: every expected answer is derived from
`gold_bank.py`'s independent parse of the raw STIX/XML. An anchor whose gold
could not be computed was discarded rather than repaired.

## How blind it is

As blind as the hand-driven holdout v1, by the same mechanism: the Author is
shown a category description, an identifier, an entity type and a name, and
nothing else — never the templates, never the schema, never an example question.
Each question is a stateless completion with no tool access and no repository
access.

Authored questions were validated, not trusted: a question that failed to name
its own anchor, or that named any *other* MITRE identifier, was rejected and
re-requested. 1 question(s) needed at least one retry; 0
anchor(s) could not be authored at all.

## What it is not

**Not a substitute for human-authored questions in a published headline figure.**
One model at one temperature explores a narrower band of phrasing than a set of
independent human authors would, and phrasing is part of what a question set
tests. This bank is a strong *regression* and *arm-comparison* instrument — it
is disjoint, fairly drawn, and mechanically scored — and a weaker basis for an
absolute claim about generalisation.

**Not immortal.** The moment a defect this bank finds gets fixed, it stops being
blind, exactly as holdout v1 did. That is expected and is no longer expensive:
draw another.

## Reproduction

```bash
uv run python -m utils.specialists.evalset.make_bank --seed 9010 \
    --scale 1
```
