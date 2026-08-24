# PROTOCOL — EXP-2026-08-014

**Written before the run.** Amended once, mid-run, and the amendment is recorded
in §6 rather than folded into the text — the original design was wrong in a way
worth keeping on the record.

## 1. The question

C-017 claims claim-level verification "eliminates unsupported claims". The
evidence has always been provenance and inspectability reading 1.0, which are
self-consistency checks: they say the verifier ran, not that it caught anything.
Q10 names the missing measurement — **disable each gate individually and see what
it was holding back.**

## 2. Conditions

Five, over the same inputs:

| condition | gate disabled |
|---|---|
| `baseline` | none — the shipped configuration |
| `no_cited` | a claim need not carry a citation |
| `no_resolvable` | a citation need not resolve to a retrieved record |
| `no_grounded` | an asserted entity need not appear in the cited records |
| `no_correlated` | a correlation need not be backed by the join index |

Gates are switched by `VERIFY_GATE_*` on `SynthesisConfig`, all defaulting on.

## 3. Population

Every question in the four committed banks: `attack_questions.json` (46),
`capec_questions.json` (34), `federated_questions.json` (40),
`holdout_questions.json` (30) — 150 in total, of which those producing at least
one claim are scored.

## 4. Design — one pipeline pass, five verifications

The verifier is a pure function of (claims, evidence). Each question is run
**once** and the five conditions re-verify the *identical* live objects, so any
difference between conditions is the gate and nothing else. Five separate runs
could not promise that: each would re-plan and re-retrieve.

Deterministic and LLM-free throughout, so the reading is byte-reproducible.

## 5. Measurement — the diff, classified without a judge

For each gate, the claims `unsupported` at baseline and `supported` with that
gate off are exactly what it cuts. Each is classified against the question's
gold:

* `gold_absent` — no entity id in gold: the gate cut something unwarranted.
* `gold_backed` — every entity id in gold: the gate cut something true.
* `ambiguous` — partial overlap or no usable gold. **The residual.**

**Pre-registered:** the residual is counted and exported, never guessed at.
Judging it is the deferred half (`docs/plans/2026-08-23-record-hardening-decisions.md`
Q2); Sonnet is the named instrument, never local `skynet`, which is measured to
overstate faithfulness by 0.43.

## 6. Amendment, mid-run — two design errors, both found by checking provenance

**(a) The committed artifacts cannot support this experiment.** The first
implementation re-verified recorded answers offline and reported zero unsupported
claims over 1,756 claims. That was an artifact:
`utils/evaluation/generate_e2e.py::_answer_dict` serialises
`ans.rendered_claims()` — the **supported** set — so every claim the verifier cut
was already gone, and no recorded answer carries a `verification` block at all.
Rewritten to run the pipeline.

**(b) The LLM composer arm was silently the deterministic composer.**
`iter_pipeline` does `replace(SynthesisConfig.from_env(), llm_enabled=use_llm)`,
so `use_llm=False` overrides `SYNTHESIS_LLM_ENABLED` and forces the deterministic
composer. Only `answer.composer` revealed it. Fixed by injecting
`synthesis_config` directly, which `iter_pipeline` honours over the override —
this also makes the composer switchable **on its own**, with planning and query
construction still deterministic, which is what an ablation requires.

`composer_used` is now counted per answer and reported, so a silent fallback can
never again be read as a clean zero.

## 7. What would falsify the claim under test

A gate whose removal admits claims classified `gold_absent` is a gate doing work.
A gate whose removal admits nothing is either redundant or facing an input that
cannot violate it — and §5's classification cannot tell those apart, so the
distinction has to be argued structurally in RESULTS, not measured here.
