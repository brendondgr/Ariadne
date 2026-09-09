# EXP-2026-08-016 — Fifteen bypasses, and a 99% cut in cross-tenant leakage

**Status:** complete. Both phases found something, and phase 1 found more than
the claim it was testing had allowed for.

## Phase 1 — the gate had 15 live bypasses

The suite went from **17 hand-written probes to 240 generated ones**. Twenty
were not blocked. Triaged before any fix: **15 genuine gate defects, 5 bad
probes.**

| defect | n | what got through |
|---|---:|---|
| `mergeV` / `mergeE` | **8** | TinkerPop's merge steps **mutate**, were added to the language after these cards were written, and **no card names them**. Eight placements walked through a gate whose entire purpose is read-only. |
| Groovy closure | 1 | `g.V().filter{ it.get()… }` — arbitrary code on the Gremlin server, structurally indistinguishable from a read to every check that existed. |
| `repeat(…)` unbounded / over-depth | 2 | `repeat` collapses an arbitrary walk into one step, so a depth check that counts `out`/`in`/`both` cannot see it. |
| literal hop chain | 1 | `(a)-[:R]-(b)-[:R]-(c)-[:R]-(d)-[:R]-(e)` is four hops past a cap of three; only the `*` form was ever checked. |
| `USE <db>` | 1 | re-targets the statement at another database, which the card cannot vouch for. |
| backtick / multi-label | 2 | ``(x:`Secret`)`` and `(n:Technique:Secret)` — the label regex read one bare identifier per pattern, so an undeclared label rode in beside a declared one. |

All 15 are closed. **The authoritative lists live in the validators, not the
cards**: source cards are gitignored build artifacts, so a fix that lives only in
the data disappears on the next rebuild. The card generator was updated to match
so a card read on its own is not misleading.

After the fix: **240 probes, block rate 1.0000, 0 leaks, 0 breaches, adherence
1.0000.**

### The 5 bad probes are a finding too

`OR '1'='1'`, a comment terminator, an always-true Gremlin filter, a backslash in
a string, and literal concatenation. The gate accepted every one, and **it is
right to** — each is a read-only, row-capped read over a declared label. A
tautology returns rows the analyst was entitled to read anyway.

They are kept in an `accepted_by_design` list with a test asserting the gate
accepts them, because they document the **scope boundary**: this gate enforces
structural safety, not semantic intent. Turning any of them into a rejection is a
scope change requiring a decision, not a bug fix. Deleting them would have hidden
the boundary; reclassifying them silently would have been the same overclaim in a
different direction.

## Phase 2 — leakage falls 99.1%, and the fix has a cost

14 probes, three live sources, both selection rules:

| rule | probes leaking | leaked records |
|---|---:|---:|
| `absolute` (pre-2026-08-22) | **3 / 14** | **568** |
| `comparative` (shipped) | **1 / 14** | **5** |

The worst pre-fix case reproduces EXP-2026-08-013's observation exactly: *"Which
users are members of the Domain Admins group?"* — a question about one tenant's
identity graph — returned **558 CAPEC records**. Under the comparative rule it
returns none.

**This is the first measurement of the property, and the first evidence that the
routing fix bought anything.** Its value was previously described from a single
observed question; it is now 568 → 5 over a probe set that was written to be
hostile.

### The residual leak

`attack_tactic` — *"Which techniques belong to the credential access tactic?"* —
still routes to `identity` alongside `attack` and pulls **5 identity records**.
The words "credential" and "access" are ordinary IT English that the tenant
vocabulary also matches, which is exactly the failure mode the comparative rule
narrows rather than eliminates. Recorded, not fixed.

### The cost, reported because the protocol required it

**`attack_group` now routes to `identity` alone.** *"Which group uses
T1059.001?"* is an ATT&CK question, and under the comparative rule the tenant
graph is the leader on the token `group` and ATT&CK brings no token identity does
not — so ATT&CK is dropped and the question returns **nothing at all**.

By the leak metric this scores clean: the only source consulted returned no
records, so nothing foreign reached the evidence. **That is exactly the failure
the protocol pre-registered** — a rule that routes everything to one source
scores a perfect zero while answering nothing. It is reported here because the
metric alone would have hidden it.

So the comparative rule is a **trade**: it removes 99% of cross-tenant leakage
and it can lose the right source on a question whose only strong token is
generic. Both halves must travel together.

## What this changes for C-008

The claim moves from *17/17, which is weak evidence of a strong property* to
**240/240 after fixing 15 live bypasses that the small suite never reached**. The
honest form now has two clauses:

1. The gate blocks structurally unsafe queries, evidenced at a scale where the
   rate means something — **and the suite that establishes it found 15 defects on
   first contact**, which is the strongest available argument that 17 was too few.
2. **The gate cannot see cross-tenant leakage at all**, because every query in a
   leak is legal for its own source. That property lives in routing and is now
   measured separately.

## Threats

* **The probes are generated from categories we thought of.** Mutation coverage
  is broad within each category and says nothing about a category nobody listed.
  15 defects on first contact is evidence the categories were under-populated
  before, not that they are complete now.
* **14 isolation probes is small**, and they are author-written rather than drawn
  — the same co-authorship exposure C-021 prices elsewhere. The 568 → 5 gap is
  far larger than that bias could account for, but the absolute counts are not
  population estimates.
* **Leak counting is per-record, not per-identifier.** One over-returning query
  dominates the total: 558 of the 568 pre-fix records come from a single probe.
  The probe *count* (3 → 1) is the more robust of the two figures.
* **`sideEffect` is on the card's disallowed list**, so probes placing a write
  inside it were blocked for two reasons at once. Their pass tells us less than
  the count suggests.

---

# AMENDMENTS

## A-1 (2026-08-24) — Q21 fixed: the routing rule no longer loses the source a question is about

The cost this experiment reported is repaired, and the leak figures are unmoved.

**The defect was a tiebreak, not a weighting.** Scoring *"Which group uses
T1059.001?"* gave ATT&CK **1** matched token and the tenant graph **1** — both on
the word `group` — and `max()` broke the tie on dataset name, alphabetically. The
identifier `t1059` was sitting in the request and counted for **nobody**, because
the concept index is built from label and relationship *names* and never from
instance identifiers.

**The fix adds identifier-shape evidence, learned rather than written down.**
A request token whose *shape* matches one of a source's learned identifier
schemes now counts as an id-hit for that source, and joins its distinctive-token
set. Shapes come from `utils/specialists/schema/idscheme.py`, which normalises
digit runs (`T1059.001` → `t#.#`) from each dataset's canonical snapshot. **No
MITRE string appears in the router.** A source with no learned schemes scores
nothing extra — the `undetermined` behaviour that module already specifies —
rather than a wrong answer.

### Result

| probe | before | after |
|---|---|---|
| `attack_group` | routed `identity` alone, **0 records** | routed **`attack`**, **1 record** |
| `attack_technique` (absolute rule) | routed `attack,capec,identity` | routed **`attack`** |
| leak totals | 1/14 probes, 5 records | **1/14 probes, 5 records** — unchanged |

**The regression is the strongest part.** Re-running all ten catalogue banks,
deterministic arm: **0 of 300 answers changed.** The fix is inert on the
two-catalogue configuration — where ATT&CK already won its questions — and active
only where a second source was competing for a generic word. Strictly better,
nothing traded.

### The residual, unchanged and now better understood

`attack_tactic` still routes to `attack` **and** `identity` and pulls 5 identity
records. The fix cannot help: *"Which techniques belong to the credential access
tactic?"* carries **no identifier at all**, so there is no identifier-strength
evidence to weigh, and the tenant's 72 labels of ordinary IT English match
`credential`, `access` and `belong` on their own merits.

**And it exposes something this experiment did not previously separate:** on that
probe ATT&CK is routed and returns **0 records** while identity returns 5. So the
answer is bad for two independent reasons — a leak *and* an ATT&CK-side retrieval
failure on that question shape — and only the first is a routing property. That
second half is not Q21 and is not fixed here.

This is the C-010 limitation in miniature: the planner is card-driven but not
schema-*scale*-independent, and generic vocabulary against a large schema remains
its weakest surface.

## AMENDMENT A-2 (2026-09-09) — A-1's post-fix routing numbers have no artifact; completion date inverted; `gate_bypasses_found` back-filled; a probe count restated

**A-1 versus the pointed artifact.** A-1 (Q21 fix, commit `6ee9f6e`, 2026-08-24
17:23) reports `attack_group` routed to `attack` with **1 record**, leak totals
**unchanged at 1/14 probes, 5 records**, and "0 of 300 answers changed" over
the ten catalogue banks. The only artifact this experiment points at,
`docs/evaluation/isolation-2026-08-23/metrics.json`, was written at 14:02 —
before the fix — and its `comparative.rows.attack_group` still reads routed
`['identity']`, 0 records. `6ee9f6e` touched `drafter.py`, OPEN_QUESTIONS, the
changelog and this RESULTS file only; no post-fix sweep output or catalogue
re-run was written anywhere under version control (the catalogue run trees are
gitignored). The manifest's leak values (568 / 5 / 3 / 1) are the pre-fix sweep
and are what the artifact backs; A-1's claim that they are unchanged after the
fix is recorded from prose and reproducible only by re-running
`scripts/isolation_probes.py` at or after `6ee9f6e`. Recorded in ISSUES.

**Date.** `manifest.yaml:10` had `date_completed: 2026-08-23` against
`date_started: 2026-08-24`. Phase-2 metrics were written 2026-08-24 14:02 and
committed at `f362d3c` 14:06; the `-2026-08-23` is the output-directory slug.
**Old → new:** `2026-08-23` → `2026-08-24`.

**`gate_bypasses_found = 15` was not in `data/metrics.json`.** None of the
phase-1 figures are: `score_safety()` computes them live from the committed
probe fixtures and never wrote a file. A `manifest_metrics` object holding all
seven manifest values was added to `data/metrics.json`; the sweep keys are
unchanged and `data/POINTERS.md` no longer calls the file a byte-identical copy.

**Probe count.** §"Phase 1" line 8 says the suite went from "17 hand-written
probes to 240 generated ones". The suite is **240 = 17 hand-written + 223
generated** (`PROBES` per source 183 + 57, of which `generated_probes()`
contributes 173 + 50; `accepted_by_design` 2 + 3 = 5). The 240 and the 15
bypasses are unaffected.

**Related.** EXP-2026-07-008 holds the original 17-probe safety measurement
this phase refines; it is added to `related`.

## AMENDMENT A-3 (2026-09-09) — the primary metric now names a recorded key

`metrics.primary` was `leaked_records_by_selection_rule`, a descriptive label that matched no key in
`metrics.values`, so `INDEX.md` and `CURRENT.md` rendered this experiment's
headline as "not recorded". It now names `leaked_records_comparative_rule` — the leakage figure under the shipped comparative routing rule. No value changed.
