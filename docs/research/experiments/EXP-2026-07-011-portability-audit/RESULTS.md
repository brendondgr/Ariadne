# RESULTS — EXP-2026-07-011 Portability audit

## 1. Headline

Most of the system transfers, and the part that does not is **bounded and
countable**: 19 of 25 distinct query templates are MITRE-specific, along with the
id-shape regexes, the canonical join key, and the question catalogue. Everything
else is driven by the source card rather than by MITRE.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json).

| Count | Value |
|---|---|
| Cypher builder template literals | 17 |
| Gremlin builder template literals | 11 |
| **Distinct template identifiers** | **25** |
| Exercised by the 120-question bank | 19 |
| MITRE-specific (need re-authoring) | 19 |

17 + 11 ≠ 28 because `describe`, `describe_by_name`, and `expand` are declared in
**both** builders. Counts are from an AST parse
([`derive_templates.py`](../../../plans/robustness/_overnight/derive_templates.py)),
not read off prose.

### Three layers, three answers

| Layer | Verdict |
|---|---|
| Harness and orchestration — LangGraph super-graph, sufficiency policy, hop cap, reducers, SSE contract, timeouts, claim composition, verifier, provenance chain, **and the entire evaluation apparatus** | **Fully portable.** Nothing here knows what MITRE is. |
| `describe` / `expand` primitives and routing glosses | **Card-driven.** Transfers with a new source card. |
| 19 hand-written templates, id regexes, the canonical join key, the 120-question catalogue, one regex in `failure_terminus.py` | **MITRE-specific.** Must be re-authored. |

## 3. Figures

None.

## 4. Interpretation

The honest framing, preserved from the audit: **the 0.9957–0.9972 scores came
from the MITRE-specific templates.** A new schema starts on the generic path.
Arm G ([`EXP-2026-07-007`](../EXP-2026-07-007-arm-g-templates-disabled/))
measures exactly what that costs — **0.6388 correctness**, a 0.3568 drop. So the
answer to "does it transfer" is: the machinery does, at roughly two-thirds of the
accuracy, until someone writes the templates.

That is a far more useful answer than either "yes" or "no", and it is the number
this audit exists to make quotable.

The most valuable portable asset is arguably not the pipeline but the
**evaluation apparatus** — arm runner, failure localisation, the judge panel,
the summariser. Only one line in it (an id regex in `failure_terminus.py`) is
MITRE-shaped.

## 5. Threats to validity

* **This is an audit, not a measurement.** No non-MITRE dataset was ever loaded.
  The portability verdict is a code reading, and code readings miss coupling
  that only shows up at run time.
* **"Portable" is not "works".** A layer that contains no MITRE strings can still
  make assumptions about graph shape, cardinality, or id density that a real
  second dataset would violate.
* **The counts are as at 2026-07-26.** The audit's own count was later refined —
  see ISSUES.md.

## 6. What surprised us

That the generic path exists and works at all. The system was built
template-first; the fact that disabling every template still answers 64 of 120
questions correctly means the card-driven primitives are a real fallback rather
than a stub.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Load one genuinely non-MITRE dataset and re-run Arm G against it. That is the
  only thing that converts this audit into evidence.
* Re-author the `failure_terminus.py` id regex to read from the source card.

## 8. Reproduction

```bash
uv run python docs/plans/robustness/_overnight/derive_templates.py
```

The layer classification is a manual read and is not automated.

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — The template counts are stale: 25 / 19 withdrawn, 29 / 20 recorded

**What was wrong.** §1 (`RESULTS.md:5–8`), §2 (`RESULTS.md:14–25`),
`manifest.yaml:52–53`, `data/metrics.json` and `portability.md:72` all state
**25 distinct template identifiers, 19 exercised by the 120-question bank**.
Those figures were correct for the tree of 2026-08-04/05 (`f87d145`, the
commit that reconciled the count; the derivation output carries
`generated_at: 2026-08-04`), which already post-dates this experiment's
recorded date of 2026-07-26 by ten days. They are wrong for the tree now:

* `EXP-2026-08-001` (2026-08-09) added `generic_bridge`, `generic_chain`,
  `generic_intersect` and `generic_walk` to the builders;
* `b72eb23` (2026-08-31, "derive_templates.py silently missed f-string
  template names") changed the derivation script, which also now counts
  `ambiguous-name` and `unanchored`; `node_lookup`, which the audit counted as
  generic, no longer exists.

The pointer at `data/POINTERS.md:9` recorded the 5888-byte `f87d145` version
of the script (`sha256:04c8acbd…`); the file is now 6853 bytes
(`sha256:9991aedf…`).

**What is now correct.** Running
`uv run python docs/plans/robustness/_overnight/derive_templates.py` on
2026-09-09 at `e7ee893` prints, verbatim from its JSON:

| Field | Value |
|---|---|
| `cypher_count` | 20 literals (+ one dynamic expression `f'{noun}_software'`, listed but not counted) |
| `gremlin_count` | 14 |
| `shared_names` | `ambiguous-name`, `describe`, `describe_by_name`, `expand`, `unanchored` (5) |
| **`distinct_identifier_count`** | **29** |
| **`exercised_count`** | **20** |
| `exercised_but_not_a_builder_template` | `boundary_refusal` (so 19 builder templates are exercised) |
| `declared_but_not_exercised` | `ambiguous-name`, `capec_facets`, `describe_by_name`, `expand`, `generic_bridge`, `generic_chain`, `generic_intersect`, `generic_neighbors`, `generic_walk`, `unanchored` |

`README.md` (after `b72eb23`) phrases the same output as "31 distinct template
labels — 29 of them actual query templates … 19 exercised": the 31 adds the two
f-string-generated names (`group_software`, `campaign_software`) that the
script lists but does not count, and the 19 excludes `boundary_refusal`. This
amendment records what the script prints, not the README's rephrasing.

**Manifest changes (old → new).**

* `metrics.values.distinct_query_templates` 25 → moved to `metrics.withdrawn`,
  `replaced_by: EXP-2026-07-011:distinct_query_template_identifiers_current` = **29**.
* `metrics.values.templates_exercised_by_the_bank` 19 → moved to
  `metrics.withdrawn`, `replaced_by:
  EXP-2026-07-011:templates_exercised_by_the_bank_current` = **20**.
* `metrics.values.mitre_specific_templates` 19 — **kept, not withdrawn.** It is
  the audit's manual classification (25 − 6 generic), which the script does
  not print. Applying the audit's own rule to today's list — 29 minus the nine
  generic or card-driven names (`describe`, `describe_by_name`, `expand`,
  `label_scan`, `generic_bridge`, `generic_chain`, `generic_intersect`,
  `generic_neighbors`, `generic_walk`) minus the two refusal outcomes
  (`ambiguous-name`, `unanchored`) — gives **18** literal MITRE-specific
  templates, or **20** if the two f-string-generated `*_software` templates
  are counted. That derivation is recorded in `data/metrics.json`
  (`current_derivation_2026_09_09.mitre_specific_by_the_audit_rule_applied_today`)
  and not promoted to a manifest value, because it is a reading, not a script
  output. C-010's "19 of 25" wording in `CLAIMS.md` should be read as "18–20 of
  29" until the ledger is updated; that edit is the ledger owner's.
* `data.version` "as at 2026-07-26" → "audit prose as at 2026-07-26
  (e938452); template counts from the 2026-08-04 derivation (f87d145),
  re-derived 2026-09-09". `data.n_examples` 25 → 29 (it is the template count).
* `data/POINTERS.md`: the derivation script re-hashed as it is now, and the
  five inputs it reads (two builders, three banks) added with today's hashes,
  so the 29/20 figures are pinned to a state. `data/metrics.json` gains
  `current_derivation_2026_09_09`, `manifest_metrics` and a `withdrawn` block;
  the original `template_counts` block is kept and labelled withdrawn.

**What does not change.** The three-layer classification, the interpretation
(§4) and the Arm G figures quoted from `EXP-2026-07-007` (0.6388, −0.3568,
64/120) — the B2 audit verified those against that experiment's manifest and
judgments.

## AMENDMENT A-2 (2026-09-09) — Superseded by EXP-2026-08-011: the audit was a code reading and the measurement disagreed with it

This experiment's verdict — that everything outside the templates, id regexes,
join key and catalogue is schema-agnostic and "transfers at roughly two-thirds
of the accuracy until someone writes the templates" (§1, §4) — was a reading
of the code, and §5 said so. `EXP-2026-08-011` (2026-08-21,
identity-schema-transfer) then *measured* it by pointing both arms at a
72-label customer identity schema with no code changes. Its finding, as its
own record states it: before any fix both arms retrieved nothing at all, and
the failure was in the **planner** — a layer this audit classified as fully
portable — not in the templates this audit counted; entity extraction is
card-driven but not schema-*scale*-independent. Five structural fixes later the
schema-derived path leads the template cascade by a wide margin on blind
questions. Quote the current figures from `EXP-2026-08-011`'s manifest (its
headline has been amended more than once and its own repair pass is moving the
original values to `metrics.withdrawn`); none of its numbers are restated here
so that this record cannot go stale a second time.

**Manifest change.** `status` complete → **superseded**; `superseded_by` null →
`EXP-2026-08-011`; `EXP-2026-08-011` added to `related`. The reverse link is
set in that experiment's manifest by its own repair. `supports_claims` (C-010)
is unchanged: C-010 was downgraded to `partial` on the strength of
`EXP-2026-08-011`, and this audit remains the record of *what was counted*, not
of *what transfers*.
