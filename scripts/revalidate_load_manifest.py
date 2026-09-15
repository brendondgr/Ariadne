#!/usr/bin/env python3
"""Re-stamp a runtime load manifest when the canonical rebuild changed no data.

    uv run python scripts/revalidate_load_manifest.py --check
    uv run python scripts/revalidate_load_manifest.py --apply

`utils/graph_loader/verify.py` compares the `canonical_manifest_hash` recorded at
load time against a fresh `file_sha256` of `canonical/manifest.json`. That file
embeds a `build_timestamp`, so rebuilding the canonical artifacts from unchanged
sources produces a different file hash and the preflight refuses to start with
"Stale runtime manifest ... canonical hash mismatch" -- even though not one node
or edge has moved. Recorded as `EXP-2026-09-018` `I-21` on 2026-09-14 and hit
again on 2026-09-15.

**This script cannot paper over a real change.** It re-stamps only when both of
these hold, and exits non-zero otherwise:

1. the recorded hash matches a manifest under `_backups/`, and diffing that
   manifest against the current one shows `build_timestamp` as the *only*
   differing key -- so every data digest is byte-identical;
2. the live store's node, edge and per-label counts equal the manifest's
   `expected_counts`.

Condition 1 is the strong one: it is a content check on the canonical artifacts
themselves, not a count. If the backup for the recorded hash is missing, the
script refuses rather than guessing -- reload the store instead.

The re-stamp is recorded in a `revalidations` list on the load manifest, naming
the old hash, the new one, and the evidence, so a later reader can see that the
recorded hash was changed by hand-equivalent means and why.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DATASETS = (("attack", "neo4j"), ("capec", "gremlin"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_backup(dataset: str, recorded: str) -> Path | None:
    want = recorded.split(":")[-1]
    for p in glob.glob(str(REPO / f"data/graphs/{dataset}/_backups/*/manifest.json")):
        if _sha256(Path(p)) == want:
            return Path(p)
    return None


def _live_counts(dataset: str, backend: str) -> dict[str, object]:
    """Node/edge/per-label counts read from the running store."""
    from utils.config import load_env

    load_env()
    import os

    if backend == "neo4j":
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "")),
        )
        try:
            with driver.session() as s:
                nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                edges = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                by_label = {
                    r["l"]: r["c"]
                    for r in s.run(
                        "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c"
                    ).data()
                }
        finally:
            driver.close()
    else:
        from gremlin_python.driver import client, serializer

        c = client.Client(
            os.environ.get("GREMLIN_URI", "ws://localhost:8182/gremlin"),
            "g",
            message_serializer=serializer.GraphSONSerializersV3d0(),
        )
        try:
            nodes = c.submit("g.V().count()").all().result()[0]
            edges = c.submit("g.E().count()").all().result()[0]
            by_label = dict(c.submit("g.V().groupCount().by(label)").all().result()[0])
        finally:
            c.close()
    return {"nodes": nodes, "edges": edges, "nodes_by_label": by_label}


def check(dataset: str, backend: str) -> tuple[bool, dict[str, object]]:
    """Return (safe_to_restamp, evidence)."""
    lm_path = REPO / f"data/graphs/{dataset}/runtime/{backend}/load-manifest.json"
    cur_path = REPO / f"data/graphs/{dataset}/canonical/manifest.json"
    lm = json.loads(lm_path.read_text())
    recorded = str(lm.get("canonical_manifest_hash", ""))
    fresh = _sha256(cur_path)
    evidence: dict[str, object] = {
        "dataset": dataset,
        "backend": backend,
        "recorded_hash": recorded,
        "current_hash": fresh,
    }
    if recorded.split(":")[-1] == fresh:
        evidence["verdict"] = "already current — nothing to do"
        return False, evidence

    backup = _find_backup(dataset, recorded)
    if backup is None:
        evidence["verdict"] = (
            "REFUSED: no backup matches the recorded hash, so the loaded manifest "
            "cannot be diffed against the current one. Reload the store."
        )
        return False, evidence
    evidence["backup"] = str(backup.relative_to(REPO))

    old = json.loads(backup.read_text())
    cur = json.loads(cur_path.read_text())
    keys = set(old) | set(cur)
    differing = sorted(k for k in keys if old.get(k) != cur.get(k))
    evidence["differing_keys"] = differing
    if differing != ["build_timestamp"]:
        evidence["verdict"] = (
            "REFUSED: the canonical manifest differs in more than build_timestamp "
            f"({differing}) — the data may genuinely have changed. Reload the store."
        )
        return False, evidence
    evidence["build_timestamp"] = {
        "loaded": old.get("build_timestamp"),
        "current": cur.get("build_timestamp"),
    }

    expected = lm.get("expected_counts") or {}
    live = _live_counts(dataset, backend)
    label_mismatch = {
        k: [expected.get("nodes_by_label", {}).get(k), live["nodes_by_label"].get(k)]
        for k in set(expected.get("nodes_by_label", {}))
        if expected["nodes_by_label"][k] != live["nodes_by_label"].get(k)
    }
    counts_ok = (
        expected.get("nodes") == live["nodes"]
        and expected.get("edges") == live["edges"]
        and not label_mismatch
    )
    evidence["live_counts"] = {"nodes": live["nodes"], "edges": live["edges"]}
    evidence["expected_counts"] = {"nodes": expected.get("nodes"), "edges": expected.get("edges")}
    evidence["label_mismatch"] = label_mismatch
    if not counts_ok:
        evidence["verdict"] = "REFUSED: live counts do not match the manifest. Reload the store."
        return False, evidence

    evidence["verdict"] = "SAFE: only build_timestamp changed and live counts match"
    return True, evidence


def apply(dataset: str, backend: str, evidence: dict[str, object]) -> None:
    lm_path = REPO / f"data/graphs/{dataset}/runtime/{backend}/load-manifest.json"
    cur_path = REPO / f"data/graphs/{dataset}/canonical/manifest.json"
    lm = json.loads(lm_path.read_text())
    old_hash = lm["canonical_manifest_hash"]
    new_hash = _sha256(cur_path)
    lm["canonical_manifest_hash"] = new_hash
    lm.setdefault("revalidations", []).append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "old_hash": old_hash,
            "new_hash": new_hash,
            "reason": "I-21: canonical rebuild changed build_timestamp only; no data moved",
            "evidence": evidence,
            "by": "scripts/revalidate_load_manifest.py",
        }
    )
    lm_path.write_text(json.dumps(lm, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="re-stamp (default is check only)")
    args = ap.parse_args(argv)

    exit_code = 0
    for dataset, backend in DATASETS:
        safe, evidence = check(dataset, backend)
        print(f"== {dataset}/{backend}: {evidence['verdict']}")
        for key in ("recorded_hash", "current_hash", "differing_keys", "expected_counts",
                    "live_counts", "label_mismatch"):
            if key in evidence:
                print(f"   {key}: {evidence[key]}")
        if safe and args.apply:
            apply(dataset, backend, evidence)
            print("   re-stamped, revalidation recorded")
        elif not safe and "already current" not in str(evidence["verdict"]):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
