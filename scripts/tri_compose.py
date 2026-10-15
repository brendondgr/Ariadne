#!/usr/bin/env python3
"""Compose a three-source data directory: ATT&CK + CAPEC + the identity graph.

    uv run python scripts/tri_compose.py            # build data-tri/
    uv run python scripts/tri_compose.py --check    # verify it matches its sources

Why a script and not a committed directory: source cards are derived artifacts
and are gitignored, so the only reproducible form of "these three sources
together" is the recipe. The manifest records the SHA-256 of every card it
copied, so a stale composition is detectable rather than silently wrong.

**The endpoint map is the load-bearing part.** Two of these three sources are
Neo4j-backed, and until 2026-08-22 a URI was resolved by *backend*, so the
second one probed the first one's store -- `identity` reported ATT&CK's 4369
nodes and "none of the expected labels present". The per-source override
(``ARIADNE_ENDPOINT_<DATASET>``) is what makes them separately addressable.

The addresses are declared here rather than read from each card's own
``connection.uri`` because two of the cards carry container-internal ports
(attack ``:7687``, capec ``:8182``) -- what the build saw from inside the
compose network, not what the host can dial. That is I-14; until it is fixed at
the build, the published address has to come from somewhere, and somewhere
explicit beats somewhere implicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OUT_DIR = REPO / "data-tri"

# dataset -> (home data dir, host-published endpoint)
#
# The card is not the whole source. The schema registry -- which is what makes
# every generic primitive schema-driven rather than MITRE-shaped -- is built
# from `<data_dir>/graphs/<dataset>/canonical/{nodes,relationships}.jsonl`, and
# `discover_datasets` finds a dataset only if that nodes file exists. Composing
# the cards alone produced a directory where the registry was EMPTY, so
# `_name_bearing_labels` fell through to its hardcoded MITRE fallback and a
# question routed correctly to `identity` was answered with a query over
# `n:Technique OR n:SubTechnique OR ...`. It looked exactly like a routing
# defect and was a missing-artifact defect; the canonical tree has to come too.
SOURCES: dict[str, tuple[str, str]] = {
    "attack": ("data", "bolt://localhost:5456"),
    "capec": ("data", "ws://localhost:6455/gremlin"),
    "identity": ("data/identity", "bolt://localhost:5459"),
}


def card_path(dataset: str) -> str:
    return f"{SOURCES[dataset][0]}/source_cards/{dataset}.json"


def canonical_paths(dataset: str) -> list[str]:
    home = SOURCES[dataset][0]
    return [
        f"{home}/graphs/{dataset}/canonical/nodes.jsonl",
        f"{home}/graphs/{dataset}/canonical/relationships.jsonl",
    ]

def overlay_path(dataset: str) -> str:
    home = SOURCES[dataset][0]
    return f"{home}/source_cards/overlays/{dataset}.overlay.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def env_exports() -> dict[str, str]:
    """The per-source endpoint overrides this composition requires."""
    return {f"ARIADNE_ENDPOINT_{ds.upper()}": uri for ds, (_, uri) in SOURCES.items()}


def compose(check_only: bool = False) -> int:
    cards_dir = OUT_DIR / "source_cards"
    overlays_dir = cards_dir / "overlays"
    # Beside source_cards/, never inside it. The card loader reads *every* JSON
    # file in that directory as a card, so a manifest left there loads as a
    # nameless one and every request fails with "Inconsistent source card '':
    # card has no node_labels".
    manifest_path = OUT_DIR / "tri_manifest.json"

    required: dict[str, list[str]] = {
        ds: [card_path(ds), *canonical_paths(ds)] for ds in SOURCES
    }
    missing = [p for paths in required.values() for p in paths if not (REPO / p).exists()]
    if missing:
        print("missing artifact(s) — build the sources first:")
        for p in missing:
            print(f"  {p}")
        return 2

    entries = {
        ds: {
            "card": card_path(ds),
            "canonical": canonical_paths(ds),
            "sha256": {p: sha256(REPO / p) for p in paths},
            "endpoint": SOURCES[ds][1],
        }
        for ds, paths in required.items()
    }

    if check_only:
        if not manifest_path.exists():
            print(f"not composed: {manifest_path} does not exist")
            return 1
        recorded = json.loads(manifest_path.read_text())["sources"]
        drifted = [
            ds for ds in entries
            if recorded.get(ds, {}).get("sha256") != entries[ds]["sha256"]
        ]
        registry_missing = [
            ds for ds in entries
            if not (OUT_DIR / "graphs" / ds / "canonical" / "nodes.jsonl").is_file()
        ]
        if registry_missing:
            print(f"INCOMPLETE — no canonical tree for: {', '.join(sorted(registry_missing))}")
            return 1
        if drifted:
            print(f"STALE — recomposed source card(s): {', '.join(sorted(drifted))}")
            return 1
        print(f"data-tri is current ({len(entries)} sources)")
        return 0

    overlays_dir.mkdir(parents=True, exist_ok=True)
    for ds in SOURCES:
        shutil.copy2(REPO / card_path(ds), cards_dir / f"{ds}.json")
        overlay = REPO / overlay_path(ds)
        if overlay.exists():
            shutil.copy2(overlay, overlays_dir / overlay.name)
        # The canonical tree, so `discover_datasets` finds all three and the
        # schema registry is built for each. Without it the registry is empty
        # and every schema-driven primitive silently reverts to its MITRE
        # fallback -- which reads as a routing bug and is not one.
        dest = OUT_DIR / "graphs" / ds / "canonical"
        dest.mkdir(parents=True, exist_ok=True)
        for rel in canonical_paths(ds):
            shutil.copy2(REPO / rel, dest / Path(rel).name)

    manifest_path.write_text(
        json.dumps({"sources": entries, "env": env_exports()}, indent=2) + "\n"
    )
    print(f"composed {OUT_DIR.relative_to(REPO)} — {len(entries)} sources")
    for ds, entry in sorted(entries.items()):
        print(f"  {ds:9s} {entry['endpoint']}")
    print("\nexport these before running against it:")
    for key, value in env_exports().items():
        print(f"  {key}={value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify, do not write")
    args = parser.parse_args(argv)
    return compose(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
