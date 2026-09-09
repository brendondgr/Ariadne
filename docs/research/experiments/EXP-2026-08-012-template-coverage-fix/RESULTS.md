# EXP-2026-08-012 — Results

Two fixes were proposed. **One shipped. One turned out to be a decision rather
than a defect and is left to its owner** (ISSUES.md I1).

All figures are on the same 182 external questions as EXP-2026-08-010, scored
the same way, with no language model in the metric.

## Headline

| | before | **shipped (Fix 2)** | if Fix 1 is also taken |
|---|---:|---:|---:|
| external recall | 0.6836 | **0.7633** | 0.9825 |
| exact match | 0.4451 | **0.6593** | 0.6923 |
| families at 0.000 | 4 of 14 | **0 of 14** | 0 of 14 |
| families matching the ceiling | 8 of 14 | **12 of 14** | 14 of 14 |
| internal answers changed | — | **0 of 60** | 0 of 60 |
| internal query strings changed | — | **0** | 2 |

Ceiling is 0.9863 recall, 0.7033 exact.

## What shipped — the Software↔actor templates

Four question families went from **0.000 to 1.000**, each matching the ceiling:

| family | before | after | ceiling |
|---|---:|---:|---:|
| `groups_for_software` | 0.000 | **1.000** | 1.000 |
| `software_for_group` | 0.000 | **1.000** | 1.000 |
| `campaigns_for_software` | 0.000 | **1.000** | 1.000 |
| `software_for_campaign` | 0.000 | **1.000** | 1.000 |

The change is one builder (`_actor_software`, either end anchorable, following
`_software_techniques`), two dispatch branches placed ahead of the branches that
used to swallow these questions, and one normalizer branch — see ISSUES.md I2
for why the last of those was nearly missed.

## H4, the hypothesis that could have stopped it

**Held completely.** The deterministic arm re-run over both committed banks
produced **60 of 60 answers byte-identical**, clock readings excluded — and with
Fix 2 alone, not one query string moved either.

That was the risk worth pre-registering: the new dispatch branches sit in a long
`if` chain, and adding to such a chain is how a question that already worked
quietly starts going somewhere else. The guard is `not has_technique_entity`,
which keeps every existing actor→technique route exactly where it was, and it is
pinned by six parametrised tests naming the routes that must not move.

## Pre-registered hypotheses

| | prediction | outcome |
|---|---|---|
| **H1** | the four dead families reach 1.000 | **held** — all four, exactly |
| **H2** | the two partial families come within 0.01 of ceiling | **not tested as shipped.** Under Fix 1 they reach 0.979 and 0.975 against 0.990 and 0.988 — gaps of 0.011 and 0.013, narrowly outside the pre-registered tolerance |
| **H3** | overall recall ≥ 0.95 | **not met as shipped** (0.7633). Met only with Fix 1 (0.9825). H3 assumed both fixes would land; one did |
| **H4** | no internal answer changes | **held** — 60/60 identical, 0 query strings moved |
| **H5** | the plan-free arm gains less | **not measured.** The plan-free arm was not re-run; with only half the change shipping, the comparison would price a smaller intervention than the hypothesis described |

Three of five hypotheses were written assuming both fixes would ship. Recording
that plainly is more useful than re-scoping them after the fact.

## What this does not show

- **A fix measured on the benchmark that found it.** These six families are no
  longer a blind test. This shows the diagnosis was right and the change is
  safe. It cannot show the system now generalises — only a benchmark nobody has
  optimised against could.
- Same limits as EXP-2026-08-010: Enterprise ATT&CK only, enumerating questions
  only, CAPEC untouched, machine-authored phrasing.
- The generic arm was not re-run and cannot have moved: `build()` returns
  `self._build_generic(resolved)` before any changed line.

---

## Addendum, same day — H5 measured after all

H5 was recorded above as "not measured". It has since been run, on the same
fixed 60 questions, after both shipped changes (the templates and D-024's
composer fix):

| arm | recall | exact |
|---|---:|---:|
| ceiling | 0.9953 | — |
| plan given (templates) | 0.8184 | 0.7000 |
| plan-free (it plans from the question text) | 0.6934 | 0.6333 |

**H5 held.** It predicted the plan-free arm would gain less from the fix,
because it must still infer the entity types the new dispatch branches key on.
It gained **+0.080** (0.6132 → 0.6934) against the plan-given arm's **+0.101**
(0.7170 → 0.8184), so the gap widened from −0.1038 to **−0.1250**.

The qualification from ISSUES.md I7 still travels with it: a "given" plan
supplies a source name and three entity strings, not the anchor. −0.125 is what
those few words are worth.

**The composer fix changed no external figure.** Recall 0.7633 and exact 0.6593
before and after, to four decimals — it moved prose and not one identifier,
externally as well as on the internal banks.

## AMENDMENT A-1 (2026-09-09) — Commit, entrypoint and placeholders corrected; pointers hashed; Addendum figures given a machine-readable source

Written during the 2026-09-09 record audit. **No figure above changes**: the
headline (0.7633 / 0.7872 / 0.6593, 0 of 14 empty, 12 of 14 at ceiling) and the
Addendum (0.8184 / 0.7000 plan-given on the fixed 60; 0.6934 / 0.6333
plan-free; gap −0.1250; oracle 0.9863) were re-scored from the stored post-fix
answers with `scripts/external_validation.py::score_cell` and reproduce
exactly. Not re-verified: "60 of 60 internal answers byte-identical" and the
Fix 1 counterfactual 0.9825 (no stored answer set; ISSUES I1, I5).

**Manifest fields corrected in place (old → new), ISSUES I5:**

| field | old | new |
|---|---|---|
| `code.commit` | `0e06ceef8bce9c1a4c33c5c20046d3a0ecf37fd5` (pre-registration tree; the builder is absent from it) | `887c2cddb75d260ce32385d0c0b724b18051fcc5` (the tree behind every surviving artifact; headline first measured on `54cdb3a22972f81114468a50d71a6e033a439fee`) |
| `code.entrypoint` | `… --out docs/evaluation/external-2026-08-21-fixed` (never existed) | `… --out docs/evaluation/external-2026-08-21-post-fix` |
| `compute.hardware` | `<cpu/gpu, ram>` | `unknown` |
| `llm.model` | `<provider>/<model>@<version-or-date>` | `relay/unknown@2026-08-21` (llm arm only) |
| `llm.max_tokens` | 2048 | 16384 |
| `llm.nondeterminism_note` | template text | one run per arm; deterministic arms byte-reproducible |

**`data/metrics.json`** held only the oracle and deterministic cells. It now
also carries `manifest_metrics` (every manifest value, including the six that
were previously only typed into the manifest: `external_recall_before` 0.6836,
`external_exact_before` 0.4451, `internal_answers_identical` 60,
`plan_free_recall_after_fix` 0.6934, `plan_given_recall_after_fix_same_60`
0.8184, `plan_free_minus_plan_given` −0.1250) and `addendum_h5`, the subset-60
and plan-free cells re-scored on 2026-09-09 from
`external-2026-08-21-post-fix/`.

**`data/POINTERS.md`** was the blank scaffold and now hashes the post-fix run
directory, its three answer directories and three summaries. The oracle
directory's tree hash is identical to EXP-2026-08-010's — the ceiling did not
move.

**Linkage.** This experiment refines EXP-2026-08-010 (its "Superseding note"
points here); EXP-2026-08-010 keeps `status: complete` and names this
experiment in `related`. No supersession link is set: EXP-2026-08-010's figures
remain the "before" side of every delta here.
