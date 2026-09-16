#!/usr/bin/env python3
"""Generate, once and offline, the words an analyst uses for each declared relationship.

EXP-2026-09-027 (plan Step 8). The router matches a question's words against
the node labels and relationship types a card declares, plus the one gloss
sentence the card carries per relationship. That is why "How do I defend
against T1047?" binds no relation: the card knows MITIGATES and "A Mitigation
mitigates a Technique", and nothing about "defend", "stop", "counter" or
"protect". 54 of the exposed bank's 172 T1/T2 misses are this.

This script asks the local model, one call per declared relationship, for the
ordinary English an analyst would use to ask for that relationship's members,
given only the card's gloss and the relationship's declared endpoints. The
output is committed into the card overlay and the built card under
``entity_descriptions.relationship_paraphrases`` — reviewable text, consumed
at query time by the same deterministic gloss index the router already reads,
with **no model call per question**. Nothing here names a catalogue: the
prompt is built from whatever the card declares, so the same script runs on
any card with glosses.

Every generated word is filtered against the cards themselves: a word that is
already a label or relationship name anywhere (a routing token) is dropped, so
a paraphrase can bind a relation but never re-route a question; a word that
the model offered for more than one relationship of the same card is dropped
as ambiguous. The dropped words are written beside the kept ones.

    uv run python scripts/generate_relation_lexicon.py --dataset attack --dataset capec
    uv run python scripts/generate_relation_lexicon.py --dataset attack --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.llm import chat  # noqa: E402
from utils.planner.cards import load_source_cards  # noqa: E402
from utils.planner.config import PlannerConfig  # noqa: E402
from utils.planner.llm_drafter import extract_json_object  # noqa: E402

PROMPT_VERSION = "relation-lexicon-v1"
_WORD_RE = re.compile(r"[a-z][a-z\-']+")
_SYSTEM = """\
You help a search system understand analyst questions. You will be shown ONE \
relationship from a knowledge graph: its name, the kinds of node at each end, \
and the one-sentence description its authors wrote. Reply with a JSON object:
  {"words": [...]}
"words" is a list of 8 to 20 lower-case English words or two-word phrases an \
analyst might use in a question that asks for the members of this relationship \
WITHOUT using the relationship's own name. Include verbs and nouns ("defend", \
"countermeasure", "protect against"). Do not include the node kinds' own names, \
do not include the relationship's name or its inflections, and do not include \
generic question words (which, what, list, show). Reply with the JSON only.\
"""


def _endpoints(card, rel: str) -> list[tuple[str, str]]:
    pairs = card.allowed_edge_patterns.get(rel) or []
    out = [(str(a), str(b)) for a, b in pairs if a and b]
    if out:
        return out
    try:
        from utils.specialists.schema import get_registry

        schema = get_registry().dataset(card.dataset)
        if schema is not None:
            return sorted({
                (label, f.neighbour_label)
                for label in schema.labels()
                for f in schema.label_facets(label)
                if f.rel_type == rel and f.direction == "out" and f.neighbour_label
            })
    except Exception:  # noqa: BLE001 — no registry, no endpoints; the gloss still carries
        pass
    return []


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _routing_tokens(cards) -> set[str]:
    out: set[str] = set()
    for card in cards.values():
        for name in list(card.node_labels) + list(card.relationship_types):
            spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").lower()
            out |= {w for w in spaced.split() if len(w) >= 3}
            out |= {w + "s" for w in spaced.split() if len(w) >= 3}
    return out


def generate(dataset: str, cards, *, dry_run: bool) -> dict:
    card = cards[dataset]
    glosses = (card.entity_descriptions or {}).get("relationships") or {}
    settings = PlannerConfig.from_env().llm_settings()
    routing = _routing_tokens(cards)
    raw: dict[str, list[str]] = {}
    for rel in sorted(card.relationship_types):
        ends = _endpoints(card, rel)
        user = (
            f"Relationship name: {rel}\n"
            f"Runs from: {', '.join(sorted({a for a, _ in ends})) or 'unknown'}\n"
            f"Runs to: {', '.join(sorted({b for _, b in ends})) or 'unknown'}\n"
            f"Description: {glosses.get(rel) or '(none)'}\n"
        )
        if dry_run:
            print(f"--- {rel}\n{user}")
            continue
        # A reasoning model spends its budget thinking before it answers; a
        # budget that fits the answer alone comes back empty (D-030). Two
        # attempts with a generous budget, and a relationship that still yields
        # nothing is recorded as ungenerated rather than crashing the run.
        words: list[str] = []
        for budget in (16384, 32768):
            try:
                result = chat(settings, [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
                              max_tokens=budget, temperature=0.0)
                payload = extract_json_object(result.content or "") or {}
            except Exception as exc:  # noqa: BLE001 — recorded below, never fatal
                print(f"{rel}: attempt at {budget} tokens failed ({type(exc).__name__}: {exc})")
                continue
            words = [str(w).strip().lower() for w in (payload.get("words") or []) if str(w).strip()]
            if words:
                break
        raw[rel] = words
        print(f"{rel}: {len(words)} words" + ("" if words else "  (ungenerated)"))
    if dry_run:
        return {}
    # -- filter: never a routing token, never shared by two relationships of this card
    offered = Counter(w for words in raw.values() for w in set(words))
    kept: dict[str, list[str]] = {}
    dropped: dict[str, dict[str, str]] = {}
    for rel, words in raw.items():
        kept[rel] = []
        dropped[rel] = {}
        for w in dict.fromkeys(words):
            toks = _tokens(w)
            if not toks:
                continue
            if toks & routing:
                dropped[rel][w] = "names a label or relationship somewhere"
            elif offered[w] > 1:
                dropped[rel][w] = "offered for more than one relationship"
            elif w.replace("-", " ").replace("_", " ") in rel.replace("_", " ").lower():
                dropped[rel][w] = "the relationship's own name"
            else:
                kept[rel].append(w)
    return {"prompt_version": PROMPT_VERSION, "model": settings.model, "kept": kept, "dropped": dropped,
            "ungenerated": sorted(rel for rel, words in raw.items() if not words)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", action="append", required=True)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cards = load_source_cards(args.data_dir, check_consistency=False)
    for dataset in args.dataset:
        out = generate(dataset, cards, dry_run=args.dry_run)
        if not out:
            continue
        # The sidecar is what the router reads (`utils/planner/drafter.py`
        # `_paraphrases_for`); the overlay carries the same words into the next
        # card build. The BUILT card is never written: it is an artifact that
        # completed experiments pin by hash.
        review = REPO / args.data_dir / "source_cards" / "overlays" / f"{dataset}.relation_lexicon.json"
        review.write_text(json.dumps(out, indent=2) + "\n")
        overlay = REPO / args.data_dir / "source_cards" / "overlays" / f"{dataset}.overlay.json"
        doc = json.loads(overlay.read_text())
        doc.setdefault("entity_descriptions", {})["relationship_paraphrases"] = out["kept"]
        overlay.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"wrote {review.relative_to(REPO)} and the overlay for {dataset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
