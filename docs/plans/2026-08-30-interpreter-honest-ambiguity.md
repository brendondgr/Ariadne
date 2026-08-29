# Understanding what the analyst meant — plan

**Date:** 2026-08-30
**Mode:** B — no worktree, straight onto `main`.
**Commit at every step. Never push.**

---

## 1. What this is

When someone types a question, the system has to work out what they meant before
it can look anything up. Right now it does that by matching their words against
the names of things in its databases. We measured what that costs: change one
word and **more than half** the questions break. Drop the ID number and it is
essentially over.

The obvious response is to add a smart layer in front that translates ordinary
English into the system's vocabulary. A review of that proposal came back with
three objections that I checked and **all three hold**. This plan is the
corrected version.

It is deliberately smaller than the original proposal. Most of the machinery
already exists in the codebase and is simply not plugged in.

---

## 2. What I checked before writing this

**The review said we are designing something we already built. That is true.**
`utils/specialists/resolve/resolver.py` already contains a ladder that tries the
ID first, then the exact name, then a curated nickname, then a fuzzy match — and
it already records *which* of those worked, and already has a way to say "this
was ambiguous, here are the candidates."

It has **no caller outside its own tests.** The live code path reaches a
different, similarly-named function that does something else entirely. There are
two functions called `resolve_anchor` in the tree with different signatures.

So the job is not "build an interpreter". It is **"connect the resolver we
already wrote, and give its ambiguity answer somewhere to go."** That is a much
smaller and much more defensible piece of work.

**The review said the "ship this today" recommendation rested on an unchecked
attribution. It did, and I have now checked it.** The review suggested an
afternoon of re-running to find out. It was not needed — the answer was already
in the saved results:

| | |
|---|---|
| Answers gained by adding name search | **3, all at difficulty level 3** |
| New wrong answers | **12** — one at level 0, one at level 3, five at level 4, four at level 5, one at level 6 |
| Variants at levels 4, 5 and 6 containing an exact name | **zero, out of 238** |

So **ten of the twelve wrong answers cannot possibly be exact-name mistakes**,
because no exact names appear at those levels. They come from the fuzzy-matching
half. That is stronger than the review assumed and it supports splitting the two.

**But the review's other objection to exact names is correct and I was wrong.**
Names in this data are not unique. "Phishing" sits inside "Mobile Phishing" and
"Voice Phishing"; "SQL Injection" sits inside "Blind SQL Injection". Our own code
comments already record this. So the rule cannot be *"an exact name always
wins."* It has to be *"an exact name wins **if only one thing has it**, and
otherwise we ask."*

**And I found something neither of us knew.** One of the 120 original questions
**broke** under name search. "List ATT&CK software entries" should return 821
entries. It returned **one** — because the name matcher found a node literally
named `enterprise-attack`, decided that was what the question was about, and
hijacked a request that was never about a single entity at all.

**The review's most serious catch is one I would have walked into.** My
suggestion was to generate the "right answers" for this new layer automatically,
by recording what the current system does. That makes **the current system the
definition of correct**. The new layer could then never beat it, every accidental
success becomes a target, and every genuine improvement scores as a failure. It
is the same mistake as tuning settings against the test set, which I refused to
do last week — and worse, because it takes truth from *system behaviour* rather
than from *the data*.

---

## 3. Things I am assuming, so we can move

- **Ambiguity is shown, not resolved silently.** When two or three things match,
  the system says which ones and asks. That is both the honest answer and the
  better demo.
- **Nothing changes by default.** Every new behaviour is switched off unless
  turned on, and with it off the system's output stays byte-for-byte what it is
  today. This has been verified three times already and must stay true.
- **The language model is out of scope for this plan.** See §5.

**One thing I need you to decide:** the review argues this work is defensible
under the accepted deliverables but is not itself one of them, and that with a
pitch in October there are competing priorities. My recommendation is to do
steps 1–4 (two or three days) and stop. Steps 5–6 are written down but should
wait. **You should confirm that split rather than have me assume it.**

---

## 4. The plan

### Step 1 — Fix the two bugs the measurement already found

**What:** Stop name-matching from hijacking bulk requests, and stop the system
declaring an entity's type from a list it uses for something else entirely.

**Why:** The first is a live regression on a real question in the golden set —
821 results collapsed to one. The second is the mislabelling already filed as
Q27, where a technique gets reported as an "Analytic" because that word happens
to be first alphabetically in an unrelated list.

**Where:** `utils/specialists/cypher/builder.py` and its Gremlin twin (the
name-lookup entry point); `utils/planner/drafter.py` (the rescue path);
`utils/planner/cards.py` (the list being misused).

**Check it worked:** the 120 original questions must come back byte-for-byte
identical with the feature off, and with it on the "List ATT&CK software
entries" question must return its 821 entries again. Then commit.

### Step 2 — Fix the actual defect we measured

**What:** Make one part of the system decide whether a word like "software" is
the *name of a category* or *part of the name of a thing*. Right now two parts
decide separately and disagree, and when they tie, the winner is chosen by
**alphabetical order**.

**Why:** This is the defect the experiment actually found, recorded as I-2.
"What are the mitigations for Software Extensions?" gets sent to the CAPEC
database, which does not contain that entity, because "capec" beats "attack" on
the letter C. It returns nothing. The proposal I wrote would have sat *underneath*
this and never fixed it.

**Where:** `utils/planner/drafter.py`, the part that scores each database and
picks a winner. The information needed to break the tie correctly is **already
computed and then thrown away** — the code knows whether a word matched a real
category name or merely appeared in a description, and then counts both the same.

**Check it worked:** the mitigations-by-name question must reach ATT&CK. Full
re-run of the 120 originals with no losses. Then commit.

### Step 3 — Plug in the resolver we already have

**What:** Route the live code through the existing tested ladder instead of the
ad-hoc path it uses now, and give the "this was ambiguous" answer somewhere to
go — a visible list of candidates rather than a silent guess.

**Why:** It exists, it is tested, it already records how each answer was reached,
and it already knows how to say "I found three of these." Nothing consumes that
today. This is the single highest-value connection available, and it is a
connection rather than a build.

**Also here:** rename one of the two `resolve_anchor` functions. Two different
things with the same name in one codebase is how the next person introduces a
third.

**Where:** `utils/specialists/resolve/resolver.py` (already written),
`utils/specialists/cypher/builder.py` and its Gremlin twin, and the
answer-composing layer that will render the candidate list.

**Check it worked:** ask something genuinely ambiguous and get a list of
candidates instead of a guess. Full re-run of the 120. Then commit.

### Step 4 — Split the question bank *before* measuring anything else

**What:** Divide the 579 paraphrases into two halves by a written-down rule.
Work against one half. **Do not look at the other.**

**Why:** Everything after this point involves choosing settings — how confident
is confident enough. Choosing them while watching the whole bank turns the bank
into practice material and makes every number we have already published a
number the system was tuned to produce.

**Where:** a new split file recorded alongside the bank, and the scoring script
learns which half it is allowed to read.

**Check it worked:** the two halves are disjoint, the rule is committed, and the
frozen half is untouched. Then commit.

### Step 5 — Work out what "correct understanding" means, from the data *not* from the system

**What:** For each of the 120 original questions, write down what the system
*should* conclude: which thing is being asked about, what relationship, what kind
of answer. Take this from **the question's own recorded metadata and the answers
computed from the raw source files**, never from what the current system does.

**Why:** This is the review's most important catch. Deriving it from current
behaviour would define the incumbent as correct.

**The bonus:** where the two independent sources disagree — where the current
system gets the right answer through a route that does not match what was
actually asked — **that disagreement is a finding**, not noise. The version I
originally proposed would have thrown it away by construction.

**Check it worked:** the disagreements are listed and explained rather than
silently reconciled. Then commit.

### Step 6 — Settings, and only then, later, a language model

**What:** With a frozen half of the bank untouched, choose how confident the
fuzzy matcher must be. Report only from the half that was never seen.

**The rule that must hold before any of this ships:** judge it first on *wrong
answers*, *whole-database dumps*, and *correctly refusing trick questions*.
Only after those hold may "how many did it get right" be considered. We already
learned this the hard way — a better matcher raised the score on the originals
while making real questions worse.

**A language model, if ever, comes after all of the above**, does nothing but
pick from a list we hand it, never writes a query or chooses a lookup, and stays
off by default.

---

## 5. What this plan deliberately does not do

**No language model.** The review is right that our "an AI planner costs about
12 points" figure measures free-form planning, not picking from a fixed list —
so the prohibition is a **schedule** decision, not a proven one, and the record
should say that honestly rather than overstating our own evidence.

**No claim that checking makes it safe.** I previously argued that validating
every symbol against the database gives a hard guarantee. It does not. The
twelve wrong answers were all perfectly well-formed — real IDs, real categories,
real relationships. Checking catches nonsense. Only *asking* and *declining*
catch confident-and-wrong. That reverses which part of the design matters most.

**No new vocabulary.** Everything fills the structures the pipeline already has.

---

## 6. Deliverables

| What | Where |
|---|---|
| Bulk-request hijack fix + Q27 mislabelling fix | `utils/specialists/*/builder.py`, `utils/planner/drafter.py`, `utils/planner/cards.py` |
| Tie-break fix (category-name match beats description match) | `utils/planner/drafter.py` |
| Tests for the tie-break, including the name-contains-a-category-word case | `utils/planner/tests/test_source_selection.py` |
| Existing resolver connected to the live path | `utils/specialists/resolve/resolver.py`, both builders |
| Ambiguity shown to the analyst as candidates | answer-composing layer + web trace |
| Tests that an ambiguous name produces candidates, not a guess | `utils/specialists/resolve/tests/` |
| Frozen split of the 579 paraphrases | `docs/evaluation/variants-2026-08-29/split.json` |
| Understanding-gold built from question metadata + source-file answers | `docs/evaluation/variants-2026-08-29/slot_gold.json` |
| Disagreements between the two gold sources, listed | experiment `ISSUES.md` |
| All results | `docs/research/experiments/EXP-2026-08-020-variant-robustness/` (amended) |
