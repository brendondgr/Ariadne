% Where this work can be published
% And what stands in the way
% Ariadne project · assessment written 2026-09-06

## What this document is

This document answers one question: given what has actually been measured and
written down, which kind of publication is this work ready for, and what is the
shortest honest path to it.

It is written for someone who is not a researcher in this field. Terms are
explained where they first appear. Every judgement points at a specific file or
experiment in the project's records; those pointers sit in a narrow column on the
right and are expanded in the appendix, so they stay out of the way of the
reading.

**What it is scored against.** A separate, web-connected agent searched the public
calls for papers on 2026-09-06 and produced a report naming real venues and, for
each of four levels of publication, a checklist of 13 to 15 things a paper must be
able to answer yes to. That report is `docs/research/paper/venue-report-2026-09.md`.
This document scores the project against those checklists, item by item, using
only what is written in the project's own records.

### How to read the scores

Those checklists are written about a **finished paper**. No paper exists yet: one
of eleven planned sections is drafted. So an item like "does the paper say X" is
scored on whether the **records contain what it would take to say X truthfully**.

| Score | Meaning |
|---|---|
| MET | The evidence is there. Writing the sentence is mechanical. |
| PARTIAL | Some of it is there. The entry says exactly what is missing. |
| UNMET | Nothing supports it. New work is needed. |
| UNKNOWN | The records cannot answer it, usually because no draft and no venue exist yet. |

Each gap is then tagged by what it would cost to close.

- **WRITING** — prose only, nothing new to run.
- **PAPERWORK** — mechanical and low risk: a permanent web link for the code, a file filled in, a number reconciled.
- **EXPERIMENT** — needs machine time.
- **OUT OF REACH** — cannot be fixed within this project's current resources. Two items are.

The venue report marks some items as **blocking**, meaning failing that one item
alone sinks the paper at that level. Each tier section reports how many blocking
items are not yet met.

### Two terms used throughout

The **held-out set** is 288 questions that were locked away unopened while the
system was being fixed, then used once, to check that the results were a property
of the system rather than of the questions it had been tuned on.

A **marker** is a second language model that reads each answer and scores it.
Every accuracy figure in this project came from one, and no person has ever
checked an answer.

---

## The answer, in one paragraph

Aim at a **journal**, specifically the Semantic Web Journal, and expect to submit
in **two to three months**. The evidence already clears a workshop bar today, but
nothing worth submitting to is open. A solid mid-tier conference is genuinely
reachable and would need roughly the same amount of writing plus one modest
re-run. The top tier is not reachable, and one of the things blocking it — a
person, rather than a machine, checking whether the answers are any good — was
formally set aside months ago because nobody with the right background is
available to do it. That decision, not the missing comparison against someone
else's system, is the real ceiling.

### Summary

| Level | Verdict | Biggest single blocker | Time to close |
|---|---|---|---|
| Workshop | Clears the bar today, but there is nothing good to submit to | The one open workshop is off-topic and would use up the work's unpublished status | Ready now |
| Journal *(recommended)* | Reachable, and the right target | The study of whether the automatic marker can be trusted is measured but never written up | 2–3 months |
| Mid-tier conference | Reachable, not today | One of the three system versions has never been run more than once | 2–3 months, including one re-run |
| Top tier | Not ready, and one blocker is out of reach | No person has ever checked a single answer | 6 months at best; one item may never close |

### Scores at a glance

| Level | Items | MET | PARTIAL | UNMET | UNKNOWN | Blocking items not yet met |
|---|---|---|---|---|---|---|
| Workshop | 13 | 7 | 2 | 1 | 2 | 4 of 11 |
| Journal | 15 | 5 | 8 | 1 | 1 | 8 of 13 |
| Mid-tier conference | 15 | 6 | 6 | 2 | 1 | 7 of 12 |
| Top tier | 15 | 3 | 6 | 4 | 2 | 10 of 11 |

---

## Eight things the records say that the venue brief did not

The brief handed to the venue searcher was written from memory. Six of the eight
corrections below make the project's position **worse**; two make it **better**.
They matter because the venue report's advice was calculated from that brief.

### 1. There is no continuous integration

The brief says automated checks make sure every number in the paper points back to
an experiment, and that stray numbers fail the build. **There are no automated
checks at all.** The folder that would hold them does not exist. The checker that
does exist verifies that experiment folders are structurally complete; it never
opens the paper and never looks at a number.

This is a reproducibility claim that would not survive being checked, and the
project's own to-do list repeats it. *Source: A, B.*

### 2. There is outside material, and it is invisible

The brief says there is no comparison against anything the authors did not write.
In fact **182 questions came from two published outside question sets**, used word
for word, neither written with any sight of this code.

This is the project's only outside anchor, it already exists, and it satisfies the
top tier's requirement for outside material outright. It appears in none of the
project's own summaries. *Source: C.*

### 3. One experiment is kept as wrong, not six

The brief says six experiments are kept on record because an earlier measurement
was found to be wrong. **One** is marked that way. A second is superseded by a link
but is still labelled as current.

The "we keep our mistakes" credibility asset is real but a sixth of the claimed
size. Overstating it in a paper would be both checkable and damaging.
*Source: D.*

### 4. The best result in the project is invisible in the record

The brief says two independent marking models graded the held-out questions, 3,456
judgements in total. **This is true, and it is the strongest evidence the project
has** — but it lives in a raw data file. The experiment that produced it is still
marked "planned", its write-up is an untouched blank template, and the previous
experiment's own results page still states that the second marker never graded one
of the three system versions.

So the record currently contradicts its own best result. *Source: E, F.*

### 5. Withdrawn figures are still in circulation

The brief says merging the two sources instead of keeping them separate costs
-0.0334 and exactly 0.0000. Those figures are **formally withdrawn on their own
results page**; a re-grading by a named model over eight passes gives **-0.0587 and
-0.0520**.

The withdrawn pair was quoted to the venue searcher and appears in its reasoning.
It must not appear in a paper. *Source: G.*

### 6. The rephrasing cliff is steeper than described

The brief describes five levels of rephrasing declining 1.0000, 0.4667, 0.0990,
0.0000. There are **seven** levels, and 1.0000 is the control — the original
questions re-run. The actual decline is **0.4667, 0.4250, 0.0990, 0.0000, 0.0000**.

Performance is already halved at the first rephrasing, not at the second.
*Source: H.*

### 7. Almost nothing was run twice

The brief says some older experiments were run only once. **37 of 41 were.** Of the
four that were not, all four repeat the *marking*, not the system. **No experiment
anywhere runs the system three times with the randomness recorded.**

This is a blocking requirement at the top tier and half-blocking at mid-tier. It is
worse than described. *Source: I.*

### 8. Human checking is a boundary, not a gap

The brief says there is no human evaluation. Correct, and stronger than stated: it
was formally **closed as "will not do"**, because the only available annotator does
not have the security background the job needs.

That converts a gap into a boundary, and it is the single reason the top tier is
out of reach. *Source: J.*

### A note on the venue report as a source

It was treated as data, not as instructions. It contains one line addressed to
whoever scores against it, telling the reader which sections to use. That
instruction was not followed because it said so; it happens to match what this
assessment was asked to do independently. Nothing else in the report attempted to
direct behaviour.

Its dates are its own: 15 venue entries were checked against official calls, 11
could not be and are marked unverified — including the EDBT deadline, which came
from a mailing-list copy of the call rather than the conference site.

### Does the project's own validation pass?

**Yes. 41 experiments, no failures.**

One honest caveat about how it was run. The documented command, `make
validate-research`, failed in this environment — not because anything is wrong with
the record, but because the command fetches a specific version of Python over the
network and the network is restricted here. The underlying checker was run directly
against the same 41 folders and reported `research record OK — 41 experiment(s)
validated`.

What that check covers is narrower than it sounds: files present, manifests valid,
completed experiments carrying results, figures matching their scripts, data
pointers carrying a fingerprint, and claim references resolving. It does not read
the paper and does not look at numbers.

---

## Workshop level

> **Verdict: the work would be accepted at this level today, and submitting it
> anywhere currently open would be a mistake.**

Every requirement here is either met or trivially closable. The record is unusually
candid, states how many times each thing was run, and says plainly that no person
ever graded an answer — which is exactly what a workshop asks for.

| What the checklist asks | Score | Why | Src |
|---|---|---|---|
| One clear claim someone could disagree with | MET | Hand-written query templates do not hold the system's accuracy | K |
| Incompleteness stated up front, not hidden | MET | A whole file exists for unresolved questions; a second lists limitations that must appear | L, M |
| At least one number with a sample size | MET | 0.6546 against 0.4862, on 288 questions | E |
| How many times each number was run, stated even when once | MET | Printed on every row of the experiment index | N |
| Says which numbers are one model marking another's work | MET | Stated in the plainest possible terms | J |
| Names exactly the one thing that differs between compared versions | MET | Every comparison in the record does this deliberately | G, O |
| Says in one sentence that no outside system was run | UNMET | This sentence exists nowhere in the project | P |
| Fits the page limit | UNKNOWN | No draft, no chosen workshop | Q |
| Limitations section present where required | PARTIAL | Material exists as seven bullet points; the section does not | M |
| States why it fits *this* workshop | UNKNOWN | No workshop chosen | Q |
| A code or data link | PARTIAL | Licensed and ready, but not yet public | R |
| Not submitted anywhere else at the same time | MET | Nothing has been submitted anywhere | S |
| Willing to spend the work's unpublished status here | *Your decision* | The one workshop with a live deadline publishes permanently | Q |

**11 of these 13 items are blocking. Four are not yet met**, and three of those four
resolve the moment a workshop is chosen.

### Gaps, cheapest first

1. **WRITING** — one sentence saying no outside system was run, and why. *One hour.*
2. **WRITING** — turn the seven limitation bullets into a section. *One day.*
3. **Decision** — the only workshop with an open deadline is eight days away, themed on a different subject, and publishes permanently. Submitting there spends the work's unpublished status on a venue it does not fit. **Recommend against.**

---

## Journal level — the recommendation

> **Verdict: this is the right target, the evidence largely supports it, and the two
> things standing in the way are paperwork rather than science.**

Journals in this area judge whether the claims match the evidence, not whether the
result is exciting. Where a claim overreaches, the remedy is to narrow the claim
rather than reject the paper. That suits a project whose records are built around
exactly that discipline — the claims file is full of instructions like "never quote
this number without that one beside it."

| What the checklist asks | Score | Why | Src |
|---|---|---|---|
| Original and unpublished, overlaps declared | MET | Nothing has been submitted anywhere | S |
| Someone in the audience would act on it, and the paper can name who | MET | Federated knowledge-graph and question-answering researchers | T |
| Nulls stated as "we could not detect a difference this large", not "there is no difference" | PARTIAL | Done well, but the merging result must be restated against its own withdrawal | G |
| Every claim in the summary traceable to a specific experiment | PARTIAL | The rule exists in four places and is enforced nowhere; the paper outline carries two figures with no experiment reference | A, B, F |
| Claims narrowed where the evidence does not stretch | PARTIAL | Done rigorously, but one claim's status still reads "supported" while the warning above it says otherwise | U |
| Run counts, randomness settings and marker identity disclosed per experiment | MET | Every manifest carries all three; two understate their own run count and need a note | I, V |
| **The marker itself characterised: how it fails, the smallest difference it can see, and which results fall inside that limit** | PARTIAL | **Measured, and striking. The write-up does not exist.** See below | E, F |
| A stated boundary: one subject area, three schemas, two query languages | MET | Stated explicitly and repeatedly | E, W |
| Absence of outside baselines stated, claims narrowed accordingly | PARTIAL | The narrowing culture is there; the sentence is not written | P |
| Related work complete enough to find the outside systems | MET | Around 90 to 100 works across twelve areas, closest competitor named | T |
| As long as the evidence requires and no longer | UNKNOWN | No draft | Q |
| Superseded experiments described | PARTIAL | Real, but one experiment rather than six | D |
| Code and records under a permanent link, licence and attribution stated | PARTIAL | Licence shipped. No permanent link, and the copyright holder is unconfirmed | R |
| Reproducibility checklist where the journal demands one | UNMET | Required only at one journal, which is not the recommendation | Q |
| Free of the "just applies known techniques" reading | PARTIAL | The strongest general-interest finding is the marker study, the least written-up thing in the record | F, T |

**13 of these 15 items are blocking. Eight are not yet met** — but every one of the
eight is closed by writing or paperwork, not by an experiment. That is what makes
this tier the recommendation.

### The one thing worth doing first

The project measured whether its own automatic marker can be trusted, and the
answer is sharper than the brief suggested. Three locally available models were
each given the same 60 frozen answers in three quality bands:

| Marking model | Distinct scores it could produce on good answers | Usable near the top? |
|---|---|---|
| A 31-billion model | 1 — it scored every good answer exactly 1.0 | No |
| A 26-billion model | 2 — only 0.5 or 1.0, and it **reversed** the ranking of mediocre and good answers | No |
| The 27-billion model behind the headline results | 3 near the top, 15 across all bands | Yes |

The test for "usable" was written down before any marking happened, so it cannot
have been tuned to the answer. The second model's reversal was not even anticipated
by that test — it is a second, independent disqualification, caught only because
someone looked.

This is the most transferable result the project has. It applies to anyone using a
language model to score another language model's work, whatever system they built.
It is also the reason one of the project's close-call findings rests on a single
marker rather than two.

**And it is recorded as "planned", with a blank template where its write-up should
be, linked to no claim, and shown as a placeholder in the experiment index.**
Filling that in is a day of work, and it converts an embarrassment into the paper's
lead contribution.

### Gaps, cheapest first

1. **PAPERWORK** — complete the marker-calibration record: fill the manifest, write the results from the data already on disk, link it to the claims it moves, list its data files with fingerprints. *One day. Highest-value item in this document.*
2. **PAPERWORK** — reconcile the held-out experiment. Its results page says the second marker never graded one of the three versions; a data file in the same folder shows it later did, across both marking positions, completing all 3,456 judgements. Decide which experiment owns those numbers and make the two agree. *One day.*
3. **PAPERWORK** — restate the merging comparison using the re-graded figures, not the withdrawn ones. *Half a day.*
4. **PAPERWORK** — stop claiming automated enforcement that does not exist. Either build the check or delete the claim from the to-do list and the working instructions. *Half a day either way.*
5. **PAPERWORK** — mint a permanent archive link for the code and records. Blocked on a real question: the copyright line names an institution that has not signed off, and the funding terms have not been read for release conditions. *Half a day of work; unknown waiting time. Start it now.*
6. **WRITING** — the sentence about outside systems, and the narrowing that goes with it. *One day.*
7. **WRITING** — ten of eleven sections. *Four to six weeks.*

> **The real risk on this path is not review. It is finishing.** A journal with no
> page limit and no deadline is exactly the condition under which a paper with
> eleven sections and one of them drafted stays unfinished. If you take this route,
> set your own deadline.

---

## Mid-tier conference level

> **Verdict: reachable, and the venue report is slightly too pessimistic about it —
> but not today, and it needs one thing that is not writing.**

The report concluded that a full mid-tier paper is "not reliably reachable" on
writing alone. Reading the record, two of its three reasons look softer than
stated, and one is real.

| What the checklist asks | Score | Why | Src |
|---|---|---|---|
| A finding a reader could act on without using your code | MET | Templates buy precision on the shapes they were written for, and cost coverage | K |
| Names the single thing each comparison changes | MET | Done deliberately throughout | G, O |
| Negative results framed as the contribution | PARTIAL | The outline does this; the practitioner advice is half written | X |
| Every headline number from at least two independent runs, single runs labelled | PARTIAL | **Narrower than it looks.** Two of three versions contain no language model and produce byte-identical output every time; the third does not, and has never been repeated | I, Y |
| Test set of at least 200 items, origin stated in the main text | MET | 288 questions, sealed with a fingerprint, predictions written down beforehand | E |
| Ranges on every claimed difference, and ranges including zero called unestablished | MET | The record already mandates this wording | U |
| Two independent marking models, disagreement reported not averaged away | PARTIAL | Fully measured; not yet written into the record properly | E, F |
| At least one countable measure no language model judged | MET | Merging rewrote 1,083 of 9,138 stored items; keeping the sources separate rewrote none | Z |
| At least one outside anchor for the absolute scores | PARTIAL | The outside question sets exist and are used; their own published scores are not quoted alongside | C |
| Says in the main text that no outside system was run, and why | UNMET | Not written | P |
| Related work covering every field the work touches | PARTIAL | Coverage is there; venue-specific citations wait on a venue | T |
| Limitations naming each deliberately-unfixed scoring fault and which way it bends the result | PARTIAL | Both named, both said to raise scores, only one bounded (worth 0.185 where measured) | E, M |
| Supplemental material under a permanent link | UNMET | No permanent link | R |
| Properly anonymous and inside the page limit | UNKNOWN | No draft | Q |
| No headline sentence asserting a result whose range includes zero | MET | The record already forbids it in writing, and the outline says not to lead with that result | U, X |

**12 of these 15 items are blocking. Seven are not yet met.** Six are writing or
paperwork; one needs machine time.

### Gaps, cheapest first

1. **WRITING** — the outside-systems sentence, the practitioner advice, the limitations section. *One week.*
2. **PAPERWORK** — quote the published scores of the two outside question sets beside your own, giving the absolute numbers an anchor. *One to two days.* A reviewer may still want a running system; that would be an experiment.
3. **PAPERWORK** — permanent archive link, as above.
4. **EXPERIMENT** — run the one version that contains a language model three times with the randomness recorded, and re-derive its ranges. This version has already been run at this size twice, so it is more of the same rather than new engineering. *Days of machine time, not weeks — treat that as an estimate, not a measured figure.*
5. **WRITING** — ten of eleven sections, compressed to a page limit. *Four to six weeks*, and the project's own to-do list judges that the record holds more method than 8 or 9 pages can carry.

---

## Top tier

> **We are not ready, and one of the blockers cannot be closed with the people and
> resources this project has.**

Three blocking requirements are unmet outright and two more cannot be answered
without a draft.

| What the checklist asks | Score | Why | Src |
|---|---|---|---|
| Claim new to the published literature, closest rival named and the difference stated | PARTIAL | Reading done. But the record now says two published systems already compared keeping sources separate against merging them, and forbids writing that no one has | T, AA |
| The finding transfers to systems the authors did not build | PARTIAL | Tested across three schemas and two query languages, but one codebase | K, W |
| A null result has at least two published targets it contradicts | MET | Named in the related-work file | T, AA |
| At least one comparison on material the authors did not write | MET | 182 questions from two published outside sets, used verbatim | C |
| Every headline number from at least three independent runs, randomness recorded, spread reported | UNMET | No experiment anywhere does this | I |
| Reproduced in two subject areas, or two further schema-and-language pairs | PARTIAL | One extra schema, not two; one subject area | W |
| Ranges or a named test on every difference; zero-crossing ranges called unestablished | PARTIAL | True of the recent work; several older manifests record no statistical test at all | U |
| **A person checking the answers, or the marker validated against human scores with an agreement figure** | UNMET | **Out of reach.** Closed as "will not do": the only available annotator lacks the security background, and a poor agreement figure was judged worse than none | J |
| Held-out set used exactly once, size stated, no tuning informed by it | MET | Locked with a fingerprint, predictions written down beforehand, spent once | E |
| At least one baseline that is a published outside system | UNMET | None run; the closest candidate is named in the related-work file but was never executed | P, T |
| Three closest published systems named, each run or with a stated reason it could not be | PARTIAL | Named. No reason written for any of them | P, T |
| Fits the page limit | UNKNOWN | No draft | Q |
| Limitations naming every threat, with the direction and an upper bound for each | PARTIAL | Direction stated for both scoring faults; upper bound for only one | E, M |
| Permanent archive link at submission | UNMET | None | R |
| Survives the automatic checks that reject a paper before anyone reads it, including the venue's rules on what is in scope | UNKNOWN | Two of the report's top-tier venues carry scope rules this work would be tested hard against | Q |

**11 of these 15 items are blocking. Ten are not yet met.** Only one blocking item
at this tier is currently satisfied.

### Gaps, most expensive last

1. **WRITING** — reasons why each named competitor was not run. *Two days.*
2. **PAPERWORK** — permanent archive link. *Half a day, plus sign-off.*
3. **EXPERIMENT** — three recorded runs of the language-model version. *Days.*
4. **EXPERIMENT** — run at least one published outside system on the same 288 questions with the same marking procedure. *Weeks*, and it is the reason a reviewer will give.
5. **EXPERIMENT** — a second subject area: a different pair of graphs with different schemas, and the whole comparison repeated. *Months.*
6. **EXPERIMENT** — a check for whether the models have memorised the source taxonomies, by swapping in invented identifiers. Not run, never asked. *Weeks.*
7. **OUT OF REACH** — human checking of at least 200 answers by two or more qualified annotators, with an agreement figure. This is not a scheduling problem; the project has recorded that it does not have the people. Closing it needs money or a collaborator.
8. **OUT OF REACH for now** — a question set written by someone outside the project *and phrased by a human*. A search in August found no human-written question set for these taxonomies anywhere public; the two outside sets that were used are machine-generated.

### Where this assessment disagrees with the venue report

The report argues the fatal top-tier objection is not the missing outside system
but the uncharacterised marker. **The record supports that, and strengthens it.**
The marker's failure is not a suspicion: it is measured, and one of the three models
tested actively reverses the ordering of mediocre and good answers in precisely the
score range where all three system versions sit.

But the report treats this as unanswerable. It is not quite. The project *has* a
marker that passes its own pre-written test, and it has the full two-marker
comparison across the whole held-out set — which the report was told did not exist
for one of the three versions. Written up honestly, that is a considerably better
position than "the instrument is uncharacterised". It still does not reach the top
tier, because no human ever checked anything, but it is the difference between a
validity failure and a stated limit.

**One place the report leans on something the record forbids.** Its main argument
for the Semantic Web Journal is that its reviewers will understand why a third graph
"that could not legally be copied" was loaded beside the other two. The record is
explicit that this was never measured and must not be claimed: the contractual
argument is a motivation, the identity records are synthetic, and what was actually
demonstrated is narrower — that keeping the sources separate asked that graph for
nothing. The venue is still the right choice. That particular sentence cannot be
written.

---

## Recommendation

> **Target the Semantic Web Journal. Submit in two to three months.**

The shortest honest path, in order:

1. **Week 1 — paperwork.** Write up the marker-calibration experiment from the data already on disk. Reconcile the held-out experiment's two-marker numbers. Restate the merging comparison against its own withdrawal. Delete or build the automated check that is currently claimed and absent. Start the copyright sign-off, because it has a waiting time you do not control.
2. **Weeks 2–7 — writing.** Ten sections. Lead with the marker study: it is the most original thing here and needs no outside system to be interesting. Do not lead with the templates-beat-a-model-writing-queries result — it is positive under both markers and solid under only one, and the project's own outline already says so.
3. **Week 8 — the honest sentences.** Why no outside system was run. What machine-only marking means. Both scoring faults, with which way they bend the result.
4. **In parallel, if you want the mid-tier conference open as an alternative** — three recorded runs of the language-model version. That single re-run is most of what separates the two paths.

Do not spend the work's unpublished status on the one workshop that is open. Do not
attempt the top tier this cycle; the item blocking it is a resourcing question, not
a writing one, and pretending otherwise costs a review round to find out.

---

## Appendix — where each judgement comes from

| Key | Source |
|---|---|
| A | `utils/research_record/validate.py` — the eight conditions it checks. `.github/` does not exist |
| B | `docs/research/paper/checklists/conference-full-paper.md` line 169, "enforced by CI"; `docs/research/AGENT_INSTRUCTIONS.md` principle 3 |
| C | `EXP-2026-08-010-external-validation` — manifest `data.name`: "CTIBench cti-ate (60 rows) and AttackQA enumerative subset", `n_examples: 182`, `data.split`: "external — neither benchmark was authored with sight of this codebase". Both are machine-generated; no human-written question set for these taxonomies was found to exist |
| D | `EXP-2026-07-010` is the only manifest with `status: superseded`. `EXP-2026-09-005` supersedes `EXP-2026-09-002`, which remains `status: complete` |
| E | `EXP-2026-09-007-holdout-spend` — manifest and `RESULTS.md` |
| F | `EXP-2026-09-008-grader-calibration` — `PROTOCOL.md`, `data/ceiling-resolution.json`, `data/state-*.json`. Manifest is `status: planned`, with a template title and `supports_claims: []` |
| G | `EXP-2026-08-009-merged-graph-counterfactual` — manifest metrics, and `RESULTS.md` amendment A-1 of 2026-08-31 |
| H | `EXP-2026-08-020-variant-robustness` — `RESULTS.md`, tiers T0 to T6 |
| I | All 41 manifests, fields `n_runs` and `seeds`. `EXP-2026-08-021` (5) and `EXP-2026-08-022` (4) count grading sessions; `EXP-2026-09-006` and `EXP-2026-09-007` (2 each) count grading positions. `EXP-2026-08-018` and `EXP-2026-08-019` ran three system repeats but record `n_runs: 1` |
| J | `docs/research/OPEN_QUESTIONS.md` — Q6, closed as "will not do" on 2026-08-23, and the "no human ever graded an answer" statement |
| K | `docs/research/CLAIMS.md` — C-023, status `partial` |
| L | `docs/research/OPEN_QUESTIONS.md` |
| M | `docs/research/paper/checklists/conference-full-paper.md` section 4 — seven unticked limitation items |
| N | `docs/research/INDEX.md` — every row prints its run count |
| O | `EXP-2026-09-005-post-repair-arm-comparison` |
| P | Absent from the repository. Nearest statement of the obligation: `docs/research/paper/OUTLINE.md` lines 104–107 |
| Q | No draft exists; `docs/research/paper/sections/` contains one file of eleven |
| R | `docs/research/paper/ARTIFACT_APPENDIX.md` — "Status: draft. Not submittable". No DOI, copyright line unconfirmed, funding terms unchecked. `LICENSE` and `NOTICE` exist |
| S | `docs/research/paper/venue-targets.md` — both near-term deadlines recorded as dropped |
| T | `docs/research/RELATED_WORK.md` — twelve areas, roughly 90 to 100 works. EICopilot named as "closest thing to the baseline C-012 needs" |
| U | `docs/research/CLAIMS.md` — the C-012 banner and the model-provenance banner |
| V | `docs/research/CLAIMS.md` — model-provenance banner, 2026-08-31 |
| W | `EXP-2026-08-011-identity-schema-transfer` and `EXP-2026-08-013-tri-source-federation` |
| X | `docs/research/paper/OUTLINE.md` — section table, sections 5 to 8 |
| Y | `EXP-2026-08-015-bank-variance` — `RESULTS.md`: re-running the model-free versions "would have produced ten byte-identical numbers" |
| Z | `EXP-2026-08-017-federation-isolation` — `merged_nodes_rewritten: 1083`, `federated_nodes_rewritten: 0`, of 9,138 |
| AA | `docs/research/CLAIMS.md` — C-022, rewritten 2026-09-06 |

*Validation at time of writing: `research record OK — 41 experiment(s) validated`.*

*Typeset by `scripts/render_readiness_pdf.py`. The venue-selection prompt asked for
`scripts/morning_report.py::render_pdf`; that renderer is deliberately minimal —
one paragraph per source line, no page numbers, auto-sized table columns — and it
produced an unreadable twenty-one pages from this document. It is unchanged and
still serves the nightly report. Regenerate this PDF with:
`uv run python scripts/render_readiness_pdf.py docs/research/paper/venue-readiness-2026-09.md`*
