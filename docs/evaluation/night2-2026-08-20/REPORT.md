# Second night — hardening yesterday's numbers

**Started** 2026-08-20T07:50:08+00:00 · **phases** 26, 2 failed: N6, N7

Yesterday's arm table came from one question set, graded once, by a grader sharing a server with the system it graded. Nothing was added last night — the night went at those three weaknesses instead.

## 1. Does the ranking survive a completely different question set?

A second question set of **30 questions** was drawn and written overnight, with every entity used by any earlier set excluded before drawing.

**No entity appears in both sets.** The exclusion list did its job, which is the first time it has been tested on a real second draw.

| version | set 1 (yesterday) | set 2 (last night) | change | fully correct | made something up |
|---|---:|---:|---:|---|---:|
| Normal system (pre-written query templates) | 0.9467 | **0.9417** | -0.0050 | 28 of 30 | 0 |
| No templates (works the schema out at run time) | 0.9700 | **0.9750** | +0.0050 | 29 of 30 | 0 |
| LLM-assisted (AI writes the prose answer) | 0.9773 | **0.9645** | -0.0128 | 28 of 29 | 1 |
| AI writes the database query itself | 0.5000 | **0.4183** | -0.0817 | 8 of 30 | 3 |

**How to read the change column.** These are two different sets of questions, not a before/after on the same ones, so a small movement means nothing. What matters is whether the *order* of the rows is the same on both sets. An order that flips means yesterday's table described one question set rather than the system.

⚠ **The ordering changed between the two sets.** Yesterday's comparison table cannot be quoted as-is.

## 2. Was the AI-written-query result unfair to the AI?

Yesterday that version scored around half. Three of its failures were the safety check refusing every attempt — but **two of those three were the model replying with nothing at all**, having spent its whole word budget thinking. That is our harness starving it, not a bad query being caught. Last night it ran again with four times the budget and nothing else changed.

| | score | fully correct | made something up |
|---|---:|---|---:|
| original budget | 0.5000 | — | — |
| **4x budget** | **0.5367** | 11 of 30 | 3 |

**It moved +0.0367 — essentially not at all.** The token budget was not what was holding it back, which makes yesterday's figure safe to quote and strengthens the comparison rather than weakening it.

Where its questions ended up this time:

| outcome | questions |
|---|---:|
| worked — query ran and produced evidence | 20 |
| **our reader's limitation** — query ran, output not understood | 5 |
| the safety check refused every attempt | 5 |

## 3. Does the system give the same answer twice?

Every score so far came from running each version **once**. If a version wanders between runs, differences of a few hundredths between versions are meaningless. Two extra runs of two versions settle it — and for the templated one this costs nothing to check, because the answers can simply be compared character by character.

- **Normal system (pre-written query templates)**, repeat `repeat-deterministic-r2`: every answer identical
- **Normal system (pre-written query templates)**, repeat `repeat-deterministic-r3`: every answer identical
- **LLM-assisted (AI writes the prose answer)**, repeat `repeat-gold_loop_llm-r2`: 24 of 30 answers differed
  - differed on: H-ABS-01, H-CHN-01, H-CHN-02, H-CHN-03, H-CTM-01, H-CTM-02, H-CTM-03, H-CTM-04, H-EXE-01, H-GRP-01
- **LLM-assisted (AI writes the prose answer)**, repeat `repeat-gold_loop_llm-r3`: 27 of 30 answers differed
  - differed on: H-ABS-01, H-CHN-01, H-CHN-02, H-CHN-03, H-CSQ-01, H-CTM-01, H-CTM-02, H-CTM-04, H-EXE-01, H-GRP-01

**The templated system is exactly reproducible.** Any difference it shows against another version is a real difference, not run-to-run wobble.

## 4. Is the ranking the system's, or the grader's?

The grader used so far is a language model served from the same box the system uses. Last night a **different model** re-graded the *same saved answers* — not new runs, the identical files — so any difference is the grader and nothing else.

| version | our grader | independent grader | difference | agreement |
|---|---:|---:|---:|---:|
| Normal system (pre-written query templates) | 0.9467 | 0.9833 | -0.0367 | -0.01 |
| No templates (works the schema out at run time) | 0.9690 | 0.9828 | -0.0138 | 0.17 |
| LLM-assisted (AI writes the prose answer) | 0.9773 | 0.9833 | -0.0060 | 0.37 |
| AI writes the database query itself | 0.5241 | 0.7407 | -0.2167 | 0.67 |

*Difference* is how much more generous our grader is. A consistent offset across all four rows is harmless — it cancels out of every comparison. An offset that varies by version is not, because then the grader is picking a winner. *Agreement* is how closely the two graders rank the same questions; near 1.0 means they disagree on the absolute score but not on which answers are better.

- `H-CTM-03` (AI writes the database query itself): ours 0.30, independent 1.00
- `H-ABS-01` (AI writes the database query itself): ours 0.35, independent 1.00
- `H-CHN-01` (AI writes the database query itself): ours 0.40, independent 1.00
- `H-CTM-01` (Normal system (pre-written query templates)): ours 0.95, independent 0.50
- `H-REV-01` (Normal system (pre-written query templates)): ours 0.60, independent 1.00
- `H-CTM-01` (No templates (works the schema out at run time)): ours 0.90, independent 0.50

Those are worth reading by hand — a question where two graders disagree by half a point is usually a question where the expected answer is ambiguous, which is a defect in the question set, not in either grader.

## 5. The merged-database counterfactual

The project's pitch is that keeping the two databases separate, each in its own language, is worth the complexity. The obvious alternative — pour both into one database — has never been built, so the pitch has never been contrasted with anything. Last night did the mechanical half: load both sources into a separate, isolated database and prove they can still be told apart inside it.

_The merged load did not run._

## 6. What ran

| phase | what it did | result | time |
|---|---|---|---:|
| `preflight` | graphs live, bank 1 and its judgments on disk | ok | 18s |
| `N1` | draw and author a second bank, disjoint from all prior anchors | ok | 739s |
| `N2-run-deterministic` | run deterministic on bank 2 — the default cascade (templates) | ok | 1s |
| `N2-judge-deterministic` | grade deterministic on bank 2 | ok | 221s |
| `N2-run-generic` | run generic on bank 2 — no templates — schema-derived primitives only | ok | 273s |
| `N2-judge-generic` | grade generic on bank 2 | ok | 190s |
| `N2-run-gold_loop_llm` | run gold_loop_llm on bank 2 — authored plan + LLM narrator | ok | 275s |
| `N2-judge-gold_loop_llm` | grade gold_loop_llm on bank 2 | ok | 362s |
| `N2-run-llm_query` | run llm_query on bank 2 — a language model writes the query itself | ok | 1087s |
| `N2-judge-llm_query` | grade llm_query on bank 2 | ok | 130s |
| `N2-split` | split the bank-2 LLM-query failures by cause | ok | 0s |
| `N3-run` | re-run the query-writing arm at 4x the token budget | ok | 1010s |
| `N3-judge` | grade it | ok | 140s |
| `N3-split` | split its failures by cause | ok | 0s |
| `N4-deterministic-r2` | repeat run 2 of deterministic on bank 1 | ok | 1s |
| `N4-deterministic-r3` | repeat run 3 of deterministic on bank 1 | ok | 1s |
| `N4-summary-deterministic` | does deterministic answer identically when re-run? | ok | 0s |
| `N4-gold_loop_llm-r2` | repeat run 2 of gold_loop_llm on bank 1 | ok | 168s |
| `N4-gold_loop_llm-r3` | repeat run 3 of gold_loop_llm on bank 1 | ok | 204s |
| `N4-summary-gold_loop_llm` | does gold_loop_llm answer identically when re-run? | ok | 0s |
| `N5-cross-deterministic` | re-grade deterministic on bank 1 with local | ok | 1329s |
| `N5-cross-generic` | re-grade generic on bank 1 with local | ok | 1623s |
| `N5-cross-gold_loop_llm` | re-grade gold_loop_llm on bank 1 with local | ok | 1115s |
| `N5-cross-llm_query` | re-grade llm_query on bank 1 with local | ok | 2671s |
| `N6` | load ATT&CK and CAPEC into the merged store and prove separation | **failed** | 301s |
| `N7` | write the morning report | **None** | 0s |

**`N6` failed:** `RuntimeError: bolt://localhost:5458 never became reachable`

**`N7` failed:** `None`

## 7. What is worth doing next

- **Write the night into the research record** as an experiment — until it is in `docs/research/`, none of it counts.
- **Build the arm that queries the merged database**, now that the database itself exists and is verified. That is the last claim with no comparison behind it.
- **Read the questions where the two graders disagreed most** (§4) — those are likely faults in the question set.
- **30 commits are still local.** Nothing has been pushed.

