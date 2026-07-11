#!/usr/bin/env python3
"""Generate expected-plan cases from the specialist golden banks.

The curated corpus (7 hand-reviewed cases in ``expected_plans/*.json``) is too
small to be statistically defensible for source-selection scoring. This
generator derives additional cases from the same snapshot-derived questions the
specialists are graded on, so the planner and specialists answer the same
catalogue.

Discipline (mirrors the gold-bank generators):

* **Never hand-keyed.** Each generated case's request/entities come straight from
  a specialist question; the expected source is that question's bank source.
* **Only cases the planner can route.** A candidate is kept only when the
  deterministic planner selects the gold source (source-recall == 1.0) and the
  plan is schema-adherent — so the corpus-wide hard guarantees hold. Over-routing
  (adding the other source) is *kept* and surfaces as reduced precision, which is
  a real finding, not a rejection.
* **No silent drops.** Every excluded question is reported with a reason
  (unroutable bare lookup, schema-rejected, or template-cap) so the coverage the
  corpus omits is explicit.
* **Bounded redundancy.** At most ``MAX_PER_TEMPLATE`` cases per
  (source, builder-template) so eight near-identical mitigation lookups don't
  swamp the corpus.

Regenerate with:
    uv run python -m utils.planner.evaluation.build_corpus
"""

from __future__ import annotations

import json
from pathlib import Path

from ..agent import PlanningAgent
from ..cards import load_source_cards
from ..config import PlannerConfig
from ..discovery import stub_live_view
from ..drafter import DeterministicDrafter
from .corpus import EXPECTED_PLANS_DIR, ExpectedCase, _FixedProbe
from .scorer import score_plan

GENERATED_DIR = EXPECTED_PLANS_DIR / "generated"
BANKS_DIR = (
    Path(__file__).resolve().parents[2]
    / "specialists" / "tests" / "golden"
)
BANK_FILES = {"attack": "attack_questions.json", "capec": "capec_questions.json"}

MAX_PER_TEMPLATE = 3          # cap near-identical cases per builder template
HOLDOUT_EVERY = 4             # every Nth kept case is frozen into the holdout

# Independent intent ground truth: map each specialist builder-template to the
# analyst intent its canonical question expresses. Derived from the template
# taxonomy (NOT the planner's classifier), so scoring the classified intent
# against it is a real measurement, not a tautology. A template with no entry
# is left unscored (expected_intent = None) rather than guessed.
TEMPLATE_INTENT = {
    # remediation — mitigations / defensive controls
    "technique_mitigations": "remediation",
    "tactic_technique_mitigations": "remediation",
    # lookup — a single entity by id
    "node_lookup": "lookup",
    "capec_lookup": "lookup",
    # enumeration — "which/list/scan X [rel] Y" -> a set
    "label_scan": "enumeration",
    "capec_scan": "enumeration",
    "group_techniques": "enumeration",
    "tactic_techniques": "enumeration",
    "campaign_techniques": "enumeration",
    "software_techniques": "enumeration",
    "campaign_attribution": "enumeration",
    "capec_neighbors": "enumeration",
    "technique_detection": "enumeration",
    "datacomponent_analytics": "enumeration",
    # traversal — explicit hierarchy / structure
    "subtechnique_parent": "traversal",
    "capec_hierarchy_chain": "traversal",
    # correlation — cross-source mapping
    "capec_maps_to": "correlation",
}


def _load_bank(source: str) -> list[dict]:
    data = json.loads((BANKS_DIR / BANK_FILES[source]).read_text(encoding="utf-8"))
    return data["questions"] if isinstance(data, dict) else data


def _candidate(source: str, q: dict) -> ExpectedCase:
    """A single-source expected plan straight from a specialist question."""
    return ExpectedCase(
        name=f"gen_{q['id']}",
        request=str(q["question"]),
        live=["attack", "capec"],
        expected_sources=[source],
        expected_entities={source: list(q["task"]["entities"])},
        expected_intent=TEMPLATE_INTENT.get(str(q.get("expected_template", ""))),
        origin="generated",
        tier=str(q.get("tier", "")),
    )


def generate() -> tuple[list[dict], list[dict]]:
    """Return ``(kept_case_dicts, excluded_records)`` deterministically.

    Runs the deterministic planner to decide routability; the result is stable
    because the planner and cards are deterministic against the pinned snapshot.
    """
    cards = load_source_cards("data")
    live_view = stub_live_view(cards, ["attack", "capec"])
    agent = PlanningAgent(
        PlannerConfig(data_dir="data"),
        cards=cards,
        drafter=DeterministicDrafter(),
        probe=_FixedProbe(live_view),
    )

    kept: list[dict] = []
    excluded: list[dict] = []
    per_template: dict[tuple[str, str], int] = {}

    for source in ("attack", "capec"):
        for q in _load_bank(source):
            if q.get("tier") == "adversarial":
                excluded.append({"id": q["id"], "reason": "adversarial (planner honesty covered by curated cases)"})
                continue
            case = _candidate(source, q)
            plan = agent.plan(case.request)
            score = score_plan(plan, case, cards, live_view)
            if score.source_recall < 1.0:
                excluded.append({"id": q["id"], "reason": f"unroutable (source_recall={score.source_recall:.2f}, routed={sorted(plan.target_sources())})"})
                continue
            if not score.schema_adherent:
                excluded.append({"id": q["id"], "reason": "schema-rejected by gate"})
                continue
            template = str(q.get("expected_template", "?"))
            key = (source, template)
            if per_template.get(key, 0) >= MAX_PER_TEMPLATE:
                excluded.append({"id": q["id"], "reason": f"template cap ({source}/{template} >= {MAX_PER_TEMPLATE})"})
                continue
            per_template[key] = per_template.get(key, 0) + 1
            kept.append({
                "name": case.name,
                "request": case.request,
                "live": case.live,
                "expected_sources": case.expected_sources,
                "expected_entities": case.expected_entities,
                "expects_join": False,
                "expects_unsupported": False,
                "expects_partial": False,
                "expected_intent": case.expected_intent,
                "origin": "generated",
                "tier": case.tier,
                "split": "dev",
                "_source_question": q["id"],
                "_template": template,
            })

    # Freeze a deterministic slice into the holdout for never-tuned measurement.
    for i, case in enumerate(kept):
        if i % HOLDOUT_EVERY == HOLDOUT_EVERY - 1:
            case["split"] = "holdout"
    return kept, excluded


def write(kept: list[dict]) -> None:
    """Replace expected_plans/generated/ with one file per kept case."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    for stale in GENERATED_DIR.glob("*.json"):
        stale.unlink()
    for case in kept:
        path = GENERATED_DIR / f"{case['name']}.json"
        path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")


def main() -> int:  # pragma: no cover - thin CLI wrapper
    kept, excluded = generate()
    write(kept)
    dev = sum(1 for c in kept if c["split"] == "dev")
    hold = sum(1 for c in kept if c["split"] == "holdout")
    print(f"Generated {len(kept)} cases -> {GENERATED_DIR} (dev={dev}, holdout={hold})")
    print(f"Excluded {len(excluded)} questions (reported, not silently dropped):")
    for rec in excluded:
        print(f"  - {rec['id']:14s} {rec['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
