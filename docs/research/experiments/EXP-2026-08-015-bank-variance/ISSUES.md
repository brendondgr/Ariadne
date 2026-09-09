# ISSUES — EXP-2026-08-015

## I-1 — The anchor registry keys on the output path, and silently degraded exclusion

`make_bank --out <dir>/<name>.json` derived the registry name from the output
file's **parent directory** (`make_bank.py:189`, `name = out.parent.name`). That
is correct for the intended `<dir>/<bank>/bank.json` layout and catastrophic for
a flat one: writing ten banks to `banks/bank9001.json … banks/bank9010.json`
made every one register under the key `banks`, each overwriting the last, so
exclusion carried forward **only the previous bank**.

It printed a plausible count throughout — `excluded 90`, then `120`, then `120`,
then `120` — which reads like accumulation flattening out rather than a bug.

**Caught by measurement, not by reading the log.** A pairwise-anchor-overlap
check over the first five banks found 3 overlapping pairs sharing 8 anchors.

**Fixed** in `make_bank.py`: the name falls back to the file stem when the file
is not the conventional `bank.json`. The five affected banks were **discarded**
and all ten redrawn into per-bank directories. The polluted `banks` key was
removed from `drawn_anchors.json`.

**Standing consequence:** disjointness is asserted in RESULTS by measuring
pairwise overlap, never by quoting the exclusion count the tool prints.

## I-2 — Identity banks shrink as the pool thins

Identity draws chain `--exclude-bank` over every prior bank plus the three the
schema-transfer fixes were developed against. The tenant graph is 1,339 nodes
with a fixed `BANK_SHAPE` of 30 questions across seven kinds, and some kinds draw
from small populations — eight declared homogeneous triples, for instance.

Later banks are therefore smaller: bank 9106 compiled **17** questions rather
than 30. This is the exclusion registry working, not failing, but it means the
identity banks are **not equal-sized**, and a per-bank mean over 17 questions is
noisier than one over 30.

**Consequence for the reading:** the identity spread is an upper bound on
stability, not a like-for-like of the catalogue's. Bank sizes are reported per
row in `metrics.json` so a reader can weight them.

## I-3 — Machine-authored phrasing

Both populations are authored by `skynet`, never by a human. They are as *blind*
as holdout-v1 — the Author never sees the templates or the code — but one model
at one temperature explores a narrower band of phrasing than a human would.

This is a **regression and comparison instrument**. The interval it produces is
an interval over *anchor* draws, not over the full space of ways an analyst might
ask. A published headline figure still wants human-authored questions, which
Q16 records as unobtainable rather than merely unpurchased.

## I-4 — The post-Q22 catalogue re-run has no surviving artifact (2026-09-09)

**Impact:** `catalogue_templates_post_q22` = 1.0000 and
`catalogue_paired_difference_post_q22` = 0.0000 (RESULTS A-1, now the manifest's
current values) are recorded from prose. The only sweep output on disk
(`catalogue/metrics.json`, `catalogue/runs/**`) is the pre-fix run of 2026-08-24
14:32; the Q22 commit `152639b` added no artifact. A-1's "15 of 300 answers
changed" is likewise unreproducible from anything committed.
**Cause:** the re-run overwrote nothing and wrote nowhere under version control.
**Resolution:** not resolved. Re-running `scripts/variance_sweep.py --population
catalogue` at any commit ≥ `152639b` reproduces the fixed figures (both arms are
LLM-free given the committed banks). Until then the withdrawn pre-fix values in
the manifest are the only artifact-backed catalogue numbers.
**Paper implication:** quote the catalogue gap as 0.0000 after Q22 with the
pre-fix −0.0100 as the defect that was found; state that the post-fix figure is
a re-run recorded in the experiment's amendment.

## I-5 — The Author model is identified from the README era table, not from the bank files (2026-09-09)

**Impact:** `llm.model` = `relay/Ornith-1.5-35B-A3B-W4A16-SYM@2026-08-24`.
Every `bank.json` records only `author_model: "skynet"`, the relay alias
(D-028). The identification rests on `docs/evaluation/README.md`'s row for
2026-08-24 (operator, serving side) and the bank mtimes (13:49–14:05 that day).
**Cause:** the authoring path wrote the alias, never the served model.
**Resolution:** recorded as the best-supported identification; no bank number
depends on the Author's identity because both arms run LLM-free.
**Paper implication:** none beyond the standing D-028 caveat.

## 2026-09-09 — n_examples was 483; the identity banks hold 193 questions, not 183
**Impact:** `data.n_examples` corrected 483 → 493 (RESULTS A-2). No metric changes; per-bank n was already correct in `metrics.json`.
**Cause:** typed, not summed.
**Resolution:** corrected in place.
