#!/usr/bin/env python3
"""Reading a *declared* schema -- a customer catalog -- rather than deriving one.

See :mod:`utils.kg_builder.catalog.declared` for why the declared/observed
distinction is carried rather than flattened, and
:mod:`utils.kg_builder.catalog.inferred` for the edges this project adds and how
they are kept separable from the delivery.
"""

from .declared import (
    DECLARED,
    INFERRED,
    DeclaredAttribute,
    DeclaredCatalog,
    DeclaredTriple,
    Truncation,
    add_triples,
)
from .inferred import INFERRED_EDGES, apply_inferred, inferred_triples, justification
from .reader import CATALOG_DIR_ENV, catalog_dir, detect_truncation, read_catalog

__all__ = [
    "CATALOG_DIR_ENV",
    "DECLARED",
    "INFERRED",
    "INFERRED_EDGES",
    "DeclaredAttribute",
    "DeclaredCatalog",
    "DeclaredTriple",
    "Truncation",
    "add_triples",
    "apply_inferred",
    "catalog_dir",
    "detect_truncation",
    "inferred_triples",
    "justification",
    "read_catalog",
]
