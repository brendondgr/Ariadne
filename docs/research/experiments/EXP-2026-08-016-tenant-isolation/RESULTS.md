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
