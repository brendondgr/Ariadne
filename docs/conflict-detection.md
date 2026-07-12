# Conflicting-Evidence Detection

Ariadne's synthesis verifier proves two independent axes of trust:

1. **Groundedness** (`verifier.py`) — every claim traces to a real retrieved
   record; uncited, unresolvable, or ungrounded claims are cut.
2. **Consistency** (`reconcile.py`) — the retrieved records agree *with each
   other*. When two sources both carry a canonical join value yet assert
   incompatible facts about it, both records pass groundedness, so nothing else
   catches the disagreement. Reconciliation is that check.

Like the rest of the verifier, it is **always deterministic** — *the model
drafts, deterministic code grades* — so it never trusts the composer it audits.

## What counts as a contradiction

A conservative, explicit allow-list, so false positives stay near zero:

| Kind | Definition | Realistic example |
|------|------------|-------------------|
| `name` | Two sources give a **materially different** canonical name for the same id (case/whitespace/punctuation-normalized, so cosmetic differences do not fire). | ATT&CK names `T1055` "Process Injection"; the label CAPEC embeds in its mapping says "Thread Hijacking". |
| `status` | The **authoritative** source marks the entity deprecated/revoked while another source still maps to it as current. | ATT&CK retired `T1156`; a CAPEC pattern still `MAPS_TO` it. |

**Mapping contradictions are deliberately out of scope.** For this federation
the CAPEC → ATT&CK bridge is *single-sourced* — only CAPEC asserts the mapping —
so there is no second source to contradict it. `name` and `status` are the two
contradiction classes the two graphs can actually produce.

## Authority

Each id scheme has a canonical owner: ATT&CK for technique ids (`T####`), CAPEC
for attack-pattern ids (`CAPEC-#`). A conflict names its `authoritative_source`
when one applies — surfaced to the analyst, **never used to silently pick a
winner**. Both asserted values are always shown.

## Flag, don't cut

A groundedness failure cites nothing real, so it is cut. A conflict's underlying
records are **both genuinely retrieved** — cutting would hide real evidence. So a
contested claim stays `supported` and rendered, but its verdict carries
`contested` (the join values in dispute) and the UI badges it. Honesty at the
point of reading, without suppressing real data.

## Where it runs

`verify_answer` (`utils/synthesis/verifier.py`) calls `detect_conflicts`
(`utils/synthesis/reconcile.py`) after per-claim verdicts, attaches the result
to `VerificationReport.conflicts`, and marks the supported claims that assert a
conflicted id via `ClaimVerdict.contested`. Both ride the answer payload:

```json
"verification": {
  "verdicts": [{"verdict": "supported", "reasons": [], "contested": ["T1055"]}],
  "conflict_count": 1,
  "conflicts": [
    {"join_value": "T1055", "kind": "name", "sources": ["attack", "capec"],
     "values": {"attack": "Process Injection", "capec": "Thread Hijacking"},
     "authoritative_source": "attack",
     "detail": "sources disagree on the name of T1055"}
  ]
}
```

`conflicts`/`conflict_count`/`contested` are **omitted when empty**, so a
conflict-free payload stays byte-identical to the pre-reconciliation stream.

## On the wire and in the UI

The `answer` SSE event carries the block above (`api/services/query.py` emits
`answer.synthesis = SynthesizedAnswer.to_dict()`). The workbench:

- **Verification pill** counts `K source conflict(s)` and turns amber when any
  exist.
- **Contested badge** (`web/components/center/ConflictPanel.tsx`) sits on each
  affected claim — in the Verified Answers prose and the Claim Table.
- **Conflicting sources panel** lists each conflict: the join key, both
  asserted values with source accents, and which source is authoritative.
- **Ticker** appends `reconcile: N source conflict(s)` to the answer event so
  reconciliation reads as a visible step.

## Evaluation

`conflict_count` is a deterministic dimension on every `JudgeVerdict`
(`utils/evaluation/llm_judge/`), taken straight from the verifier (the LLM judge
never sets it). The judge report rolls up `total_conflicts` and
`answers_with_conflicts`, and `e2e_report.py` prints a "cross-source conflicts"
line.

## Key files

| Concern | Location |
|---------|----------|
| `Conflict` contract, `ClaimVerdict.contested`, `VerificationReport.conflicts` | `utils/synthesis/contracts.py` |
| Deterministic reconciler | `utils/synthesis/reconcile.py` |
| Verifier integration | `utils/synthesis/verifier.py` |
| Reconciler tests (incl. no-false-positive) | `utils/synthesis/tests/test_reconcile.py` |
| Front-end view model + projection | `web/lib/types.ts`, `web/lib/adapt.ts` |
| Conflict UI (panel + badge) | `web/components/center/ConflictPanel.tsx`, `AnswerCard.tsx`, `ClaimTable.tsx` |
| Eval metric | `utils/evaluation/llm_judge/` |
