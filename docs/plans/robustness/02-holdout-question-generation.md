# Plan 02 — Holdout question generation

**Audience:** the agent authoring the blind holdout, plus the operator running
it.
**Goal:** 30 questions that were not shaped by knowledge of which query
templates exist, with gold computed independently, in a form the existing
harness can execute.
**Prerequisite:** Plan 01 complete and `freeze/holdout-v1` tagged.
**Blocks:** the Step 4 gate, and therefore Steps 6 and 7 of the parent plan.

---

## 0. What this experiment is for, and how it dies

The 120-question evaluation set was written by the same person who wrote the
templates that answer it, at the same time. The correctness figure of 0.9972 is
therefore ambiguous: it could mean the system works, or it could mean the
questions were shaped — consciously or not — by knowing what the system handles.
This experiment distinguishes those.

**It dies in three ways, all silent.**

*The author sees the templates.* Then the questions are co-authored again and
nothing has been tested. This is why §3 is a write-lock, not a suggestion.

*The anchors are chosen badly.* The current set draws anchors from the rich,
well-connected part of the data by explicit design —
`utils/specialists/evalset/federated_questions.py:58-60` states that CWE anchors
were selected because "many famous web CWEs bridge only to unmapped patterns and
would be empty chains." If the new anchors are also chosen for richness, the
holdout reproduces the bias it exists to detect. A language model asked to
invent CAPEC or ATT&CK questions will reach for T1003, T1055 and Mimikatz
unprompted. **This is the single most likely failure and §2 exists to prevent
it.**

*Something gets fixed in response to a failure.* A template tweaked because a
holdout question failed converts the experiment into a second development set.
The result still looks like a number, which is what makes it dangerous.

---

## 1. Roles

Three roles, deliberately separated. One agent may not hold two of them.

| Role | Does | May see |
|---|---|---|
| **Sampler** | Draws anchors mechanically from a seed | Everything. It is a script. |
| **Author** | Writes question text for a given anchor | Only what §3 permits |
| **Compiler** | Computes gold, assembles the bank, runs the arms | Everything |

The Author is the only role with a context restriction, and it is absolute.

---

## 2. Anchor sampling — mechanical, seeded, uniform

Write `utils/specialists/evalset/holdout_protocol.py`. It is committed and it is
part of the artifact.

### 2.1 Population

Draw from the **live** id space in the pinned snapshot, not from any curated
subset:

- **ATT&CK:** all live Technique and SubTechnique ids in ATT&CK 19.0, excluding
  the 157 revoked and 251 deprecated (`data/graphs/attack/runtime/fixture-qa-report.json`).
- **CAPEC:** all 558 live AttackPattern ids in CAPEC 3.9, excluding the 114
  retired. **Including the 381 that carry no ATT&CK mapping** — this is the
  point, see §2.4.
- **CWE:** all 336 bridged weaknesses in `gold_bank.json` `capec.cwe_to_capec`,
  with no filtering for whether the bridge terminates in a mapped pattern.

### 2.2 Stratification

Match the existing bank's source proportions so the comparison is
like-for-like. The bank is 46 ATT&CK / 34 CAPEC / 40 federated. For 30 questions:

| Class | Count |
|---|---|
| ATT&CK single-source | 12 |
| CAPEC single-source | 8 |
| Federated | 10 |

Stratify **by class only**. Within a class, sample anchors **uniformly at
random** — no weighting by degree, mapping count, fame, or category.

### 2.3 Seed

Use a fixed, recorded seed. `1729` is already used elsewhere in the repository
(`utils/evaluation/stats.py:108`); pick a different one so the two are not
confused, and write it into the protocol module as a module-level constant with
a comment saying it must never change.

Emit `docs/evaluation/holdout-v1/anchors.json`: the seed, the population size
per class, the drawn anchors in draw order, and a SHA256 of the population lists
so a reviewer can confirm the draw was made against the snapshot claimed.

### 2.4 The unmapped-anchor case — read this before writing the sampler

Uniform sampling of CAPEC means roughly **68% of federated anchors will have no
ATT&CK mapping at all** (177 of 558 patterns carry one). For those, the
*correct* system behaviour is not an answer — it is an **abstention carrying the
executed query as proof**, which is a capability the system explicitly has
(`utils/synthesis/verifier.py:_enforce_abstentions`).

Do not filter these out. They are the most informative questions in the set. But
do not blend them into one number either, because "correctness" means something
different for each.

Partition the federated stratum and report the two separately:

- **Answerable** — anchor carries ≥1 live ATT&CK mapping. Scored on answer
  correctness.
- **Abstention-expected** — anchor carries none. Scored on whether the system
  abstains, whether the abstention carries the executed query, and whether it
  avoids fabricating a mapping.

Target roughly 6 answerable and 4 abstention-expected out of the 10 federated,
which means over-drawing and partitioning rather than filtering. Record the
over-draw in `anchors.json`.

A system that scores 0.99 on answerable questions and hallucinates mappings on
unmapped anchors has a much worse result than the aggregate would suggest. That
is worth knowing before a reviewer finds it.

---

## 3. The Author's context — a hard write-lock

The authoring agent runs against a **detached checkout of `freeze/holdout-v1`**
with read access denied to the following. This is enforced by what you put in
the agent's working directory, not by instructing it to avert its eyes.

### Must NOT see

| Path | Why |
|---|---|
| `utils/specialists/**` | The templates. The entire point. |
| `utils/specialists/evalset/**` | The existing question archetypes and anchor lists |
| `utils/specialists/tests/golden/*.json` | The existing questions — leaks phrasing style and template shape |
| `README.md` | Describes what the system can do, including the template inventory |
| `docs/evaluation/**` | Results, category performance, arm tables |
| `docs/research/audit-2026-08-03.md` | Everything |
| `docs/plans/**` | Including this file |

### May see

- `docs/references/ATT&CK_structure.md` — the ATT&CK data model, so questions
  reference real entity types.
- The raw pinned snapshot under `data/raw/` — **for entity names and
  descriptions only**, never for relationships or mappings. See §4.
- The category scheme in §5, as reproduced there. Not the source file.
- One anchor at a time, with its type and its human-readable name.

### The prompt contract

The Author receives, per question: an anchor id, its entity type, its
human-readable name, and a category label from §5. It returns one natural-language
analyst question and nothing else.

It does **not** propose an answer, an expected template, a tier, or an assertion.
Those are the Compiler's job and three of them are computed rather than
authored.

---

## 4. The offline rule

**The Author has no network access, and neither does the Compiler.**

Every fact used to construct a question or a gold answer comes from the pinned
local snapshot recorded in `data/versions.json`:

- ATT&CK 19.0, sha256 `df520ea0…`, 52,680,865 bytes
- CAPEC 3.9, sha256 `70279a2d…`, 3,849,998 bytes

Verify both hashes before starting and abort if either mismatches.

**Why this is non-negotiable.** MITRE publishes continuously. A question written
against the live web references a version the graph was not built from, so the
question is unanswerable through no fault of the system and the failure looks
like a system failure. A "wrong" answer that is actually a version skew is the
worst possible outcome for this experiment: it produces a low number with a
plausible explanation, and nobody checks.

The same rule kills two related temptations. Do not resolve an id against
memory — model recall of ATT&CK and CAPEC is exactly the long-tail enumerated
knowledge that is known to be unreliable. Do not "sanity check" a mapping
against anything outside the snapshot.

**Reference discipline.** Entities are referenced by canonical id and, on first
mention in a question, by their snapshot name: *"CAPEC-150 (Collect Data from
Common Resource Locations)"*. Never by description alone, never by a name that
does not appear verbatim in the snapshot.

---

## 5. Category scheme for the Author

Give the Author these labels and descriptions. **Do not give it example
questions from the existing bank** — phrasing style is itself a leak.

**ATT&CK single-source**

| Label | Ask for |
|---|---|
| `mitigations` | The mitigations listed for a technique |
| `groups` | The techniques a named group uses, or the groups using a technique |
| `software` | The techniques a piece of software implements |
| `detection` | How a technique is detected — data components, analytics |
| `tactics` | The tactics a technique belongs to |
| `subtechnique` | The parent/child relationship around a sub-technique |
| `lookup` | A plain description of one entity |

**CAPEC single-source**

| Label | Ask for |
|---|---|
| `mapping` | The ATT&CK techniques a pattern maps to |
| `weakness` | The CWEs a pattern exploits |
| `hierarchy` | The abstraction chain — Detailed → Standard → Meta |
| `execution` | The execution steps of a pattern |
| `consequence` | The consequences a pattern carries |
| `prerequisite` | What a pattern requires |
| `lookup` | A plain description of one pattern |

**Federated**

| Label | Ask for |
|---|---|
| `pattern-to-mitigation` | From a CAPEC pattern, through its ATT&CK techniques, to mitigations |
| `reverse-mapping` | From an ATT&CK technique back to the patterns referencing it |
| `cwe-chain` | From a CWE, through patterns, to ATT&CK techniques |

Questions should read as a security analyst would actually type them. Length
varies naturally. Do not signal the category in the wording.

---

## 6. Gold computation — Compiler only

**Gold is never authored.** Compute it with the existing
`utils/specialists/evalset/gold_bank.py`, which parses the raw STIX bundle and
CAPEC XML directly rather than going through `utils/kg_builder` — so the answer
key stays independent of both the ingest and the specialists. Preserving that
independence is the reason to reuse it rather than write something new.

For each question, compute:

- `assertions.must_include_ids` — the anchor
- `assertions.must_include_related` — the resolved neighbour set from the raw
  snapshot
- `assertions.must_correlate` (federated) — the intersection of the CAPEC-side
  ATTACK-taxonomy map with ATT&CK-side existence, per
  `federated_questions.py:_live_mappings`
- `ex_gold` — `{pool, expected, scheme}`, pool ∈ `node | neighbors | join`
- For abstention-expected questions — `expect_no_correlation`, and an empty
  related set

If gold computation raises for an anchor, **discard the anchor and draw the next
one from the seeded sequence.** Do not repair it, do not substitute by hand. Log
every discard with its reason in `anchors.json`; a high discard rate is itself a
finding about the join surface.

---

## 7. Output format

Match the existing bank schema exactly so the harness runs unmodified. Write to
`utils/specialists/tests/golden/holdout_questions.json`, keyed by id.

Ids use an `H-` prefix and the §5 category, e.g. `H-MIT-01`, `H-MAP-03`,
`H-CTM-02`.

### Single-source entry

```json
{
  "id": "H-MIT-01",
  "tier": "medium",
  "split": "holdout",
  "question": "<authored text>",
  "expected_template": "<COMPUTED, see below>",
  "task": {
    "sub_question_id": "H-MIT-01",
    "source": "attack",
    "text": "<authored text>",
    "entities": ["Technique", "Mitigation"],
    "limits": {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000},
    "join_key": null,
    "seed_ids": ["T1047"],
    "rationale": "holdout-v1 seeded draw"
  },
  "assertions": { "...computed..." },
  "ex_gold": { "...computed..." },
  "holdout_meta": {
    "anchor": "T1047",
    "anchor_draw_index": 7,
    "category": "mitigations",
    "author_model": "<model id and version>",
    "expected_template_is_derived": true
  }
}
```

Federated entries follow `federated_questions.json`: `hops`, `sources`,
`sequenced`, `partial_mode`, and a `sub_questions[]` array carrying `seed_from`
and `join_key`.

### Two schema notes that matter

**`split: "holdout"`.** The three existing banks carry no `split` field at all,
which is the gap this closes. Follow the convention the repository already has
at `utils/planner/evaluation/build_corpus.py:51` (`HOLDOUT_EVERY = 4`, separate
dev/holdout reporting) rather than inventing new mechanics.

**`expected_template` is derived, not gold.** The Author never sees the template
inventory, so it cannot supply this. The Compiler fills it from the anchor's
entity type and category. It is therefore **not a scoring signal** — you may not
report template-routing accuracy from the holdout, because the "expected" value
was inferred rather than independently known. `expected_template_is_derived: true`
records this so nobody later mistakes it for ground truth.

---

## 8. Deliverables

Everything goes under `docs/evaluation/holdout-v1/` except the bank itself.

```
utils/specialists/evalset/holdout_protocol.py       # sampler + prompt + seed
utils/specialists/tests/golden/holdout_questions.json
docs/evaluation/holdout-v1/
├── anchors.json          # seed, populations, draw order, discards, SHA256s
├── author-prompt.md      # the exact prompt, verbatim
├── README.md             # the write-up (§10)
└── results.json          # per-question outcomes, both arms
docs/evaluation/experiments/holdout-v1/             # raw answers + judgments
```

The first four are the reproducibility contribution. A human-authored holdout
cannot be re-run; this one can, and a reviewer can regenerate the entire set and
check that the anchors really were drawn uniformly. Say so in the write-up.

---

## 9. Execution

1. Verify both snapshot hashes against `data/versions.json`.
2. Confirm `git describe --exact-match` reports `freeze/holdout-v1`.
3. Run the sampler. Commit `anchors.json` **before** any question is written —
   this timestamps the draw as prior to authoring.
4. Run the Author under the §3 lock, one anchor per invocation.
5. Compile gold, assemble the bank, commit.
6. Run **Arms A and F only**, against the frozen tag, judged by the consolidated
   judge.
7. Write the results up.

**Between steps 5 and 7, change nothing.** No template edits, no planner edits,
no prompt edits, no re-draws. If step 6 reveals a crash rather than a wrong
answer, fix the crash, record it prominently as a deviation, and re-run — but a
wrong answer is a result, not a bug.

---

## 10. Reporting

`docs/evaluation/holdout-v1/README.md` must contain:

- Blind correctness for Arms A and F, with **Wilson score intervals** — at n=30
  the interval is wide and quoting a bare point estimate would overclaim.
- The development-set figure alongside, with the same interval treatment.
- **Per-category breakdown.** A uniform drop and a drop concentrated in the
  categories whose original anchors were richest mean very different things.
- **The two federated strata reported separately** (§2.4), with the
  abstention-expected cases scored on abstention behaviour rather than answer
  correctness.
- The discard count and reasons from gold computation.
- The stated limitation, in these terms or close to them: *an LLM-authored
  holdout controls co-authorship bias — the author had no knowledge of the
  template inventory — but does not control for the question distribution being
  a model's idea of what an analyst asks. A human-authored set remains the
  stronger test; a further 15–20 questions would be a cheap secondary check.*

Then hand the number to the gate in
`docs/plans/branch-a-publication-readiness-plan.md` §6 and follow the decision
rule as written. **Do not renegotiate the thresholds after seeing the result.**
