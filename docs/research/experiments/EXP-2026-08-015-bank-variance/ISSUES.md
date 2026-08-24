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
