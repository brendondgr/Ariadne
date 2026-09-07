# Checklist — full conference paper / JMLR

**Target set 2026-09-05** (operator): a full archival paper. Demo track dropped.
**No venue chosen yet, and that is now the binding decision** — page limit
changes what survives the cut (see §6).

Live to-do. Tick things off; do not rewrite history.

---

## 0. Where we actually are

| | |
|---|---|
| **Measurement** | ✅ Closed again, 2026-09-07. It was called closed on 09-06 and was not — see §1 |
| **Positioning — reading** | ✅ **Closed** 2026-09-06 (`Q25`) |
| **Positioning — writing** | ⬜ Not started |
| **Paper prose** | ⬜ **1 of 11 sections** |
| **Artifact / DOI** | 🟡 `LICENSE` ✅, `NOTICE` ✅, appendix draft, **no DOI** |

**44 experiments in the record; `make validate-research` green.**
**Every number in the paper traces to a manifest** — 0 untraced of 86,
`make verify-paper-numbers`, first run 2026-09-07.

---

## 1. Measurement — done, nothing to run

- [x] Empty-query fault fixed; both arms re-measured (`EXP-2026-09-003/-004/-005`)
- [x] Query-writing arm settled at n=284, unstarved baseline
- [x] **Cross-family re-grade of every judged claim** (`EXP-2026-09-006`) — 510
      frozen answers, two named graders, **zero contrast sign flips**
- [x] **Holdout spent** (`EXP-2026-09-007`) — 288 unseen questions, 3 arms,
      2 positions, 2 grader families, **3,456 judgments**
- [x] **Grader calibration** (`EXP-2026-09-008`) — which models can resolve near
      the ceiling, and two of three cannot
- [x] Thinking-cap lever tested and **closed**: it destroys the arm
- [ ] ~~Gold-query resource (`Q26`)~~ — **recommend dropping.** It targets query
      correctness, and the holdout shows that is not the binding constraint
      (retrieval +0.0503 while judged correctness moved −0.0084)

### Reopened and re-closed, 2026-09-07

This section said "nothing remains" on 2026-09-06. Three things did, and each was
found by doing the previous one rather than by planning.

- [x] **`EXP-2026-09-009`** — the query-writing arm across three seeded runs.
      `C-012` rested on one draw; the concern was that run-to-run spread might be
      the size of the margin. It is not: **0.0089 against a 0.0831 margin**. But
      the same runs give **opposite orderings** under the two graders, because
      the second emitted **two distinct values** across 852 judgments.
- [x] **`EXP-2026-09-010`** — do the model-free arms repeat?
      `deterministic` is **284/284 byte-identical** in every scored field, so a
      single run of it is sufficient *by construction*. `generic` is **not**: it
      composes with a language model, and words **143 of 276** answers
      differently on a rerun at the same seed. **The assumption that let the
      primary arm run once was false**, not merely unverified.
- [ ] **`EXP-2026-09-011`** — running. Whether that wording variation moves the
      judged score. First block: **SD 0.0088**. Second block completing.

**The lesson is worth more than the three results.** "Measurement closed" was
asserted, not checked. The assumption underneath it — that the model-free arms
were model-free — was contradicted by a field in every answer artifact
(`run_meta.synthesis`), which nothing had read.

---

## 2. Positioning — reading done, writing not started

- [x] `Q25` closed: CEUR-WS enumerated (12,764 rows), four systems opened in
      full, arXiv field sweep with a validated control, both phantom statistics
      resolved
- [x] **C-022 rewritten** (`D-030`) — its null was false
- [ ] **§2 Related work prose.** Material is in `RELATED_WORK.md` + the sweep;
      **no prose exists**
- [ ] **`Q24` paragraph** — why our failure distribution runs opposite to the
      only comparable published one. One day of writing, open since 2026-08-26,
      and it blocks §9
- [ ] **`Q27` — re-check RAGE-KG 2026 in November**, before camera-ready. Dated
      live risk to C-025; volume does not exist yet but acceptance decisions do

### Things the sweep says the paper must now do

- [ ] **Cite Emonet et al. (arXiv:2410.06062v4) ourselves**, as the
      single-language federated predecessor, *before* a reviewer raises it.
      C-024's novelty rests **entirely** on the two-query-language axis
- [ ] **Carry the TITAN acknowledgement inline** in C-025's section, in the exact
      wording recorded in `CLAIMS.md`
- [ ] **Answer the SPLIT-RAG question in §7.** Their split-vs-merged gap is
      **17.6 Hit points**; ours is neutral. A reviewer *will* ask why. Most
      likely answer: their ablation changes agent count as well as store
      topology, so it is not the same variable
- [ ] Cite **QAnswer's unswept θ₂** — the field holding the abstention knob and
      never turning it
- [ ] Fix two inherited citation errors: **QUINT is WWW 2017** (Riedewald not on
      the demo); **TeBaQA's** substantive paper is SEMANTiCS 2021,
      DOI 10.3233/SSW210038
- [ ] Defensive sentence distinguishing **federated learning** from federated
      query execution — the homonym floods this literature

---

## 3. Prose — 1 of 11 sections

| § | Section | State |
|---|---|---|
| 1 | Introduction | ⬜ framing decided (`D-027`), unwritten |
| 2 | Related work | ⬜ **blocked on nothing now — write it** |
| 3 | System | ⬜ documented, unwritten |
| 4 | Experimental design | ⬜ one `PROTOCOL.md` per experiment |
| 5 | Templates vs schema-derived | ⬜ evidence complete |
| 6 | Templates vs LLM-written queries | ⬜ **needs the grader-dependence caveat** |
| 7 | Federated vs merged | ⬜ **needs the SPLIT-RAG answer** |
| 8 | Co-authored benchmarks | ⬜ evidence complete |
| 9 | Failure localisation | ⬜ blocked on `Q24` |
| 10 | Coverage cliff | ⬜ evidence complete |
| 11 | Limitations | ⬜ material in `OPEN_QUESTIONS.md` |
| — | **Grader calibration** | ⬜ **new — needs a home.** See §5 |

---

## 4. Limitations that must appear — not optional

Every one is measured, and stating them is cheaper than being caught.

- [ ] **C-012 is grader-dependent.** Significant under qwen on both halves
      (+0.1147, +0.0822); **not** significant under gemma on either
      (+0.0696 [−0.0024, +0.1450]; +0.0643 [−0.0080, +0.1333]). Report as
      *positive under both families, statistically solid under one*
- [ ] **The holdout is a random split of one bank**, not an independently
      authored set. It controls for tuning to specific questions; it does
      **not** control for co-authorship bias
- [ ] **C-021 rests on one named grader because it has to.** Two of three local
      models cannot express a 0.03 difference near the ceiling
- [ ] **Two scoring faults remain unfixed by design** — abstention boilerplate
      crediting refusals, and the scorer recognising the source's identifier
      vocabulary rather than the graph's (0.185 on the subset measured). Both
      *raise* scores; fixing either mid-comparison would have broken the
      comparison
- [ ] **The census-weighted repair gain is +0.0017**, against +0.0503 pooled.
      Quote both; the pooled figure alone is a draw artifact of a bank that
      deliberately over-samples rare shapes
- [ ] `n_runs: 1` on several older experiments; seeds unrecorded (`D-010`)
- [ ] The `llm_query` arm loses evidence on some questions to a reserved-word
      Gremlin binding — **pre-existing and priced into the published figures**,
      but its origin (ours or the model's) is undiagnosed

---

## 5. The contribution question — decide before writing

The night of 2026-09-06 produced something the outline has no section for:
**grader calibration as a method**. Two of three local models cannot resolve
differences near 1.0; one of them *inverts* the mid/low ordering; and this was
found only because a near-miss forced the check. Three claim-level near-misses
trace to it, including a tie-break one commit from being published as four
arm-order reversals.

- [ ] **Decide:** is this a §12, a subsection of §4, or a separate short paper?
- [ ] If it stays in: it needs `EXP-2026-09-008` written up as `RESULTS.md`

---

## 6. Venue — the binding decision

- [ ] **Choose: conference or JMLR.** Nothing else is blocked by it, but §3's
      cut list depends entirely on the page limit

| | conference (8–9 pp) | JMLR (no limit) |
|---|---|---|
| Instrument-failure narrative | one paragraph + appendix | **a full section** |
| Grader calibration | cut or folded into §4 | its own section |
| Six repairs, three measurement faults | a table | the story it actually is |
| Related work | compressed | the sweep's full nearest-neighbour set |

**Assessment:** the record now contains more method than a conference page limit
can carry. Four guards that turned out not to be guarding, a saturated grader
that would have inverted a conclusion, and a null that survived being rewritten
are the *interesting* content — and they are exactly what gets cut at 9 pages.

- [ ] Re-verify any deadline before planning against it — `venue-targets.md` is
      **stale** and says so

### Outcome of the 2026-09-06 venue selection

Run under [`../../../prompts/2026-09-06-venue-selection.md`](../../../prompts/2026-09-06-venue-selection.md).
Nothing above is rewritten; this is the appended result.

- Part A — an isolated web-connected agent produced
  [`../venue-report-2026-09.md`](../venue-report-2026-09.md): 15 venue entries
  verified against official calls, 11 `UNVERIFIED` (EDBT 2027 among them — its
  dates came from a mailing-list republication, not the conference site).
  **Supersedes [`../venue-targets.md`](../venue-targets.md)** as the calendar.
- Part C — scored against that report's four tier checklists in
  [`../venue-readiness-2026-09.md`](../venue-readiness-2026-09.md) (+ PDF).
  `make validate-research` green: 41 experiments — though the `make` target itself
  needs network access to fetch its interpreter; `scripts/validate_research.py` was
  run directly.
- **Renderer deviation, recorded rather than absorbed:** the prompt specified
  `scripts/morning_report.py::render_pdf`. It returned `True`, but it emits one
  paragraph per *source line*, prints `---` literally and auto-sizes table columns,
  which is unreadable at this length. `scripts/render_readiness_pdf.py` was added
  for documents meant to be sat down with; `morning_report.py` is untouched.

- [ ] **DECISION RECOMMENDED, NOT YET TAKEN: journal, Semantic Web Journal**
      (rolling, no page limit, no deadline). Answers the `conference or JMLR`
      box above in the JMLR column. Estimated 2–3 months to submission.
- [ ] **Do not spend the unpublished status on NORA @ AACL 2026** (2026-09-14,
      ACL Anthology archival, off-theme). The evidence clears a workshop bar
      today; nothing worth submitting to is open.
- [ ] **B-tier stays live as the alternative** — reachable on the same writing
      plus one bounded re-run (three seeded `llm_query` runs). ECIR 2027 short
      (2026-10-12) is the near-term option if that route is taken.
- [ ] **A-tier not attempted this cycle.** `A8` (human anchor / grader-vs-human
      agreement) is blocked by `Q6`, closed as WILL NOT DO — a resourcing
      question, not a writing one.

**Five record defects the scoring surfaced** (each is `PAPERWORK`, each is now an
open question — see `../../OPEN_QUESTIONS.md` Q30–Q34):

1. `EXP-2026-09-008` is `status: planned` with a template manifest and RESULTS,
   `supports_claims: []`, placeholder title in `INDEX.md` — while its `data/`
   holds the calibration verdict the paper's §12 depends on.
2. `EXP-2026-09-007`'s manifest metrics and `RESULTS.md` §4 are stale against
   `data/judged-two-family-final.json` in the same folder: RESULTS says gemma
   never graded `llm_query`'s holdout answers; the data file completes all
   **3,456** judgments (3 arms × 288 × 2 positions × 2 families).
3. ~~"Every number in the paper traces to an `EXP-` ID — **enforced by CI**"~~
   **Corrected 2026-09-07.** There is no CI. There is now a check —
   `make verify-paper-numbers` — that you run yourself. It found four wrong
   recorded metrics and a table row living outside the record on its first
   night, and reports 0 untraced of 86 figures.
   (§7 below, and `AGENT_INSTRUCTIONS.md` principle 3) is **false**: `.github/`
   does not exist and `utils/research_record/validate.py` reads no paper prose
   and extracts no numbers. `OUTLINE.md:44`'s +0.0822/+0.0643 are the live
   example — no `EXP-` ID, matching no manifest.
4. `EXP-2026-08-009`'s −0.0334 / +0.0000 are retracted by its own amendment A-1
   and were nonetheless quoted into the Part A brief. Re-graded: −0.0587 /
   −0.0520.
5. `EXP-2026-08-018` and `EXP-2026-08-019` ran `--repeats 3` and report metrics
   at `n: 3`, but both manifests record `n_runs: 1`.

**One correction in the project's favour:** `EXP-2026-08-010` used **182
externally authored questions** (CTIBench `cti-ate`, 60 rows, plus an AttackQA
enumerative subset; questions used verbatim;
`data.split: "external — neither benchmark was authored with sight of this
codebase"`). That satisfies the A-tier item A4 outright and half of B9. It is
invisible in `OUTLINE.md` and in §4's limitations list, and it should not be.

**Where the readiness assessment disagrees with the venue report:** the report's
lead argument for SWJ leans on the third graph being one that "could not legally
be copied". `EXP-2026-08-017` RESULTS explicitly refuses that claim — the
contractual case is motivation, the identity records are synthetic, and what was
measured is only that federation asked that graph for nothing. Venue choice
stands; that sentence cannot be written.

---

## 7. Artifact and DOI — half a day, no risk

- [x] `LICENSE`, `NOTICE`
- [ ] MITRE attribution visible in the artifact itself, not only in `NOTICE`
- [ ] `ARTIFACT_APPENDIX.md` off draft — its blockers section is the to-do
- [ ] **Mint the DOI** (Zenodo). Not started; no dependency on anything above
- [x] Every number in the paper traces to an `EXP-` ID — **0 untraced of 86**
      as of 2026-09-07, by `make verify-paper-numbers`. **Not** CI; re-run it
      at camera-ready and after any number changes. Verify
      once more at camera-ready
- [ ] `data/POINTERS.md` hashes re-verified for the artifacts that live outside
      the cloneable record
