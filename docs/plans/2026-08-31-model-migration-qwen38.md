# Plan — migrating the record onto `qwen38-27B-v2`

**Status:** proposed, 2026-08-31. Nothing below has been run.
**Trigger:** the relay alias `skynet` was repointed a third time.
**Owner decision required at Step 1 and Step 4.**

---

## 1. What changed, and how we know

`skynet` now serves **`qwen38-27B-v2`**. Verified this session by issuing a
completion and reading the `model` field off the response envelope:

```bash
uv run python scripts/model_identity.py
```

```
  auto    ->  qwen38-27B-v2
  local   ->  gemma-4-26B-it
  skynet  ->  qwen38-27B-v2   [relay advertises 'auto']
```

`GET /v1/models` is **not** sufficient — the relay reports `skynet` with
`upstream_model: "auto"` because it hot-swaps, which is precisely why the
previous two swaps went unnoticed.

**This is the third model behind one alias.**

| Era | Model | Shape |
|---|---|---|
| July 2026 | Gemma 4 31B | dense, quantisation never recorded |
| ~August, exact start **unknown** | **undetermined** | ⚠️ covers `EXP-2026-08-007`, `-008`, `-009` |
| 2026-08-24 | `Ornith-1.5-35B-A3B-W4A16-SYM` | MoE, ~3B active of 35B, 4-bit weights, 96k context, 16-way concurrency |
| **2026-08-31** | **`qwen38-27B-v2`** | quantisation, `max_model_len`, concurrency **unconfirmed** |

The operator states this is the model the project will stay on. That makes now
the right moment to put the record on one model deliberately, rather than
discovering a fourth swap later.

---

## 2. The taxonomy that decides everything below

The model plays **three separate roles**, and a result depends on the swap only
through the roles it actually used.

| Role | Where | Which results depend on it |
|---|---|---|
| **R1 — answer path** | planner drafter, narrator, claims composer, LLM query builder | Arms B/C/D/E/F, `generic` (narrator), `llm_query`, `llm_claims` |
| **R2 — grader** | `utils/evaluation/judge_answers.py` | **every judged figure from 19 August onward** |
| **R3 — bank author** | `utils/specialists/evalset/author.py`, `make_bank.py` | the banks are **frozen artifacts**; the author is not in any measurement loop |

**The single most important consequence:** the swap moved R1 **and** R2 at the
same time. Re-running a judged arm now changes two variables at once and the
result is uninterpretable. **Separate them, and do R2 first**, because R2 can be
isolated for free — the answers are already on disk.

---

## 3. Triage — what to re-run, re-grade, and leave alone

### 3.1 Leave alone. No model participates in the metric.

Re-running these costs days and cannot change a number.

| Experiment | Primary metric |
|---|---|
| `EXP-2026-08-004`, `-005`, `-006` | retrieval coverage, deterministic arms |
| `EXP-2026-08-010`, `-012` | external benchmark recall — *"No language model participates in any score"* |
| `EXP-2026-08-013` | tri-source retrieval — no model in the answer path |
| `EXP-2026-08-014` | verifier ablation — deterministic composer |
| `EXP-2026-08-015` | ten-bank resampling — both arms LLM-free |
| `EXP-2026-08-016` | safety and leakage probes — no model |
| `EXP-2026-08-017` | node-edit counts — no model |
| `EXP-2026-08-020` | variant robustness — every LLM seam off; variants Sonnet-authored and frozen |
| retrieval halves of `-001`, `-003`, `-011` | set-membership against gold |

**This is the payoff of the LLM-free design and it should be said out loud in
the paper:** a model swap invalidates roughly a fifth of this record, not all of
it, because most of the primary metrics take no model.

### 3.2 Unaffected for a different reason — the judge was never local

| Experiment | Judge |
|---|---|
| `EXP-2026-08-002` (blind holdout) | one **Sonnet 5** agent per question |
| `EXP-2026-08-011` A-7, A-9, A-10 | panels of **10 / 12 / 6 Sonnet judges** |

Provider-hosted, so the local swap does not touch them. **This is the argument
for using the cross-model panel for anything that will be quoted externally**,
and it is now an argument from experience rather than from principle.

### 3.3 Do **not** re-run

- **The July seven-arm study.** Those weights are gone. Re-running it produces a
  *new* study, not a reproduction. If the arm matrix is wanted on `qwen38`, it
  is a new experiment with a new ID and the July record stays as history.
- **Any frozen bank.** Banks are inputs. Re-authoring them on a new model
  destroys cross-experiment comparability and burns every holdout in the record.
  `D-006`-style discipline applies: a bank is drawn once.
- **Anything in §3.1.** Twice, because the temptation to "refresh everything"
  is exactly how a record loses its comparability.

### 3.4 Re-grade — saved answers, grader-only change

Byte-identical inputs, one variable. These three carry live claims and were
graded in the window where **the serving model is not determinable**.

| Experiment | Cells | Claims at risk |
|---|---|---|
| `EXP-2026-08-007` | 3 arms × (30 blind + 120 catalogue) | C-001, C-014, C-017, C-021, C-023 |
| `EXP-2026-08-008` | 4 arms × 30 fresh + 1 catalogue re-run | **C-012**, C-021 |
| `EXP-2026-08-009` | 8 cells | **C-022** (and C-015's refutation) |

### 3.5 Re-run — the answer path genuinely changes

| Arm | Why | Claim |
|---|---|---|
| **`llm_query`** | **The falsification target.** A more capable model writing its own Cypher and Gremlin is exactly the condition that threatens C-012, the project's one unambiguously positive claim | **C-012** |
| `gold_loop_llm` (Arm F) / `generic` + narrator | The narrator is the only LLM role on any recommended path | C-005, C-006 |
| LLM planner drafter (Arms B/E shape) | C-002's whole content is what an LLM planner costs | C-002 |
| `llm_claims` (`EXP-2026-08-018` replication) | The only configuration in which the verifier gates fire. Whether the `correlated` gate still dominates on a different model is what turns that from an anecdote about one model into a pattern | **C-017** |

---

## 4. Sequence

### Step 0 — confirm the serving facts (operator, minutes)

`scripts/model_identity.py` gives the model id. The rest must come from the
serving side, exactly as `Q11`/`Q12` were answered:

- `max_model_len` — **load-bearing.** Ornith served 96,000 and two evaluation
  questions (`C-SCN-01`, `F-CWE-05`) already overflowed it. A smaller window
  breaks the un-truncation profile and silently changes which questions are
  answerable.
- quantisation and parameter shape (dense or MoE, active parameters).
- concurrency ceiling at full context.
- **whether it is a reasoning model**, and its thinking budget. The current
  `.env` sets `SYNTHESIS_LLM_THINKING_BUDGET=4096`; a model that spends its
  budget thinking truncates to empty below roughly 2048 and the failure looks
  like "LLM unavailable" rather than like a truncation.

Record all of it against `Q11`/`Q12` before anything is run.

### Step 1 — calibrate the grader (hours) · **gate**

```bash
uv run python -m utils.evaluation.judge_answers \
  --root docs/evaluation/experiments/holdout-v1 --arm deterministic --calibrate
```

Produces `r` and mean-delta against the **committed Sonnet judgments**, directly
comparable to the Ornith-era **r = 0.9275, +0.031**.

**Pre-register the gate before looking:**

| Outcome | Action |
|---|---|
| r ≥ 0.90 and \|delta\| ≤ 0.05 | Proceed. `qwen38` is usable for arm comparison, not for publication figures |
| 0.80 ≤ r < 0.90, or \|delta\| ≤ 0.10 | Proceed for *ordering* only. Levels are not quotable at all |
| r < 0.80, or \|delta\| > 0.10 | **Stop using the local grader.** Escalate everything to the Sonnet panel |

Nothing downstream is interpretable without this number, and it costs one run
over 30 saved answers.

### Step 2 — re-grade the saved answers · **file as `EXP-2026-08-021`**

Grade §3.4's cells with `qwen38`, **all of them in one session** so the grader
cancels out of every within-session comparison — the discipline
`EXP-2026-08-009`'s protocol exists to enforce.

**This is not bookkeeping; it is a free experiment the project has never been
able to run.** Two different local models grading byte-identical answers gives
the first measurement of **grader-model sensitivity**. The existing 0.0050
"grader spread" was measured *within one model over three passes* and says
nothing about this.

Pre-registered hypotheses:

- **H1** — arm *ordering* is preserved on every cell. *(If it is not, no judged
  comparison in this record survives, and that is the finding.)*
- **H2** — the between-model spread exceeds the 0.0050 within-model spread by at
  least an order of magnitude, as the `skynet`-vs-Sonnet gap did on the identity
  bank (0.43).
- **H3** — C-012's margin (0.9467 vs 0.5000) survives any grader. It is 0.45
  wide; nothing plausible closes it.

Decision rule, written first: if H1 holds, the affected claims keep their
direction and gain a "reproduced under a second grader" note. If H1 fails on any
cell, that cell's claim drops to `partial` pending a Sonnet panel.

### Step 3 — re-measure the engagement regime before judging any LLM arm

**Do not skip this, and do not fold it into Step 4.** `EXP-2026-08-019`
established that the binding constraint is the **120-second read timeout**, not
concurrency, and that fallbacks *inflate* measured quality — r(fallbacks, gold)
= **+0.62**, because a timed-out LLM call falls back to the deterministic
composer, which scores better than the arm under test.

A dense 27B and a 35B MoE with ~3B active have very different per-token latency.
**The timeout will bite differently and the fallback rate will move for reasons
that have nothing to do with quality.** Measure first:

- one short narrator run at the standing `SYNTHESIS_LLM_TIMEOUT_S=120.0`,
  recording per-request latency, fallback count and fallback reason;
- re-tune the timeout and worker count so engagement is comparable to the
  Ornith-era baseline (86–88% at 16 workers);
- **report engagement beside every score from here on**, per that experiment's
  own recommendation.

### Step 4 — re-run the answer-path arms · **new experiment, pre-registered** · **gate**

One night, `scripts/measure_arms.py`, graded by the Step-1-calibrated grader.

**Pre-register C-012's falsification before the run**, because this is the
claim a better model most plausibly overturns:

> **H4** — on the same fresh bank, `llm_query` on `qwen38-27B-v2` scores below
> the template cascade by more than the grader's spread.
>
> - **Holds** → C-012 is reproduced across two model generations and becomes
>   materially stronger. Restate it as *"across two locally-served models a
>   generation apart"*.
> - **Fails, gap narrows but persists** → C-012 becomes **model-conditional** and
>   must say so in its own sentence. This is the likely outcome and it is not a
>   defeat; "the advantage of authored structure shrinks as models improve" is a
>   better paper than "templates win", because it is a *trend* claim with a
>   mechanism.
> - **Fails, gap closes or inverts** → C-012 drops to `refuted`, and the primary
>   result reverts to C-023, which does not depend on any model.

### ⚠️ Step 4 has acquired a second variable, and the plan above no longer isolates the model

**Added 2026-08-31, after `9f02dc6` landed mid-run.** That commit flipped
`ARIADNE_LEXICON` and `ARIADNE_EXACTNAME` to default **on** and moved name
resolution to the top of `build()`. It is a good change, properly regressed — and
it means **the tree that would produce Step 4's answers is no longer the tree
that produced the answers Step 4 compares against.**

Re-running the arms now varies *model* **and** *builder* at once, which is
exactly the confound Step 2 was designed to avoid on the grader side. Three ways
out, and the choice must be made before the run rather than explained after it:

| Option | What it measures | Cost |
|---|---|---|
| **A — isolate the model.** Re-run from a worktree pinned at `758813f` (pre-`9f02dc6`) with the new model | The model change alone, comparable to the recorded arms | one extra worktree; `data/` and `.env` symlinked per the usual setup |
| **B — isolate the builder.** Re-run at `HEAD` with both flags forced `0` | The builder change alone, on the new model | one flag pair, no worktree |
| **C — measure the current system and say so.** Re-run at `HEAD` with defaults | What a user gets today. **Not** attributable to either change | cheapest, and the least informative about *why* anything moved |

**Recommended: A and B, in that order, then C for free** — B is a flag flip on the
same run, so A+B costs one extra pass and yields a clean 2×2. Doing C alone would
produce a number that cannot be attributed, which is the defect `D-028` was
written about, reappearing on a different axis.

#### Measured 2026-08-31, and it narrows the problem considerably

The builder half was isolated exactly, because **the deterministic arm has no
model in it**: re-running it at `HEAD` over both fresh banks and diffing against
the committed answers varies the builder and nothing else. It costs 1.2–1.5 s per
bank.

| of 60 deterministic answers, clock keys excluded | |
|---|---|
| byte-identical | **29** |
| **answer text changed, retrieval identical** | **30** |
| retrieval changed | **1** |

The one retrieval change is `bank20260820/H-ABS-01`, and it is an **improvement**:
`records 0 → 1, related 0 → 1`, i.e. an anchor that previously resolved to nothing
now resolves. Consistent with `9f02dc6`'s reported +18/−8.

**So `9f02dc6` is, on these banks, a rendering change with one retrieval fix**, and
the confound is far more contained than the three-option table above assumes:

- **Retrieval-metric work can go straight to `HEAD`.** 59 of 60 answers retrieve
  identically, so `gold_in_evidence`, external recall and the isolation counts are
  effectively unaffected. **Option A's worktree is not needed for those.**
- **Judged work still needs the isolation.** 31 of 60 answers carry different
  text, and text is precisely what a judge scores. Re-running any judged arm at
  `HEAD` and comparing to the recorded judgments would mix the builder's prose
  changes into a model comparison.

**⚠️ And this is a gap in `9f02dc6`'s own evidence, recorded without blame.** That
commit reported *"catalogue regression unchanged at 6 better, 0 worse"* — which is
the 120-question **catalogue**. It did not report the two fresh banks, and those
are the banks carrying **C-012, C-021 and C-022**. Half their answers moved. The
change still looks net-positive; the point is that the banks the live claims rest
on were not in the regression check, and the standing rule
(`memory: recorded-answer regression`) says both banks are.

**Revised recommendation:** run **A (worktree at `758813f`) for the judged arms
only**, skip the worktree for anything scored on retrieval, and keep **C** as the
"what a user gets today" number, clearly labelled as attributable to neither
change alone.

**Step 2 is unaffected.** It grades answers already on disk; a builder change
cannot reach them. This note bounds Step 4 only.

### Step 5 — optional, and the most scientifically interesting

Replicate `EXP-2026-08-018` on `qwen38`. The finding worth testing is not the
level but the **shape**: does the `correlated` gate still do almost all the work
(92 cuts against 19 / 1 / 0)? *"A language model proposing claims over federated
evidence characteristically invents cross-source correlations rather than
uncited claims"* is a statement about models. One model makes it an anecdote;
two make it a pattern, and it is the only claim in the record that would
generalise beyond this system.

---

## 5. Cost

| Step | Wall clock | Blocks |
|---|---|---|
| 0 — serving facts | minutes (operator) | everything |
| 1 — grader calibration | ~15 min | Steps 2 and 4 |
| 2 — re-grade saved answers | 2–4 h | C-012, C-021, C-022 provenance |
| 3 — engagement regime | ~1 h | Step 4's interpretability |
| 4 — answer-path arms | one night | C-002, C-005, C-012 |
| 5 — claims composer | ~3 h | C-017 generality |

**Steps 0–2 are the whole of the urgent work** — under half a day, no pipeline
run, and they convert three live claims from "graded by an unidentified model"
to "graded by a named, calibrated one". Steps 3–5 are a night and are worth
doing before any writing starts, so that the paper quotes one model throughout.

---

## 6. Discipline changes, so there is no fourth surprise

Proposed as **`D-028`**:

1. **Never record an alias as a model.** Manifests carry
   `relay/<served-model>@<YYYY-MM-DD>`, the shape `EXP-2026-08-018` established.
2. **Record the served model automatically.** `scripts/model_identity.py`
   exists; wire it into the run harness so `run_meta` carries the served model
   alongside `max_hops` and the rest, instead of the alias. A run that cannot
   identify its model records `unknown`, never a guess (`D-009`).
3. **Fail a judged run on a model mismatch.** If the served model differs from
   the manifest's declared model, stop rather than produce a figure nobody can
   attribute later.
4. **Pinning is not available and recording is the mitigation.** `qwen38-27B-v2`
   is not separately addressable on the relay — only `auto` and `skynet` are, and
   both hot-swap. Detection is therefore the only defence.

---

## 7. What this changes in the ledgers

- **`Q12`** gains the third era and the `model_identity.py` route to answering it
  without asking.
- **`Q11`** reopens for `max_model_len` and concurrency on the new model.
- **C-002, C-005, C-012, C-017** carry a model-provenance note until Step 4.
- **C-021 and C-022** carry one until Step 2.
- **C-009** — *self-judged evaluation overstates* — gets a second, independent
  line of evidence from Step 2 if H2 holds.
- A new experiment `EXP-2026-08-021` for the grader-sensitivity result.
