# Overnight results

*Generated 03 September 2026, 09:51 UTC. Every number below was read from a file produced during the run — nothing here is typed in by hand.*

## What this project is, in one paragraph

Ariadne answers security questions by looking things up in two public reference catalogues rather than by asking a language model to recall them. The catalogues are **ATT&CK**, a catalogue of the techniques attackers use, and **CAPEC**, a catalogue of attack patterns. They are stored as *graphs*: things (a technique, a piece of malware) connected by relationships (this malware *uses* that technique). A question like "what mitigates technique T1055?" becomes a walk along those connections. Because the answer comes from the catalogue rather than from a model's memory, it can be checked.

## What was done tonight

Until yesterday the system was tested with **30 questions at a time**, hand-written from a list of 16 question types somebody wrote from memory. Two things came out of the last few days: that list covers only **a third** of the kinds of question the catalogues can answer, and some of the catalogue was never even loaded into the database.

Both are now fixed. Tonight's run tests the system against a new set of questions built to cover **everything the catalogues support**, including the corners nothing had ever asked about.

### The new question set

- **572 questions**, written by an AI author that was shown only the subject of each question and what to ask about it — never the answer. The answers were worked out separately, straight from the source files, *before* the questions existed. That is what makes the scores meaningful: the questions cannot have been bent to fit the answers.
- Split into two halves by a fixed rule before anything was run: **284 for development** and **288 held back and untouched**. The second half stays sealed so it can be a genuine test later. Nothing tonight looked at it.
- Questions come in seven kinds, from "read one fact about one thing" up to "follow a chain across both catalogues", plus a set of questions that have **no answer at all**, to check the system says so instead of inventing one.

| kind of question | how many |
|---|---:|
| no answer exists (a trap) | 61 |
| read one fact about one thing | 63 |
| follow one connection forwards | 77 |
| follow one connection backwards | 89 |
| follow two connections | 117 |
| follow one connection, with a filter | 105 |
| follow a chain across both catalogues | 60 |

## The headline result

The measure below is **recall**: of the things the correct answer contains, what fraction did the system actually find? A recall of 1.0 means it found everything; 0.5 means it found half. **No AI was used to mark these** — the correct answers were computed from the source files, so this is a count, not an opinion.

| | score |
|---|---:|
| across all questions as drawn | **45%** |
| adjusted for how common each question type really is | **51%** |
| development half | 44% |
| held-back half | 47% |

**Why two headline numbers.** The question set was built on purpose to over-represent the rare corners of the catalogues — that is where problems hide. So the plain average is pulled down by question types that barely occur in real use. The adjusted number re-weights each question type by how common it actually is, and is the fairer summary.

**What this is not.** The older 30-question sets score 95–100%. That is not the same test: they cover 12 kinds of connection instead of 34, they ask each one in the direction it was written for, and they are marked differently. **These numbers cannot be compared to those, and a drop from one to the other is not the system getting worse.**

One reassuring sign: the two halves score within 3.3 percentage points of each other. Since the split was fixed before any question was run, that is evidence the question set was not tuned to flatter the system.

## What we learned

### 1. Harder questions really are harder — with one exception

| kind of question | recall |
|---|---:|
| one connection, backwards | 60% |
| one connection plus a filter | 55% |
| one connection, forwards | 53% |
| read one fact | 40% |
| a chain across both catalogues | 39% |
| two connections | 26% |

Following two connections is the hardest, which is what we expected: each extra step is another chance to lose the thread. **The surprise is that reading a single fact scores below following a connection** — that is backwards, and it is diagnosed below.

### 2. Long answers are harder than short ones

| how many items the correct answer contains | recall |
|---|---:|
| 1 | 52% |
| 2-5 | 43% |
| 6-20 | 31% |
| 21+ | 29% |

The more items the correct answer has, the smaller the fraction the system finds. This is worth knowing because an earlier study concluded answer length made no difference — but that study measured whether an AI marker *liked* the answer, and only had six long questions to work with. This one counts what was actually retrieved, across 39 long questions. Both can be true at once: finding half a long answer may still read well.

### 3. Saying "I don't know" is the weakest area

Of **61 questions that have no answer**, the system correctly returned nothing **37 times (61%)**. The rest returned something.

Breaking down the failures: **18** returned only the thing the question was about and nothing else — a mild failure, closer to an unhelpful answer than a wrong one. **6** returned unrelated material, which is the more serious kind.

This matters more than the number suggests. Before tonight this behaviour had been tested on **four** questions. It has now been tested on 61.

### 4. Direction: a contradiction, resolved

Connections have a direction. "What mitigates this technique?" and "what does this mitigation cover?" walk the same link opposite ways, and a system can be good at one and bad at the other.

Two earlier readings disagreed. Simply averaging all forward questions (51%) against all backward ones (60%) says backward is easier. But that comparison is unfair: the forward and backward questions are about *different* connections, so it may just be that the backward ones landed on easier subject matter.

Comparing **like with like** — the same connection asked both ways — gives a mean difference of **-0.080** across 20 connections (plus or minus 0.109), where a positive number means forward was easier.

Forward was easier for **3** connections, backward for **10**, and **7** were level. **So there is no single answer: direction matters a lot, but which direction is harder depends entirely on the connection.** That is a more useful finding than either average, and it is why the fair comparison was worth doing.

The widest gaps in each direction:

| connection | which way is easier | gap |
|---|---|---:|
| Mitigation -[mitigates]-> Technique | backwards | 0.80 |
| Campaign -[uses]-> Technique | backwards | 0.66 |
| Group -[uses]-> Technique | backwards | 0.63 |
| Technique -[kill_chain_phase]-> Tactic | forwards | 0.70 |
| AttackPattern -[ChildOf]-> AttackPattern | forwards | 0.87 |
| AttackPattern -[CanPrecede]-> AttackPattern | forwards | 0.98 |

### 5. Why the weak areas are weak

The two weak areas — reading a single fact, and questions about which group or collection something belongs to — **fail in exactly the same way**. In 63 of 63 cases the system builds a database query correctly and the query comes back empty.

That is a useful thing to know, because it rules out most explanations. It is not misunderstanding the question, and it is not failing to build a query. The query is being built and is looking in a place where the answer is not.

Reading single facts fails **completely** for Group, Tactic, View — a score of zero — while working roughly half the time for everything else. The problem is specific to certain kinds of thing, not general.

## Comparing the different ways of answering

**These scores are not the headline number above, and the two must not be compared.** The headline counts *how much of the right answer was found*, over every question, by comparing against answers computed from the source files. The table below is a different measure — an AI marker reading each written answer and rating it — over the development half only, and each answer was marked twice with the order swapped. Its use is to rank the three strategies against each other, nothing else.

| strategy | score | what it is |
|---|---:|---|
| generic | 66% | Queries assembled on the spot out of the catalogue's own structure — still nothing written by a model. |
| deterministic | 49% | Fixed, pre-written database queries, picked by rules. No model decides what to look up. |
| llm_query | 37% | A language model is shown the catalogue's structure and asked to write the database query itself. |

### Read the AI-written-query row with care

It is not a fair test of that idea, and it should not be reported as one.

The model doing the writing thinks out loud before it answers, and the thinking and the answer come back separately. It gets a fixed allowance of words per question. On these questions it spent the whole allowance on the thinking and never reached the answer, so what came back was blank — and a blank is recorded exactly like a wrong answer.

That happened on **153 of 284** questions in that row.

Afterwards the identical request was put to the same model again, word for word.

* At the allowance the run actually used, **2 of 2** replies came back blank — the model used every word it was given on thinking.
* Given **8x** the allowance, the single reply that came back at all contained an actual query instead of a blank. Whether that query is *correct* is a separate question this check does not ask — the point is only that something was written at all.
* 1 of those larger attempts never returned: the service in front of the model gave up waiting. That is a limit of the plumbing, not of the model, and it is recorded as such rather than counted as a failure to answer.

So the row above measures how much room the model was given to think, not whether it can write a query.

There is a second, separate lesson here. The project's settings file asks for an allowance of 2,048, but this run never read that file — it used the built-in default of 4,096 instead. Neither number was large enough, so it made no difference to the result tonight; but a setting that is written down, looks correct, and is silently ignored is worth knowing about before it matters.

Fixing it needs either a much larger allowance — which makes every question far slower — or a model that answers without a long preamble. Either way it needs its own run. **Nothing was changed tonight**; this was found by reading the run's own records and asking the model the same question again.

## What did not run

16 of 16 steps finished.

Every planned step finished.

**The held-back half of the questions was not touched.** That was deliberate: it is only useful as a test if nothing has been tuned against it.

**Nothing about the system itself was changed tonight.** Every fix that involves a judgement call was left for the morning.

## What to decide

1. **The empty-query problem.** Two weak areas share one cause, and it looks like a single fixable defect rather than a deep limitation. Worth looking at first.
2. **Saying "I don't know".** The system returns something for about four in ten unanswerable questions. Most of those are mild, but it is the clearest weakness the new question set found.
3. **Direction.** Now known to matter, and to matter differently for different connections. Whether to do anything about it is a design decision, not a bug fix.
