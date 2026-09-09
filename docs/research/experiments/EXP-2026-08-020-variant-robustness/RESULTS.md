# RESULTS — EXP-2026-08-020 Arm 0 (baseline, shipped router)

**Status: Arm 0 complete.** 699 runs — 120 control + 579 variants — against a
reference captured twice and proved byte-identical. Every figure below is read
from [`data/metrics.json`](data/metrics.json).

## The control passes, so the rest is readable

| tier | n | `records_exact` | `records_recall` | **recall, dumps removed** | `queries_exact` | abstained | `wrong_entity` | **`catalogue_dump`** |
|---|---|---|---|---|---|---|---|---|
| **T0** control | 120 | **1.0000** | **1.0000** | 1.0000 | **1.0000** | 0.1333 | 0.0000 | 0.0000 |
| T1 id + synonym | 120 | 0.4667 | 0.5790 | 0.5790 | 0.4500 | 0.1500 | 0.1083 | 0.0000 |
| T2 id + restructured | 120 | 0.4250 | 0.5674 | 0.5674 | 0.4083 | 0.1917 | 0.1083 | 0.0000 |
| T3 exact name | 101 | 0.0990 | 0.5093 | **0.3166** | 0.0000 | 0.2079 | 0.1485 | **0.5248** |
| T4 paraphrased name | 104 | **0.0000** | 0.0719 | **0.0013** | 0.0000 | 0.7212 | 0.1635 | 0.1827 |
| T5 description only | 104 | **0.0000** | 0.0284 | **0.0000** | 0.0000 | 0.7596 | 0.1731 | 0.1827 |
| T6 negative control | 30 | — | — | — | — | **0.8667** | 0.0333 | 0.1333 |

T0 is the gold questions themselves, re-run through the harness: **1.0000 on
every metric.** The instrument measures the system, not itself.

## H1 — confirmed, and the cliff is steeper than the tiers suggest

Record identity falls monotonically and then hits the floor: **0.4667 → 0.4250 →
0.0990 → 0.0000 → 0.0000.**

**Keeping the identifier is worth almost everything, and it is still not enough.**
T1 changes only the verb — *"How do I defend against T1176?"* — and **more than
half the questions break**. Removing the identifier while keeping the entity's
exact name takes exact identity to 0.0990. Paraphrasing that name takes it to
**exactly zero, on 104 questions**.

`queries_exact` is **0.0000 for every tier from T3 down**. Not one paraphrase
that dropped the identifier reached the interpretation its gold question
reached.

## H2 — confirmed, and it is tier-dependent in a way the hypothesis missed

The prediction was that silent downgrade would dominate abstention. That is true
**only where the identifier survives**:

- **T1/T2:** abstention 0.15/0.19 against 0.47/0.43 exact — so roughly **a third
  of all runs land in neither box**: they answer, and answer partially or wrongly.
  `wrong_entity` alone is 0.1083, meaning **13 of 120** returned records of which
  *not one* was in the gold answer.
- **T4/T5:** abstention rises to 0.72/0.76. Here the system mostly does decline.

So the shape is: **with an identifier it guesses; without one it mostly stops.**
That is a better outcome than the hypothesis assumed, and it makes the residual
`wrong_entity` of 0.16/0.17 at T4/T5 more serious, not less — those are the cases
where it did not stop.

## The finding that was not hypothesised: recall at T3–T5 is dumping, not retrieval

**`catalogue_dump`** — a result both ≥50 records absolute and ≥10× the gold's
size — fires on **95 of 699 runs (13.6%)**, and on **52.5% of T3**.

Splitting recall by it is the result of this experiment:

| tier | recall, dumping | recall, **not** dumping |
|---|---|---|
| T3 | 0.6838 (n=53) | **0.3166** (n=48) |
| T4 | 0.3876 (n=19) | **0.0013** (n=85) |
| T5 | 0.1556 (n=19) | **0.0000** (n=85) |

**At T4 and T5, when the system does not return the catalogue, it retrieves
essentially nothing.** Every point of apparent recall at those tiers is the gold
answer happening to sit inside a bulk scan of a whole label.

Quoting T3's pooled 0.5093 without the 0.3166 beside it would credit the router
for answers it found by returning everything. **This is the same defect class as
I-11 in C-023** — *"the template arm's earlier apparent recall was scoring by
dumping records rather than by retrieving"* — reproduced on a completely
different axis, which is evidence that the pattern is structural rather than one
bad template.

## H3 — refuted. The negative controls are answered, confidently, at scale

26 of 30 correctly return nothing. **The 4 that answer are the most serious
result in this experiment**, because nothing in the pipeline can catch them:

| asked about | records returned | asserted |
|---|---|---|
| the threat group **"Obsidian Larch"** | **158** | *"All 158 result(s) for this question: T1529, T1686, T1105…"* |
| the **"Quantum Exfiltration"** tactic + **"Biometric Lockdown"** mitigation | **222** | *"All 200 result(s) for this question…"* |
| the **"Chimeric Handshake Exploit"** pattern | **558** | *"All 200 result(s)…"* |
| the **"Recursive Token Bleaching"** pattern | **558** | *"All 200 result(s)…"* |

None of these entities exists. 558 records is essentially the entire CAPEC
catalogue.

**The verifier cannot catch this and it is not a verifier bug.** Every record is
genuinely retrieved; every claim is genuinely grounded in one; every citation
resolves. What is false is the *framing* — "all results for this question" — and
a claim-level verifier has no claim to reject. **This is precisely the limit
C-017 names as a ceiling by construction, seen from the other side: a property
that cannot be violated also cannot protect you.**

It also qualifies C-001's *zero hallucinations*. That figure is measured on
questions phrased in the schema's own vocabulary. Off that vocabulary, the system
fabricates by *selection* rather than by invention — and no metric currently
reported would show it.

## What this does and does not license

**Does:** the deterministic router's measured correctness is substantially a
property of question phrasing, quantified per tier, on a bank that no template
was written against.

**Does not:** this is not absolute robustness. The variants derive from the
120-question catalogue, which is itself co-authored with the templates (C-021,
bias 0.0483), so the reference sits at the favourable end. A question set drawn
independently would likely be worse, not better.

## Next

Arms 1–3 are the staged fixes; each is re-scored on this same frozen bank, so
arm-to-arm differences carry no authoring variance at all. The two named defects
to fix first are recorded in [`ISSUES.md`](ISSUES.md): the alphabetical
source-selection tiebreak (I-2), and the unanchored fall-through to `label_scan`
that produces every dump above.

---

# Arms 1 and 2 — the deterministic fixes

Both behind one flag, `ARIADNE_LEXICON`, default **off**. With it off the
reference is **byte-identical** to the committed Arm 0 capture, verified twice.

**Arm 1** — stemming, gloss stems, bounded edit distance in the router
(`utils/planner/lexicon.py`, wired into `_concept_indexes` / `_match_card`).
**Arm 2** — Arm 1 plus: an unanchored question runs a real bounded query that
finds nothing, instead of scanning the whole label.

## On the catalogue, both arms are a clean gain

| | Arm 0 | Arm 1 | Arm 2 |
|---|---|---|---|
| gold recall over 66 scorable golden questions | 0.8698 | **0.9161** | **0.9161** |
| answers changed | — | 14 | 14 |
| **better / worse / same** | — | **6 / 0 / 2** | **6 / 0 / 2** |

**Zero regressions**, and the gains are large where they land: the three
detection questions go from 0.3333 / 0.1429 / 0.1250 to **1.0000**, and the
three mitigation-coverage questions from ~0.78 to **1.0000** while returning
*fewer* records — a precision and recall win at once. The two `C-PRE` changes
drop spurious CWE records from a question about patterns and stay at 1.0000.

## On the variants, Arm 1 alone is actively harmful — and that is the finding

| tier | `wrong_entity` A0 → A1 → A2 | `catalogue_dump` A0 → A1 → A2 | abstained A0 → A1 → A2 |
|---|---|---|---|
| T1 | 0.1083 → 0.1083 → 0.1083 | 0.0000 → 0.0000 → 0.0000 | 0.1500 → 0.1583 → 0.1667 |
| T2 | 0.1083 → 0.1083 → 0.1083 | 0.0000 → 0.0000 → 0.0000 | 0.1917 → 0.2000 → 0.2000 |
| T3 | 0.1485 → 0.1485 → **0.1089** | 0.5248 → 0.5248 → **0.3267** | 0.2079 → 0.2079 → **0.4059** |
| T4 | 0.1635 → **0.2500** → **0.1154** | 0.1827 → **0.3077** → **0.1635** | 0.7212 → **0.6250** → **0.7788** |
| T5 | 0.1731 → **0.2885** → **0.1346** | 0.1827 → **0.3173** → **0.1538** | 0.7596 → **0.6058** → **0.7981** |
| T6 | 0.0333 → 0.0667 → 0.0667 | 0.1333 → 0.1667 → **0.1000** | 0.8667 → 0.8667 → **0.9333** |

**Arm 1 converts abstentions into catalogue dumps.** Wrong-entity rate rises
**+0.0865** at T4 and **+0.1154** at T5; dumps rise **+0.1250** and **+0.1346**;
abstention falls by roughly the same amount. Widening word matching means more
questions find *a* schema word, so more of them route — and with no anchor
resolved they fall through to the label scan and return everything.

**The lexicon was not the defect; it exposed the defect.** A better matcher
pointed at a fall-through that answers by dumping makes the dumping worse. The
two changes are one change, and shipping the first without the second would have
looked like an improvement on the catalogue while degrading exactly the
questions the catalogue cannot see.

**Arm 2 beats the baseline on every safety metric.** Wrong entities fall below
Arm 0 at T3, T4 and T5. Dumps fall at every tier. T6 abstention rises to
**0.9333** — **28 of 30** negative controls now correctly silent, against 26.

## What Arm 2 does *not* do, stated plainly

`records_exact` is unmoved at T3 (0.0990) and still **0.0000** at T4 and T5.
T3's pooled recall *falls*, 0.5093 → 0.4058, and its no-dump recall falls
0.3166 → 0.2235 — **because the denominator changed**: runs that used to be
scored as high-recall dumps are now abstentions scoring zero.

**Arm 2 does not retrieve more. It stops pretending.** That is the correct fix
for this stage and it is not a retrieval improvement. Closing the retrieval gap
is what a candidate index over canonical names and descriptions is for, and
until that exists the honest summary of T4/T5 is: **the system now mostly knows
that it does not know.**

---

# Arm 3 — the name index. It works as a component and fails as a router.

`utils/specialists/schema/namesearch.py`: BM25 over the 9,138 canonical
name+description records, plus an exact-name boost, restricted to the labels the
router already has in scope. **No new dependency.** Behind its own flag,
`ARIADNE_NAMESEARCH`, default off; with both flags off the reference is
byte-identical to Arm 0, verified a third time. Catalogue gold recall is
unchanged from Arm 2 at **0.9161, 6 better / 0 worse**.

## As a component it resolves what it should

Direct probes, 7 of 9 exact: `SQL Injection`→CAPEC-66 (over *Blind* SQL
Injection), `Phishing`→CAPEC-98 (over Mobile and Voice Phishing),
`Software Extensions`→T1176, `Inhibit System Recovery`→T1490. Both misses are
honest: `browser extension persistence` resolves to **T1176.001 Browser
Extensions**, a real sub-technique of the gold's parent; and the pure
description-only probe returns **None** rather than guessing.

The exact-name boost is what makes those work. BM25 alone ranks
*Blind SQL Injection* above *SQL Injection* for the query "SQL Injection", and
puts Phishing / Mobile Phishing / Voice Phishing in a three-way numerical tie
that the margin rule then rejects entirely.

## As a router it answers more than it should

| tier | `records_exact` A2 → A3 | `wrong_entity` A2 → A3 | net |
|---|---|---|---|
| T3 | 0.0990 → **0.1287** (+3 questions) | 0.1089 → 0.1188 (**+1**) | +2 |
| T4 | 0.0000 → 0.0000 (0) | 0.1154 → **0.1635** (**+5**) | −5 |
| T5 | 0.0000 → 0.0000 (0) | 0.1346 → **0.1731** (**+4**) | −4 |
| T6 | — | 0.0667 → **0.1000** (**+1**) | −1 |

**Three questions gained, eleven wrong answers bought.** Every one of the eleven
is a confident answer about the wrong entity, which is the failure mode this
experiment named as the one nothing downstream catches.

## The recommendation, and the reason it is not "tune the threshold"

**`ARIADNE_NAMESEARCH` stays off.** The obvious next move — raise `MIN_SCORE`
and `MIN_MARGIN` until the wrong answers stop — is available and is **declined
on purpose.**

`MIN_SCORE = 4.0` and `MIN_MARGIN = 1.25` were set *a priori*, before any
variant was scored, and were never fitted. Fitting them against this bank would
turn the bank into a training set and every number above into a training
number — which is precisely the co-authorship failure C-021 exists to measure,
committed deliberately after having spent a week quantifying it.

If the thresholds are to be tuned, they need a held-out split of the variant
bank that is drawn before any tuning begins, and the reported figure has to come
from the half that was never seen. That is a real and cheap piece of work, and
it is **Q28** rather than something to do quietly here.

## Where this leaves the retrieval gap

Open. Arm 2 made the system honest; Arm 3 shows that closing the gap with a
ranked index is *possible in principle* — the right entity is usually in the top
one or two — and that converting "is in the top two" into "is what we answer
with" is where the difficulty actually lives.

**T4 and T5 record identity remains exactly 0.0000 across all four arms.**
Nothing measured here moved it, and no claim should say otherwise.

---

# Arms 4 and 5 — splitting the two kinds of evidence

An external review of the follow-on design (2026-08-30) argued that the "+3
right, −11 wrong" of Arm 3 had never been decomposed, and that the recommendation
to ship exact-name matching alone rested on an unchecked attribution. Both
points were correct. **The decomposition was recoverable from the saved Arm 2/3
results without re-running anything:**

- The 3 gains are **all at T3**.
- The new wrong answers are T0:1, T3:1, T4:5, T5:4, T6:1.
- **Zero of the 238 variants at T4, T5 and T6 contain an exact name.** So ten of
  the twelve cannot be exact-name misfires — they are ranked-matching failures.

That is *stronger* than the review assumed, and it made the split worth building.

**The review's other objection was also correct, and it changed the design.**
"Exact" is not "unique": `Phishing` is a complete CAPEC name and also sits inside
`Mobile Phishing`; `SQL Injection` sits inside `Blind SQL Injection`. So
`exact_name_matches` returns a **list**, and more than one surviving match is an
ambiguity to surface, never a tie to break. A subsumption filter drops names
nested inside a longer match — `Software Extensions` contains the complete name
`Software` (T1592.002) — so multi-word entities do not become false ambiguities,
while two separately-named entities ("how does Phishing relate to Excavation")
still resolve as two.

## The measured split

Both arms include Steps 1–2 (bulk-scan hijack fixed, Q27 fixed, tie-break fixed).
Arm 4 adds ranked matching; **Arm 5 adds exact-name matching only.**

| tier | `records_exact` A2 → A5 | `wrong_entity` A2 → ranked → **exact** |
|---|---|---|
| T1 | 0.5000 → 0.5000 | 0.1083 → 0.1083 → **0.1083** |
| T2 | 0.4250 → 0.4250 | 0.1083 → 0.1083 → **0.1083** |
| T3 | 0.0990 → **0.1287** | 0.1089 → 0.1188 → **0.1089** |
| T4 | 0.0000 → 0.0000 | 0.1154 → 0.1635 → **0.1250** |
| T5 | 0.0000 → 0.0000 | 0.1346 → 0.1731 → **0.1346** |
| T6 | — | 0.0667 → 0.1000 → **0.0667** |

| | answers gained | wrong answers bought |
|---|---|---|
| ranked matching | **+3** | **+11** |
| **exact name only** | **+3** | **+1** |

**The entire T3 gain survives the split; eleven-twelfths of the cost does not.**
Negative-control abstention returns to **0.9333** (28 of 30) from ranked
matching's 0.9000, and T3, T5 and T6 wrong-entity rates all return to Arm 2's
levels. The single residual is one extra wrong answer at T4.

Catalogue regression is unchanged from Arm 2: **6 better, 0 worse, gold recall
0.8698 → 0.9161.** With every flag off the 120 golden answers are byte-identical
to the Arm 0 capture.

## What this licenses

`ARIADNE_EXACTNAME` is a **shippable win** and is separated from
`ARIADNE_NAMESEARCH` precisely so it can ship without it. Exact-name resolution
is a lookup with no threshold to fit; ranked matching is a guess whose thresholds
remain unfitted and are Q28's subject. Welding them to one flag held the clean
win hostage to the dirty one, and that is now undone.

**T4 and T5 record identity is still exactly 0.0000 across every arm.** Nothing
measured here has moved it.

---

# Step 6 — the thresholds, fitted honestly, and the answer is still no

Q28's protocol, executed: the bank was split **by gold question** (so a question
and all its paraphrases stay together) using `sha256(case_id)` parity — 63 tune,
57 report — **drawn before any threshold was touched**, and the harness filters
the frozen half out so a sweep physically cannot reach it.

## The score threshold is not the lever; the margin is

A first grid over score ∈ {4, 8, 12} × margin ∈ {1.25, 1.6, 2.2} moved nothing:
every configuration returned identical wrong-entity, dump and exact rates except
that margin 1.25 was worse. The grid was badly chosen — typical winning scores
are 11–17, so every "threshold" tested sat *below* the scores it was meant to
filter.

Measuring the distributions directly is faster and more informative than a
second blind sweep. Over the tuning half, restricted to cases where **exact-name
matching did not already answer** — so this isolates ranked matching's marginal
contribution:

| | n | score median | **margin median** |
|---|---|---|---|
| resolved **correctly** | 22 | 27.1 | **1.72** |
| resolved **wrongly** | 64 | 14.8 | **1.08** |

The scores overlap heavily; the margins barely do. **The discriminating signal is
how far ahead the leader is, not how strong it is** — and the shipped default of
1.25 sat inside the wrong-answer distribution. On the tuning half, margin ≥ 1.4
with **no score floor at all** yields **12 right, 0 wrong**.

## And it did not hold on the frozen half

Scored once, as the protocol requires:

| | tune half (fitted) | **frozen half (never seen)** |
|---|---|---|
| at margin ≥ 1.4 | **12 right, 0 wrong** | **17 right, 8 wrong** |
| at the old default 1.25 | — | 24 right, 12 wrong |
| margin median, correct | 1.72 | 1.39 |
| margin median, wrong | 1.08 | 1.12 |

**Perfect precision on the half it was fitted to became 68% on the half it had
not seen**, and the fitted threshold barely beat the unfitted default (68% vs
67%). The margin distributions that separated so cleanly on the tuning half
overlap on the frozen half — 1.39 against 1.12.

**This is what the holdout is for**, and it is the clearest demonstration the
project has that the discipline pays. Had the threshold been fitted against the
whole bank, as the obvious approach would have, the reported figure would have
been *12 right, 0 wrong* — and it would have been an artifact.

## Verdict

**`ARIADNE_NAMESEARCH` stays off.** A 68%-precision anchor resolver does not
belong in a system whose entire value proposition is not being confidently
wrong, and no threshold on the signals available separates the cases.

**`ARIADNE_EXACTNAME` ships.** It is a lookup, not a guess; it needs no
threshold; and it delivers the full +3 for +1.

The frozen half has now been spent, once, on the one candidate that warranted
it. Any future threshold work needs a fresh split.

---

# Arm 6 — defaults on, and names resolved before the ladder

Two changes, measured together because they share a regression run.

**Enabled by default.** `ARIADNE_LEXICON` and `ARIADNE_EXACTNAME` now default
**on**, with the env var still accepting `0`/`false` to restore the prior path
for reproducing earlier arms. `ARIADNE_NAMESEARCH` remains **off** — Step 6's
holdout result stands.

**Names resolved first.** Name resolution used to sit at step 7, the no-anchor
fall-through, so it only ran for questions that matched *no template at all*.
"Which techniques did the Frankenstein campaign use?" takes the campaign branch
on the word "campaign", with no seed, and never reached the resolver. Resolving
first means a name-anchored question reaches the **same template it would have
reached had the analyst typed the identifier**.

## Against the shipped baseline

| tier | `records_exact` base → A5 → **A6** | `wrong_entity` base → A5 → **A6** | `catalogue_dump` base → **A6** |
|---|---|---|---|
| T1 | 0.4667 → 0.5000 → 0.5000 | 0.1083 → 0.1083 → 0.1083 | 0.0000 → 0.0000 |
| T2 | 0.4250 → 0.4250 → 0.4250 | 0.1083 → 0.1083 → 0.1083 | 0.0000 → 0.0000 |
| **T3** | 0.0990 → 0.1287 → **0.2376** | 0.1485 → 0.1089 → **0.1089** | 0.5248 → **0.1683** |
| T4 | 0.0000 → 0.0000 → 0.0000 | 0.1635 → 0.1250 → 0.1346 | 0.1827 → 0.1635 |
| T5 | 0.0000 → 0.0000 → 0.0000 | 0.1731 → 0.1346 → 0.1442 | 0.1827 → 0.1346 |
| T6 | — | 0.0333 → 0.0667 → 0.1000 | 0.1333 → **0.0667** |

| | vs baseline |
|---|---|
| exact names, resolved late (Arm 5) | **+7** right, **−11** wrong |
| **exact names, resolved early (Arm 6)** | **+18** right, **−8** wrong |

**Better on both axes.** T3 more than doubles (0.0990 → 0.2376), its
byte-identical-query rate goes 0.0000 → 0.1584, and its catalogue-dump rate
falls by two-thirds. Catalogue regression is unchanged: **6 better, 0 worse,
gold recall 0.8698 → 0.9161.**

## Two design corrections found by tests, not by reasoning

**Several exact names is a conjunction, not an ambiguity.** The rule shipped in
Arm 5 returned "did you mean?" whenever more than one complete name appeared.
A test caught it: *"What exactly is User Training and Software Configuration
respectively?"* names two entities and wants **both**, and the existing
describe-by-name path already serves several names in one query. Refusing it
would have broken a question the system answers correctly. Multiple exact names
now fall through to that path.

That narrows where genuine ambiguity can arise: with exact matching plus the
subsumption filter, a second surviving match means the question named a second
*thing*, not that the first was unclear. **The "did you mean?" surface therefore
belongs on the fuzzy path, which is off — so it is presently near-unreachable,
and that is recorded rather than glossed.**

**An exactly-resolving name should not take the substring path.** Measured while
updating a test: `"What is Phishing?"` returns **four** records through
`describe_by_name` — Phishing, Spear Phishing, Mobile Phishing, Voice Phishing —
because the pattern matches any name containing the word. Resolving the name
first returns **one**. Three tests asserted the older routing and were updated
with that measurement in their docstrings.

## Cost

`exact_name_matches` originally scanned all 9,138 canonical entities per call,
which was tolerable at step 7 and is not when it runs on every seedless
question. A first-token prefilter — a name can only appear if its first word
does — takes it to **0.067 ms per call** with identical results.

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — pointers filled, provenance brought up to the last arm, one table cell taken from the wrong arm, and a stale status line

**Pointers.** `data/POINTERS.md` was the empty scaffold (one blank row) from
2026-08-29 until 2026-09-09, although every artifact — seven `scored_arm*.json`,
the references, the variant bank, the Step 6 split, sweeps and gold — is
git-tracked under `docs/evaluation/variants-2026-08-29/`. The table now lists
33 rows, each hashed with `utils.research_record.hashing` on 2026-09-09 and
labelled with its introducing commit. Files committed there on 2026-09-08 by
EXP-2026-09-014 (`reference_2026-09-08.json`, `scored_R*_tune*.json`) are not
this experiment's and are excluded.

**Provenance.** `manifest.yaml` was last edited 2026-08-31 11:40 without
updating three fields:

* `date_completed: 2026-08-29` covered Arm 0 only. Arms 4–6 and Step 6 ran
  2026-08-30 23:57 – 2026-08-31 11:39 (artifact mtimes; commits `0dc748c`,
  `538d0c0`, `b8c3b99`, `9f02dc6`). **Old → new:** `2026-08-29` → `2026-08-31`,
  the date of the last artifact and its commit.
* `code.commit: b040e185…` is "Variant Robustness (2a/8)" (16:06), the
  authoring commit *before* Arm 0 ran. **Old → new:** → `0ae78c1948adcd52…`,
  the commit that introduced `scored_arm0.json` (16:16), which is the primary
  metric's artifact. The arms were not all run at one commit; each artifact's
  introducing commit is: Arm 0 `0ae78c1`; Arms 1–2 `2b48a91`; Arm 3 `a65bcd9`;
  Arm 4 `0dc748c`; Arm 5 `538d0c0`; Step 6 split/gold `f6893c8`, sweeps
  `446bc45` / `b8c3b99`; Arm 6 `9f02dc6`. Recorded in ISSUES.
* `compute.wall_clock_hours: 1.6` was recorded for Arm 0 and never revised; the
  total across seven arms and Step 6 is not recoverable and the field is left
  as recorded with that scope noted in ISSUES.

**One table cell from the wrong arm.** §"Arms 4 and 5" › "The measured split"
gives, in the `wrong_entity` column at **T4**, `0.1154 → 0.1635 → 0.1250` (A2 →
ranked → exact). `arm4_steps12_plus_ranked.T4.wrong_entity` in
`data/metrics.json` is **0.1538**; 0.1635 is *Arm 3's* T4 value. The derived
cost line "ranked matching **+3 / +11**" is therefore Arm 3's tally; Arm 4
against Arm 2 is **+3 right / +10 wrong** (T3 +1, T4 +4, T5 +4, T6 +1, from
the tier rates × n). Recomputed 2026-09-09 from `data/metrics.json`; the
`scored_arm4.json` tier rates reproduce that file. The conclusion —
exact-name-only keeps the T3 gain and sheds almost all of the cost — is
unchanged; "eleven-twelfths of the cost" reads as ten-elevenths.

**Stale status line.** Line 3 still says "**Status: Arm 0 complete.**" The
experiment is complete through Arm 6 and Step 6, as the sections below it
record; the manifest says `complete`.

**Unrecorded seeds.** `seeds: []` with no ISSUES entry. The system under test
has no randomness (every seam off; the reference was captured twice and
matched byte-for-byte), and the one model call — Sonnet authoring the variants
— was a single unseeded pass whose output is frozen in `variants.json`. Now
recorded in ISSUES.

**`data/metrics.json`.** `arm6_net_right_vs_baseline = 18` and
`arm6_net_wrong_vs_baseline = −8` are count differences derived from the Arm 6
and Arm 0 tier rates and were never written by the harness; a
`manifest_metrics` object now carries every manifest value. Verified: Σ over
T1–T5 of (arm6 − arm0) `records_exact` counts = +18; Σ over T1–T6 of
`wrong_entity` counts = −8.

**Related work.** EXP-2026-08-022 judged the builder change Arm 6 shipped
(`9f02dc6`) on the two fresh banks and found it invisible to the judge (DiD
inside its own spread), which is consistent with those banks sitting at ceiling;
EXP-2026-09-014 re-uses this variant bank, re-captured the Arm 6 reference on
2026-09-08 and scores its rewrite stage against it. Both are added to
`related`; nothing here is superseded.

## AMENDMENT A-2 (2026-09-09) — the primary metric now names a recorded key

`metrics.primary` was `records_exact`, a descriptive label that matched no key in
`metrics.values`, so `INDEX.md` and `CURRENT.md` rendered this experiment's
headline as "not recorded". It now names `records_exact_T4` — the tier at which record identity first reaches 0.0000. No value changed.
