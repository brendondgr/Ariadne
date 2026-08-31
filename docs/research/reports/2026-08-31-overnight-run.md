<title>Overnight Run</title>

# Overnight run — 30/31 August

**All six steps of the plan are done, measured, and committed.** Nothing is
pushed. The working tree is clean, the research record validates, and with every
new feature switched off the system's answers are byte-for-byte what they were
before I started.

Two things shipped, one thing was deliberately **not** shipped, and the reason
it wasn't is the most interesting result of the night.

---

## The short version

| | |
|---|---|
| **Fixed** | Three real defects, two of which were making answers wrong today |
| **Shipped** | Understanding a question by the entity's **name** — +3 right answers for +1 wrong |
| **Not shipped** | Fuzzy name guessing — it looked perfect when tuned, and fell apart when tested honestly |
| **New tooling** | A guard that stops the system measuring itself against an empty database |

---

## What I fixed

**A question asking for a list was being answered with a single item.**
"List ATT&CK software entries" should return 821 things. It returned **one** —
because the fuzzy matcher found a database node literally named
`enterprise-attack`, decided *that* was the subject of the question, and
hijacked a request that was never about one entity at all. This was a live
regression I had introduced earlier and missed; the external review's prompt to
break the numbers down by difficulty is what surfaced it.

**Things were being reported as the wrong type.** Technique T1176 was being
described as an "Analytic" — because when the system can't tell what a question
is about, it borrows a label from a list used for an entirely different purpose
(checking the database is loaded), and "Analytic" happens to be first
alphabetically.

My first attempt at this fix was in the wrong place and broke a test, which was
useful: the borrowed label is legitimate *for routing*. The defect was the
**answer inheriting it as a fact**. An identifier's own shape is stronger
evidence than the labels a question happened to route on — T1176 can only be a
Technique whatever the plan said — so that now wins.

**Which database to search was being decided by the alphabet.** "What are the
mitigations for Software Extensions?" was being sent to CAPEC, which does not
contain that entity, so it returned nothing. Both databases matched two words,
the tie went to whichever name sorts later, and "capec" beats "attack" on the
letter C.

The information needed to break that tie properly was **already being computed
and then thrown away**: the system knows whether a word matched a real category
name or merely appeared in a description. ATT&CK matched two real names; CAPEC
matched one real name and one passing mention. That now decides it, and the
question reaches the right database.

---

## What shipped: understanding a question by name

Previously the only reliable way to be understood was to type an ID number. Now,
if you name the thing — "what are the mitigations for Software Extensions" — it
resolves.

**The review caught a real error in my design here and it changed the rule.** I
had proposed "an exact name always wins." That is wrong, because names in this
data are not unique: *Phishing* is a complete CAPEC name and also sits inside
*Mobile Phishing* and *Voice Phishing*; *SQL Injection* sits inside *Blind SQL
Injection*. So the rule is now **"a name wins if only one thing has it"**, and
otherwise the system asks which you meant.

There's one wrinkle the data taught me: "Software Extensions" also contains the
complete name "Software", a different entity. That's a name *nested inside*
another, not a genuine ambiguity, so nested matches are dropped. Two entities
named *separately* in one question still resolve as two.

**Measured, on 579 paraphrases of the 120 standard questions:**

| | right answers gained | wrong answers bought |
|---|---|---|
| fuzzy guessing | +3 | **+11** |
| **exact names only** | **+3** | **+1** |

Same gain, one-eleventh of the cost. They're now separate switches precisely so
the clean one can ship without the dirty one.

---

## What did not ship, and why it's the best result of the night

The fuzzy matcher — guessing which entity you meant from a description — needed
a confidence setting: how sure is sure enough. The obvious approach is to try
settings until the wrong answers stop.

**I split the question bank in half first, froze one half, and never looked at
it while tuning.**

On the half I *could* see, the tuned setting looked perfect: **12 right, 0
wrong.** I then scored it once against the frozen half:

> **17 right, 8 wrong.**

Perfect precision became 68%. And the tuned setting barely beat the untuned one
it replaced (68% against 67%).

**Had I tuned against the whole bank — which is what the obvious approach does —
I would have reported "12 right, 0 wrong" this morning, and it would have been
false.** That is the clearest demonstration this project has that holding data
back actually pays for itself, and it came out of a discipline the review
insisted on.

So the fuzzy matcher stays off. A 68%-accurate guesser does not belong in a
system whose entire selling point is not being confidently wrong.

**One genuinely useful thing came out of it.** The signal that tells a good guess
from a bad one is **not** how strong the match is — those overlap almost
completely. It's **how far ahead the top candidate is over the runner-up**. My
original setting sat right inside the range where wrong answers live. That's
worth knowing even though the feature isn't shipping.

---

## Operational finding you should know about

**The CAPEC database silently emptied itself twice during the night.** It runs
in memory, so a container restart wipes it — and the health check keeps
reporting "reachable", because the socket still answers.

The first time this happened it cost me a full measurement round that looked
exactly like a code regression: 22 of 120 questions returning nothing.

The harness now **verifies both databases against their checksums before it
measures anything, and refuses to run** rather than produce a plausible wrong
number. For unattended work this matters more than any of the fixes above — a
silent empty database turns every subsequent result into confident nonsense.

---

## Where things stand

| | before | after |
|---|---|---|
| Verb changed, ID kept | 0.47 | **0.50** |
| Real name, no ID | 0.10 | **0.13** |
| Paraphrased name | 0.00 | 0.00 |
| Described only | 0.00 | 0.00 |
| Returns the whole database when confused | 52% of name questions | **33%** |
| Correctly refuses invented entities | 26 of 30 | **28 of 30** |
| Confidently wrong on described-only questions | 17% | **13%** |

**The two hardest levels have not moved and I'm not going to dress that up.**
Describing something without naming it still doesn't work. What has improved is
that the system is now much better at *knowing* it doesn't know: fewer whole-
database dumps, fewer confident wrong answers, more correct refusals.

On the original 120 questions the system is measurably **better**: accuracy 0.87
→ 0.92, six questions improved, none worse.

---

## Two things I want to flag honestly

**The "did you mean?" feature is wired but rarely fires.** When a question names
two entities, the answer now offers the choice instead of guessing. But a
question naming two entities usually also matches a category word, so it routes
normally and never reaches the code path where this lives. The mechanism is
correct and tested; its real-world coverage on this question set is thin.

**Your 20-variant read is still outstanding.** I've read about 20 myself and
they're good, but a question set that no human has checked isn't evidence yet,
and it underpins every number above.

---

## What I'd do next

1. **Widen where "did you mean?" can fire** — it's the best demo asset here and
   it's currently boxed into a corner of the routing logic.
2. **Score the interpreter per-slot.** The gold for this now exists — built from
   the questions' own metadata and the raw source files, never from system
   behaviour. It would turn "level 5 is at zero" into "it gets the relationship
   right 80% of the time and the entity 4%", which tells you what to build.
3. **Leave the fuzzy matcher off.** If it's revisited, it needs a fresh split;
   the frozen half has been spent.
