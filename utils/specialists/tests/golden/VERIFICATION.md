# Gold Bank Verification Report

Independent AI re-derivation of every golden-bank claim from the pinned raw
snapshot (ATT&CK v19.0 STIX bundle, CAPEC v3.9 XML), run 2026-07-04.

> **Addendum (CAPEC exclude-at-load).** When CAPEC moved to exclude-at-load
> (Deprecated/Obsolete entries dropped at build), the CAPEC-557 positive lookup
> `C-LKP-06` was retired and replaced by `C-NEG-02`, a deterministic
> `expect_empty` negative asserting the now-excluded CAPEC-557 is not
> retrievable. `C-NEG-02` is verified by construction — CAPEC-557 has Status
> Deprecated and is absent from the built graph — rather than by the two-agent
> pass above.

## Method

- Every one of the 45 bank questions was restated as a factual claim about the
  raw snapshot (complete mitigation sets, membership subsets, exact names and
  field values, verified negatives).
- Each claim was audited by **two independent agents** with different tooling:
  verifier A restricted to command-line tools (jq / grep / sed / awk), verifier B
  writing its own Python parsers. Neither was permitted to read
  `utils/specialists/` (the code under audit) — derivation strictly from
  `data/raw/`.
- Verifiers were instructed to be adversarial: agree only when every element
  matches exactly; report every extra, missing, or mismatched id.

## Result

**45 / 45 claims verified — 90 / 90 verdicts `agree`, zero discrepancies.**

| Question | Verifier A (jq/grep) | Verifier B (python) |
|---|---|---|
| A-MIT-01 | agree | agree |
| A-MIT-02 | agree | agree |
| A-MIT-03 | agree | agree |
| A-MIT-04 | agree | agree |
| A-MIT-05 | agree | agree |
| A-MIT-06 | agree | agree |
| A-MIT-07 | agree | agree |
| A-MIT-08 | agree | agree |
| A-GRP-01 | agree | agree |
| A-GRP-02 | agree | agree |
| A-GRP-03 | agree | agree |
| A-GRP-04 | agree | agree |
| A-TAC-01 | agree | agree |
| A-TAC-02 | agree | agree |
| A-TAC-03 | agree | agree |
| A-LKP-01 | agree | agree |
| A-LKP-02 | agree | agree |
| A-LKP-03 | agree | agree |
| A-LKP-04 | agree | agree |
| A-CMP-01 | agree | agree |
| A-CMP-02 | agree | agree |
| A-SCN-01 | agree | agree |
| A-NEG-01 | agree | agree |
| A-NEG-02 | agree | agree |
| C-LKP-01 | agree | agree |
| C-LKP-02 | agree | agree |
| C-LKP-03 | agree | agree |
| C-LKP-04 | agree | agree |
| C-LKP-05 | agree | agree |
| C-CWE-01 | agree | agree |
| C-CWE-02 | agree | agree |
| C-CWE-03 | agree | agree |
| C-HIE-01 | agree | agree |
| C-HIE-02 | agree | agree |
| C-HIE-03 | agree | agree |
| C-PRE-01 | agree | agree |
| C-PRE-02 | agree | agree |
| C-MAP-01 | agree | agree |
| C-MAP-02 | agree | agree |
| C-MAP-03 | agree | agree |
| C-MAP-04 | agree | agree |
| C-MAP-NEG-01 | agree | agree |
| C-NEG-01 | agree | agree |
| C-NEG-02 | agree | agree |
| C-SCN-01 | agree | agree |

## Step 7 additions (run 2026-07-04, same method)

The eight Step 7 entries (campaign relationship coverage + boundary negatives)
were audited with the identical protocol: two independent adversarial agents —
verifier A restricted to jq/grep/sed/awk, verifier B writing its own Python
parsers — re-deriving every claim from `data/raw/` only, forbidden from
reading `utils/specialists/` or `utils/synthesis/`.

**8 / 8 claims verified — 16 / 16 verdicts `agree`, zero discrepancies.**

| Question | Verifier A (jq/grep) | Verifier B (python) |
|---|---|---|
| A-CMP-TEC-01 | agree | agree |
| A-CMP-TEC-02 | agree | agree |
| A-CMP-TEC-03 | agree | agree |
| A-CMP-ATT-01 | agree | agree |
| A-CMP-ATT-02 | agree | agree |
| A-CMP-NEG-01 | agree | agree |
| A-AST-01 | agree | agree |
| A-AST-02 | agree | agree |

Independently derived counts agreed exactly with the gold bank: C0027 uses 10
live top-level techniques, C0024 24, C0001 13; attribution sets are exactly
C0027 → {G1015} and C0028 → {G0034}; no live object carries external id C9999;
and the Enterprise bundle contains **zero** `x-mitre-asset` objects — the
premise of the A-AST boundary questions (Assets are ICS-only, so the honest
answer is a schema-boundary refusal, which also live-tests Step 6 abstention).

## Step 10 additions (run 2026-07-07, same method)

The 67 Step 10 entries — Slice B (14 ATT&CK: detection chains, software usage,
sub-technique hierarchy, 2-predicate tactic×mitigation, data-component
analytics, retired-id negatives), Slice C (13 CAPEC: execution flows,
consequences/skills, abstraction chains, extra CWE coverage, deprecated
negatives), and Slice A (40 federated: CAPEC→technique→mitigation/tactic,
reverse joins, CWE→CAPEC→ATT&CK chains, no-mapping negatives, partials,
fan-in unions) — were audited with the identical protocol, expressed as **93
machine-checkable claims** (one per single-source entry; per federated entry a
`must_correlate` intersection claim plus its mitigation/tactic-union and
reverse-pattern side claims; negatives as no-mapping claims).

Two independent adversarial agents — verifier A restricted to a CLI toolchain
(jq/grep/sed/awk/xmlstarlet), verifier B writing its own stdlib-Python parsers —
re-derived every claim from `data/raw/` only, forbidden from reading
`utils/` or any committed bank. Verdicts were then machine-compared (exact
set/sequence equality) against the committed gold and against each other.

**93 / 93 claims verified by BOTH verifiers — 186 / 186 verdicts `agree`,
zero discrepancies, zero A-vs-B derivation disagreements.**

Notable independently confirmed censuses: the three detection chains
(T1047→DET0364→AN1031; T1110→DET0463; T1566→DET0070), Mimikatz S0002 using 17
techniques, the tactic×mitigation intersections (TA0006×M1027 = 7 techniques,
TA0002×M1038 = 9, TA0006×M1041 = 6), DC0084 monitored by 9 analytics, T1002/
T1004 carried only by retired objects, CAPEC-66's 4-step execution flow
(Explore→Experiment×2→Exploit), all three Detailed→Standard→Meta abstraction
chains, every federated `must_correlate` intersection (e.g. CWE-522 bridging
10 mapped patterns to 12 live T-IDs), and the six verified no-mapping
negatives (incl. CAPEC-66 and CAPEC-116, which carry no ATTACK taxonomy
mapping at all).

## Known limitations recorded during evalset construction

These are *system* gaps the golden suite exposed, not gold-answer errors:

- **CAPEC severity/likelihood not ingested.** `Typical_Severity` and
  `Likelihood_Of_Attack` exist in the gold bank (from the XML) but the loaded
  graph carries only `Abstraction`/`Status`, so no live question can assert
  severity until the ingest adds those properties.
- **Group/Tactic name-lookups unroutable.** The Cypher builder routes any task
  carrying a Group or Tactic entity to the traversal templates before
  node_lookup is considered, so "what is G0016 called" cannot be asked today.
- **Inverse hierarchy unroutable.** The graph stores CAPEC natures exactly as
  declared (no ParentOf/CanFollow inverse edges) and the Gremlin builder only
  emits out()-traversals; the gold `children` map exists for when in()-support
  lands.
- **Edge-label convention bug found and fixed.** The loader stores Gremlin edge
  labels SCREAMING_SNAKE (`CHILD_OF`) while the source card declares CAPEC's
  vocabulary (`ChildOf`); builder and validator now translate through the
  loader's own `gremlin_edge_label()` so the convention cannot drift.

Regenerate the underlying artifacts with:

```bash
uv run python -m utils.specialists.evalset.gold_bank
uv run python -m utils.specialists.evalset.compile_banks
```
