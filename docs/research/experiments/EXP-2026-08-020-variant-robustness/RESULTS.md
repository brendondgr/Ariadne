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
