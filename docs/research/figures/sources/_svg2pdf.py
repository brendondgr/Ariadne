"""Deterministic SVG → PDF conversion, shared by the promoted-figure generators.

`rsvg-convert` embeds a creation timestamp in the PDF's (compressed) Info
dictionary, so two conversions of the *same* SVG minutes apart differ by ~560
bytes. That would make `make figures --check` fail spuriously in CI on every run
after the first — the check would be measuring the clock, not the figures.

librsvg's cairo backend honours the reproducible-builds `SOURCE_DATE_EPOCH`
convention, so pinning it makes conversion byte-deterministic. The epoch below is
fixed deliberately: it is the date the research record was established, and it is
a constant rather than "now" precisely so the output does not move.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

#: 2026-08-06T00:00:00Z — the date the research record was established.
#: Any fixed value works; what matters is that it never changes.
SOURCE_DATE_EPOCH = "1785974400"


def svg_to_pdf(svg_path: Path, pdf_path: Path) -> bool:
    """Convert deterministically. Returns True on success."""
    env = {**os.environ, "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH, "TZ": "UTC"}
    try:
        subprocess.run(
            ["rsvg-convert", "-f", "pdf", "-o", str(pdf_path), str(svg_path)],
            check=True, capture_output=True, env=env,
        )
    except FileNotFoundError:
        print(
            "error: rsvg-convert not found — install librsvg2-tools (Fedora) "
            "or librsvg2-bin (Debian/Ubuntu)",
            file=sys.stderr,
        )
        return False
    except subprocess.CalledProcessError as exc:
        print(f"error: rsvg-convert failed — {exc.stderr.decode(errors='replace')}", file=sys.stderr)
        return False
    return True
