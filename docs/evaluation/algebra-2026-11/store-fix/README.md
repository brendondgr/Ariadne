# Store fix regression (Era 2, Step 9, amendment 4), 2026-11-20

**The change.** Both engines now store values alike, through one rule in
`utils/kg_builder/property_encoding.py`:
- string lists are list values, never JSON text;
- empty lists are not stored;
- lists of objects are JSON text in both engines;
- relationship properties, including the STIX `description`, are written in both loaders.

**The procedure:**
1. `capture.sh before` ran in a detached worktree at 1d9e46e8, on freshly reloaded stores.
2. `after.sh` rebuilt the artifacts (`main.py --build all`), wiped Gremlin, reloaded both
   measured stores, and ran `capture.sh after` on the changed tree.
3. Each capture covers the R reference, the deterministic arm on three banks, and the typed-plan
   pipeline replay of three arms.
4. `diff.py` compares the two captures, clock keys excluded.

**The result** (`before-after-diff.json`):

| Capture | n | Same entity ids | Same bytes (clock keys excluded) |
|---|---|---|---|
| R reference (gold 120) | 120 | 120 | 92 |
| deterministic, bank-2026-08-19 | 30 | 28 | 26 |
| deterministic, bank-2026-08-20 | 30 | 30 | 25 |
| deterministic, dev 284 | 284 | 284 | 223 |
| typed replay T-lazy / T-full / T-lazy-G | 681 / 685 / 683 | all | — |

**What changed:**
- **The byte changes are all CAPEC answers.** List values now print as lists instead of JSON
  text, and `_attribute_pairs` orders lists after scalars, which moves some attribute claims.
- **The two id changes** (H-CHN-02, H-CHN-03) are truncated answers. They show 8 of 29 and
  4 of 12 patterns of a CWE.
  - Both before and after are correct subsets of the full set in the store.
  - Which subset is shown follows the store's insertion order, and the wipe and reload
    changed that order.
  - This is an existing property of capped answers, not the encoding change.
