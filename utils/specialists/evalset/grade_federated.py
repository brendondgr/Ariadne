#!/usr/bin/env python3
"""Grade a federated credential-theft run against the snapshot-derived gold.

Deterministic grader for the Wk 10–11 A-vs-B decision gate and the live
acceptance test. Takes a ``FederatedEvidence`` dict (what the pipeline emits)
and the federated gold, and answers the three Phase-2 questions:

  (a) fetch fidelity — did the ATT&CK sub-question return mitigations for the
      T-IDs CAPEC actually surfaced, or a broader/narrower set?
  (b) correlation fidelity — does the cross-source correlation set equal the
      expected overlap?
  (c) silent drops — which expected technique→mitigation pairs are absent from
      the evidence?
"""

from __future__ import annotations

from typing import Any


def _records_by_source(evidence: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for result in evidence.get("results", []):
        source = (result.get("task") or {}).get("source", "?")
        out.setdefault(source, []).extend(result.get("records", []))
    return out


def grade_credential_theft(
    evidence: dict[str, Any], gold: dict[str, Any]
) -> dict[str, Any]:
    """Return a verdict dict; ``faithful`` is the A-vs-B decision bit."""
    by_source = _records_by_source(evidence)
    capec_records = by_source.get("capec", [])
    attack_records = by_source.get("attack", [])

    expected_capec = set(gold["capec_to_techniques"])
    expected_tids = set(gold["technique_ids"])
    expected_corr = set(gold["expected_correlation"])
    expected_pairs = {
        (tid, mid)
        for tid, mids in gold["technique_mitigations"].items()
        for mid in mids
    }

    # CAPEC side: which selected patterns (and their T-IDs) were retrieved.
    got_capec = {r.get("primary_id") for r in capec_records}
    capec_tids = {v for r in capec_records for v in r.get("join_values", [])}
    missing_capec = sorted(expected_capec - got_capec)

    # ATT&CK side: technique→mitigation pairs present in the evidence. A
    # mitigation may appear as a related entry on a technique record or as its
    # own record naming the technique in join_values.
    got_pairs: set[tuple[str, str]] = set()
    for rec in attack_records:
        rid = rec.get("primary_id", "")
        for rel in rec.get("related", []):
            other = rel.get("id", "")
            if rid.startswith("T") and other.startswith("M"):
                got_pairs.add((rid, other))
            elif rid.startswith("M") and other.startswith("T"):
                got_pairs.add((other, rid))
        if rid.startswith("M"):
            for v in rec.get("join_values", []):
                if v.startswith("T"):
                    got_pairs.add((v, rid))
    attack_tids = {v for r in attack_records for v in r.get("join_values", [])}

    # (a) fetch fidelity.
    over_fetch_capec = sorted(capec_tids - expected_tids)
    over_fetch_attack = sorted(attack_tids - expected_tids)
    under_fetch_attack = sorted(expected_corr - attack_tids)

    # (b) correlation fidelity (the synthesis correlation claims derive from
    # the evidence bundle's cross-source join values).
    corr = set(evidence.get("cross_source_join_values", []))
    corr_matches = corr == expected_corr

    # (c) silent drops.
    dropped_pairs = sorted(expected_pairs - got_pairs)

    faithful = (
        not missing_capec
        and corr_matches
        and not dropped_pairs
        and not under_fetch_attack
    )
    return {
        "faithful": faithful,
        "missing_capec_patterns": missing_capec,
        "capec_tids_expected": len(expected_tids),
        "capec_tids_retrieved": len(capec_tids & expected_tids),
        "over_fetch_capec_tids": len(over_fetch_capec),
        "over_fetch_attack_tids": len(over_fetch_attack),
        "under_fetch_attack_tids": under_fetch_attack,
        "correlation_matches_gold": corr_matches,
        "correlation_size": len(corr),
        "correlation_expected_size": len(expected_corr),
        "correlation_extra": sorted(corr - expected_corr)[:10],
        "correlation_missing": sorted(expected_corr - corr),
        "expected_pairs": len(expected_pairs),
        "retrieved_pairs": len(expected_pairs & got_pairs),
        "dropped_pairs": dropped_pairs[:20],
        "dropped_pair_count": len(dropped_pairs),
    }
