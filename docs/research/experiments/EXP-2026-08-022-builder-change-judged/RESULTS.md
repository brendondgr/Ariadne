# RESULTS — EXP-2026-08-022 The builder change is invisible to the judge

**Status: complete.** Four grading sessions — three forward, one order-reversed —
over 120 answers in two conditions. **The shipped builder change (`9f02dc6`) has
no judged effect on either fresh bank.** The experiment's larger finding is about
the instrument: **grading order biases a paired comparison by about ±0.01**, and
the null control caught it.

## 1. Headline

| bank | null control (byte-identical) | changed answers | **difference-in-differences** |
|---|---|---|---|
| 19 | signed −0.0089, \|d\| 0.0214 | signed −0.0070, \|d\| 0.0149 | **+0.0019 ± 0.0172**, sign unstable |
| 20 | signed +0.0017, \|d\| 0.0166 | signed −0.0150, \|d\| 0.0150 | **−0.0167 ± 0.0170**, sign unstable |

Both corrected effects sit **well inside their own session-to-session spread** and
**flip sign across sessions**. On the pre-registered decision rule this is the
"invisible to the judge" branch.

Pooled counts say the same thing without any arithmetic: across the three forward
sessions the answers the change *touched* regressed **less** often (11.8%) than
the ones it left **byte-identical** (17.2%).

## 2. The finding that outlives this experiment: grading order is a bias

The null control was built as a noise floor. It turned out to be a bias detector.

Across all three forward sessions the byte-identical answers — **the same bytes,
scored twice** — came back with a *signed* difference of **−0.0088 pooled**,
consistently negative. Identical inputs should differ by zero on average. In
every one of those sessions the **old** condition was graded first and the **new**
second.

**A fourth session with the order reversed settled it:**

| | null control, signed difference on byte-identical answers |
|---|---|
| forward (old graded first) — bank 19 / 20 | **−0.0143** / −0.0033 |
| **reversed (new graded first)** — bank 19 / 20 | **+0.0071** / **+0.0167** |

**Both flip sign.** The condition graded **second** scores lower, whichever
condition it is, by roughly **0.01**.

That is the same size as the effect this experiment set out to detect. A paired
judged comparison run in a fixed order **cannot** resolve a difference of ~0.01,
and would report the second-graded condition as worse.

**Consequences beyond this run:**

* **Randomise or alternate grading order in any paired judged comparison**, or
  report a difference-in-differences against a null control. `EXP-2026-08-009`'s
  rule — grade every cell of a comparison in one session — is *necessary and not
  sufficient*: it cancels between-session drift and **creates** within-session
  position bias.
* This is a fourth instance of the recurring pattern in this harness: **a
  procedural artifact that moves a number in a consistent direction**, after
  dropout (I-2), fallback-to-a-stronger-path (`EXP-2026-08-019`) and
  size-correlated grading failure (`EXP-2026-08-021` I-8).

## 3. Hypotheses

| | Outcome |
|---|---|
| **H1** — null control signed ≈ 0 | **FAILED.** −0.0088 pooled forward, and the failure was informative: it is grading order, proved by reversal. See §4 |
| **H2** — new builder not worse | **Held.** DiD +0.0019 and −0.0167, both inside their spread, both sign-unstable |
| **H3** — movement confined to the changed answers, exceeding the floor | **Refuted.** The changed set moves *less* than the control on the count test and no more on the mean |
| **H4** — among changed answers, more improve than regress | **Not evaluable as written.** See §5 — the ceiling forecloses it |

## 4. H1 failed, and the pre-registered rule was to stop

`PROTOCOL.md` §5: *"H1 fails → stop. Report the session comparison as void and
re-run; nothing else in this experiment is interpretable."*

H1 failed. A difference-in-differences correction was available and defensible —
and **adopting it after seeing the numbers would have been fitting the analysis
to the result**, which is the failure this project measures in others (`C-021`)
and the reason `EXP-2026-08-020` Step 6 refused to tune a threshold on the bank
it reported.

So the rule was honoured in substance: a **new session was run**, with the one
variable the diagnosis named. The reversal was a *prediction* — the control must
flip sign — recorded before that session ran, and it flipped on both banks. The
DiD is reported **because an independent test confirmed the mechanism it
corrects**, not because it rescued the result.

**Deviation recorded:** the rule said re-run and it was interpreted as re-run
*the diagnostic*, not the whole three-session design. A full re-run under
randomised order would be cleaner. It is not free (~4 sessions) and the null is
now supported three independent ways — DiD, count test, sign instability — so it
was judged not worth the server time. **A reader who disagrees should discount
§1 to the count test alone, which needs no correction at all.**

## 5. The ceiling forecloses "is it better?", and that is a limit of the banks

**29 of the 31 changed answers scored 1.0 under the old builder.** They could only
stay or fall.

| bank | set | n | at 1.0 | could improve |
|---|---|---|---|---|
| 19 | changed | 16 | **15** | **1** |
| 20 | changed | 15 | **14** | **1** |

An early reading of "0 improved, 5 regressed" looked like a directional signal.
It was not: **it was 0 improved out of 2 that could.** Quoting an
improvement/regression count without the headroom that permits it is the same
error as quoting a judged mean without its `n`.

**So this experiment can say `9f02dc6` is not a regression here, and cannot say it
is an improvement.** Not because the change is small, but because these banks
leave no room to show one. Demonstrating improvement needs a question set where
the deterministic arm is *not* already at ceiling — which is what the paraphrase
variants of `EXP-2026-08-020` are, and where `9f02dc6` already reports +18/−8.

## 6. What this licenses

* **`9f02dc6`'s regression-evidence gap is closed for these banks.** Its own check
  covered the 120-question catalogue and the variant bank, not the two fresh
  banks — and those carry **C-012, C-021 and C-022**. Half their answers moved.
  They are now checked, and nothing moved that a judge can see.
* **Judged figures recorded before `9f02dc6` may be quoted after it**, for these
  banks. That is the practically useful result: it means C-012, C-021 and C-022
  do not need re-measuring because of the builder change.
* **Step 4/A of the migration plan is now cheaper.** The judged arms still need
  the `758813f` worktree to isolate the *model*, but the builder contributes no
  judged difference on these banks, so an uncorrected comparison would not be
  misled by it.

## 7. Threats to validity

* **The order bias is measured on one reversed session per bank.** Its existence
  is established by a sign flip on both banks; its *magnitude* (~0.01) rests on
  few sessions.
* **n = 30 per bank**, and the deterministic arm is bunched near 1.0, so this
  design has little power for any effect. The bootstrap interval over *questions*
  is roughly ±0.06 (`EXP-2026-08-009`) — far wider than anything here. **A grader
  sd is not an interval on the builder change.**
* **Retrieval is unchanged on 59 of 60 answers**, so nothing here speaks to
  retrieval quality. The one retrieval change is an improvement and is a single
  case.
* **Only the deterministic arm.** The LLM arms were not re-run; a builder change
  could interact with a narrator differently.
* **The grader is `qwen38-27B-v2`**, calibrated at r = 0.9612 against Sonnet but
  not itself a publication instrument (`D-002`, `C-009`).

## 8. Reproduction

```bash
for b in 19 20; do
  uv run python -m utils.evaluation.experiment_untruncated --arm deterministic \
    --bank docs/evaluation/banks/bank-2026-08-$b/bank.json \
    --root docs/evaluation/experiments/builderiso-b$b-newbuilder --workers 4
done

# three forward sessions (old first), then one reversed (new first)
for s in bld1 bld2 bld3; do for b in 19 20; do
  for root in "bank202608$b" "builderiso-b$b-newbuilder"; do
    uv run python -m utils.evaluation.judge_answers \
      --root "docs/evaluation/experiments/$root" --arm deterministic --suffix ".$s" --workers 12
  done
done; done
for b in 19 20; do for root in "builderiso-b$b-newbuilder" "bank202608$b"; do
  uv run python -m utils.evaluation.judge_answers \
    --root "docs/evaluation/experiments/$root" --arm deterministic --suffix ".bldrev" --workers 12
done; done

uv run python scripts/builder_change_judged.py \
  --old docs/evaluation/experiments/bank20260819 \
  --new docs/evaluation/experiments/builderiso-b19-newbuilder \
  --suffixes .bld1 .bld2 .bld3 .bldrev
```

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — `data/metrics.json` created; answer-directory pointers re-pinned; wall clock, dirty tree and seeds recorded

**`data/metrics.json` did not exist.** The manifest's seven values had no
machine-readable source in the folder. The file now holds the verbatim `--out`
of `scripts/builder_change_judged.py` for both banks, run 2026-09-09 over the
pointed answers and judgments, plus a `derived` block for the pooled figures
and a `manifest_metrics` copy. Everything reproduces exactly: per-session DiD
[−0.0138, −0.0023, +0.0308, −0.0071] → **+0.0019 sd 0.0172** and [−0.0166,
+0.0033, −0.0100, −0.0434] → **−0.0167 sd 0.0170**, both sign-unstable; forward
null control −0.0143/−0.0071/−0.0214 and +0.0033/−0.0133/0.0000 → **−0.0088**
over six sessions; reversed +0.0071 / +0.0167 → **+0.0119**; regressions among
byte-identical answers 8 + 7 = 15 of 87 → **0.1724**, among changed answers
6 + 5 = 11 of 93 → **0.1183**; changed answers scoring 1.0 in the old `.bld1`
pass 15 + 14 = **29** of 31.

**Pointers.** The four answer-directory rows in `data/POINTERS.md` recorded a
digest over the 30 answer files (`sha256:ecb8c1c2…`, `c9206758…`, `1310e640…`,
`b790beb7…`), while the validator hashes a directory as a tree including every
judgment sidecar — so they reported a mismatch although nothing had changed.
Verified 2026-09-09: the 30-file digests still reproduce byte-for-byte for all
four directories. The rows now carry tree hashes computed with
`utils.research_record.hashing` (`sha256:e034f420…` 828,548 B; `e18d54a8…`
607,473 B; `264c26e3…` 893,664 B; `ae336a06…` 694,890 B). The `bank2026*`
trees include gradings from EXP-2026-08-008/009/021 and later passes
(`.judgment.json`, `.c015`, `.cross`, `.g31`, `.g31p2`, `.qwen38…`); the
`builderiso-*` trees hold only this experiment's `.bld1/.bld2/.bld3/.bldrev`
sidecars. The sixteen judgment-set rows (glob paths) are unchanged and remain
the stable pins.

**Wall clock.** `compute.wall_clock_hours: 0.0`. From file mtimes on
2026-08-31: new-builder answers 17:45–17:5x, `.bld1` 17:57–18:48, `.bld2`
18:49–19:29, `.bld3` 19:29–19:53, `.bldrev` 19:54–20:17. **Old → new:** `0.0`
→ `2.5`.

**Dirty tree.** `code.dirty: true` with the ISSUES template empty.
`code.commit` `bfac8cc` (17:47) precedes the run; `git show --stat 338ad90`
(20:19) shows `scripts/builder_change_judged.py`, PROTOCOL, RESULTS and this
folder entering the repository together after the four sessions — the script
was uncommitted while it ran. The answer path was committed at `bfac8cc`
(new) and at the pre-`9f02dc6` tree (old), both LLM-free. Recorded in ISSUES,
with `seeds: []` (no seed parameter on the grader; both answer conditions are
byte-reproducible).

## AMENDMENT A-2 (2026-09-09) — the primary metric now names a recorded key

`metrics.primary` was `difference_in_differences`, a descriptive label that matched no key in
`metrics.values`, so `INDEX.md` and `CURRENT.md` rendered this experiment's
headline as "not recorded". It now names `did_bank19` — the difference-in-differences on bank 19. No value changed.
