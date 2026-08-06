#!/usr/bin/env python3
"""Promoted figure: fig-arm-comparison.

    Source experiments: EXP-2026-07-001 … EXP-2026-07-007 (arms A–G)
    Output:             docs/research/figures/fig-arm-comparison.{svg,pdf}

Reads every arm's ``data/metrics.json``. **No number is hardcoded here** — that
is the rule this file exists to obey. Change a metric in an experiment and this
figure changes; change it here and nothing does, because there is nothing here to
change.

SVG is written by hand rather than via a plotting library, for three reasons:
no new dependency, byte-deterministic output (matplotlib embeds ids and dates
that break `make figures --check`), and the source stays diffable.

Palette: Okabe–Ito, colour-blind safe. Colour is never the only encoding —
every bar carries its arm letter and its value as text.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EXPERIMENTS = ROOT / "docs/research/experiments"
OUT_DIR = ROOT / "docs/research/figures"
STEM = "fig-arm-comparison"

# Okabe–Ito. Deterministic assignment by configuration family, so the reader can
# tell the three families apart without relying on hue alone (the letters and
# values are printed on every bar).
DETERMINISTIC = "#0072B2"   # blue   — no LLM in planning
LLM_PLANNED = "#D55E00"     # orange — LLM planner
CONTROL = "#666666"         # grey   — templates disabled

ARMS = [
    ("A", "EXP-2026-07-001", "Deterministic", DETERMINISTIC),
    ("F", "EXP-2026-07-006", "Determ. + loop\n+ LLM writer", DETERMINISTIC),
    ("D", "EXP-2026-07-004", "Determ. + LLM\nwriter (claims)", DETERMINISTIC),
    ("C", "EXP-2026-07-003", "Determ. + LLM\nwriter (evidence)", DETERMINISTIC),
    ("E", "EXP-2026-07-005", "LLM-planned\n+ loop", LLM_PLANNED),
    ("B", "EXP-2026-07-002", "LLM-planned", LLM_PLANNED),
    ("G", "EXP-2026-07-007", "Templates\ndisabled", CONTROL),
]

W, H = 760, 430
PAD_L, PAD_R, PAD_T, PAD_B = 62, 18, 58, 96
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B


def load() -> list[dict]:
    rows = []
    for letter, exp_id, label, colour in ARMS:
        matches = list(EXPERIMENTS.glob(f"{exp_id}-*/data/metrics.json"))
        if not matches:
            sys.exit(f"error: no metrics.json for {exp_id}")
        data = json.loads(matches[0].read_text())
        rows.append({
            "letter": letter,
            "label": label,
            "colour": colour,
            "correctness": data["metrics"]["correctness"]["mean"],
            "verdicts": data["verdicts"],
            "wall_s": data["wall_clock_seconds"],
        })
    return rows


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(rows: list[dict]) -> str:
    n = len(rows)
    slot = PLOT_W / n
    bar_w = slot * 0.58
    y0 = PAD_T + PLOT_H  # baseline

    out: list[str] = []
    add = out.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">')
    add('<rect width="100%" height="100%" fill="#ffffff"/>')

    # Title. 13pt at final print size — comfortably above the 7pt floor.
    add(f'<text x="{PAD_L}" y="26" font-size="13" font-weight="bold" fill="#111111">'
        f'Correctness by pipeline configuration, 120-question catalogue</text>')
    add(f'<text x="{PAD_L}" y="43" font-size="10" fill="#555555">'
        f'One independent Sonnet 5 judge per answer. Single run per arm (n=1); no seed variance.</text>')

    # Y axis: gridlines and labels at 0.2 intervals.
    for i in range(6):
        value = i / 5
        y = y0 - value * PLOT_H
        add(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + PLOT_W}" y2="{y:.1f}" '
            f'stroke="#e0e0e0" stroke-width="1"/>')
        add(f'<text x="{PAD_L - 8}" y="{y + 3.5:.1f}" font-size="9" fill="#444444" '
            f'text-anchor="end">{value:.1f}</text>')
    add(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{y0}" stroke="#111111" stroke-width="1.2"/>')
    add(f'<line x1="{PAD_L}" y1="{y0}" x2="{PAD_L + PLOT_W}" y2="{y0}" stroke="#111111" stroke-width="1.2"/>')
    add(f'<text x="14" y="{PAD_T + PLOT_H / 2:.1f}" font-size="10" fill="#222222" '
        f'text-anchor="middle" transform="rotate(-90 14 {PAD_T + PLOT_H / 2:.1f})">'
        f'mean correctness</text>')

    for i, row in enumerate(rows):
        cx = PAD_L + slot * (i + 0.5)
        x = cx - bar_w / 2
        h = row["correctness"] * PLOT_H
        y = y0 - h
        add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="{row["colour"]}"/>')
        # Value above the bar — colour is never the only encoding.
        add(f'<text x="{cx:.1f}" y="{y - 6:.1f}" font-size="10" font-weight="bold" '
            f'fill="#111111" text-anchor="middle">{row["correctness"]:.4f}</text>')
        # Arm letter inside the bar.
        add(f'<text x="{cx:.1f}" y="{y + 17:.1f}" font-size="12" font-weight="bold" '
            f'fill="#ffffff" text-anchor="middle">{row["letter"]}</text>')
        # Wrapped configuration label below the axis.
        for j, part in enumerate(row["label"].split("\n")):
            add(f'<text x="{cx:.1f}" y="{y0 + 15 + j * 11:.1f}" font-size="9" '
                f'fill="#333333" text-anchor="middle">{esc(part)}</text>')
        v = row["verdicts"]
        add(f'<text x="{cx:.1f}" y="{y0 + 40:.1f}" font-size="8" fill="#666666" '
            f'text-anchor="middle">{v["CORRECT"]}/{v["PARTIAL"]}/{v["INCORRECT"]}</text>')

    # Legend.
    ly = H - 30
    for k, (colour, text) in enumerate([
        (DETERMINISTIC, "authored plan"),
        (LLM_PLANNED, "LLM planner"),
        (CONTROL, "templates disabled (control)"),
    ]):
        lx = PAD_L + k * 210
        add(f'<rect x="{lx}" y="{ly - 8}" width="11" height="11" fill="{colour}"/>')
        add(f'<text x="{lx + 16}" y="{ly + 1}" font-size="9" fill="#333333">{esc(text)}</text>')
    add(f'<text x="{PAD_L}" y="{H - 10}" font-size="8" fill="#777777">'
        f'Bar labels: mean correctness. Under each bar: CORRECT/PARTIAL/INCORRECT. '
        f'Generated by figures/sources/make_arm_comparison.py</text>')
    add("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    rows = load()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = OUT_DIR / f"{STEM}.svg"
    svg_path.write_text(build_svg(rows))
    print(f"wrote {svg_path.relative_to(ROOT)}")

    pdf_path = OUT_DIR / f"{STEM}.pdf"
    try:
        subprocess.run(
            ["rsvg-convert", "-f", "pdf", "-o", str(pdf_path), str(svg_path)],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"error: rsvg-convert failed — {exc}", file=sys.stderr)
        print("install librsvg2-tools (Fedora) / librsvg2-bin (Debian)", file=sys.stderr)
        return 1
    print(f"wrote {pdf_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
