# RESULTS — EXP-2026-08-001 Arm H — generic primitives with composition, join projection and anchor resolution

## 1. Headline

**Gold-in-evidence 1.0000 over 120 questions — every gold identifier the
catalogue asks for now reaches the retrieved evidence, in every question.**
Against Arm G's 0.7191: 120/120 fully covered (was 73), 424 gold ids recovered,
**0 questions regressed**.

**This arm has no correctness number and must not be given one.** It was scored
mechanically from the artifacts; no judge ran. See §5.

The hypothesis in `PROTOCOL.md` — that Arm G's gap is a **capability** gap in the
schema-driven layer rather than a **domain-knowledge** gap — is supported on the
retrieval half of the question. Not one MITRE-specific literal was added to
either query builder; every new primitive is driven by the source card, the
derived schema registry, or the declared join-key registry.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), itself computed by
`utils/evaluation/retrieval_coverage.py` over the committed artifacts.

| Metric | Arm G | **Arm H** | Delta |
|---|---|---|---|
| `gold_in_evidence` **(primary)** | 0.7191 | **1.0000** | **+0.2809** |
| `gold_in_evidence_scorable` | 0.6595 | **1.0000** | +0.3405 |
| Questions fully covered | 73 / 120 | **120 / 120** | +47 |
| Gold ids never retrieved | 424 | **0** | −424 |
| Dependent hops skipped for want of seeds | 56 | **7** | −49 |

The seven remaining skipped hops are all `F-NEG`, where the correct behaviour is
to find no mapping and abstain. Arm G scored those correctly too; nothing
regressed there.

| Paired against Arm G | Value |
|---|---|
| Questions compared | 120 |
| Improved | 47 |
| **Regressed** | **0** |
| Gold ids recovered | 424 |
| Gold ids lost | 0 |

| Cost / volume | Arm G | Arm H |
|---|---|---|
| Wall clock (120 questions) | 914.8 s | 1574.1 s |
| Evidence records | 252 | 950 |

Retrieval is **not** what got slower: the heaviest executed query in the run
took 40 ms. The extra wall clock is the LLM narrator working over 3.8× more
evidence.

Per-category coverage is in
[`tables/tab-coverage-by-category.md`](tables/tab-coverage-by-category.md). The
categories that were worst in Arm G are the ones that moved:

| Category | Arm G | Arm H |
|---|---|---|
| `F-CWE` | 0.000 | 1.000 |
| `A-DCA` | 0.100 | 1.000 |
| `F-CTM` | 0.101 | 1.000 |
| `F-FAN` | 0.167 | 1.000 |
| `F-CTT` | 0.253 | 1.000 |

## 3. Figures

None generated. The study's cross-arm figure plots judged correctness, and this
arm has none; adding it would invite exactly the category error §5 warns about.

## 4. Interpretation

Arm G's −0.3568 was read as evidence for C-003 — that accuracy lives in the
hand-written templates. This experiment splits that claim in two.

The **retrieval** half does not survive as stated. Every retrieval failure Arm G
suffered was closable from declarations the repository already had:

* the **join-key registry** already declared `MAPS_TO`, `TaxonomyEntry` and
  `entry_id`; nothing was walking them;
* the **schema registry** already declared every `(rel, direction, neighbour)`
  facet, so `Technique → DetectionStrategy → Analytic` is an ordinary
  breadth-first search;
* the **anchor label** was being guessed from `labels[0]`, the order the planner
  happened to list entities in, rather than resolved.

What remains genuinely template-shaped is **precision**, and it is now the
sharper finding. Two primitives answer correctly but too broadly, and neither
can be narrowed from the schema (see `ISSUES.md`):

* `generic_intersect` returns 29 records for A-MC-01 where gold wants 7 — the
  sub-techniques are also mitigated by M1027 and also under TA0006, and nothing
  in the schema says "techniques" excludes them;
* the hierarchy walk returns descendants alongside ancestors, because nothing in
  the schema says which direction of a self-loop means "up".

That is a much more precise account of what a template buys than "accuracy":
templates encode **which of several schema-valid readings the analyst meant**.
A generic layer can find everything; it cannot know what to leave out.

## 5. Threats to validity

* **No judged correctness.** The primary metric here is retrieval. Judging needs
  120 independent Sonnet 5 agents and was not run. **Do not place Arm H on the
  arm-comparison figure, and do not compare 1.0000 against any arm's
  `correctness`.** Until a judge run exists, the only defensible statement is
  about what reached the evidence.
* **`gold_in_evidence` saturates.** At 1.0 the metric has no headroom and cannot
  distinguish a good answer from an over-broad one — which is precisely where
  the two over-returning primitives would show up. A ceiling result on a
  recall metric is weaker evidence than its face value suggests.
* **Not a clean pre-registration.** Spot checks over 30 of the 120 questions
  preceded the protocol. See `ISSUES.md`.
* **The catalogue is still co-authored and still has no holdout.** This
  experiment does not address C-013 and does not claim to. A generic layer
  reaching full coverage on a question set written alongside the templates says
  nothing about an unseen one.
* **All 120 questions are anchored.** Nothing here measures open-ended questions.
* **Single run, one model, seeds unrecorded.** As with every arm of the study.
  `gold_in_evidence` is deterministic given the plan, but the plan comes from an
  LLM planner, so it is not fully deterministic across runs.
* **It took three runs to get here.** The first full run regressed 8 CAPEC
  hierarchy questions to zero retrieval — the shared Gremlin validator counts
  every traversal step in a query against `max_traversal_depth`, so a wide union
  was rejected before execution. The paired per-question regression check is the
  only reason that was caught rather than absorbed into a rising mean.

## 6. What surprised us

That it went to exactly 1.0. The expectation recorded in `PROTOCOL.md` was
`≥ 0.97` with up to five `incomplete_retrieval` cases surviving. That every
category closed completely is a stronger result than predicted and, for that
reason, a result to be more suspicious of rather than less — §5 says why.

## 7. Follow-ups

* **Judge this arm** under the same protocol as Arms A–G. Until then the
  precision cost of the two over-returning primitives is unmeasured, and it is
  the one number that would make this experiment conclusive.
* **Qualify C-003.** Its current wording attributes the whole −0.3568 to the
  templates. The retrieval component is now shown to be a capability gap. The
  claim should be re-scoped to precision and disambiguation, with this
  experiment as the evidence. Not edited here — a `supported` claim's rewording
  is an operator decision.
* C-012 is untouched. No LLM writes Cypher or Gremlin in this arm either.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm generic --root docs/evaluation/experiments/untruncated-generic-fixed --workers 4
uv run python -m utils.evaluation.retrieval_coverage \
  --root docs/evaluation/experiments/untruncated-generic-fixed --arm generic \
  --reference-root docs/evaluation/experiments/untruncated-generic
```

`data/metrics.json` and `tables/tab-coverage-by-category.md` are both generated
from the artifacts by the second command's library functions; neither holds a
hand-entered number.

The artifact-directory hashes recorded in [`data/POINTERS.md`](data/POINTERS.md)
reproduce with:

```bash
find docs/evaluation/experiments/untruncated-generic-fixed/generic -type f -name '*.json' | sort | xargs cat | sha256sum
```

---

# AMENDMENTS

> The two dated amendments of 2026-08-09 live at the foot of `ISSUES.md`
> (written before this record adopted numbered amendments in `RESULTS.md`).
> Numbering starts here at A-1.

## AMENDMENT A-1 (2026-09-09) — Provenance: the run commit, a mistyped sha, the hash method and the model string

**What was wrong, and what is now correct.**

1. `manifest.yaml:34` recorded `code.commit:
   b6c4f12c67b8e93cbe9c8162123af4c003b49d67` (Arm H 2–6/7, 2026-08-09 12:59).
   The manifest's own `dirty:` comment (line 37) says the run started from a
   clean tree at `0826c3f` (Arm H 7e/7, 13:37), and the 121 artifact files
   under `untruncated-generic-fixed/generic/` are dated 2026-08-09 14:02–14:03.
   **Old:** `b6c4f12c…` → **new:** `0826c3f22852b38d4700f8c4f45da2ee4e2cd9e1`,
   verified with `git cat-file -e`. The record-side commit that added this
   folder's results is later still.
2. `PROTOCOL.md:7` and `ISSUES.md:7` cite the Arm H (1/7) commit as `925f2a3`.
   No such object exists; the commit is **`925fa3e`** ("Arm H (1/7): Give the
   generic branch a schema-driven cross-source bridge", 2026-08-09 12:38).
   Prose is append-only, so the typo stands in place; read it as `925fa3e`.
3. `data/POINTERS.md:12–13` hashed its two rows by different methods while
   stating one definition. Row 12 (`8170724a…`) was the documented
   `find|cat|sha256sum` recipe; row 13 (`de75c852…`) was the repository's
   tree method. On 2026-09-09 both recipes were run over both directories:
   the `find|cat` recipe over `untruncated-generic-fixed/generic` still gives
   exactly `8170724a…` and 4 806 684 bytes, so **the artifacts are unchanged**
   (the validator's "hashes to `f7e2c012…`" finding was a method mismatch, not
   a content change). Row 12 is re-recorded with the tree hash
   `sha256:f7e2c0121320…` so both rows verify by the method the validator
   uses; row 13 is unchanged. The directory still holds no judgment files.
4. `manifest.yaml:61` recorded `llm.model: "local/skynet (Gemma 4 31B)@unknown"`.
   **New:** `relay/gemma-4-31B@2026-08-09` — the model the run-time ISSUES
   entry names, in the format `docs/evaluation/README.md` prescribes, with the
   caveat from that README that the relay's August repoint date is unknown,
   so "Gemma 4 31B on 2026-08-09" is what was recorded, not what was verified
   from the serving side.

**Established by:** `git log`/`git cat-file` for the commits; file mtimes and
`utils.research_record.hashing` plus the §8 recipe for the hashes; the B2
audit of 2026-09-09, which also re-ran `retrieval_coverage` over both
directories and reproduced every number in §2 exactly.

## AMENDMENT A-2 (2026-09-09) — Arm H has since been judged; this experiment supersedes Arm G

**Stale prose.** §1 ("This arm has no correctness number and must not be
given one"), §5 first bullet, §7 item 1 ("Judge this arm") and the 2026-08-09
amendment in `ISSUES.md` ("the generic arm has never been run against
`holdout_questions.json`") were true when written and are now historical:

* `EXP-2026-08-003` (2026-08-10) ran Arm H against the blind holdout
  (retrieval 0.7688 → 0.8952, 0 regressions) and `EXP-2026-08-004` (same day)
  took it to 1.0000 on both banks with the outer-join bridge.
* `EXP-2026-08-007` (2026-08-19) **judged** Arm H — on the outer-join
  artifacts of `EXP-2026-08-004`, not on the inner-join artifacts pointed at
  here — at **0.8483** blind (n = 30) and **0.9692** on the development
  catalogue (n = 120), against the repaired cascade's 0.8367 / 0.9839 and Arm
  F's 0.9157 / 0.9852 (values from that experiment's manifest). Arm H judged
  level with the cascade on the blind set; the precision cost §4 predicted for
  the two over-returning primitives did not show up as a correctness gap. The
  "Judge this arm" follow-up is therefore closed by `EXP-2026-08-007`, which is
  added to `related`.
* §7 item 2 ("Qualify C-003") was overtaken: `CLAIMS.md` now records C-003 as
  **`refuted`** and the templates' remaining contribution — precision on the
  schema they were written for and provable abstention — as C-023. §4 of this
  experiment is the first statement of that reading.

**Supersession.** `manifest.yaml` now records `supersedes: EXP-2026-07-007`:
Arm H replaces Arm G as the study's generic-path arm, and Arm G's −0.3568 is no
longer the price of the generic path (it was the price of three missing
capabilities). Arm G's artifacts remain the paired baseline of every number
here and its record is not deleted. The reverse link (`superseded_by`) is set
in `EXP-2026-07-007`'s manifest. `EXP-2026-08-003` and `EXP-2026-08-004`, which
continue this line on the blind set, are added to `related`.

**Numbers in this record: unchanged.** Gold-in-evidence 1.0000 / 120 / 0
regressions on the inner-join artifacts stand as measured; nothing here may be
quoted as a correctness figure — for that, quote `EXP-2026-08-007`.
