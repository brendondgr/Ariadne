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

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — Pointers filled; lockfile, wall clock and commit timing corrected

**What was wrong, and what is now correct.** Nothing was re-run. The B2 audit
of 2026-09-09 re-ran `retrieval_coverage` over the four run directories and
reproduced every retrieval number in §2 (blind 0.8952 / 26 / 5 / 216 vs
0.7688 / 22 / 192 / 43, 4 improved 0 regressed 187 recovered; development
1.0000 / 120 / 1061 both sides, 0 / 0). The binding-audit counts in §3 were
not re-derived — they need the builders at `ec01fe7` and `8ac1049`, which have
since changed.

1. `data/POINTERS.md` was the blank scaffold. The four gitignored run
   directories (`binding-fix-{dev,holdout}`, `binding-baseline-{dev,holdout}`,
   all `deterministic/`, dated 2026-08-18 15:08–15:09, no judgment files then
   or now) and the blind bank are now hashed. The development bank is
   deliberately **not** hashed: two of its three files were modified by
   `c10caaa` 35 minutes after the run, so the state that ran is
   `8ac1049:utils/specialists/tests/golden/*`, not the working tree (ISSUES
   2026-09-09).
2. `manifest.yaml:50` `environment.lockfile: env/requirements.lock` — no such
   path exists in the repository or this folder. **→ `null`**, with the note
   every other experiment carries: the repository lockfile is `uv.lock` at
   root and is not snapshotted per run.
3. `manifest.yaml:54` `compute.wall_clock_hours: 0.01`. The four run
   `manifest.json` files record 1.9 + 1.1 + 2.4 + 0.9 = 6.3 s. **→ 0.002.**
4. `manifest.yaml:32` `code.commit: 63c2d2a…` (15:10:04) post-dates the
   artifacts (15:08–15:09) by one to two minutes. `git show --stat 63c2d2a`
   touches only `docs/changelog.jsonl`, so its code tree is identical to
   `8ac1049` (15:07:50, "(4/7): Resolve direction from the schema, both
   halves"), the last code commit before the run. The field is **kept** at
   `63c2d2a` with that explanation beside it; `dirty: false` is not
   verifiable from the artifacts and is annotated as such.

## AMENDMENT A-2 (2026-09-09) — Superseded 34 minutes later by EXP-2026-08-006; the "not fixed" decision was taken

**Supersession.** §4 and `ISSUES.md:21–33` say the templates keep the inner
join "deliberately … not fixed. This is an operator decision", and price the
decision at five identifiers in four cases. The decision was taken the same
afternoon: `c10caaa` (2026-08-18 15:43, "Binding portability (6/7): Outer-join
the template bridges, and keep the abstention") ported the outer join to
`capec_maps_to` and `cwe_chain`, and `EXP-2026-08-006` (record commit
`3c038d1`, 15:44) measured the default cascade at blind retrieval
**0.8952 → 1.0000** with the development catalogue still at 1.0000. That is
this experiment's blind headline replaced on the same arm and bank, so
`manifest.yaml` now records `status: superseded`, `superseded_by:
EXP-2026-08-006` (that manifest already carries `supersedes: EXP-2026-08-005`).
The 0.8952 here stays in `metrics.values` as the measurement of the direction
half alone, which is what §4 says it is.

**Follow-ups closed.** §7 item 2 (port the outer join): `EXP-2026-08-006`.
§7 item 1 (judge this arm on both banks): `EXP-2026-08-007` (2026-08-19)
judged the repaired cascade at **0.8367** blind and 0.9839 on the development
catalogue (its manifest's `blind_correctness_cascade` /
`dev_correctness_cascade`), after both halves of the fix; no judged figure
exists for the direction-only state measured here. Both experiments are added
to `related`. §7 items 3 (holdout v2) and 4 (the three misroutes) are not
closed by anything this amendment can cite.

**What C-010 keeps from here.** The mechanism — identifier schemes learned
from the snapshot, the three-valued binding check, direction resolved from the
declared triples — is the part `CLAIMS.md` C-010 cites from this experiment,
and it is unaffected by the supersession of the retrieval headline.
