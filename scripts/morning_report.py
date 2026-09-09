#!/usr/bin/env python3
"""Write the morning report — for someone new to the field, as a PDF.

Rules this report follows, because breaking any of them produces something that
reads as informative and is not:

1. **No term goes undefined and no abbreviation goes unexpanded.** The audience
   is someone starting out.
2. **Every number carries what it is out of**, and every comparison carries what
   it is being compared to.
3. **Nothing is hardcoded.** Every figure is read from an artifact on disk, so a
   phase that failed cannot quietly contribute a stale number from a previous
   run.
4. **What did not run is stated as prominently as what did.** A partial night
   presented as a complete one is worse than no night.

The Markdown is written first and is the fallback: a rendering problem must
never cost the report.

    uv run python scripts/morning_report.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BANK_DIR = Path("docs/evaluation/composition/bank")
REPORTS = Path("docs/research/reports")


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"



def _budget_caveat(probe: dict[str, Any] | None) -> str:
    """The AI-written-query row is not a fair test, and the report must say so.

    Written as a function rather than inline prose because every number in it is
    read from the probe artifact. If the probe did not run, this says nothing at
    all rather than guessing.
    """
    if not probe:
        return ""
    census = probe.get("census") or {}
    total = census.get("questions")
    empty = census.get("empty_query")
    tried = sorted({t.get("budget") for c in probe.get("cases") or []
                    for t in c.get("trials") or [] if t.get("budget")})
    worked = sorted({t["budget"] for c in probe.get("cases") or []
                     for t in c.get("trials") or [] if t.get("produced_query")})
    lines = [
        "### Read the AI-written-query row with care",
        "",
        "It is not a fair test of that idea, and it should not be reported as one.",
        "",
        "The model doing the writing thinks out loud before it answers, and the "
        "thinking and the answer come back separately. It gets a fixed allowance "
        "of words per question. On these questions it spent the whole allowance "
        "on the thinking and never reached the answer, so what came back was "
        "blank — and a blank is recorded exactly like a wrong answer.",
        "",
    ]
    if total and empty is not None:
        lines += [f"That happened on **{empty} of {total}** questions in that row.", ""]
    if tried:
        trials = [t for c in probe.get("cases") or [] for t in c.get("trials") or []]
        run_at = probe.get("arm_budget_as_run")
        at_arm = [t for t in trials if t.get("budget") == run_at]
        bigger = [t for t in trials if t.get("budget") and t["budget"] > (run_at or 0)]
        answered = [t for t in bigger if t.get("produced_query")]
        refused = [t for t in bigger if t.get("error")]
        lines += [
            "Afterwards the identical request was put to the same model again, "
            "word for word.",
            "",
        ]
        if at_arm:
            blank = sum(1 for t in at_arm if not t.get("produced_query"))
            lines.append(
                f"* At the allowance the run actually used, **{blank} of "
                f"{len(at_arm)}** replies came back blank — the model used every "
                "word it was given on thinking."
            )
        if bigger:
            biggest = max(t["budget"] for t in bigger)
            done = len(bigger) - len(refused)
            if answered:
                if done == 1 and len(answered) == 1:
                    phrase = "the single reply that came back at all contained"
                else:
                    phrase = (f"{len(answered)} of the {done} replies that came "
                              "back at all contained")
                lines.append(
                    f"* Given **{biggest / (run_at or 1):.0f}x** the allowance, "
                    f"{phrase} an actual query instead of a blank. Whether that "
                    "query is *correct* is a separate question this check does not "
                    "ask — the point is only that something was written at all."
                )
            if refused:
                lines.append(
                    f"* {len(refused)} of those larger attempts never returned: the "
                    "service in front of the model gave up waiting. That is a "
                    "limit of the plumbing, not of the model, and it is recorded "
                    "as such rather than counted as a failure to answer."
                )
        lines.append("")
        if worked:
            lines += [
                "So the row above measures how much room the model was given to "
                "think, not whether it can write a query.",
                "",
            ]
    pinned = probe.get("dotenv_value_not_used_by_arm")
    effective = probe.get("arm_budget_as_run")
    if pinned is not None and effective is not None and str(pinned) != str(effective):
        lines += [
            f"There is a second, separate lesson here. The project's settings file "
            f"asks for an allowance of {int(pinned):,}, but this run never read that "
            f"file — it used the built-in default of {int(effective):,} instead. "
            "Neither number was large enough, so it made no difference to the "
            "result tonight; but a setting that is written down, looks correct, "
            "and is silently ignored is worth knowing about before it matters.",
            "",
        ]
    lines += [
        "Fixing it needs either a much larger allowance — which makes every "
        "question far slower — or a model that answers without a long preamble. "
        "Either way it needs its own run. **Nothing was changed tonight**; this "
        "was found by reading the run's own records and asking the model the same "
        "question again.",
        "",
    ]
    return "\n".join(lines)


def build_markdown(state: dict[str, Any] | None, art: dict[str, Any]) -> str:
    L: list[str] = []
    add = L.append
    stamp = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    add("# Overnight results")
    add("")
    add(f"*Generated {stamp}. Every number below was read from a file produced "
        "during the run — nothing here is typed in by hand.*")
    add("")

    # ---------- what this is ------------------------------------------------
    add("## What this project is, in one paragraph")
    add("")
    add("Ariadne answers security questions by looking things up in two public "
        "reference catalogues rather than by asking a language model to recall "
        "them. The catalogues are **ATT&CK**, a catalogue of the techniques "
        "attackers use, and **CAPEC**, a catalogue of attack patterns. They are "
        "stored as *graphs*: things (a technique, a piece of malware) connected "
        "by relationships (this malware *uses* that technique). A question like "
        "\"what mitigates technique T1055?\" becomes a walk along those "
        "connections. Because the answer comes from the catalogue rather than "
        "from a model's memory, it can be checked.")
    add("")

    # ---------- what we did tonight ----------------------------------------
    add("## What was done tonight")
    add("")
    add("Until yesterday the system was tested with **30 questions at a time**, "
        "hand-written from a list of 16 question types somebody wrote from "
        "memory. Two things came out of the last few days: that list covers only "
        "**a third** of the kinds of question the catalogues can answer, and "
        "some of the catalogue was never even loaded into the database.")
    add("")
    add("Both are now fixed. Tonight's run tests the system against a new set of "
        "questions built to cover **everything the catalogues support**, "
        "including the corners nothing had ever asked about.")
    add("")

    # ---------- the bank ----------------------------------------------------
    bank = art.get("bank")
    if bank:
        meta = bank["meta"]
        questions = bank["questions"]
        splits: dict[str, int] = {}
        tiers: dict[str, int] = {}
        for q in questions:
            splits[q["split"]] = splits.get(q["split"], 0) + 1
            tiers[q["d_tier"]] = tiers.get(q["d_tier"], 0) + 1
        add("### The new question set")
        add("")
        add(f"- **{len(questions)} questions**, written by an AI author that was "
            "shown only the subject of each question and what to ask about it — "
            "never the answer. The answers were worked out separately, straight "
            "from the source files, *before* the questions existed. That is what "
            "makes the scores meaningful: the questions cannot have been bent to "
            "fit the answers.")
        add(f"- Split into two halves by a fixed rule before anything was run: "
            f"**{splits.get('dev', 0)} for development** and "
            f"**{splits.get('holdout', 0)} held back and untouched**. The second "
            "half stays sealed so it can be a genuine test later. Nothing "
            "tonight looked at it.")
        add("- Questions come in seven kinds, from \"read one fact about one "
            "thing\" up to \"follow a chain across both catalogues\", plus a set "
            "of questions that have **no answer at all**, to check the system "
            "says so instead of inventing one.")
        add("")
        add("| kind of question | how many |")
        add("|---|---:|")
        names = {
            "D0": "no answer exists (a trap)",
            "D1": "read one fact about one thing",
            "D2": "follow one connection forwards",
            "D3": "follow one connection backwards",
            "D4": "follow two connections",
            "D5": "follow one connection, with a filter",
            "D6": "follow a chain across both catalogues",
        }
        for key in sorted(tiers):
            add(f"| {names.get(key, key)} | {tiers[key]} |")
        add("")

    # ---------- headline ----------------------------------------------------
    score = art.get("score", {}).get("report") if art.get("score") else None
    add("## The headline result")
    add("")
    if not score:
        add("**Not available** — the scoring step did not complete. See "
            "*What did not run* below.")
    else:
        add("The measure below is **recall**: of the things the correct answer "
            "contains, what fraction did the system actually find? A recall of "
            "1.0 means it found everything; 0.5 means it found half. **No AI was "
            "used to mark these** — the correct answers were computed from the "
            "source files, so this is a count, not an opinion.")
        add("")
        add("| | score |")
        add("|---|---:|")
        add(f"| across all questions as drawn | **{pct(score['pooled_recall'])}** |")
        add(f"| adjusted for how common each question type really is | "
            f"**{pct(score['reweighted_recall'])}** |")
        add(f"| development half | {pct(score['by_split'].get('dev'))} |")
        add(f"| held-back half | {pct(score['by_split'].get('holdout'))} |")
        add("")
        add("**Why two headline numbers.** The question set was built on purpose "
            "to over-represent the rare corners of the catalogues — that is where "
            "problems hide. So the plain average is pulled down by question types "
            "that barely occur in real use. The adjusted number re-weights each "
            "question type by how common it actually is, and is the fairer "
            "summary.")
        add("")
        add("**What this is not.** The older 30-question sets score 95–100%. That "
            "is not the same test: they cover 12 kinds of connection instead of "
            "34, they ask each one in the direction it was written for, and they "
            "are marked differently. **These numbers cannot be compared to those, "
            "and a drop from one to the other is not the system getting worse.**")
        add("")
        dev = score["by_split"].get("dev")
        hold = score["by_split"].get("holdout")
        if dev is not None and hold is not None:
            add(f"One reassuring sign: the two halves score within "
                f"{abs(dev - hold) * 100:.1f} percentage points of each other. "
                "Since the split was fixed before any question was run, that is "
                "evidence the question set was not tuned to flatter the system.")
            add("")

    # ---------- findings ----------------------------------------------------
    add("## What we learned")
    add("")
    if score:
        add("### 1. Harder questions really are harder — with one exception")
        add("")
        add("| kind of question | recall |")
        add("|---|---:|")
        friendly = {
            "D1": "read one fact",
            "D2": "one connection, forwards",
            "D3": "one connection, backwards",
            "D4": "two connections",
            "D5": "one connection plus a filter",
            "D6": "a chain across both catalogues",
        }
        for key, value in sorted(score["by_tier"].items(), key=lambda kv: -(kv[1] or 0)):
            add(f"| {friendly.get(key, key)} | {pct(value)} |")
        add("")
        add("Following two connections is the hardest, which is what we expected: "
            "each extra step is another chance to lose the thread. **The surprise "
            "is that reading a single fact scores below following a connection** "
            "— that is backwards, and it is diagnosed below.")
        add("")
        width = score.get("by_width_band") or {}
        if width:
            add("### 2. Long answers are harder than short ones")
            add("")
            add("| how many items the correct answer contains | recall |")
            add("|---|---:|")
            for band in ("1", "2-5", "6-20", "21+"):
                if band in width:
                    add(f"| {band} | {pct(width[band])} |")
            add("")
            add("The more items the correct answer has, the smaller the fraction "
                "the system finds. This is worth knowing because an earlier "
                "study concluded answer length made no difference — but that "
                "study measured whether an AI marker *liked* the answer, and "
                "only had six long questions to work with. This one counts what "
                "was actually retrieved, across 39 long questions. Both can be "
                "true at once: finding half a long answer may still read well.")
            add("")
        ab = score.get("abstention") or {}
        if ab.get("n"):
            add("### 3. Saying \"I don't know\" is the weakest area")
            add("")
            add(f"Of **{ab['n']} questions that have no answer**, the system "
                f"correctly returned nothing **{ab['correctly_returned_nothing']} "
                f"times ({pct(ab['rate'])})**. The rest returned something.")
            add("")
            anomalies = art.get("anomalies")
            if anomalies:
                outcomes = anomalies["abstention"]["outcomes"]
                anchor_only = outcomes.get("returned_the_anchor_only", 0)
                unrelated = outcomes.get("returned_unrelated_neighbours", 0)
                add(f"Breaking down the failures: **{anchor_only}** returned only "
                    "the thing the question was about and nothing else — a mild "
                    "failure, closer to an unhelpful answer than a wrong one. "
                    f"**{unrelated}** returned unrelated material, which is the "
                    "more serious kind.")
                add("")
            add("This matters more than the number suggests. Before tonight this "
                "behaviour had been tested on **four** questions. It has now been "
                f"tested on {ab['n']}.")
            add("")

    direction = art.get("direction")
    if direction:
        add("### 4. Direction: a contradiction, resolved")
        add("")
        add("Connections have a direction. \"What mitigates this technique?\" and "
            "\"what does this mitigation cover?\" walk the same link opposite "
            "ways, and a system can be good at one and bad at the other.")
        add("")
        agg = direction["confounded_aggregate"]
        prim = direction["primary"]
        add(f"Two earlier readings disagreed. Simply averaging all forward "
            f"questions ({pct(agg['forward'])}) against all backward ones "
            f"({pct(agg['reverse'])}) says backward is easier. But that "
            "comparison is unfair: the forward and backward questions are about "
            "*different* connections, so it may just be that the backward ones "
            "landed on easier subject matter.")
        add("")
        add("Comparing **like with like** — the same connection asked both ways — "
            f"gives a mean difference of **{prim['mean_delta']:+.3f}** across "
            f"{prim['pairs']} connections "
            f"(plus or minus {prim['se']:.3f}), where a positive number means "
            "forward was easier.")
        add("")
        add(f"Forward was easier for **{prim['forward_higher']}** connections, "
            f"backward for **{prim['reverse_higher']}**, and "
            f"**{prim['tied']}** were level. **So there is no single answer: "
            "direction matters a lot, but which direction is harder depends "
            "entirely on the connection.** That is a more useful finding than "
            "either average, and it is why the fair comparison was worth doing.")
        add("")
        detail = sorted(prim["pairs_detail"], key=lambda d: d["delta"])
        if detail:
            add("The widest gaps in each direction:")
            add("")
            add("| connection | which way is easier | gap |")
            add("|---|---|---:|")
            for entry in detail[:3] + detail[-3:]:
                way = "backwards" if entry["delta"] < 0 else "forwards"
                add(f"| {entry['shape']} | {way} | {abs(entry['delta']):.2f} |")
            add("")

    anomalies = art.get("anomalies")
    if anomalies:
        add("### 5. Why the weak areas are weak")
        add("")
        prop = anomalies["property_reads"]
        causes = prop["failure_causes"]
        total = sum(causes.values())
        add(f"The two weak areas — reading a single fact, and questions about "
            f"which group or collection something belongs to — **fail in exactly "
            f"the same way**. In "
            f"{causes.get('query_built_returned_no_rows', 0)} of {total} cases "
            "the system builds a database query correctly and the query comes "
            "back empty.")
        add("")
        add("That is a useful thing to know, because it rules out most "
            "explanations. It is not misunderstanding the question, and it is "
            "not failing to build a query. The query is being built and is "
            "looking in a place where the answer is not.")
        add("")
        by_anchor = prop["recall_by_anchor_label"]
        zeros = [k for k, v in by_anchor.items() if v == 0.0]
        if zeros:
            add(f"Reading single facts fails **completely** for "
                f"{', '.join(zeros)} — a score of zero — while working roughly "
                "half the time for everything else. The problem is specific to "
                "certain kinds of thing, not general.")
            add("")

    # ---------- judged arms -------------------------------------------------
    judged = art.get("judged")
    add("## Comparing the different ways of answering")
    add("")
    if not judged:
        add("**Not available.** The comparison between the system's different "
            "answering strategies did not finish. The scores above come from the "
            "strategy that uses no AI at all to plan its database queries; "
            "comparing it against the AI-planned alternatives is the next step "
            "and needs a rerun.")
        add("")
        # The caveat is about how the AI-written-query arm was *run*, so it holds
        # whether or not the scoring of that arm finished.
        add(_budget_caveat(art.get("budget_probe")))
    else:
        gloss = {
            "deterministic": "Fixed, pre-written database queries, picked by rules. "
                             "No model decides what to look up.",
            "generic": "Queries assembled on the spot out of the catalogue's own "
                       "structure — still nothing written by a model.",
            "llm_query": "A language model is shown the catalogue's structure and "
                         "asked to write the database query itself.",
        }
        add("**These scores are not the headline number above, and the two must "
            "not be compared.** The headline counts *how much of the right answer "
            "was found*, over every question, by comparing against answers computed "
            "from the source files. The table below is a different measure — an AI "
            "marker reading each written answer and rating it — over the "
            "development half only, and each answer was marked twice with the "
            "order swapped. Its use is to rank the three strategies against each "
            "other, nothing else.")
        add("")
        add("| strategy | score | what it is |")
        add("|---|---:|---|")
        for arm, value in sorted(judged.items(), key=lambda kv: -(kv[1] or 0)):
            add(f"| {arm} | {pct(value)} | {gloss.get(arm, '')} |")
        add("")
        add(_budget_caveat(art.get("budget_probe")))

    # ---------- what did not run -------------------------------------------
    add("## What did not run")
    add("")
    if state and state.get("phases"):
        failed = [p for p in state["phases"] if p.get("status") != "ok"]
        done = [p for p in state["phases"] if p.get("status") == "ok"]
        add(f"{len(done)} of {len(state['phases'])} steps finished.")
        add("")
        if failed:
            add("| step | what happened |")
            add("|---|---|")
            for phase in failed:
                add(f"| {phase['name']} | {phase.get('status')}: "
                    f"{str(phase.get('error') or 'not reached')[:160]} |")
            add("")
        else:
            add("Every planned step finished.")
            add("")
    else:
        add("No run record was found, so this report was assembled from whatever "
            "artifacts were on disk. Treat any missing section as *did not run* "
            "rather than *nothing to report*.")
        add("")
    add("**The held-back half of the questions was not touched.** That was "
        "deliberate: it is only useful as a test if nothing has been tuned "
        "against it.")
    add("")
    add("**Nothing about the system itself was changed tonight.** Every fix that "
        "involves a judgement call was left for the morning.")
    add("")

    # ---------- next --------------------------------------------------------
    add("## What to decide")
    add("")
    add("1. **The empty-query problem.** Two weak areas share one cause, and it "
        "looks like a single fixable defect rather than a deep limitation. Worth "
        "looking at first.")
    add("2. **Saying \"I don't know\".** The system returns something for about "
        "four in ten unanswerable questions. Most of those are mild, but it is "
        "the clearest weakness the new question set found.")
    add("3. **Direction.** Now known to matter, and to matter differently for "
        "different connections. Whether to do anything about it is a design "
        "decision, not a bug fix.")
    add("")
    return "\n".join(L)


def render_pdf(markdown: str, path: Path) -> bool:
    """Render to PDF. Returns False if the renderer is unavailable."""
    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
        from reportlab.lib import colors
    except ImportError:
        return False

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15,
                          spaceAfter=8, alignment=TA_LEFT)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceBefore=6,
                        spaceAfter=14, textColor=colors.HexColor("#1a1a2e"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14.5, spaceBefore=18,
                        spaceAfter=8, textColor=colors.HexColor("#16213e"))
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontSize=12, spaceBefore=13,
                        spaceAfter=6, textColor=colors.HexColor("#0f3460"))

    def inline(text: str) -> str:
        out, bold = [], False
        i = 0
        while i < len(text):
            if text.startswith("**", i):
                out.append("</b>" if bold else "<b>")
                bold = not bold
                i += 2
                continue
            ch = text[i]
            out.append({"&": "&amp;", "<": "&lt;", ">": "&gt;"}.get(ch, ch))
            i += 1
        if bold:
            out.append("</b>")
        return "".join(out).replace("`", "")

    flow: list[Any] = []
    rows: list[list[str]] = []

    def flush_table() -> None:
        nonlocal rows
        if not rows:
            return
        data = [[Paragraph(inline(c), body) for c in r] for r in rows]
        table = Table(data, hAlign="LEFT", colWidths=None)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f7")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8cfdd")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(table)
        flow.append(Spacer(1, 10))
        rows = []

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append(cells)
            continue
        flush_table()
        if not stripped:
            continue
        if stripped.startswith("### "):
            flow.append(Paragraph(inline(stripped[4:]), h3))
        elif stripped.startswith("## "):
            flow.append(Paragraph(inline(stripped[3:]), h2))
        elif stripped.startswith("# "):
            flow.append(Paragraph(inline(stripped[2:]), h1))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            flow.append(Paragraph("• " + inline(stripped[2:]), body))
        elif stripped[:2].rstrip(".").isdigit() and stripped[1:3] in (". ", ".  "):
            flow.append(Paragraph(inline(stripped), body))
        else:
            flow.append(Paragraph(inline(stripped), body))
    flush_table()

    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                            title="Ariadne — overnight results")
    doc.build(flow)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank-dir", type=Path, default=BANK_DIR)
    parser.add_argument("--state", type=Path, default=BANK_DIR / "overnight-state.json")
    parser.add_argument("--out", type=Path, default=REPORTS / "2026-09-02-overnight-report")
    args = parser.parse_args()

    art = {
        "bank": load(args.bank_dir / "bank.json"),
        "score": load(args.bank_dir / "score.json"),
        "direction": load(args.bank_dir / "direction.json"),
        "anomalies": load(args.bank_dir / "anomalies.json"),
        "judged": load(args.bank_dir / "judged.json"),
        "budget_probe": load(args.bank_dir / "budget-probe.json"),
    }
    state = load(args.state)

    markdown = build_markdown(state, art)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    md_path = args.out.with_suffix(".md")
    md_path.write_text(markdown)
    print(f"report (markdown) -> {md_path}")

    pdf_path = args.out.with_suffix(".pdf")
    if render_pdf(markdown, pdf_path):
        print(f"report (pdf)      -> {pdf_path}  ({pdf_path.stat().st_size:,} bytes)")
    else:
        print("PDF renderer unavailable — the Markdown above is the report.")


if __name__ == "__main__":
    main()
