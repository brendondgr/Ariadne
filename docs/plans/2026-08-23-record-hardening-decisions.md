# Record Hardening — the two open questions, resolved

**Date:** 2026-08-23
**Resolves:** §2 "Human intervention is needed" in
[`2026-08-23-record-hardening.md`](2026-08-23-record-hardening.md).

Written as a separate file because `docs/plans/` is append-only (global rule 4).
The plan itself is unchanged; this records what was decided before execution
began, so a later reader does not find two questions marked open and assume they
still are.

---

## Q1 — Does the variance sweep cover the identity schema as well as the catalogues?

**Decided: yes, both.** Operator's call, 2026-08-23.

Step 6 (`EXP-2026-08-015`) therefore runs two populations rather than one:

| Population | Arms | Why it is in |
|---|---|---|
| ATT&CK + CAPEC catalogues | `deterministic`, `generic` | This is where the templates-vs-generic comparison is the paper claim, and where every recorded arm figure lives. A confidence interval here prices the claim as written. |
| ReliaQuest identity schema | `deterministic`, `generic` | The arm gap is an order of magnitude larger here (+0.59 retrieval, EXP-2026-08-011) and it is the only foreign-schema evidence the study has. A gap that size with no interval is the most exposed number in the record. |

Both are retrieval-only and LLM-free in the answer path, so the pipeline
contributes zero variance in either population and all spread is bank-draw
variance. The identity population needs its stack live and uses
`identity_bank.py` / `identity_gold.py` rather than the catalogue bank machinery,
so the two halves are drawn and scored separately and reported side by side.

**Concurrency:** bank authoring is the only LLM step and runs at `--workers 8`,
authorised by the operator on 2026-08-23. The Author model must not be the
pipeline's (`make_bank --model`).

---

## Q2 — Does the verifier ablation stop at the mechanical diff, or buy Sonnet for the residual?

**Decided: stop at the mechanical diff, and export the residual judge-ready.**
My call, delegated by the operator.

Three reasons:

1. **Most of the delta needs no judge.** The four gates are deterministic
   predicates and gold is set-valued, so a claim that survives with one gate off
   can usually be classified by the other three plus gold. Paying a judge for
   what a predicate already answers is waste.
2. **The residual count is itself the result.** "Gate X admitted N claims, of
   which M are mechanically ungrounded and R are ambiguous" is a complete
   finding. R being small argues the gate is precise; R being large is itself
   worth reporting.
3. **It preserves the operator's sequencing.** The standing decision is to see
   the retrieval-only results before deciding whether to buy judging at all.
   Judging the residual inside this experiment would pre-empt that.

**What ships anyway:** the residual is written to a judge-ready artifact in the
experiment's `data/` directory, with the claim, its citations, the executed
query, and the gold row — so buying Sonnet later is one command, not a redesign.
`PROTOCOL.md` declares the judged half as deferred rather than absent, per the
rule that an unrun half is recorded, not omitted.

**Instrument, when bought:** Sonnet via the relay, never local `skynet` — the
local judge is measured to overstate faithfulness by 0.43 (EXP-2026-07-010).
