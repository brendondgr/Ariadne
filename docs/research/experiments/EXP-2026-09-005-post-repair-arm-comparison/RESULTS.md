# RESULTS — EXP-2026-09-005

## The gap survives, and the grader did not notice the repair

| | pre-repair | post-repair | move |
|---|---:|---:|---:|
| deterministic, judged correctness | 0.4934 | **0.4946** | +0.0012 |
| generic, judged correctness | 0.6576 | **0.6569** | −0.0007 |
| **judged gap** | 0.1642 | **0.1623** | −0.0019 |
| deterministic, model-free recall (dev) | 0.4492 | **0.5176** | **+0.0684** |
| generic, model-free recall (dev) | — | 0.6058 pooled / 0.6756 reweighted | — |

568 judgments per arm, 284 cases, **zero grading failures**. Order effect
+0.0043 for deterministic and −0.0063 for generic — both inside the ~0.01
EXP-2026-08-022 measured, and counterbalancing removes them.

**The headline claim is now defensible.** The 0.1642 gap was measured against a
baseline carrying three retrieval defects; repaired, the gap is 0.1623. A
reviewer can no longer say the template arm was simply broken.

## The finding nobody asked for

The deterministic arm's **retrieval improved by 0.0684** on these same 284
questions and its **judged score moved by 0.0012** — inside the grader's own
measured spread of 0.0050 (EXP-2026-09-002 I-5). Statistically, the grader did
not see the repair at all.

Three defects were fixed. 24 questions became answerable that the graph could not
previously answer. Property reads went 0.3958 → 0.6395. A category's members are
now retrieved instead of its status. **None of it reached the score a reader of
the answers assigns.**

That is a claim about the composer, and it is consistent with what this project
already recorded: the deterministic composer's `summarize()` is an id line, and
`ariadne-e2e-sufficiency-ceiling` names exactly this ceiling. Retrieval is no
longer the binding constraint on the deterministic arm — **the answer is**.

## What this does and does not license

**Does:** quoting 0.1623 with the baseline's defects named and repaired. Saying
that schema-assembled queries beat a hand-written template library on the
templates' own catalogues, at a grader-measured 0.16 and a model-free 0.09
pooled / 0.16 reweighted.

**Does not:**
- Any claim about `llm_query`. It was not re-run; its 0.3712 remains a budget
  artifact and must not be cited.
- Any claim that the generic advantage is uniform. On multi-hop (D6) the
  deterministic arm **leads**, 0.3548 to 0.0717.
- Any claim about the holdout, which stays sealed.
- Reading +0.0684 as the repair's full value: two scorer defects recorded in
  EXP-2026-09-004 (id vocabulary, abstention credit) still depress both arms,
  the first by 0.185 on the subset where it was measured.

---

## AMENDMENT A-2 (2026-09-09) — Record repair: pointers moved under later sidecars, the pre-repair baseline was unpinned, one sentence mixes scoring rules

(A-1, 2026-09-04, is in `ISSUES.md`; numbering continues here.) Written from
the 2026-09-09 audit (`verify-b5.md`), the pointed directories, `git log`, and
EXP-2026-09-007's `data/recall-summary.json`. The audit reproduced every judged
figure from the `.judgment.json` / `.judgment.pass2.json` sidecars —
**0.4946 / 0.6569 / 0.1623**, passes 0.4924 / 0.4967 and 0.6600 / 0.6537 — and
every model-free figure from `post-repair-*.json` (pooled 0.5176 / 0.6058,
reweighted 0.5199 / 0.6756). No number changes.

### 1. Both directory pointers were stale, and why

The tree hashes recorded on 2026-09-03 covered 852 files per arm. Since then
EXP-2026-09-008 and EXP-2026-09-012 wrote gemma grading sidecars into the same
directories (`.judgment.gemma.json`, `.gemma2`, `.gemma_r3` … `.gemma_r10`):
2,840 files under `deterministic/answers` (now 3,692) and 2,556 under
`generic/answers` (now 3,408). **The original 852 files are unchanged** — a tree
hash restricted to `*.json` answers plus `.judgment.json` / `.judgment.pass2.json`
reproduces `sha256:5c0e8d63…` and `sha256:a41681361…` exactly (verified
2026-09-09). Both rows are re-hashed over the directory as it stands, with the
original hashes kept in the description. This is the judge-pass contamination
pattern the project has already recorded: a tree hash over a directory that
later passes write into cannot stay valid, and the fix is to say what was added.

### 2. The pre-repair recall baseline (0.4492) was stored nowhere in this experiment

`deterministic_recall_move_vs_prerepair` (0.0684) is 0.5176 − 0.4492, and
PROTOCOL.md `:49-51` / ISSUES I-3 explain why 0.4492 rather than the published
0.4350. But 0.4492 itself was not in any pointed file: `post-repair-deterministic.json`'s
`recall_before` column equals its `recall` column (both 0.5176), so it does not
carry the pre-repair values. The figure is recoverable only from
EXP-2026-09-007's `data/recall-summary.json` (`pooled.dev_pre: 0.4492`,
`reweighted.dev_pre: 0.5170`, computed by `scripts/score_bank.py
--rescore-property-gold @ 96a72d4` over `expansion-2026-09-01`). That file and
the pre-repair answer directory are now pointed, and the baseline is recorded
as a manifest metric, `deterministic_recall_prerepair_dev: 0.4492` (n = 248
answerable dev questions), so the 0.0684 has a source on both sides (ISSUES
I-8).

### 3. `RESULTS.md:29` compares across scoring rules

*"Property reads went 0.3958 → 0.6395."* 0.3958 is the D1 figure from
`score.json@eeef322` — the **old** scorer, over the **full** 572-question bank
(EXP-2026-09-001 A-5's tier table) — and 0.6395 is the D1 figure from
`post-repair-deterministic.json` — the **property-gold** scorer, **dev only**.
That is exactly the cross-rule comparison ISSUES I-3 forbids for the headline.
The sentence is left as written; the D1 movement under one rule is not recorded
in this experiment and should not be quoted from it. The "24 questions became
answerable" count in the same paragraph was not verified by the audit and has
no pointed source.

### 4. Provenance

`code.commit` was `ed1acfae…` (19:56:04, *"cost table not measured, and why"*),
the commit that wrote this folder up; the manifest's own `dirty` comment said
the arms and grading ran against `a1e20f6` (19:10:13). Answer mtimes
19:10:30–19:32:30 and judgment mtimes from 19:36 are consistent with `a1e20f6`
and not with `ed1acfa`. `code.commit` → `a1e20f6a3283f910a928f9bdb63e9ec463ef5239`;
`dirty` stays false. `environment.lockfile`: env/requirements.lock → null (never
written; ISSUES I-7).

### 5. Later refinement, and the holdout sentence

PROTOCOL.md `:55` (*"288 questions, untouched"*) and the RESULTS line *"Any
claim about the holdout, which stays sealed"* are corrected by A-1
(2026-09-04): the deterministic arm had one model-free look at the holdout,
pre-repair, and no holdout question had been judged. EXP-2026-09-007 then
spent the holdout (2026-09-05) and repeated this comparison on it under the
same grader and protocol: generic 0.6546, deterministic 0.4862, gap **0.1684**
[0.1340, 0.2049] against 0.1623 here; the D6 template lead reproduced (+0.3344
vs +0.2831 dev). It refines this result and does not overturn it; `related`
gains EXP-2026-09-007.

### 6. `data/metrics.json`

Did not exist. Created 2026-09-09 from `metrics.values`.

### 7. `metrics.primary`

Named `judged_correctness_gap`, a key that does not exist in `metrics.values`;
it now names `judged_gap` (0.1623).
