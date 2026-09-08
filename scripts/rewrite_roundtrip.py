#!/usr/bin/env python3
"""Does a correctly filled form render to a question the engine answers the same way?

    uv run python scripts/rewrite_roundtrip.py --reference docs/evaluation/variants-2026-08-29/reference_2026-09-08.json

The whole hybrid design rests on one property. If the form is right, the sentence
:func:`utils.planner.canonical.render` emits must extract what the gold question
extracts — not merely something reasonable, the *same records*. That has to be
proved on the 120 gold forms before a model is anywhere near the pipeline,
because every later number is a comparison against this.

Nothing is reconciled. A gold form whose rendering does not round-trip is a
finding about the renderer or about the gold (the 2026-08-30 plan's "disagreement
is a finding" rule) and is written out for the experiment's ISSUES.md, never
quietly fixed by special-casing the case that missed.

Scored the way the variant harness scores, and for the same reason: ``records``
is the primary metric — the set of identifiers pulled out of the graph — because
reaching the same records through a different query is a success, not a failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.planner.canonical import (  # noqa: E402
    FormError,
    form_from_slot_gold,
    load_slot_gold,
    render,
)
from utils.planner.cards import load_source_cards  # noqa: E402
from utils.synthesis.config import SynthesisConfig  # noqa: E402

DEFAULT_SLOT_GOLD = "docs/evaluation/variants-2026-08-29/slot_gold.json"
DEFAULT_REFERENCE = "docs/evaluation/variants-2026-08-29/reference_2026-09-08.json"

#: Every LLM seam off, exactly as the variant harness sets them. A rendered
#: sentence that only round-trips with a model in the chain has proved nothing.
BASE_ENV: dict[str, str] = {
    "PLANNER_LLM_ENABLED": "false",
    "SPECIALIST_LLM_ENABLED": "false",
    "SYNTHESIS_LLM_ENABLED": "false",
    "CONVERSATION_LLM_ENABLED": "false",
    "ORCH_MAX_HOPS": "5",
}


def _apply_env() -> None:
    import os

    for key, value in BASE_ENV.items():
        os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot-gold", default=DEFAULT_SLOT_GOLD)
    parser.add_argument("--reference", default=DEFAULT_REFERENCE)
    parser.add_argument("--out", default=None, help="write the per-case report here")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="render every form and report coverage without touching the graphs",
    )
    args = parser.parse_args()

    _apply_env()
    from scripts.variant_harness import capture_one  # noqa: E402  (env first)

    cards = load_source_cards()
    reference = {r["case_id"]: r for r in json.loads(Path(args.reference).read_text())}
    records = load_slot_gold(args.slot_gold)
    if args.limit:
        records = records[: args.limit]

    rendered: list[dict[str, Any]] = []
    for record in records:
        case_id = str(record.get("case_id") or "")
        form = form_from_slot_gold(record)
        entry: dict[str, Any] = {
            "case_id": case_id,
            "bank": record.get("bank"),
            "form": form.to_dict(),
            "gold_question": (reference.get(case_id) or {}).get("question", ""),
        }
        try:
            entry["question"] = render(form, cards)
        except FormError as exc:
            entry["question"] = None
            entry["skip_reason"] = str(exc)
        rendered.append(entry)

    renderable = [e for e in rendered if e.get("question")]
    print(f"== {len(renderable)}/{len(rendered)} forms render")
    if args.render_only:
        _report(rendered, args.out)
        return 0

    config = SynthesisConfig.from_env()
    started = time.monotonic()

    def work(entry: dict[str, Any]) -> dict[str, Any]:
        return {**entry, **capture_one(entry["question"], config)}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        captured = list(pool.map(work, renderable))
    print(f"   ran {len(captured)} rendered questions in {time.monotonic() - started:.1f}s")

    by_id = {e["case_id"]: e for e in captured}
    for entry in rendered:
        got = by_id.get(entry["case_id"])
        if got is None:
            entry["records_exact"] = None
            continue
        entry.update(got)
        ref = reference.get(entry["case_id"]) or {}
        want = set(ref.get("entity_ids") or ())
        have = set(entry.get("entity_ids") or ())
        entry["records_exact"] = want == have
        entry["records_recall"] = (len(want & have) / len(want)) if want else None
        entry["missing"] = sorted(want - have)
        entry["extra"] = sorted(have - want)
        entry["queries_exact"] = sorted(ref.get("queries") or ()) == sorted(
            entry.get("queries") or ()
        )

    _report(rendered, args.out)
    return 0


def _report(rendered: list[dict[str, Any]], out: str | None) -> None:
    scored = [e for e in rendered if e.get("records_exact") is not None]
    exact = [e for e in scored if e["records_exact"]]
    print(f"== records_exact {len(exact)}/{len(scored)}")
    misses = [e for e in scored if not e["records_exact"]]
    if misses:
        print(f"== {len(misses)} miss(es):")
        for e in misses:
            print(f"   {e['case_id']:<16} missing={e['missing'][:4]} extra={e['extra'][:4]}")
            print(f"       rendered: {e['question']}")
            print(f"       gold:     {e['gold_question']}")
    skipped = [e for e in rendered if not e.get("question")]
    if skipped:
        print(f"== {len(skipped)} form(s) did not render:")
        for e in skipped:
            print(f"   {e['case_id']:<16} {e.get('skip_reason')}")
    if out:
        Path(out).write_text(json.dumps(rendered, indent=2, sort_keys=True) + "\n")
        print(f"   wrote {out}")


if __name__ == "__main__":
    raise SystemExit(main())
