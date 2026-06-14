#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from ..io import write_text
from ..schema.attack import constraints_cypher_lines as attack_constraints_cypher_lines
from ..schema.attack import schema_cypher_lines as attack_schema_cypher_lines
from ..schema.capec import constraints_cypher_lines as capec_constraints_cypher_lines
from ..schema.capec import schema_cypher_lines as capec_schema_cypher_lines


def export_cypher_artifacts(output_dir: Path, *, dataset: str = "attack") -> dict[str, Path]:
    """Write schema.cypher and constraints.cypher for a dataset."""
    if dataset == "capec":
        schema_lines = capec_schema_cypher_lines()
        constraint_lines = capec_constraints_cypher_lines()
    else:
        schema_lines = attack_schema_cypher_lines()
        constraint_lines = attack_constraints_cypher_lines()

    schema_path = output_dir / "schema.cypher"
    constraints_path = output_dir / "constraints.cypher"
    write_text(schema_path, "\n".join(schema_lines) + "\n")
    write_text(constraints_path, "\n".join(constraint_lines) + "\n")
    return {"schema": schema_path, "constraints": constraints_path}
