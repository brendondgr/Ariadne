# What happened, in plain language

Covering 3–5 September 2026. Written 2026-09-05 10:31.

## The short version

The project compares three ways of answering a security question against a knowledge graph: a library of **hand-written queries**, queries **assembled on the spot** from the catalogue's own structure, and letting a **language model write the query** itself.

Two days ago the hand-written library looked far worse than the assembled one. The worry was that this was unfair — that the hand-written path was simply broken, and a reviewer would say so. **It was broken, in six separate ways.** All six are now fixed, and the comparison was run again. The assembled path still wins, by about the same margin.

## The main result

| way of answering | scored by grader 1 | scored by grader 2 |
|---|---:|---:|
| hand-written library | 0.4946 | 0.4166 |
| assembled from the catalogue | 0.6569 | 0.6697 |
| model writes the query | 0.3781 | not graded |

The gap between the two is **0.1623** under the first grader and **0.2531** under the second. Different graders, same winner.

## How confident we can be

A single grader could simply be having an opinion. So the same answers were graded again by a **different model**, and then repeatedly, to see how much one grader wanders on its own.

| grader | grading sessions | its own wobble | range the gap sits in |
|---|---:|---:|---|
| qwen | 2 | 0.0075 | 0.1258 to 0.2001 |
| gemma | 8 | 0.0113 | 0.199 to 0.304 |

The two graders differ by **0.09**, against a wobble of **0.0113**. offset exceeds the within-grader spread. Both ranges stay well clear of zero, so the winner is not an artefact of who was marking.

## What was actually broken

Six faults in the system, and three in the measuring equipment. The last group matters most, because they are why nobody noticed the others.

**In the system.**

1. The graph was built from a list of ten allowed fields, so most of what MITRE publishes was thrown away on load. Asked *who contributed this campaign*, the answer existed in the source file and not in the graph. 24 questions were unanswerable for this reason alone.
2. Loading a node with many fields hit an undocumented ceiling and silently capped it at fourteen.
3. One record's own identifier overwrote the identity of the node it was stored under. A single connection has been missing from the live graph for the entire life of the project — 8,581 of 8,582.
4. Questions about a *view* or a *category* were looked up as though they were an *attack pattern*, so they matched nothing. 45 questions.
5. Asked what a threat group *is*, the system answered with a list of that group's techniques — a valid answer to a different question.
6. Questions about what a category *contains* were answered with the category's status, because the containment link was invisible to the part that chooses a query. 63 questions.

**In the measuring equipment.**

1. The tool that classified failures read a field from the wrong place, so *"the query came back empty"* was the only verdict it could ever give. The headline finding of the previous report was that verdict.
2. Questions asking for a fact about something were scored against a rule nothing could satisfy: the expected answer was a sentence, and the marker only recognised identifiers.
3. A correct answer naming nine categories scored zero, because it wrote them in the graph's spelling and the answer key used the source's.

## The third way, and why it took four attempts

Letting the model write the query kept producing a number that turned out to measure our own settings rather than the model:

- **First**: the model was given a word allowance so small it spent all of it thinking and said nothing. 153 of 284 questions came back blank.
- **Second**: the allowance was raised, but it was being read once when the program started rather than when it was used, so the new value never applied.
- **Third**: with the allowance genuinely raised, a separate **two-minute cut-off** stopped the model mid-thought. 282 of 284 produced nothing. That run was deleted rather than reported.
- **Fourth**: cut-off raised to 68 minutes and allowance to its maximum. 140 of 284 produced a query.
- **Fifth**, split across two dedicated machines: **235 of 284** produced a query.

A check on the hard questions before the fifth run: **9 of 10** produced an answer, so the remaining failures are no longer the equipment.

**What it costs.** This was the one thing the claim had never measured. Answering the same 284 questions took the hand-written library about **four seconds** in total. Letting the model write the queries took **roughly two days of machine time**. That is a difference of about **forty thousand times**, before anyone argues about accuracy.

## Where I got it wrong

Recorded because the record is the point, and because each one cost hours.

- I said the 131 failures shared a single cause. They had six.
- I predicted a fix would recover 47 questions; it recovered 2. A later prediction of 23 recovered 14. Both times, predicting what would **not** move was exactly right and predicting what **would** move was optimistic.
- I said the held-back questions were untouched. They had been answered once, months-of-work ago in project time, and the published figure came from that. Never graded, which is the property that actually matters — but *untouched* was the wrong word and the record now says so.
- I reported a run as in progress when it had never started, because I checked for it by name and matched my own command.
- I chose a word allowance from a single easy question and applied it to all of them.
- I predicted that running 16 jobs at once per machine would starve them. Measured, it did not.

## What is still open

- **The held-back half.** 288 questions, never graded. They are the honest test of whether these fixes generalise, and they can only be used once. Best spent when all three ways of answering are ready, not two.
- **Two known scoring faults remain**, both of which make the current numbers *too low* rather than too high. Left alone deliberately: fixing them raises our own scores, so the rule has to be written down and agreed before it is applied.
- **An outside grader.** Everything so far is graded by models running on this hardware. The strongest check would be a grader from a different provider entirely.

