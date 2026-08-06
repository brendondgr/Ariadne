#!/usr/bin/env python3
"""Promoted figure: fig01-architecture.

    Source:  docs/assets/architecture.svg  (hand-authored SVG — the source IS the SVG)
    Output:  docs/research/figures/fig01-architecture.{svg,pdf}

**This figure is the one documented exception to "every figure has a generating
script that computes it".** It is a system diagram, not a plot of data, and §4 of
the contract explicitly permits architecture diagrams authored as SVG and
committed with their source. There is no data to read and nothing to compute.

What this script does provide is the other half of the rule: the promotion is
*reproducible*. `make figures` re-derives both outputs from the authored source,
so the promoted copy can never silently drift from `docs/assets/architecture.svg`,
and the `--check` mode fails if someone hand-edits the promoted file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/assets/architecture.svg"
OUT_DIR = ROOT / "docs/research/figures"
STEM = "fig01-architecture"

HEADER = (
    "<!-- PROMOTED FIGURE — DO NOT EDIT THIS COPY.\n"
    "     Source:      docs/assets/architecture.svg (hand-authored)\n"
    "     Promoted by: docs/research/figures/sources/make_architecture.py\n"
    "     Regenerate:  make figures\n"
    "     Exception:   a system diagram, not a plot; see this script's docstring. -->\n"
)


def main() -> int:
    if not SOURCE.is_file():
        print(f"error: missing authored source {SOURCE}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = OUT_DIR / f"{STEM}.svg"
    svg_path.write_text(HEADER + SOURCE.read_text())
    print(f"wrote {svg_path.relative_to(ROOT)}")

    pdf_path = OUT_DIR / f"{STEM}.pdf"
    try:
        subprocess.run(
            ["rsvg-convert", "-f", "pdf", "-o", str(pdf_path), str(svg_path)],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"error: rsvg-convert failed — {exc}", file=sys.stderr)
        return 1
    print(f"wrote {pdf_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
