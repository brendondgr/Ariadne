# ISSUES — EXP-2026-11-020

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-11-20 — the census ran on an uncommitted tree
**Impact:** none on the figures. The script, rubric and labels are committed with this record.
**Cause:** the base commit is 6cbb3590; the new script and its test were uncommitted when run.
**Resolution:** `dirty: true` in the manifest. The commit that adds this record holds exactly
the code that produced `counts.json`, and re-running `count` reproduces it byte for byte.
**Paper implication:** none.

## 2026-11-20 — labeller A ran as three batches
**Impact:** none expected. The same rubric and instructions went to three Opus 5.5 subagents,
on 225, 225 and 223 items in draw order.
**Cause:** batch size.
**Resolution:** `labels-a.jsonl` is the three outputs concatenated in order. Batch 2 was almost
all one template family (`relationships_uses_software`), so its uniform labels are expected.
**Paper implication:** none.

## 2026-11-20 — labeller B labelled one template by its first words
**Impact:** none. The 31 "How does attack software S use technique T" items are one AttackQA
template; B read them, then assigned `O4.verify` by the opening words. A labelled each one, and
labelled them the same.
**Cause:** the subagent's own shortcut, reported in its hand-back.
**Resolution:** recorded; the κ is unaffected, since A and B agree on all 31.
**Paper implication:** none.

## 2026-11-20 — relationship edges carry no description
**Impact:** verify questions (0.44 of AttackQA) can be answered as existence, not as the "how"
text they ask for.
**Cause:** the live store's `USES`, `MITIGATES` and `DETECTS` edges hold only `id` (queried
2026-11-20). The STIX relationship descriptions are not loaded.
**Resolution:** not resolved. It is a builder change, proposed to the operator.
**Paper implication:** any external verify score must say whether edge text was available.

## 2026-11-20 — correction: the loader, not the builder, drops edge descriptions
**Impact:** none on any figure. It corrects where the "how" text is lost.
**Cause:** RESULTS § 4 and § 6 first said the builder drops relationship descriptions. Phase E
of Step 9 read the built records: canonical edges carry `properties`, including `description`.
The Neo4j and Gremlin stores write only `id` (`relationship_merge_cypher`,
`edge_upsert_traversal`).
**Resolution:** RESULTS corrected. Loading edge properties is proposed to the operator as a
loader change.
**Paper implication:** none.

