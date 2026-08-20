#!/usr/bin/env python3
"""Build both report figures from ``data/briefing.json``.

No number is written in this file. Every value plotted is read from the JSON
that ``data/collect.py`` extracts out of the experiments themselves, so a figure
cannot drift away from the record it claims to show.

SVG is emitted by hand and converted with ``rsvg-convert`` under a pinned
``SOURCE_DATE_EPOCH``. That is the convention the repository already uses for
its promoted figures, for the reason recorded there: a plotting library embeds
element ids and a creation timestamp, which makes byte-comparison of two
identical builds fail on the clock.

Sizing: the report's text block is 5.5 in wide. ``rsvg-convert`` treats an SVG
user unit as a CSS pixel at 96 dpi, so 528 units is exactly 5.5 in and the
figure is included at natural size with no LaTeX scaling.

Palette is Okabe-Ito. Colour never carries information on its own — every bar
is directly labelled with its value, and the rows are named on the axis.

    python3 figures/make_figures.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE.parent / "data" / "briefing.json").read_text())

#: Fixed so two builds of an unchanged figure produce identical bytes.
SOURCE_DATE_EPOCH = "1785974400"

W = 528  # 5.5 in at 96 dpi
INK, MUTED, RULE = "#1A1A1A", "#5A5F66", "#C9CED6"
BLUE, ORANGE, GREY, VERMILION = "#0072B2", "#E69F00", "#8A9099", "#D55E00"


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def convert(svg: Path, pdf: Path) -> None:
    env = {**os.environ, "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH, "TZ": "UTC"}
    try:
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(pdf), str(svg)],
                       check=True, capture_output=True, env=env)
    except FileNotFoundError:
        sys.exit("rsvg-convert not found — install librsvg2-tools")


def axis(add, x0: int, x_span: int, y_top: int, y_base: int) -> None:
    """A zero-based 0.0–1.0 axis with gridlines behind the bars."""
    for frac in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        x = x0 + frac * x_span
        add(f'<line x1="{x:.1f}" y1="{y_top}" x2="{x:.1f}" y2="{y_base}" '
            f'stroke="{RULE}" stroke-width="0.6"/>')
        add(f'<text x="{x:.1f}" y="{y_base + 14}" font-size="10" fill="{MUTED}" '
            f'text-anchor="middle">{frac:.1f}</text>')
    add(f'<line x1="{x0}" y1="{y_top}" x2="{x0}" y2="{y_base}" '
        f'stroke="{INK}" stroke-width="1.1"/>')


# ---------------------------------------------------------------------------
# Figure 1 — four configurations, two disjoint question sets
# ---------------------------------------------------------------------------

def figure_one() -> None:
    rows = [
        ("gold_loop_llm", "Authored plan, LLM writes the prose", BLUE),
        ("generic", "No templates, schema worked out at run time", BLUE),
        ("deterministic", "Templates (the default cascade)", BLUE),
        ("llm_query", "LLM writes the database query itself", VERMILION),
    ]
    b1 = DATA["generated_bank_1"]["arms"]
    b2 = DATA["generated_bank_2"]["arms"]

    x0, x_span, y_top = 250, 210, 44
    bar_h, pair_gap, group_gap = 13, 3, 15
    y = y_top + 8
    body: list[str] = []
    add = body.append

    for key, label, colour in rows:
        add(f'<text x="{x0 - 8}" y="{y + bar_h + 1}" font-size="10.5" fill="{INK}" '
            f'text-anchor="end">{esc(label)}</text>')
        for idx, (bank, shade) in enumerate(((b1, colour), (b2, colour))):
            v = bank[key]
            top = y + idx * (bar_h + pair_gap)
            width = v["correctness"] * x_span
            opacity = "1" if idx == 0 else "0.55"
            add(f'<rect x="{x0}" y="{top}" width="{width:.1f}" height="{bar_h}" '
                f'fill="{shade}" opacity="{opacity}"/>')
            lo, hi = v["ci95"]
            xl, xh = x0 + lo * x_span, x0 + hi * x_span
            mid = top + bar_h / 2
            add(f'<line x1="{xl:.1f}" y1="{mid:.1f}" x2="{xh:.1f}" y2="{mid:.1f}" '
                f'stroke="{INK}" stroke-width="0.9"/>')
            for cap in (xl, xh):
                add(f'<line x1="{cap:.1f}" y1="{mid - 3:.1f}" x2="{cap:.1f}" '
                    f'y2="{mid + 3:.1f}" stroke="{INK}" stroke-width="0.9"/>')
            add(f'<text x="{xh + 5:.1f}" y="{mid + 3.5:.1f}" font-size="10" '
                f'fill="{INK}">{v["correctness"]:.3f}</text>')
            if key == "gold_loop_llm":
                tag = "set 1" if idx == 0 else "set 2"
                add(f'<text x="{xh + 34:.1f}" y="{mid + 3.5:.1f}" font-size="9.5" '
                    f'fill="{MUTED}">{tag}</text>')
        y += 2 * bar_h + pair_gap + group_gap

    y_base = y - group_gap + 2
    height = y_base + 46

    out: list[str] = []
    o = out.append
    o(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
      f'viewBox="0 0 {W} {height}" font-family="Helvetica, Arial, sans-serif">')
    o(f'<rect width="100%" height="100%" fill="#ffffff"/>')
    o(f'<text x="8" y="18" font-size="12" font-weight="bold" fill="{INK}">'
      'Letting the model write the query costs about half the correctness</text>')
    o(f'<text x="8" y="33" font-size="10" fill="{MUTED}">'
      'Judged correctness on two question sets that share no entity. '
      'Solid bar: set 1. Pale bar: set 2.</text>')
    axis(o, x0, x_span, y_top, y_base)
    o("".join(body))
    o(f'<text x="{x0 + x_span / 2:.0f}" y="{y_base + 32}" font-size="10.5" '
      f'fill="{INK}" text-anchor="middle">Judged correctness (0–1)</text>')
    o("</svg>")

    svg = HERE / "fig01-two-banks.svg"
    svg.write_text("\n".join(out) + "\n")
    convert(svg, HERE / "fig01-two-banks.pdf")
    print(f"fig01-two-banks: {W}x{height}")


# ---------------------------------------------------------------------------
# Figure 2 — the same system, measured six ways
# ---------------------------------------------------------------------------

def figure_two() -> None:
    g1 = DATA["generated_bank_1"]
    g2 = DATA["judged_gen2"]
    b2 = DATA["generated_bank_2"]["arms"]["deterministic"]

    rows = [
        ("Co-authored catalogue", f'n={g1["catalogue_after_fix"]["n"]}',
         g1["catalogue_after_fix"]["correctness"], GREY),
        ("Blind set, as first measured", "n=30", g2["repair_before"], ORANGE),
        ("…after the retrieval repair", "n=30, same questions",
         g2["repair_after"], ORANGE),
        ("…after the answer-writing fix", "n=30, same questions",
         g1["composer_fix"]["after_mean"], ORANGE),
        ("Generated set 1", "n=30", g1["arms"]["deterministic"]["correctness"], BLUE),
        ("Generated set 2", "n=30", b2["correctness"], BLUE),
    ]

    x0, x_span, y_top = 210, 250, 46
    bar_h, gap = 15, 11
    y = y_top + 8
    body: list[str] = []
    add = body.append

    for label, note, value, colour in rows:
        add(f'<text x="{x0 - 8}" y="{y + 8}" font-size="10.5" fill="{INK}" '
            f'text-anchor="end">{esc(label)}</text>')
        add(f'<text x="{x0 - 8}" y="{y + 19}" font-size="9" fill="{MUTED}" '
            f'text-anchor="end">{esc(note)}</text>')
        add(f'<rect x="{x0}" y="{y}" width="{value * x_span:.1f}" height="{bar_h}" '
            f'fill="{colour}"/>')
        add(f'<text x="{x0 + value * x_span + 5:.1f}" y="{y + bar_h - 3.5:.1f}" '
            f'font-size="10" fill="{INK}">{value:.4f}</text>')
        y += bar_h + gap

    y_base = y - gap + 2
    height = y_base + 46

    out: list[str] = []
    o = out.append
    o(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
      f'viewBox="0 0 {W} {height}" font-family="Helvetica, Arial, sans-serif">')
    o('<rect width="100%" height="100%" fill="#ffffff"/>')
    o(f'<text x="8" y="18" font-size="12" font-weight="bold" fill="{INK}">'
      'One system, one grader, six defensible numbers</text>')
    o(f'<text x="8" y="34" font-size="10" fill="{MUTED}">'
      'The deterministic template cascade. Orange bars are the same 30 questions '
      'at three code states.</text>')
    axis(o, x0, x_span, y_top, y_base)
    o("".join(body))
    o(f'<text x="{x0 + x_span / 2:.0f}" y="{y_base + 32}" font-size="10.5" '
      f'fill="{INK}" text-anchor="middle">Judged correctness (0–1)</text>')
    o("</svg>")

    svg = HERE / "fig02-six-numbers.svg"
    svg.write_text("\n".join(out) + "\n")
    convert(svg, HERE / "fig02-six-numbers.pdf")
    print(f"fig02-six-numbers: {W}x{height}")


if __name__ == "__main__":
    figure_one()
    figure_two()
