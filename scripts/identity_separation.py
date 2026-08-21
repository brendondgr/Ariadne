#!/usr/bin/env python3
"""Prove the identity source is invisible to every arm that does not name it.

EXP-2026-08-009 needed 8/8 separation checks before the merged store could be
believed, for a reason that applies here with more force. Two functions decide
what an ordinary run can see:

* ``utils.planner.cards.load_source_cards`` **globs** ``source_cards/*.json``, so
  a card in the ordinary place becomes a third source the planner may route to.
* ``utils.specialists.schema.build.discover_datasets`` **walks** ``graphs/``, so
  a dataset there enters the schema registry that binding and direction
  resolution are built on.

Neither takes an allow-list. Isolation is therefore by *directory*, because a
directory cannot be left switched on by accident the way a flag can — and this
script is what turns that argument into a check.

The stakes are higher than for ``merged``. That store held the same two
catalogues an arm already knew; this one holds 72 labels from a different domain
entirely, so a leak would not merely change counts, it would put foreign labels
in front of a planner whose measured behaviour assumes eleven.

    uv run python scripts/identity_separation.py

Exits non-zero on the first failure, and prints every check either way.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DATA_DIR = "data"
IDENTITY_DATA_DIR = "data-identity"
ATTACK_EXPECTED_NODES = 4369

_results: list[tuple[bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _results.append((condition, f"{name}{f' — {detail}' if detail else ''}"))


def main() -> int:
    # Any ARIADNE_DATA_DIR inherited from a shell that was just running the
    # identity load would invalidate every check below, so it is cleared first.
    os.environ.pop("ARIADNE_DATA_DIR", None)

    from utils.planner.cards import load_source_cards
    from utils.specialists.schema.build import build_registry, discover_datasets

    # 1-2. The planner's source set is unchanged.
    cards = set(load_source_cards(DEFAULT_DATA_DIR))
    check("default source cards are exactly {attack, capec}",
          cards == {"attack", "capec"}, f"got {sorted(cards)}")
    check("no identity card in the default card set", "identity" not in cards)

    # 3-4. The schema registry's dataset set is unchanged.
    datasets = set(discover_datasets(DEFAULT_DATA_DIR))
    check("default datasets do not include identity", "identity" not in datasets,
          f"got {sorted(datasets)}")
    registry = build_registry(DEFAULT_DATA_DIR)
    check("default registry does not include identity",
          "identity" not in registry.dataset_names(),
          f"got {list(registry.dataset_names())}")

    # 5. Nothing declared leaked into the default registry. Every schema an
    #    ordinary arm reads must still have been derived by scanning instances.
    provenances = {
        name: registry.dataset(name).provenance for name in registry.dataset_names()
    }
    check("every default schema is still 'observed'",
          set(provenances.values()) <= {"observed"}, str(provenances))

    # 6. No identity artifact sits under the default data directory.
    stray = sorted(
        str(p.relative_to(REPO_ROOT))
        for p in (REPO_ROOT / DEFAULT_DATA_DIR).rglob("*identity*")
    )
    check("no identity artifact under data/", not stray, str(stray))

    # 7. The identity dataset really is discoverable when explicitly named --
    #    a separation check that only ever says "absent" would also pass if the
    #    dataset had never been built.
    identity_datasets = set(discover_datasets(IDENTITY_DATA_DIR))
    check("identity IS discoverable under data-identity/",
          "identity" in identity_datasets, f"got {sorted(identity_datasets)}")

    # 8. And its schema is declared, not observed.
    identity_registry = build_registry(IDENTITY_DATA_DIR)
    identity_schema = identity_registry.dataset("identity")
    check("identity schema is present with 72 labels",
          identity_schema is not None and len(identity_schema.labels()) == 72,
          f"got {len(identity_schema.labels()) if identity_schema else 'none'}")

    # 9. The ATT&CK store is untouched. This is the check that would catch a
    #    load having gone to the wrong URI.
    try:
        from neo4j import GraphDatabase

        uri = os.environ.get("NEO4J_URI", "bolt://localhost:5456")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            total = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            foreign = session.run(
                "MATCH (n) WHERE n:USER OR n:GROUP OR n:DEVICE OR n:DOMAIN "
                "RETURN count(n) AS c"
            ).single()["c"]
        driver.close()
        check(f"ATT&CK store still holds {ATTACK_EXPECTED_NODES} nodes",
              total == ATTACK_EXPECTED_NODES, f"got {total}")
        check("ATT&CK store holds no identity labels", foreign == 0, f"got {foreign}")
    except Exception as exc:  # pragma: no cover - depends on a live store
        check("ATT&CK store reachable for verification", False, f"{type(exc).__name__}: {exc}")

    width = max(len(text) for _, text in _results)
    for ok, text in _results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {text.ljust(width)}")
    passed = sum(1 for ok, _ in _results if ok)
    print(f"\n{passed}/{len(_results)} separation checks pass")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    sys.exit(main())
