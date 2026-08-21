#!/usr/bin/env python3
"""Parse ReliaQuest's two catalog CSVs into a :class:`DeclaredCatalog`.

The delivery is two files produced by the queries in ``customer_xref.sql.rtf``:

``node_attributes.csv``          ``node_type, attribute_name, value_type``
``relationship_attributes.csv``  ``source_node_type, edge_label, target_node_type,
                                  attribute_name, value_type``

Both are the result of an **inner** join to ``customer_attribute_catalog``, which
is why :func:`detect_truncation` exists and runs on every read. See
:class:`utils.kg_builder.catalog.declared.Truncation`.

Two parsing decisions worth stating, because both look like bugs and neither is:

* **Nothing is normalised.** Labels are used exactly as delivered, which means
  ``ENTRA_LICENCE`` and ``ENTRA_LICENSE`` both survive as distinct node types.
  That collision is real, it is in the customer's production catalog, and
  merging them would mean evaluating against a schema tidier than the one that
  exists. It is also a free disambiguation test case for the planner.
* **The files are never committed.** They are funder-supplied and not
  redistributable, so they live outside the repository and are referenced by
  checksum. Tests use small hand-written fixtures; the one test that pins the
  real counts skips when the delivery is not present.
"""

from __future__ import annotations

import csv
import hashlib
import os
from collections import defaultdict
from pathlib import Path

from .declared import (
    DeclaredAttribute,
    DeclaredCatalog,
    DeclaredTriple,
    Truncation,
)

# Where the delivery sits when it has not been pointed at explicitly. This is an
# operator path, not a repository path -- the CSVs are not redistributable and
# must not be copied into the tree.
CATALOG_DIR_ENV = "ARIADNE_IDENTITY_CATALOG_DIR"
DEFAULT_CATALOG_DIR = (
    "/home/bdgr/Documents/2026_ReliaQuest_innovation_challenge_data/Graph schema"
)

NODE_CSV = "node_attributes.csv"
EDGE_CSV = "relationship_attributes.csv"

# The query that would have produced an untruncated edge catalog. Recorded so the
# artifact carries the fix rather than only the complaint.
CORRECTED_EDGE_QUERY = (
    "select distinct source_node_type, edge_label, target_node_type "
    "from customer_edge_catalog;"
)


def catalog_dir(explicit: str | Path | None = None) -> Path:
    """Resolve where the delivered CSVs live, preferring an explicit path."""
    if explicit is not None:
        return Path(explicit)
    return Path(os.environ.get(CATALOG_DIR_ENV, DEFAULT_CATALOG_DIR))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path, expected: list[str]) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = [h.strip() for h in (reader.fieldnames or [])]
        if header != expected:
            raise ValueError(f"{path.name}: expected header {expected}, found {header}")
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def detect_truncation(catalog: DeclaredCatalog) -> Truncation:
    """Decide whether the delivered edge set is structurally incomplete.

    The test is not "does it look short" -- it is a specific structural
    impossibility. An identity graph whose ``MEMBER_OF`` never reaches its own
    ``GROUP`` type is a graph in which no user belongs to any group, which no
    real Active Directory deployment resembles. Combined with the inner join
    visible in the delivered SQL, that is sufficient to call it.

    Returns a :class:`Truncation` either way; ``suspected`` carries the verdict,
    so a future corrected delivery produces an artifact of the same shape saying
    the opposite.
    """
    evidence: list[str] = []
    triples = catalog.triples

    member_of_targets = {t.target for t in triples if t.edge == "MEMBER_OF"}
    if member_of_targets and "GROUP" not in member_of_targets:
        evidence.append(
            "MEMBER_OF reaches "
            + ", ".join(sorted(member_of_targets))
            + " but never GROUP: no user belongs to any Active Directory group."
        )

    if triples:
        by_source: dict[str, int] = defaultdict(int)
        for triple in triples:
            by_source[triple.source] += 1
        top_label, top_count = max(by_source.items(), key=lambda kv: (kv[1], kv[0]))
        share = top_count / len(triples)
        if share >= 0.5:
            evidence.append(
                f"{top_count} of {len(triples)} triples have {top_label} as source "
                f"({share:.0%}), which is not a plausible distribution for a whole schema."
            )

    return Truncation(
        suspected=bool(evidence),
        reason=(
            "The delivered export joins customer_edge_catalog to "
            "customer_attribute_catalog with an INNER join, so any edge type "
            "carrying no attributes never reached the file. The operator "
            "confirmed on 2026-08-21 that no corrected export will be supplied, "
            "so this is a permanent property of the dataset."
        ),
        corrected_query=CORRECTED_EDGE_QUERY,
        evidence=tuple(evidence),
    )


def read_catalog(
    directory: str | Path | None = None,
    *,
    name: str = "identity",
) -> DeclaredCatalog:
    """Read both CSVs from ``directory`` into one catalog.

    Does **not** add inferred triples -- that is a separate, explicit step so the
    delivered schema and this project's additions can never be conflated. See
    :mod:`utils.kg_builder.catalog.inferred`.
    """
    base = catalog_dir(directory)
    node_path, edge_path = base / NODE_CSV, base / EDGE_CSV
    for path in (node_path, edge_path):
        if not path.is_file():
            raise FileNotFoundError(
                f"catalog file not found: {path}. Point at the delivery with "
                f"${CATALOG_DIR_ENV} or pass an explicit directory."
            )

    catalog = DeclaredCatalog(
        name=name,
        source_files={
            NODE_CSV: f"sha256:{_sha256(node_path)}",
            EDGE_CSV: f"sha256:{_sha256(edge_path)}",
        },
    )

    node_attrs: dict[str, dict[str, DeclaredAttribute]] = defaultdict(dict)
    for row in _rows(node_path, ["node_type", "attribute_name", "value_type"]):
        label, attr, vtype = row["node_type"], row["attribute_name"], row["value_type"]
        if not label or not attr:
            continue
        node_attrs[label][attr] = DeclaredAttribute(attr, vtype)
    catalog.node_attributes = dict(node_attrs)

    edge_attrs: dict[tuple[str, str, str], dict[str, DeclaredAttribute]] = defaultdict(dict)
    seen: set[tuple[str, str, str]] = set()
    for row in _rows(
        edge_path,
        ["source_node_type", "edge_label", "target_node_type", "attribute_name", "value_type"],
    ):
        key = (row["source_node_type"], row["edge_label"], row["target_node_type"])
        if not all(key):
            continue
        if key not in seen:
            seen.add(key)
            catalog.triples.append(DeclaredTriple(*key))
        attr, vtype = row["attribute_name"], row["value_type"]
        if attr:
            edge_attrs[key][attr] = DeclaredAttribute(attr, vtype)
    catalog.edge_attributes = dict(edge_attrs)

    # A node type may appear as a triple endpoint without appearing in the node
    # CSV. Register it with no attributes rather than dropping the triple --
    # losing an edge to tidy a label set would be the wrong trade.
    for triple in catalog.triples:
        catalog.node_attributes.setdefault(triple.source, {})
        catalog.node_attributes.setdefault(triple.target, {})

    catalog.truncation = detect_truncation(catalog)
    return catalog
