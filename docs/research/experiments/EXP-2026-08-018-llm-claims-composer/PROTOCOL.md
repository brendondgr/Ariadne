# PROTOCOL — EXP-2026-08-018

**Written before the run.**

## 1. The question

Q20. `OpenAICompatibleComposer` is the only thing in this codebase that lets a
language model **propose a claim**, and `factory.synthesize` never called
`select_composer`, so it had no caller. That is why EXP-2026-08-014 could report
only that all four verifier gates cut **zero** claims from 888 — a true result
and a vacuous one. **A gate cannot cut what cannot be constructed.**

The operator's instruction was explicit: reconnect and measure **before** any
decision to delete, and run **a series of tests, not a single check**.

## 2. Reconnected behind its own flag, and why that is not fussiness

`SYNTHESIS_LLM_ENABLED` has always meant *"an LLM writes the narrative prose over
already-verified claims"*. Arms `llm` and `gold_llm` set it, and the figures
behind C-002, C-005 and C-006 were all measured with it true. Gating the claims
composer on that same flag would have silently changed what those arms do and
made every one of those figures unreproducible.

So the claims composer gets `SYNTHESIS_LLM_CLAIMS`, defaulting **false**. Nothing
recorded moves.

## 3. The five tests

| | what it asks | why it is not the same as the next one |
|---|---|---|
| **T1 engagement** | does the composer actually run per question, or does the hybrid fall back? | measured from `answer.composer` and `fallback_reason`, never from the flag — EXP-2026-08-014's first LLM arm was silently deterministic and only this field revealed it |
| **T2 gates** | do the four verifier gates fire on LLM-proposed claims? | the measurement Q10 and C-017 could not make |
| **T3 grounding** | do surviving claims carry the gold the deterministic composer carries? | retrieval is identical, so any difference is *composition* |
| **T4 variance** | spread across repeats | the composer is nondeterministic; a single-run figure here would be the n=1 problem Q2 exists to fix |
| **T5 cost** | wall clock against deterministic | C-004 priced the deterministic path; this prices what an LLM claims step costs on top |

## 4. Controls

* **Retrieval is held constant.** Planning and query construction stay
  deterministic in every condition, so the evidence bundle for a question is
  identical and only composition varies.
* **The prose narrator is off** (`SYNTHESIS_LLM_ENABLED=false`) in both arms.
  Leaving it on would confound two LLM seams.
* **The deterministic arm runs once**, deliberately: it is byte-reproducible, so
  one run is its whole distribution.
* **Population** is the 120-question golden catalogue — attack, capec and
  federated — not the holdout, because the question is about the composer rather
  than about generalisation.

## 5. Pre-registered decision rule

Q20 asks whether to keep or delete. Stated **before** the numbers:

* **Delete** if the composer cannot be made to run reliably (T1 fallback rate
  high), *or* it runs and the gates never fire (T2 zero) — the latter would mean
  reconnecting bought no measurement, which was the entire justification.
* **Keep** if the gates fire on real LLM output, because that is the only
  configuration in which C-017's central property is testable at all — even if
  the arm is worse on every other axis.
* **Keep-but-never-default** if it engages and the gates fire but T3 or T5 is
  materially worse. That would make it an *instrument*, not a shipping path, and
  it must be recorded as such.

## 6. Threats declared in advance

* **One model, one quantisation, one day** — and per Q12 the relay alias now
  serves `Ornith-1.5-35B-A3B-W4A16-SYM`, not the Gemma build the July arms used.
  Nothing here transfers to another model.
* **The gates firing is not the same as the gates being *right*.** A cut claim
  might have been true. This measures that the mechanism engages; whether each
  cut was correct needs a judge and is not bought here.
* **Under-enumeration is expected and is not a defect of the verifier.** If the
  LLM proposes fewer claims than the deterministic composer, the gates have less
  to cut, and T2 must be read against T3 rather than alone.
