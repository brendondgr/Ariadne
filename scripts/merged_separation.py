#!/usr/bin/env python3
"""Prove the merged store holds both catalogues and can still tell them apart.

The C-015 counterfactual is only worth running if the merged graph is (a) whole
and (b) not quietly mixing the two sources. Both failures look like a working
database: a short load still answers questions, and a `Mitigation` scan that
silently returns both catalogues' mitigations still returns rows.

Two checks are load-bearing.

**Nothing is missing.** Live counts must equal the merged manifest's, which is
the sum of the two source manifests. A count *below* expectation means records
did not land.

**The sources are separable.** `Mitigation` is the one label both catalogues
use. Every node carries a marker label (``AttackObject`` / ``CapecObject``), so
the split must be exact and must sum to the total — no node in both, none in
neither. A relationship-scoped traversal from a technique must return only
ATT&CK mitigations, which is the property that makes the collision harmless in
practice: the two catalogues reach their mitigations by different edges.

It also re-counts the **main** ATT&CK store and fails if it moved. A CAPEC load
that reached the main graph would invalidate every ATT&CK figure on record at
once, and it would do so silently — the store would simply have more in it.

    uv run python scripts/merged_separation.py [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

MERGED_URI = f"bolt://localhost:{os.environ.get('NEO4J_MERGED_BOLT_PORT', '5458')}"
MAIN_URI = os.environ.get("NEO4J_URI", "bolt://localhost:5456")
MANIFEST = REPO / "data-merged" / "graphs" / "merged" / "canonical" / "manifest.json"

#: The five relationship names MITRE spells itself, which the loader refused
#: until 2026-08-20. Their presence is the proof that D-016 actually landed.
MITRE_SPELLED = ("ChildOf", "CanPrecede", "CanFollow", "PeerOf", "CanAlsoBe")


def _session(uri: str):
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        uri,
        auth=(os.environ.get("NEO4J_USER", "neo4j"),
              os.environ.get("NEO4J_PASSWORD", "password")),
    )


def _one(session, query: str, **params):
    return session.run(query, **params).single()[0]


def run() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    expected = manifest["counts"]
    checks: list[dict] = []
    facts: dict = {"merged_uri": MERGED_URI, "main_uri": MAIN_URI}

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    if MERGED_URI == MAIN_URI:
        raise SystemExit(f"refusing: merged uri equals the main uri ({MAIN_URI})")

    driver = _session(MERGED_URI)
    try:
        with driver.session() as s:
            nodes = _one(s, "MATCH (n) RETURN count(n)")
            edges = _one(s, "MATCH ()-[r]->() RETURN count(r)")
            facts["nodes"] = nodes
            facts["relationships"] = edges
            check("every node landed", nodes == expected["nodes"],
                  f"{nodes} live against {expected['nodes']} expected")
            check("every relationship landed", edges == expected["relationships"],
                  f"{edges} live against {expected['relationships']} expected")

            attack_nodes = _one(s, "MATCH (n:AttackObject) RETURN count(n)")
            capec_nodes = _one(s, "MATCH (n:CapecObject) RETURN count(n)")
            unmarked = _one(
                s, "MATCH (n) WHERE NOT n:AttackObject AND NOT n:CapecObject "
                   "RETURN count(n)")
            both = _one(s, "MATCH (n:AttackObject:CapecObject) RETURN count(n)")
            facts["by_source"] = {"attack": attack_nodes, "capec": capec_nodes}
            check("every node carries exactly one source marker",
                  unmarked == 0 and both == 0 and attack_nodes + capec_nodes == nodes,
                  f"attack {attack_nodes} + capec {capec_nodes} = {nodes}; "
                  f"{unmarked} unmarked, {both} in both")

            # The one label both catalogues use.
            mit_total = _one(s, "MATCH (n:Mitigation) RETURN count(n)")
            mit_attack = _one(s, "MATCH (n:Mitigation:AttackObject) RETURN count(n)")
            mit_capec = _one(s, "MATCH (n:Mitigation:CapecObject) RETURN count(n)")
            facts["mitigation"] = {
                "total": mit_total, "attack": mit_attack, "capec": mit_capec,
            }
            check("the shared Mitigation label splits exactly",
                  mit_attack + mit_capec == mit_total and mit_attack and mit_capec,
                  f"{mit_attack} ATT&CK + {mit_capec} CAPEC = {mit_total}")

            # The property that makes the collision harmless: the two catalogues
            # reach their mitigations by different edges, so a traversal is
            # scoped even when the label is not.
            leaked = _one(
                s,
                "MATCH (m:Mitigation)-[:MITIGATES]->(t) WHERE m:CapecObject "
                "RETURN count(m)")
            reached = _one(
                s,
                "MATCH (m:Mitigation)-[:MITIGATES]->(t {attack_id: $tid}) "
                "RETURN count(DISTINCT m)", tid="T1047")
            facts["mitigates_T1047"] = reached
            check("a MITIGATES traversal reaches only ATT&CK mitigations",
                  leaked == 0 and reached > 0,
                  f"{reached} mitigations for T1047, {leaked} CAPEC nodes on MITIGATES")

            capec_reached = _one(
                s,
                "MATCH (a:AttackPattern {attack_id: $cid})-[:HAS_MITIGATION]->(m) "
                "RETURN count(m)", cid="CAPEC-66")
            facts["has_mitigation_CAPEC_66"] = capec_reached
            check("a CAPEC anchor resolves by its promoted public id",
                  capec_reached > 0,
                  f"CAPEC-66 has {capec_reached} mitigations via HAS_MITIGATION")

            spelled = {
                rel: _one(s, f"MATCH ()-[r:{rel}]->() RETURN count(r)")
                for rel in MITRE_SPELLED
            }
            facts["mitre_spelled_relationships"] = spelled
            check("the relationship names MITRE spells itself are present",
                  all(v > 0 for v in spelled.values()),
                  ", ".join(f"{k}={v}" for k, v in spelled.items()))
    finally:
        driver.close()

    # The guard. A CAPEC load reaching the main store would be silent.
    main = _session(MAIN_URI)
    try:
        with main.session() as s:
            main_nodes = _one(s, "MATCH (n) RETURN count(n)")
            main_capec = _one(s, "MATCH (n:CapecObject) RETURN count(n)")
    finally:
        main.close()
    facts["main_store"] = {"nodes": main_nodes, "capec_nodes": main_capec}
    check("the main ATT&CK store is untouched",
          main_capec == 0 and main_nodes == 4369,
          f"{main_nodes} nodes, {main_capec} of them CAPEC")

    return {"facts": facts, "checks": checks,
            "passed": all(c["ok"] for c in checks)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="also write the result to this path")
    args = parser.parse_args(argv)

    result = run()
    for c in result["checks"]:
        print(f"{'ok  ' if c['ok'] else 'FAIL'}  {c['check']}: {c['detail']}")
    print(f"\n{'all checks passed' if result['passed'] else 'FAILURES ABOVE'}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
