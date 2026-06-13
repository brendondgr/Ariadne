#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from ..io import write_text
from ..schema.attack import constraints_cypher_lines, schema_cypher_lines


def export_cypher_artifacts(output_dir: Path) -> dict[str, Path]:
    """Write schema.cypher and constraints.cypher."""
    schema_path = output_dir / "schema.cypher"
    constraints_path = output_dir / "constraints.cypher"
    write_text(schema_path, "\n".join(schema_cypher_lines()) + "\n")
    write_text(constraints_path, "\n".join(constraints_cypher_lines()) + "\n")
    return {"schema": schema_path, "constraints": constraints_path}
