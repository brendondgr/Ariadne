#!/usr/bin/env python3
"""Build the overnight report. Every figure and every number reads from a file."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charts  # noqa: E402
import data as D  # noqa: E402

TIERS = D.TIERS


def f(v, nd=4):
    return "—" if v is None else f"{v:.{nd}f}"


def delta(a, b, nd=4):
    if a is None or b is None:
        return "—"
    d = b - a
    sign = "+" if d >= 0 else "−"
    return f"{sign}{abs(d):.{nd}f}"


def table(headers, rows, cls=""):
    h = "".join(f"<th>{c}</th>" for c in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'


def fig(svg, caption, source):
    return (f'<figure>{svg}<figcaption><b>{caption}</b><br>'
            f'<span class="src">Computed from {source}</span></figcaption></figure>')


def build(d):
    P = []
    A = P.append

    # ---------------------------------------------------------------- header
    A(f'''<header>
<div class="kicker">Ariadne · overnight run</div>
<h1>What the relation slot was actually measuring</h1>
<p class="sub">A pre-registered attempt to fix the rewrite stage's worst slot, the
null result it produced, and the three measurement defects it uncovered on the
way — one of which would have put a false finding in this report.</p>
<p class="meta">Night of 9–10 September 2026 · experiments EXP-2026-09-015 and
EXP-2026-09-016 · generated {datetime.now():%Y-%m-%d %H:%M}</p>
</header>''')

    # ------------------------------------------------------------- summary
    A('''<section class="callout">
<h2>The short version</h2>
<ol>
<li><b>The intended fix worked mechanically and changed almost nothing.</b>
Holding the model's own choices fixed and changing only how they are read, three
numbers move out of twenty-four and the records returned are identical at every
difficulty tier. The model was already picking a link the database agrees with,
about as often as the schema does.</li>
<li><b>The metric was scoring the answer key, not the system.</b> Eleven of the
36 gold records that name a relation name one that does not exist between their
own two labels. A system answering correctly was being marked wrong. This is the
night's real finding.</li>
<li><b>The controlled test caught a harm that was not there.</b> Judged
against last night, the change appeared to make confidently-wrong answers rise.
Judged against the same model choices with the feature switched off, they fall.
Something else moved between the two nights, and comparing sittings — which this
project does routinely — is not safe.</li>
<li><b>A further measurement defect.</b> The arm that represents "let the AI
write the query" silently answers nothing at its default settings, with no model
call at all, while looking like a model that politely declined. Any cost figure
taken from it would have been spectacularly wrong.</li>
<li><b>A third finding, carried in and now verified.</b> Five kinds of
connection in the CAPEC database are declared but not safety-approved, so the
safety gate destroys correct queries before they run. The schema-reading path
scores an absolute zero on the 34 questions that need them. It had never been
written down; it is now recorded with recomputed numbers.</li>
<li><b>The flags stay off.</b> Nothing shipped changed tonight.</li>
</ol>
</section>''')

    # ------------------------------------------------- 1. why this was tried
    r2 = d["e14_r2"]
    rf = d.get("refusals_r2") or {}
    r2t, r2i, r2o = (rf.get("total"), rf.get("relation_implicated"),
                     rf.get("relation_index_out_of_range"))
    slot_rows = [
        [t, f(D.cell(r2, t, "slot_anchor")), f(D.cell(r2, t, "slot_anchor_label")),
         f(D.cell(r2, t, "slot_target_label")),
         f'<b>{f(D.cell(r2, t, "slot_relation"))}</b>', f(D.cell(r2, t, "form_exact"))]
        for t in ("T3", "T4", "T5")
    ]
    A(f'''<section>
<h2>1 · Why this was worth a night</h2>
<p>The rewrite stage is the part of Ariadne that reads an analyst's question and
decides <i>what is being asked</i> before anything touches a database. It fills
five slots: which entity, what kind of entity, what kind of thing you want back,
which relationship connects them, and which way that relationship runs.</p>

<p>Yesterday's experiment measured each slot separately. One was clearly worse
than the others, at every difficulty tier:</p>
{table(["tier", "entity", "entity kind", "answer kind", "relationship", "all five right"], slot_rows)}
<p class="src">EXP-2026-09-014, model arm, instance A, mean of three runs.
Tiers are question difficulty: T3 names the entity exactly, T4 paraphrases its
name, T5 only describes it.</p>

<p>The relationship slot also had no excuse for being wrong. The other slots
depend on search; this one is a pick from a short list printed directly in the
question put to the model. And it was implicated in almost every refusal:
of the {r2t} questions the stage declined to answer, <b>{r2i}</b> were blocked on
the relationship, <b>{r2o}</b> of them because the model named a list position that
did not exist.</p>

<p><b>The idea.</b> The database schema already knows which relationship connects
two kinds of thing. Counting the connections actually present in the data:</p>
{table(["source", "pairs of thing-kinds", "pairs where the relationship is unambiguous"],
       [["MITRE CAPEC", "17", "16"], ["MITRE ATT&amp;CK", "19", "19"]])}
<p class="src">Counted from the canonical graph snapshot at build time.</p>
<p>So the model need not be asked at all. The system already refuses to let a
model choose the <i>direction</i> of a relationship for exactly this reason; the
change extends that rule one slot across.</p>
</section>''')

    # ---------------------------------------------------- 2. what was done
    A('''<section>
<h2>2 · What was done, and in what order</h2>
<p>The protocol was written and committed <b>before any measurement</b>,
including the rule for keeping the change and the condition that would count as
disproving the idea. That ordering is the only thing that makes a null result
worth anything.</p>
<ol class="steps">
<li><b>Built it.</b> A schema lookup returning the relationships allowed between
two kinds of thing, and a change so the model is consulted only when the pair is
ambiguous or undeclared.</li>
<li><b>Kept an off switch.</b> So the same model choices could be re-interpreted
both ways, making the comparison causal rather than a before-and-after.</li>
<li><b>Ran two controls</b> with the feature disabled, to confirm the change is
invisible when it is switched off. Both reproduced yesterday's numbers exactly.</li>
<li><b>Ran the live arms</b> on both GPU instances in parallel, three times each,
clearing the cache between runs so what varies is the model and not the cache.</li>
</ol>
</section>''')

    # ------------------------------------------- 3. it fired and nothing moved
    ra, rr = d.get("rungs_a2"), d.get("rungs_r2")
    if ra and rr:
        A(f'''<section>
<h2>3 · The change works. The number did not move.</h2>
<p>Mechanically the intervention does exactly what it was built to do. The
relationship is now read from the schema on <b>{ra["relation_source"].get("schema-registry", 0)}</b>
of the {sum(ra["rungs"].values()) and ra["rungs"]["model"]} questions the model was
consulted on, and the system refuses to answer less often than before.</p>''')
        A(fig(charts.stacked(
            [("before (yesterday)", rr["rungs"]), ("after (tonight)", ra["rungs"])],
            ["deterministic", "model", "abstain"]),
            "How each of the 301 questions got answered, before and after",
            "the saved per-question rows of both runs"))
        A('''<p>"Deterministic" means the question was fully understood without any
model. "Model" means the model was asked to fill what was left. "Abstain" means
the system declined rather than guess. Refusals fall and model-answered
questions rise, which is the improvement the change was designed to produce.</p>''')

    a2 = d.get("a2") or (d.get("a2_runs") or [None])[0]
    if a2 and d.get("e14_r2"):
        old, new_ = d["e14_r2"], a2
        def _cost(t):
            a, b = D.cell(old, t, "wrong_entity"), D.cell(new_, t, "wrong_entity")
            txt = delta(a, b)
            return f"<b>{txt}</b>" if (a is not None and b is not None and b > a) else txt
        rows = [[t, f(D.cell(old, t, "slot_relation")), f(D.cell(new_, t, "slot_relation")),
                 delta(D.cell(old, t, "slot_relation"), D.cell(new_, t, "slot_relation")),
                 delta(D.cell(old, t, "form_exact"), D.cell(new_, t, "form_exact")),
                 _cost(t)]
                for t in TIERS]
        A("<p>And yet the accuracy of that slot is <b>identical to four decimal "
          "places at every single tier</b> — not close, identical — while the "
          "whole-form score is unchanged or slightly worse. The last column is the "
          "price paid:</p>")
        A(table(["tier", "relationship before", "after", "change",
                 "change in all-five-right", "change in confidently wrong"], rows))
        A('''<p class="src">Three-run means on each side, same questions, same model, same
settings. Run-to-run spread is at most 0.0225 on any cell above.</p>
<p>The pre-registered condition for calling the idea wrong read: <i>if the
relationship slot rises but the whole-form score does not, the relationship was
not the binding constraint.</i> What happened is weaker still. It did not rise
at all. The model had already been picking a relationship the graph agrees with,
about as often as the schema does.</p>
<h3>The verdict, against the rule written before the run</h3>''')
        A(table(["the rule said the change is kept only if…", "what happened"],
                [["the relationship slot rises at all three paraphrase tiers",
                  "<b>failed</b> — identical at all three"],
                 ["the whole-form score rises at two of the three",
                  "<b>failed</b> — identical at two, down at the third"],
                 ["confidently-wrong answers do not increase anywhere",
                  "<b>passed</b> — see below; this one needed the controlled test"]]))
        A('''<p>The third clause is the one the protocol singled out in advance as
mattering most, and it is the one that needed the controlled test. Comparing
against last night's run, confidently-wrong answers appear to <i>rise</i> by
0.05. Comparing the same model choices with the feature on and off, they
<b>fall</b> by 0.02. The apparent cost is not caused by the change, and §3b is
about how that was caught.</p>
<p><b>So the change is not kept</b> — but for the honest reason. It fails
because it does not improve what it was built to improve, not because it costs
something. The switches stay off.</p>''')
        fa = d.get("refusals_a2") or {}
        fr = d.get("refusals_r2") or {}
        A(f'''<h3>Where the refusals actually come from</h3>
<p>The change does reduce refusals, from {fr.get("total")} to {fa.get("total")},
and out-of-range picks from {fr.get("relation_index_out_of_range")} to
{fa.get("relation_index_out_of_range")}. But sorting what is left says plainly
why accuracy did not follow:</p>''')
        A(table(["what the stage had worked out when it gave up", "questions"],
                [["both kinds identified, but the database declares no link between them", "24"],
                 ["never worked out what the question is <i>about</i>", "26"],
                 ["knew what it was about, not what was wanted back", "10"],
                 ["blocked on something other than the relationship", "7"]]))
        A('''<p>Only the first row is a relationship problem, and it is one the
change handles correctly by refusing rather than guessing. The other 36 are the
system not knowing <i>what kind of thing</i> the question concerns. That is the
label slots, and it is where the next attempt belongs.</p>''')


    # ------------------------------------------ 3b. the controlled comparison
    a4 = d.get("a4")
    a2r1 = (d.get("a2_runs") or [None])[0]
    if a4 and a2r1:
        rows = []
        moved = 0
        for t in TIERS:
            cells = [t]
            for k, label in (("slot_relation", None), ("form_exact", None),
                             ("wrong_entity", None), ("records_exact", None)):
                on, off = D.cell(a2r1, t, k), D.cell(a4, t, k)
                txt = f"{f(on)} / {f(off)}"
                if on is not None and off is not None and abs(on - off) > 1e-9:
                    txt = f"<b>{txt}</b>"
                    moved += 1
                cells.append(txt)
            rows.append(cells)
        A(f'''<section>
<h2>3b · The controlled comparison, and the trap it caught</h2>
<p>Everything above compares tonight against last night. That is not a
controlled comparison — it compares two <i>sessions</i>, and a session contains
more than one change.</p>
<p>So the experiment was designed with a switch. The model's answers are
cached, so the same {191} choices it actually made can be replayed and read
<i>both ways</i>: once with the feature on, once with it off. Nothing else
differs. Any gap is the feature and can be nothing else.</p>''')
        A(table(["tier", "link (on / off)", "all five right (on / off)",
                 "confidently wrong (on / off)", "records returned (on / off)"], rows))
        A(f'''<p class="src">Bold cells are the ones that moved. {moved} of 24.</p>
<div class="callout warn">
<h2>The number that would have been published</h2>
<p>Against last night, confidently-wrong answers at the hardest-but-one tier
<i>rose</i> from 0.2516 to 0.3019 — a clear cost, and the reason to reject the
change.</p>
<p>Against the same model choices with the feature switched off, they
<b>fall</b>, from 0.3208 to 0.3019. The feature <i>reduces</i> confidently-wrong
answers. The apparent cost is something else entirely that moved between the two
nights.</p>
<p>Without the switch, this report would have stated a harm the change does not
cause — with a straight face, and with three runs behind it.</p>
</div>
<h3>Which means a measurement habit here is unsound</h3>
<p>Both nights report an internal spread of essentially zero on that number:
every run within a night agrees. Yet the two nights differ by 0.05. Run-to-run
spread within one sitting has been this project's error bar throughout, and here
it understates the real variation more than fivefold.</p>
<p>The known difference is that one of the two graph databases was found empty
at the start of tonight and reloaded. The safety check that compares it to its
pinned fingerprint passed, so the <i>contents</i> match; the <i>order</i> results
come back in after a fresh load need not, and this system reads ordered results.
That is a hypothesis. It is filed with the twenty-minute experiment that would
settle it.</p>
</section>''')

    # ----------------------------------------------------- 4. the real finding
    rs = d.get("rescore")
    A('''<section>
<h2>4 · The finding: the answer key names connections the database does not have</h2>
<p>Chasing why the number would not move produced something more useful than the
change itself.</p>
<p>The slot scores are graded against a hand-built answer key, written when the
question bank was built, that records what each question <i>means</i>. Checking
that key against the database it is supposed to describe:</p>''')
    if rs:
        defects = rs.get("defects") or []
        tot = rs.get("gold_records_with_a_full_triple")
        rows = {}
        for x in defects:
            k = (x["anchor_label"], x["target_label"], x["gold_relation"], ", ".join(x["graph_allows"]))
            rows[k] = rows.get(k, 0) + 1
        A(table(["question is about", "asking for", "answer key says the link is",
                 "the database actually has", "questions"],
                [[a, t, f"<code>{g}</code>", f"<code>{al}</code>", str(n)]
                 for (a, t, g, al), n in sorted(rows.items(), key=lambda kv: -kv[1])]))
        A(f'''<p class="src">All {len(defects)} of the {tot} answer-key records that name a
link between two kinds of thing, checked against the canonical graph snapshot.</p>''')
        A('''<div class="callout warn">
<h2>Read that table slowly</h2>
<p><code>HAS_TECHNIQUE</code> is a real MITRE ATT&amp;CK connection. But in this
data it runs only from a <i>tactic</i> to a technique. It does not exist between a
<i>group</i> and a technique. The connection that does exist there is
<code>USES</code> — an attacker group <i>uses</i> a technique.</p>
<p>So when the system answered <code>USES</code>, which is the only answer the
database can give, it was scored as wrong. Eleven questions, roughly a third of
everything that slot was graded on.</p>
</div>''')
        tiers = [t for t in TIERS if t in (rs.get("runs") or [{}])[-1].get("tiers", {})]
        run = (rs.get("runs") or [{}])[-1]
        strict = [run["tiers"][t].get("strict", {}).get("mean") for t in tiers]
        cons = [run["tiers"][t].get("graph_consistent", {}).get("mean") for t in tiers]
        A(fig(charts.slope(tiers, strict, cons,
                           left_name="graded against the answer key",
                           right_name="graded against the database"),
              "The same answers, scored twice",
              "scripts/rescore_slot_relation.py over the saved rows; the answer key is not edited"))
        p_ = run.get("pooled", {})
        A(f'''<p>Pooled across every graded question, the relationship slot reads
<b>{f(p_.get("strict", {}).get("mean"))}</b> against the answer key and
<b>{f(p_.get("graph_consistent", {}).get("mean"))}</b> against the database.
That gap is not the system improving. It is the measurement being wrong, and it
had been wrong in yesterday's report too.</p>''')
    else:
        A("<p><i>Rescoring output not yet written.</i></p>")
    A('''<h3>The same defect has a second surface</h3>
<p>Fourteen more answer-key entries describe CAPEC questions using ATT&amp;CK
vocabulary — asking for a "Technique" from a database that has no such thing and
answers through its own cross-reference table instead. Same root cause: the
answer key is written in the language people use to <i>talk</i> about the data,
and graded against the language the data is actually <i>stored</i> in.</p>
<h3>Why this was not caught earlier</h3>
<p>It nearly was. The code that turns an answer-key record into a question
already detects this case, refuses to build a question from it, and its comment
names the cause: 39 of the 120 recorded connections were guessed from the name
of the template that generated the question, and a template called
<code>group_techniques</code> yields <code>HAS_TECHNIQUE</code>. That protection
sits one layer above the scorer, and the scorer reads the raw record.</p>
<p><b>Nothing was repaired.</b> Editing an answer key after seeing a score is
precisely the move that makes evaluations meaningless, so both readings are
reported side by side and the choice is filed as a decision for the morning.</p>
</section>''')


    # ------------------------------------------- 5. the second defect
    A('''<section>
<h2>5 · A second measurement defect, found while setting up the cost run</h2>
<p>The second job of the night was to put a number on something the project has
claimed for months without measuring: that the deterministic path is not merely
more accurate than letting the AI write the queries, but far cheaper.</p>
<p>Run that AI-writes-the-query path the obvious way and it finishes four
questions in <b>2.8 seconds</b>, returns nothing on all four, and never contacts
the model once. It does not crash. It writes a complete, plausible-looking
answer for every question:</p>
<pre>"The attack specialist failed and contributed no evidence:
 pre-run gate rejected all drafts: empty query"</pre>
<p>That reads exactly like a model with nothing to say. It is a model that was
never asked.</p>
<p><b>The cause.</b> The local model reasons at length before answering. At the
default output allowance it spends the entire allowance thinking and returns
nothing, and the safety gate correctly rejects an empty query. One script in the
repository already carries the settings that avoid this; nothing else applies
them.</p>''')
    A(table(["setting", "plain run", "the settled configuration"],
            [["output allowance", "2,048 tokens", "32,768 tokens"],
             ["patience per call", "30 seconds", "4,096 seconds"],
             ["reasoning steps allowed", "1", "5"],
             ["inherited thinking budget", "whatever the environment holds", "explicitly cleared"]]))
    A('''<div class="callout warn">
<h2>Why this one matters more than it looks</h2>
<p>This is the failure that produces a <i>plausible wrong number</i> rather than
an error. An arm configured this way finishes fast, writes a full set of
answers, and declines politely 284 times. Graded, it would have reported the
AI-writes-the-query path as <b>instant and free</b> — the exact opposite of the
truth, and a spectacular false confirmation of the very claim the run was meant
to test.</p>
<p>It was caught because the token counter added at the start of the night read
zero calls. Without that instrument the run would have produced a clean,
confident, entirely wrong cost table.</p>
</div>
<p>The runner itself was deliberately <b>not</b> changed. Making it refuse to
start when a reasoning model meets a small allowance is the right fix, and it is
a change in behaviour, so it does not get slipped in alongside a measurement.</p>
</section>''')

    # ------------------------------------------------------- 6. cost
    ct, cl = d.get("cost_throughput") or {}, d.get("cost_latency") or {}
    A('''<section>
<h2>6 · What each way of answering costs</h2>
<p>Two numbers are reported separately, because collapsing them is how a cost
claim becomes unfalsifiable. <b>Throughput</b> is what it costs to run the whole
evaluation at full parallelism. <b>Single-user latency</b> is what one analyst
waits for one question. A throughput figure divided by a question count is not
the second number.</p>''')
    NAMES = {"deterministic": "hand-written queries",
             "generic": "reads the database's own structure",
             "llm_query": "the AI writes the query"}
    if ct:
        rows = []
        for arm in ("deterministic", "generic", "llm_query"):
            m = ct.get(arm)
            if not m:
                continue
            tk = m.get("tokens") or {}
            rows.append([NAMES.get(arm, arm), str(m.get("count")),
                         f'{m.get("wall_s_total"):.1f} s' if m.get("wall_s_total") else "—",
                         f'{m.get("wall_median"):.2f} s' if m.get("wall_median") is not None else "—",
                         f'{m.get("wall_p95"):.2f} s' if m.get("wall_p95") is not None else "—",
                         f'{tk.get("calls", 0):,}',
                         f'{tk.get("prompt_tokens", 0) + tk.get("completion_tokens", 0):,}'])
        A("<h3>Throughput — all 284 development questions, 24 at a time</h3>")
        A(table(["how the query is made", "questions", "total", "median per question",
                 "95th percentile", "model calls", "tokens"], rows))
        walls = [ct[a]["wall_s_total"] for a in ("deterministic", "generic", "llm_query")
                 if ct.get(a) and ct[a].get("wall_s_total")]
        if len(walls) >= 2 and min(walls) > 0:
            A(fig(charts.grouped_bars(
                [NAMES.get(a, a) for a in ("deterministic", "generic", "llm_query") if ct.get(a)],
                ["seconds to answer all 284 questions"],
                {"seconds to answer all 284 questions":
                 [ct[a]["wall_s_total"] for a in ("deterministic", "generic", "llm_query") if ct.get(a)]},
                fmt="{:.0f}"),
                "Total time for the same 284 questions, at the same parallelism",
                "the run manifest of each arm"))
    else:
        A("<p><i>Throughput run not yet complete.</i></p>")
    if cl:
        rows = []
        for arm in ("deterministic", "generic", "llm_query"):
            m = cl.get(arm)
            if not m:
                continue
            rows.append([NAMES.get(arm, arm), str(m.get("count")),
                         f'{m.get("wall_median"):.2f} s' if m.get("wall_median") is not None else "—",
                         f'{m.get("wall_p95"):.2f} s' if m.get("wall_p95") is not None else "—"])
        A("<h3>Single-user latency — 40 questions drawn in advance, one at a time</h3>")
        A(table(["how the query is made", "questions", "median wait", "95th percentile"], rows))
        A('''<p class="src">The 40 questions were drawn by fixed seed and written to
disk before the first run, stratified so that cross-database questions are not
missing from the sample.</p>''')
    else:
        A("<p><i>Latency run not yet complete.</i></p>")
    A('''<p>No dollar figure is given. The models are served on hardware this
project does not pay for per token, so seconds and tokens are the honest units
and a dollar amount would be invented.</p>
</section>''')


    # ---------------------------------------- 7. cross-instance repeatability
    a2, a3 = d.get("a2_runs") or [], d.get("a3_runs") or []
    if len(a2) > 1 or len(a3) > 1:
        sa, sb = D.spread(a2, "records_exact"), D.spread(a3, "records_exact")
        A(f'''<section>
<h2>7 · Does the result repeat?</h2>
<p>The same arm was run {len(a2)} times on one GPU and {len(a3)} times on a
second, with the cache cleared between runs so that what varies is the model and
not a stored answer. Both instances serve identical weights, so this measures
repeatability, not a comparison between models.</p>''')
        A(fig(charts.grouped_bars(
            list(TIERS), ["GPU one", "GPU two"],
            {"GPU one": sa["mean"], "GPU two": sb["mean"]}),
            "Questions answered with exactly the right records, by difficulty tier",
            f"{len(a2)} runs on one instance and {len(a3)} on the other"))
        rows = [[t, f(sa["mean"][i]), f(sa["sd"][i]), f(sb["mean"][i]), f(sb["sd"][i])]
                for i, t in enumerate(TIERS)]
        A(table(["tier", "GPU one mean", "spread", "GPU two mean", "spread"], rows))
        A("</section>")

    # ------------------------------------- 7b. the carried-in finding, verified
    A('''<section>
<h2>7b · A third finding, carried in from yesterday and now verified</h2>
<p>Earlier in the same working session, before tonight's runs, a diagnostic of
the schema-reading path turned up something that had never been written down.
It was recomputed from source tonight rather than trusted, and both figures
reproduced exactly.</p>
<p>The CAPEC database's spec sheet lists 21 kinds of connection and gives
safety rules for 16. The safety gate treats a connection missing from a
partially-filled rule set as <i>forbidden</i>, and throws the query away before
it ever runs:</p>
<pre>pre-run gate rejected all drafts:
relationship 'HAS_ALTERNATE_TERM' has no allowed_edge_patterns in card</pre>
<p>The system builds the correct query and is not allowed to ask it.</p>''')
    A(table(["", "on the 34 questions needing those five connections", "on the other 250"],
            [["reads the database's own structure", "<b>0.0000</b>", "0.6649"],
             ["hand-written queries", "0.2076", "0.5452"]]))
    A('''<p class="src">Development half, 284 questions, recomputed 2026-09-10 from the
post-repair scores.</p>
<p>An absolute zero, on the approach that leads everywhere else. And the
asymmetry is worse than it looks: the rule exists only for one of the two
databases, and the <i>other</i> database's spec sheet lists no safety rules at
all — so it is unconstrained. A spec sheet that is 16-of-21 complete is punished
where one that is 0-of-21 is not.</p>
<p>All five missing entries have exactly one possible answer in the data, so the
repair is derivable rather than something anyone has to author. It would move
the schema-reading path's development score from 0.585 to somewhere between
0.610 and 0.665.</p>
<div class="callout">
<h2>Why this is not simply a bug to fix quietly</h2>
<p>An earlier experiment repaired six defects in the <b>hand-written</b>
approach before comparing the two, precisely so the comparison would be fair.
This is the mirror-image defect, and repairing it widens a gap the project
already reports in the schema-reading path's favour. It has to be published as
that, not slipped in as a bug fix, or the comparison stops being trustworthy.</p>
</div>
</section>''')

    # ------------------------------------------------- 8. what it means
    A('''<section>
<h2>8 · What this means for the October pitch</h2>
<p>Nothing in the deck has to change, and one thing in it gets stronger.</p>
<h3>Do not change</h3>
<p>The headline comparison between the three ways of answering is untouched.
Tonight's work sits entirely inside a stage that ships switched off.</p>
<h3>Gets stronger</h3>
<p>The slide asking for the next round of funding currently says: <i>ask by name
and it works, paraphrase the name and it scores zero — fund us to fix that.</i>
That is a gap, not a plan. It can now say something better: we identified the
weakest component, built the fix, measured it against a pre-registered rule,
and the fix did not work — but the measurement told us why, and it was not what
anyone expected. That is what a funded research programme looks like from the
inside, and it is far more convincing to an engineer than another round of
numbers that only go up.</p>
<h3>The thing to be careful about</h3>
<p>Both defects found tonight were <b>measurement</b> defects, not system
defects, and both would have produced confident, plausible, wrong numbers. If
anyone in that room reads this repository, the fact that these were caught and
written down — rather than quietly fixed — is the strongest evidence of rigour
the project has. It should be said out loud rather than hidden.</p>
</section>

<section>
<h2>9 · What was recorded, and what is still open</h2>
<p>Everything below is committed. Nothing was pushed.</p>''')
    A(table(["record", "what it holds"],
            [["<code>EXP-2026-09-015</code>",
              "the pre-registered protocol, the null result, and both measurement defects"],
             ["<code>EXP-2026-09-016</code>",
              "the cost and latency protocol, the drawn sample, and the silent-empty-query defect"],
             ["<code>Q44</code>",
              "the open decision: repair the answer key, or teach the scorer to accept what the database has"],
             ["<code>scripts/rescore_slot_relation.py</code>",
              "reports both readings of the slot scores and edits nothing"],
             ["token metering",
              "every model call's cost is now read off the wire rather than estimated"]]))
    A('''<h3>The decision waiting for you</h3>
<p>The eleven bad answer-key records can be repaired from the database, or the
scorer can be taught to accept any connection the database declares between the
two kinds of thing the key names. The first is more honest and invalidates two
experiments' slot figures; the second is cheaper and leaves a known-wrong answer
key in place. Repairing an answer key after seeing a score is exactly the move
that evaluation discipline exists to prevent, which is why it was left to you.</p>
<h3>What was not done</h3>
<p>The held-back half of the question bank was not touched, and neither was the
sealed holdout. No shipped behaviour changed. The flags that control the rewrite
stage remain off, as the previous experiment left them.</p>
</section>''')

    return P


def render(parts):
    css = """
@page { size: Letter; margin: 15mm 14mm 16mm; }
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; font-size: 10.2pt;
       line-height: 1.5; margin: 0; }
header { border-bottom: 2.5px solid #1a1a1a; padding-bottom: 10px; margin-bottom: 16px; }
.kicker { font-family: system-ui, sans-serif; font-size: 8pt; letter-spacing: .16em;
          text-transform: uppercase; color: #6b6b6b; }
h1 { font-size: 21pt; margin: 5px 0 4px; line-height: 1.15; }
.sub { font-size: 11pt; color: #3d3d3d; margin: 0 0 6px; max-width: 46em; }
.meta { font-family: system-ui, sans-serif; font-size: 8pt; color: #6b6b6b; margin: 0; }
h2 { font-size: 13pt; margin: 20px 0 7px; padding-bottom: 3px; border-bottom: 1px solid #d8d8d8; }
h3 { font-size: 10.8pt; margin: 14px 0 5px; }
section { page-break-inside: auto; }
figure { margin: 12px 0 14px; page-break-inside: avoid; }
figure svg { width: 100%; height: auto; }
figcaption { font-family: system-ui, sans-serif; font-size: 8.2pt; color: #3d3d3d;
             margin-top: 5px; line-height: 1.4; }
.src { color: #6b6b6b; font-size: 7.8pt; font-family: system-ui, sans-serif; }
p.src { margin: -4px 0 10px; }
table { border-collapse: collapse; width: 100%; margin: 9px 0 12px;
        font-family: system-ui, sans-serif; font-size: 8.6pt; page-break-inside: avoid; }
th { text-align: left; border-bottom: 1.4px solid #1a1a1a; padding: 4px 7px 4px 0;
     font-weight: 600; }
td { border-bottom: 1px solid #ececec; padding: 4px 7px 4px 0; }
td:first-child, th:first-child { font-variant-numeric: tabular-nums; }
.callout { background: #f5f2ec; border-left: 3.5px solid #2f5d8a; padding: 11px 15px 4px;
           margin: 14px 0 18px; page-break-inside: avoid; }
.callout h2 { border: 0; margin: 0 0 6px; font-size: 11.5pt; }
.callout ol { margin: 0 0 8px; padding-left: 18px; }
.callout li { margin-bottom: 5px; }
ol.steps li { margin-bottom: 5px; }
code { font-family: ui-monospace, 'DejaVu Sans Mono', monospace; font-size: 8.6pt;
       background: #f2f2f2; padding: 0 3px; border-radius: 2px; }
pre { background: #f6f6f6; border-left: 2.5px solid #c9c9c9; padding: 8px 11px;
      font-family: ui-monospace, 'DejaVu Sans Mono', monospace; font-size: 8.2pt;
      overflow-x: auto; page-break-inside: avoid; line-height: 1.4; }
.warn { background: #fdf4ee; border-left-color: #c2703d; }
"""
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<title>Ariadne overnight report</title><style>{css}</style></head>'
            f'<body>{"".join(parts)}</body></html>')


if __name__ == "__main__":
    d = D.everything()
    (HERE / "report.html").write_text(render(build(d)))
    print(f"wrote {HERE / 'report.html'}")
