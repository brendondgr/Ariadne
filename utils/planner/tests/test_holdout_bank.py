"""The 2026-09 entity-held-out variant bank is sealed, disjoint, and reproducible.

Three properties the plan `docs/plans/2026-09-15-open-question-correctness.md`
depends on, each of which would silently stop being true if someone re-drew,
re-authored or re-captured the bank:

* every file's SHA-256 matches `SEAL.md` — the bank is the one that was sealed;
* no anchor entity of the held-out gold appears in any exposed-bank anchor;
* the two reference captures are byte-identical, so a variant is scored against
  a reproducible behaviour and not against a run.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
HOLDOUT = REPO / "docs/evaluation/variants-holdout-2026-09"
EXPOSED = REPO / "docs/evaluation/variants-2026-08-29"
_ID_RE = re.compile(
    r"\b(?:T\d{4}(?:\.\d{3})?|G\d{4}|S\d{4}|M\d{4}|TA\d{4}|C\d{4}|CAPEC-\d+)\b"
)

pytestmark = pytest.mark.skipif(
    not (HOLDOUT / "SEAL.md").exists(), reason="holdout bank not present"
)


def _sealed_hashes() -> dict[str, str]:
    rows = re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", (HOLDOUT / "SEAL.md").read_text())
    assert rows, "SEAL.md carries no hash table"
    return dict(rows)


def test_every_sealed_file_matches_its_hash() -> None:
    for name, digest in _sealed_hashes().items():
        assert hashlib.sha256((HOLDOUT / name).read_bytes()).hexdigest() == digest, name


def test_reference_capture_is_reproducible() -> None:
    assert (HOLDOUT / "reference.json").read_bytes() == (HOLDOUT / "reference_check.json").read_bytes()


def test_no_held_out_anchor_appears_in_the_exposed_bank() -> None:
    exposed: set[str] = set()
    for row in json.loads((EXPOSED / "reference.json").read_text()):
        exposed |= set(row.get("seed_ids") or [])
        exposed |= set(_ID_RE.findall(row["question"]))
    held = {sid for g in json.loads((HOLDOUT / "gold.json").read_text()) for sid in g["seed_ids"]}
    assert held and not (held & exposed), sorted(held & exposed)


def test_every_gold_question_has_all_four_tiers_and_no_empty_reference() -> None:
    gold = {g["case_id"] for g in json.loads((HOLDOUT / "gold.json").read_text())}
    tiers: dict[str, set[str]] = {}
    for v in json.loads((HOLDOUT / "variants.json").read_text()):
        tiers.setdefault(v["case_id"], set()).add(v["tier"])
    assert all(tiers.get(c) == {"T3", "T4", "T5", "T6"} for c in gold)
    for row in json.loads((HOLDOUT / "reference.json").read_text()):
        assert row["entity_ids"], row["case_id"]
        assert len(row["entity_ids"]) < 50, f"{row['case_id']} reference is a dump"


def test_the_authored_variants_still_pass_the_gate() -> None:
    from scripts.author_variants import gate_one

    src = {r["case_id"]: r for r in json.loads((HOLDOUT / "authoring/inputs.json").read_text())}
    for v in json.loads((HOLDOUT / "variants.json").read_text()):
        assert gate_one(v, src[v["case_id"]]) is None, v
