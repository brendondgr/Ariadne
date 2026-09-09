# RESULTS — EXP-2026-07-009 End-to-end evaluation

## 1. Headline

All four deterministic end-to-end metrics score **1.0**: cross-source
exact-set-match 30/30, CAPEC to ATT&CK mapping recall 113/113, provenance
correctness 120/120, and analyst inspectability 1.0 — with zero fabrication on
10 negatives. No hypothesis was registered.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json).

| Metric | Value | k | 95% CI |
|---|---|---|---|
| Cross-source answer accuracy **(primary)** | 1.0000 | 30/30 | [0.89, 1.00] |
| — precision / recall / F1 | 1.0 / 1.0 / 1.0 | — | — |
| No-fabrication (negatives) | 1.0000 | 10/10 | [0.72, 1.00] |
| CAPEC→ATT&CK mapping recall (micro) | 1.0000 | 113/113 mappings, 30 entries | — |
| Provenance correctness | 1.0000 | 120/120 | [0.97, 1.00] |
| Analyst inspectability | 1.0000 | 120 | — |
| Unsupported-claim rate | 0.0 | — | — |
| Cross-source conflicts | 0 | — | — |

**LLM judge — non-reproducible, recorded separately:**

| Metric | Value |
|---|---|
| `judge_faithfulness` | 0.9733 |
| `judge_groundedness` | 0.9342 |
| `judge_evidence_sufficiency` | 0.9500 |

By tier, `x_source_exact` is 0.0 for the *adversarial* and *easy* tiers. That is
not a failure: neither tier contains cross-source questions, so the metric has
no population there. Mapping recall, provenance, and inspectability are 1.0 in
every tier.

## 3. Figures

None.

## 4. Interpretation

Provenance and inspectability at 1.0 across all 120 answers is the strongest
result in this folder, because it is the property the system is architecturally
designed to guarantee: every rendered claim resolves to a retrieved record whose
query was actually executed. A single failure here would indicate a real defect
in the citation chain, and there are none.

The judge scores are the weakest thing in this record and are labelled as such —
see §5.

## 5. Threats to validity

* **Three of the four metrics are self-consistency checks.** Provenance
  correctness, analyst inspectability, and no-fabrication all measure whether
  the system's own outputs are internally coherent with its own retrieved
  records. They do not measure whether the answer is *right*. The repository's
  own analysis says exactly this, and it is preserved rather than softened.
* **The judge is the same model that wrote the answers.** `skynet` grading
  `skynet` carries self-preference bias. That is precisely why
  [`EXP-2026-07-010`](../EXP-2026-07-010-independent-eval-baseline/) exists as
  an independent cross-model check, and it scored the same pipeline at 0.8946
  correctness rather than the near-1.0 these numbers suggest.
* **Gold comes from the pinned snapshot.** An ingest error present in both the
  snapshot and the live graph is invisible to exact-set-match.
* **30 cross-source entries and 10 negatives is a small population.** The
  confidence intervals say so: [0.72, 1.00] on the negatives is wide.

## 6. What surprised us

How little the four `goals.md` metrics constrain answer quality. All four sit at
1.0 while an independent cross-model judge scored the same pipeline's answers at
0.8946 correctness with hallucinations in 11 of them. A metric suite can be
fully satisfied by a pipeline that is still wrong a tenth of the time — which is
the argument for the seven-arm study existing at all.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Replace or supplement the self-consistency metrics with something that
  measures correctness rather than coherence.
* Never report the `judge_` scores from this experiment without the independent
  panel beside them.

## 8. Reproduction

```bash
uv run main.py --docker start
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run main.py --e2e-generate
uv run main.py --e2e-eval --judge
```

The four deterministic metrics reproduce exactly. The `--judge` scores do not.

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — Run date, judge-model string and one pointer description corrected

**What was wrong.**

1. `manifest.yaml:6–7` recorded `date_started: 2026-07-26` /
   `date_completed: 2026-07-26`. That is the date of the standing-record commit
   (`e938452`), not of the run. The pointed-at report
   `docs/evaluation/e2e-evaluation.json` was last regenerated and committed in
   `14fd58f` on 2026-07-19 22:36 −0400 (733 lines rewritten; earlier versions
   on 2026-07-07 `efa7f4e` and 2026-07-08 `970a683`). The JSON carries no
   timestamp of its own (`meta` holds only the ATT&CK/CAPEC versions), so the
   commit date is the best available date and the run happened no later than
   it. **Old:** `2026-07-26` → **new:** `2026-07-19` for both fields. Established
   from `git log -- docs/evaluation/e2e-evaluation.json`.
2. `manifest.yaml:47` recorded `llm.model: "vllm/gemma-4-31b@unknown"` with a
   comment naming the relay alias. `docs/evaluation/README.md` §"The model
   behind `skynet`" records the July-2026 served model as Gemma 4 31B
   (quantisation never recorded). **Old:** `vllm/gemma-4-31b@unknown` →
   **new:** `relay/gemma-4-31B@2026-07-19`, in the format that README
   prescribes; the date is the artifact commit above. This is the judge only;
   the pipeline's own model is the same alias.
3. `data/POINTERS.md:10` described `docs/evaluation/answers` as "the 120
   end-to-end answers and their judgments backing this report". The 120
   `*.judgment.json` files in that directory are the Sonnet 5 cross-model
   judgments of `EXP-2026-07-010` (keys `case_id, verdict, correctness, …`),
   not this run's `--judge` verdicts, which exist only inside
   `e2e-evaluation.json` under `e2e.overall.llm_judge.verdicts`. The
   description is corrected in place; the hash
   `sha256:c0828b08…` was re-verified today with
   `utils.research_record.hashing` and is unchanged.

**What is unchanged.** Every number. The B2 audit of 2026-09-09 recomputed all
four deterministic metrics and the three judge scores from
`e2e-evaluation.json` and reproduced them exactly (30/30, 10/10, 113/113,
120/120; 0.9733 / 0.9342 / 0.9500). `code.commit` stays `unknown` (ISSUES
2026-08-06).

**Refinement link.** `EXP-2026-07-010` is the independent cross-model check on
these same 120 answers and is the experiment that refines this one: its 0.8946
correctness is the figure to quote beside, never instead of, the deterministic
1.0s here. It is already in `related`; recorded here so the direction of
refinement is explicit.
