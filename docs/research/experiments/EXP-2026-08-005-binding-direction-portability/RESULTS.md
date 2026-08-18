# RESULTS — EXP-2026-08-005 Binding consistency and direction resolution

## 1. Headline

Giving the default cascade a schema-derived binding check and schema-resolved
edge direction takes blind-holdout retrieval from **0.7688 to 0.8952** — 22/30
to 26/30 fully covered, 187 gold identifiers recovered, **0 lost** — while the
120-question development catalogue does not move at all: **0 improved, 0
regressed, 1061 evidence records on both sides.**

The pre-registered additivity claim therefore holds, and the 2026-07-26 arm
figures stay comparable.

**Nothing here is judged.** See §5.

## 2. Results table

From [`data/metrics.json`](data/metrics.json).

| Set | Before (`ec01fe7`) | After | Paired |
|---|---|---|---|
| Blind `gold_in_evidence` | 0.7688 | **0.8952** | 4 improved, 0 regressed |
| Blind fully covered | 22/30 | **26/30** | 187 ids recovered, 0 lost |
| Blind evidence records | 43 | 216 | — |
| Development `gold_in_evidence` | 1.0000 | **1.0000** | **0 improved, 0 regressed** |
| Development fully covered | 120/120 | 120/120 | 0 ids recovered, 0 lost |
| Development evidence records | 1061 | 1061 | — |

0.8952 is, to four places, the figure the schema-driven branch reached on the
same bank before its bridge became an outer join (`EXP-2026-08-003`). That is
not a coincidence; §4 says why.

## 3. What the defect actually was

Two components, and the second is the one an audit of queries alone would have
missed.

**The query.** `group_techniques` routes on the *word* Group and then binds
`$ids` to the task's seed ids whatever they identify, so "which groups use
T1550.002" emitted `WHERE g.attack_id IN ['T1550.002']` — Group identifiers
filtered against a technique identifier. Structurally unsatisfiable, silently
empty, and indistinguishable from an honest "no groups use this".

**The answer.** Fixing the query was not enough. `_normalize_technique_rows`
deduplicated rows on `technique_id` and discarded the group columns — correct
when a group is the anchor and the answer is its technique list, and destructive
when the technique is the anchor and the answer is the group list. Live, "which
groups use T1003" went from 0 usable records, to 1 record and no neighbours, to
the technique anchored with **13 groups** attached, only after the normalizer
learned to pivot on which column carries a seed.

**The inventory is wider than the blind set found.** The read-only audit over
615 task shapes reports the same defect under five routes, not the two the blind
author happened to ask:

| Template | Repairable findings before |
|---|---|
| `group_techniques` | 7 |
| `campaign_techniques` | 5 |
| `campaign_attribution` | 3 |
| `tactic_techniques` | 1 |
| `software_techniques` | (unroutable: fell through to `describe`) |

After the repair, 3 remain, and none is a direction defect: each is a *misroute*
where the scope names a label the seed fits but the template walks a different
edge. The gate rejects those, so they end as a stated refusal rather than an
empty answer.

## 4. The residue is the join half, exactly

Five identifiers in four cases still miss: `CAPEC-116` (`H-CHN-01`), `CAPEC-456`
and `CAPEC-679` (`H-CHN-02`), `CAPEC-603` (`H-CTM-01`), `CAPEC-40` (`H-CTM-02`).

These are precisely the identifiers `EXP-2026-08-004` recovered on the generic
branch by making the cross-source bridge an outer join, and `capec_maps_to` and
`cwe_chain` still carry the inner join deliberately. So the blind gap now splits
cleanly along two independent defects: **the direction half is closed here, the
join half is not, and it is the same fix already proven on the other branch.**

That converts the outstanding operator decision from an abstract cost into a
priced one: porting the outer join is worth these five identifiers, against the
cost of re-cutting the comparability baseline.

## 5. Threats to validity

* **Nothing is judged.** Every figure is retrieval. 0.8952 may not be printed
  beside Arm A's 0.689 correctness; whether the recovered rows reach the answer
  is a question for a judged run.
* **A post-fix blind figure is not a headline.** Holdout v1 diagnosed this
  defect, so this number is co-authored with its own test. It is a diagnostic.
  The headline blind number must come from a holdout v2 drawn after the fix.
* **The audit's CAPEC coverage is thin.** Seed vocabulary comes from the
  committed banks, and the CAPEC bank anchors only on CAPEC identifiers; CWE and
  ATT&CK anchors reach the Gremlin builder only when passed in explicitly.
* **`seed_in_scope` under-reports on CAPEC**, where the analyst identifier
  (`CAPEC-1`) differs from the stored one (`capec:attack-pattern:1`), so those
  findings triage as misroutes.
* **The guard is timid by construction** and misses a conjunction of one good
  and one impossible filter. That is the chosen bias: a guard that accuses
  wrongly drops real answers.
* **n = 30** on the blind set, single run, seeds unrecorded, one snapshot.

## 6. What surprised us

That the development catalogue did not move by a single record — 1061 both
sides — while the blind set recovered 187 identifiers. The two banks ask the
same graph the same kinds of question; the only difference is that one of them
was written by someone who could see the templates. This is the co-authoring
effect measured directly, and it is a cleaner demonstration of it than the
original holdout, because here the *system* changed and only the blind bank
could tell.

Also: that the normalizer, not the query builder, held half the defect. An audit
of emitted queries — which is what the plan originally scoped — would have
declared the job done at a point where "which groups use T1003" still answered
with nothing.

## 7. Follow-ups

1. **Judge this arm** on both banks. Retrieval cannot see whether the recovered
   neighbours reach the answer, and the composer's under-enumeration defect
   (`EXP-2026-08-004` §7) sits exactly on that path.
2. **Port the outer join** to `capec_maps_to` and `cwe_chain` — the priced
   decision in §4.
3. **Author holdout v2** after both, and report the blind figure from it.
4. **The three misroutes** are a router question, not a direction one: the
   router prefers the template whose entity was mentioned over the one whose
   anchor was seeded.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin

ORCH_MAX_HOPS=5 uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --root docs/evaluation/experiments/binding-fix-dev --workers 4
ORCH_MAX_HOPS=5 uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/binding-fix-holdout --workers 4

# baselines, from a worktree at ec01fe7 with data/ and .env symlinked
uv run python -m utils.evaluation.retrieval_coverage \
  --root docs/evaluation/experiments/binding-fix-holdout --arm deterministic \
  --reference-root docs/evaluation/experiments/binding-baseline-holdout \
  --reference-arm deterministic

uv run python -m utils.specialists.audit.binding_audit \
  --seed capec=CWE-1243 --seed capec=T1003
```
