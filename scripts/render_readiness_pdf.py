#!/usr/bin/env python3
"""Render a research-record report from Markdown to a typeset PDF.

Written 2026-09-06 for ``docs/research/paper/venue-readiness-2026-09.md``.

``scripts/morning_report.py::render_pdf`` is deliberately minimal: it exists so a
nightly run always produces *something*, and it treats each source line as its own
paragraph, prints ``---`` literally, and lets ReportLab auto-size table columns.
That is fine for a one-page overnight note and produces an unreadable document at
twenty pages of dense tables. This renderer is for documents a person is expected
to sit down and read.

What it does that the minimal one does not:

* joins wrapped source lines into real paragraphs;
* a title page, a generated table of contents, running headers and ``Page N of M``;
* horizontal rules, block quotes, ordered lists and inline ``code`` spans;
* table columns sized in proportion to their content, with the header row repeated
  on every page a table spans;
* score words (MET / PARTIAL / UNMET / UNKNOWN) coloured so a tier table can be
  skimmed.

It returns ``False`` rather than raising if ReportLab is unavailable, matching the
contract of the renderer it sits beside.

    uv run python scripts/render_readiness_pdf.py \
        docs/research/paper/venue-readiness-2026-09.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# --- palette -----------------------------------------------------------------

INK = "#12253D"
NAVY = "#0F2A47"
ACCENT = "#1F4E79"
MUTED = "#5B6470"
RULE = "#C9D2E0"
ZEBRA = "#F5F7FA"
BAND = "#EDF1F7"

SCORE_COLOURS = {
    "MET": "#1B7A46",
    "PARTIAL": "#A2660A",
    "UNMET": "#B3261E",
    "UNKNOWN": "#5B6470",
}

# Tags used in the gap lists; coloured the same way wherever they appear.
TAG_COLOURS = {
    "WRITING": "#1F4E79",
    "PAPERWORK": "#1B7A46",
    "EXPERIMENT": "#A2660A",
    "OUT OF REACH": "#B3261E",
}


# --- inline markdown ---------------------------------------------------------

def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    """Convert inline Markdown to ReportLab's mini-HTML.

    Handles ``code``, **bold**, *italic*, and leaves everything else alone. Code
    spans are protected before the emphasis pass so a path containing an asterisk
    cannot be mangled.
    """
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<i>\1</i>", text)

    def restore(match: re.Match[str]) -> str:
        body = _escape(spans[int(match.group(1))])
        # Relative size: ReportLab accepts "-0.8" but not a percentage.
        return f'<font face="Courier" size="-0.8" color="{ACCENT}">{body}</font>'

    return re.sub(r"\x00(\d+)\x00", restore, text)


def score_of(cell: str) -> str | None:
    """Return the score word a table cell consists of, if it is one."""
    bare = re.sub(r"[*`]", "", cell).strip()
    return bare if bare in SCORE_COLOURS else None


# --- block parsing -----------------------------------------------------------

def parse_blocks(lines: list[str]) -> list[tuple[str, Any]]:
    """Group source lines into ('kind', payload) blocks.

    The important difference from a line-at-a-time renderer: consecutive non-blank
    prose lines become one paragraph, so ReportLab wraps them itself instead of
    inheriting the source file's hard line breaks.
    """
    blocks: list[tuple[str, Any]] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            blocks.append(("para", " ".join(buf).strip()))
            buf.clear()

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if not line:
            flush()
            i += 1
            continue

        if line.startswith("%"):
            flush()
            blocks.append(("meta", line[1:].strip()))
            i += 1
            continue

        if set(line) <= set("-") and len(line) >= 3:
            flush()
            blocks.append(("rule", None))
            i += 1
            continue

        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            blocks.append((f"h{min(level, 3)}", line.lstrip("#").strip()))
            i += 1
            continue

        if line.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(("quote", " ".join(quote).strip()))
            continue

        if line.startswith("|"):
            flush()
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") and c for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", line)
        number = re.match(r"^(\d+)\.\s+(.*)$", line)
        if bullet or number:
            flush()
            marker = "•" if bullet else f"{number.group(1)}."      # type: ignore[union-attr]
            body = bullet.group(1) if bullet else number.group(2)        # type: ignore[union-attr]
            i += 1
            # A list item may continue on indented following lines.
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip() or nxt[:1] not in " \t":
                    break
                if re.match(r"^\s*(?:[-*]|\d+\.)\s+", nxt):
                    break
                body += " " + nxt.strip()
                i += 1
            blocks.append(("item", (marker, body)))
            continue

        buf.append(line)
        i += 1

    flush()

    # Normalise heading depth. A document whose top-level heading is "##" should
    # still typeset that as its major section, and produce a two-level contents
    # list rather than a flat one.
    levels = [int(k[1]) for k, _ in blocks if k.startswith("h") and k[1:].isdigit()]
    if levels:
        shift = min(levels) - 1
        if shift:
            blocks = [
                (f"h{max(1, int(k[1]) - shift)}", v)
                if k.startswith("h") and k[1:].isdigit() else (k, v)
                for k, v in blocks
            ]

    # A horizontal rule immediately before a major heading is redundant: the
    # heading draws its own. Drop it rather than stacking two rules.
    cleaned: list[tuple[str, Any]] = []
    for idx, (kind, payload) in enumerate(blocks):
        if kind == "rule":
            nxt = next((k for k, _ in blocks[idx + 1:] if k != "meta"), None)
            if nxt == "h1":
                continue
        cleaned.append((kind, payload))
    return cleaned


# --- column widths -----------------------------------------------------------

def column_widths(rows: list[list[str]], avail: float,
                  font_size: float = 8.3) -> list[float]:
    """Size columns in proportion to how much text they actually carry.

    Auto-sizing is what wrecks the minimal renderer: a four-column table with one
    long column and three short ones comes out with the long column crushed. Here
    each column's weight is its mean content length, dampened so one very long
    column cannot swallow the table.

    Each column is then given at least enough room for its own longest *word*.
    Without that, ReportLab hyphenates nothing and simply breaks mid-word, which
    is how a header cell ends up reading "UNKNO / WN".
    """
    n = max(len(r) for r in rows)
    plain = [[re.sub(r"[*`]", "", r[c]) if c < len(r) else "" for c in range(n)]
             for r in rows]

    weights, minima = [], []
    for c in range(n):
        col = [row[c] for row in plain]
        mean = sum(len(v) for v in col) / max(len(col), 1)
        weights.append(max(mean, 3.0) ** 0.7)
        longest_word = max((len(w) for v in col for w in v.split()), default=1)
        # A short cell should not wrap at all: "E, W" broken over two lines reads
        # as an error. Anything under 11 characters is kept whole.
        longest_short = max((len(v) for v in col if len(v) <= 11), default=1)
        longest = max(longest_word, longest_short)
        # 0.76em covers Helvetica-Bold capitals, which is what the score column
        # holds ("UNKNOWN" averages 0.76em per glyph); plus the table's 12pt of
        # horizontal padding and 2pt of slack.
        minima.append(min(longest * font_size * 0.76 + 14, avail * 0.34))

    total = sum(weights)
    widths = [avail * w / total for w in weights]

    for _ in range(4):  # settle: raising one column takes width from the others
        debt = 0.0
        for idx, w in enumerate(widths):
            if w < minima[idx]:
                debt += minima[idx] - w
                widths[idx] = minima[idx]
        if debt <= 0.01:
            break
        donors = [i for i, w in enumerate(widths) if w > minima[i] + 6]
        pool = sum(widths[i] - minima[i] for i in donors)
        if not donors or pool <= 0:
            break
        for idx in donors:
            widths[idx] -= debt * (widths[idx] - minima[idx]) / pool

    # Take up the remaining slack from the columns that can spare it. A flat
    # rescale here would be a bug: it would pull columns back under the minima
    # the loop above just established, and the header cells would break again.
    slack = avail - sum(widths)
    if abs(slack) > 0.01:
        movable = [i for i, w in enumerate(widths) if w > minima[i] + 1] \
            if slack < 0 else list(range(len(widths)))
        pool = sum(widths[i] for i in movable)
        if movable and pool > 0:
            for idx in movable:
                widths[idx] += slack * widths[idx] / pool
    return widths


# --- the renderer ------------------------------------------------------------

def render(markdown: str, path: Path, running_title: str = "") -> bool:
    """Typeset ``markdown`` to ``path``. False if ReportLab is not installed."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas as pdfcanvas
        from reportlab.platypus import (
            BaseDocTemplate, CondPageBreak, Frame, HRFlowable, NextPageTemplate,
            PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
        )
        from reportlab.platypus.tableofcontents import TableOfContents
    except ImportError:
        return False

    ss = getSampleStyleSheet()

    body = ParagraphStyle(
        "body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.6,
        leading=13.8, spaceBefore=0, spaceAfter=7.5, alignment=TA_LEFT,
        textColor=colors.HexColor(INK),
    )
    lead = ParagraphStyle("lead", parent=body, fontSize=10.6, leading=15.4,
                          textColor=colors.HexColor(INK))
    h1 = ParagraphStyle(
        "h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15.5,
        leading=19, spaceBefore=4, spaceAfter=3, keepWithNext=True,
        textColor=colors.HexColor(NAVY),
    )
    h2 = ParagraphStyle(
        "h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.4,
        leading=15, spaceBefore=15, spaceAfter=5, keepWithNext=True,
        textColor=colors.HexColor(ACCENT),
    )
    h3 = ParagraphStyle(
        "h3", parent=ss["Heading3"], fontName="Helvetica-BoldOblique", fontSize=9.9,
        leading=13.5, spaceBefore=12, spaceAfter=3, keepWithNext=True,
        textColor=colors.HexColor(ACCENT),
    )
    cell = ParagraphStyle("cell", parent=body, fontSize=8.3, leading=11.0,
                          spaceAfter=0)
    cell_head = ParagraphStyle("cellhead", parent=cell, fontName="Helvetica-Bold",
                               textColor=colors.white)
    quote = ParagraphStyle("quote", parent=body, fontName="Helvetica-Bold",
                           fontSize=10.0, leading=14.4, spaceAfter=0,
                           textColor=colors.HexColor(NAVY))
    item = ParagraphStyle("item", parent=body, leftIndent=15, bulletIndent=2,
                          spaceAfter=5.5)
    title_style = ParagraphStyle("title", parent=body, fontName="Helvetica-Bold",
                                 fontSize=27, leading=32, spaceAfter=0,
                                 textColor=colors.HexColor(NAVY))
    sub_style = ParagraphStyle("sub", parent=body, fontSize=14.5, leading=19,
                               textColor=colors.HexColor(ACCENT))
    by_style = ParagraphStyle("by", parent=body, fontSize=9.5, leading=13,
                              textColor=colors.HexColor(MUTED))
    toc_title = ParagraphStyle("toctitle", parent=h1, spaceAfter=10)

    frame_w = LETTER[0] - 2 * 0.95 * inch

    # --- page furniture ------------------------------------------------------

    def cover_page(cv: Any, _doc: Any) -> None:
        cv.saveState()
        cv.setFillColor(colors.HexColor(NAVY))
        cv.rect(0, LETTER[1] - 0.42 * inch, LETTER[0], 0.42 * inch, stroke=0, fill=1)
        cv.restoreState()

    def body_page(cv: Any, doc: Any) -> None:
        cv.saveState()
        cv.setFont("Helvetica", 7.6)
        cv.setFillColor(colors.HexColor(MUTED))
        cv.drawRightString(LETTER[0] - 0.95 * inch, LETTER[1] - 0.62 * inch,
                           running_title)
        cv.setStrokeColor(colors.HexColor(RULE))
        cv.setLineWidth(0.5)
        cv.line(0.95 * inch, LETTER[1] - 0.72 * inch,
                LETTER[0] - 0.95 * inch, LETTER[1] - 0.72 * inch)
        cv.line(0.95 * inch, 0.72 * inch, LETTER[0] - 0.95 * inch, 0.72 * inch)
        cv.drawString(0.95 * inch, 0.56 * inch, doc.footer_left)
        cv.restoreState()

    class Numbered(pdfcanvas.Canvas):
        """Two-pass canvas so the footer can say 'Page N of M'."""

        def __init__(self, *a: Any, **kw: Any) -> None:
            super().__init__(*a, **kw)
            self._pages: list[dict[str, Any]] = []

        def showPage(self) -> None:
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._pages)
            for n, state in enumerate(self._pages, 1):
                self.__dict__.update(state)
                if n > 1:
                    self.setFont("Helvetica", 7.6)
                    self.setFillColor(colors.HexColor(MUTED))
                    self.drawRightString(LETTER[0] - 0.95 * inch, 0.56 * inch,
                                         f"Page {n} of {total}")
                super().showPage()
            super().save()

    class Doc(BaseDocTemplate):
        footer_left = ""

        def afterFlowable(self, flowable: Any) -> None:
            if not isinstance(flowable, Paragraph):
                return
            name = flowable.style.name
            if name in ("h1", "h2"):
                level = 0 if name == "h1" else 1
                self.notify("TOCEntry", (level, flowable.getPlainText(), self.page))

    doc = Doc(str(path), pagesize=LETTER,
              leftMargin=0.95 * inch, rightMargin=0.95 * inch,
              topMargin=0.95 * inch, bottomMargin=0.95 * inch,
              title=running_title or path.stem, author="Ariadne research record")
    # Zero padding so a full-width table's rule lands on the margin rather than
    # 6pt outside it; ReportLab's Frame default would push boxes past the text.
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover_page),
        PageTemplate(id="body", frames=[frame], onPage=body_page),
    ])

    blocks = parse_blocks(markdown.splitlines())
    meta = [payload for kind, payload in blocks if kind == "meta"]
    doc.footer_left = meta[2] if len(meta) > 2 else ""

    # The cover repeats the document's own bottom line, so page 1 answers the
    # question without being turned over.
    bottom_line = ""
    for idx, (kind, payload) in enumerate(blocks):
        if kind == "h1" and str(payload).lower().startswith("the answer"):
            for nk, np_ in blocks[idx + 1:]:
                if nk == "para":
                    bottom_line = str(np_)
                    break
            break

    story: list[Any] = []

    # --- title page ----------------------------------------------------------
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph(inline(meta[0]) if meta else path.stem, title_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor(ACCENT), spaceAfter=12))
    if len(meta) > 1:
        story.append(Paragraph(inline(meta[1]), sub_style))
    if len(meta) > 2:
        story.append(Spacer(1, 6))
        story.append(Paragraph(inline(meta[2]), by_style))

    if bottom_line:
        story.append(Spacer(1, 34))
        box = Table([[Paragraph("THE BOTTOM LINE", ParagraphStyle(
                        "kicker", parent=by_style, fontName="Helvetica-Bold",
                        fontSize=7.6, textColor=colors.HexColor(ACCENT)))],
                     [Paragraph(inline(bottom_line), body)]],
                    colWidths=[frame_w])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BAND)),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor(ACCENT)),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 12),
        ]))
        story.append(box)

    story.append(NextPageTemplate("body"))
    story.append(PageBreak())

    # --- contents ------------------------------------------------------------
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", parent=body, fontName="Helvetica-Bold", fontSize=10,
                       leading=15, spaceBefore=7, textColor=colors.HexColor(NAVY)),
        ParagraphStyle("toc1", parent=body, fontSize=9.2, leading=13.2,
                       leftIndent=18, textColor=colors.HexColor(INK)),
    ]
    story.append(Paragraph("Contents", toc_title))
    story.append(HRFlowable(width="100%", thickness=0.8,
                            color=colors.HexColor(RULE), spaceAfter=10))
    story.append(toc)
    story.append(PageBreak())

    # --- body ----------------------------------------------------------------
    first_h1 = True
    for kind, payload in blocks:
        if kind == "meta":
            continue

        if kind == "rule":
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.7,
                                    color=colors.HexColor(RULE),
                                    spaceBefore=4, spaceAfter=12))

        elif kind == "h1":
            if not first_h1:
                story.append(CondPageBreak(2.6 * inch))
            first_h1 = False
            story.append(Paragraph(inline(str(payload)), h1))
            story.append(HRFlowable(width="100%", thickness=1.4,
                                    color=colors.HexColor(NAVY), spaceAfter=9))

        elif kind == "h2":
            story.append(CondPageBreak(1.5 * inch))
            story.append(Paragraph(inline(str(payload)), h2))

        elif kind == "h3":
            story.append(Paragraph(inline(str(payload)), h3))

        elif kind == "quote":
            para = Paragraph(inline(str(payload)), quote)
            box = Table([[para]], colWidths=[frame_w])
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BAND)),
                ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor(ACCENT)),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]))
            story.append(box)
            story.append(Spacer(1, 10))

        elif kind == "item":
            marker, text = payload
            story.append(Paragraph(inline(text), item, bulletText=marker))

        elif kind == "para":
            style = lead if payload and str(payload).startswith("Aim at a") else body
            story.append(Paragraph(inline(str(payload)), style))

        elif kind == "table":
            rows: list[list[str]] = payload
            if not rows:
                continue
            widths = column_widths(rows, frame_w, font_size=cell.fontSize)
            data = [[Paragraph(inline(c), cell_head) for c in rows[0]]]
            for r in rows[1:]:
                padded = r + [""] * (len(rows[0]) - len(r))
                data.append([Paragraph(inline(c), cell) for c in padded])

            style_cmds = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(RULE)),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(NAVY)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
            for ridx in range(1, len(data)):
                if ridx % 2 == 0:
                    style_cmds.append(
                        ("BACKGROUND", (0, ridx), (-1, ridx), colors.HexColor(ZEBRA)))

            # Colour any cell that is exactly a score word.
            for ridx, r in enumerate(rows[1:], start=1):
                for cidx, raw in enumerate(r):
                    word = score_of(raw)
                    if word:
                        data[ridx][cidx] = Paragraph(
                            f'<b>{word}</b>',
                            ParagraphStyle(f"s{ridx}{cidx}", parent=cell,
                                           textColor=colors.HexColor(
                                               SCORE_COLOURS[word])))

            table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle(style_cmds))
            story.append(table)
            story.append(Spacer(1, 12))

    doc.multiBuild(story, canvasmaker=Numbered)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="Markdown file to render")
    ap.add_argument("--out", type=Path, default=None, help="PDF path")
    ap.add_argument("--running-title", default="")
    args = ap.parse_args()

    out = args.out or args.source.with_suffix(".pdf")
    text = args.source.read_text()
    running = args.running_title
    if not running:
        meta = [l[1:].strip() for l in text.splitlines() if l.startswith("%")]
        running = " — ".join(meta[:1] + meta[2:3]) if meta else args.source.stem

    ok = render(text, out, running_title=running)
    if not ok:
        print("reportlab unavailable — no PDF written", file=sys.stderr)
        return 1
    print(f"{out}  ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
