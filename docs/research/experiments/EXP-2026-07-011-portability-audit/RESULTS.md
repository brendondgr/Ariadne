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
