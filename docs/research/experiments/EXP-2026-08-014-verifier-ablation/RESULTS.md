# EXP-2026-08-014 — The verifier is a guarantee, not a filter

**Status:** complete. The answer to Q10 is a clean negative, and it is more
useful than a positive would have been.

## The headline

Five conditions over 888 claims from 137 answered questions in four banks:

| condition | claims | supported | unsupported |
|---|---:|---:|---:|
| `baseline` (all gates on) | 888 | **888** | **0** |
| `no_cited` | 888 | 888 | 0 |
| `no_resolvable` | 888 | 888 | 0 |
| `no_grounded` | 888 | 888 | 0 |
| `no_correlated` | 888 | 888 | 0 |

| gate | claims it cuts | gold_absent | gold_backed | ambiguous |
|---|---:|---:|---:|---:|
| cited | **0** | 0 | 0 | 0 |
| resolvable | **0** | 0 | 0 | 0 |
| grounded | **0** | 0 | 0 | 0 |
| correlated | **0** | 0 | 0 | 0 |

**No gate cuts anything, because nothing reaching the verifier can fail one.**
The residual is empty, so the deferred judged half has nothing to judge and is
closed rather than pending.

## Why, and why it is not a null result

`utils/synthesis/factory.py::synthesize` composes claims with
`DeterministicComposer` **unconditionally**. The deterministic composer builds
each claim *from* a retrieved record: the citation is the record it was built
from, and the entity ids are that record's own identifiers. A claim that is
uncited, unresolvable or ungrounded is therefore **not constructible** on this
path — not rare, not filtered, unconstructible.

That is a real property, and it is the one C-007 states about query safety:
**a ceiling by construction rather than a score achieved by tuning.** It is also
why the ablation reports zeroes rather than small numbers. A gate that never
fires because its violation cannot be built is not dead code; it is a proof
obligation discharged at the type level, and it becomes load-bearing the moment
anything else composes a claim.

## The finding that matters for C-017

**C-017's first half is true and vacuous on the shipped path, and the claim must
say so.** "Claim-level verification eliminates unsupported claims" is
unfalsifiable here: there are no unsupported claims to eliminate. Evidence for
the property cannot come from an ablation of this pipeline, and the honest
sources are two:

1. **The unit proof** — `utils/synthesis/tests/test_verifier_gates.py` shows each
   gate cuts the violation it names when one is constructed. 13 assertions.
2. **The structural argument** above, which is a design claim, not a measurement.

Stating it as a measured rate would be the same overclaim C-007's note already
warns against.

## A second dead-code finding, of the same class as the deleted templates

`select_composer` and `OpenAICompatibleComposer`
(`utils/synthesis/llm_composer.py`, which builds `Claim.from_dict` off model
JSON) are **unreachable from the pipeline**. `synthesize()` never calls
`select_composer`; it always constructs `DeterministicComposer` directly. The
LLM seam that does ship is `apply_llm_narrative`, which rewrites prose over
already-verified claims and cannot add one — exactly as the README describes.

So **no shipped path lets a language model propose a claim.** This is the same
class of inflation as the two unreachable query templates deleted on 2026-08-23:
described capability with no caller. It is recorded here rather than fixed,
because deleting a composer is a larger change than deleting a template and
belongs in its own step.

**It also bounds this experiment's generality.** The verifier is untested against
the only input that could stress it — LLM-proposed claims — because that input
does not occur. If the LLM composer is ever reconnected, this ablation must be
re-run before any verification claim is made about it, and it will then be
measuring something.

## Threats

* **The zero is a property of the composer, not of the questions.** A different
  bank would not change it; only a different composer would.
* **13 of 150 questions produced no claim** and are outside the denominator
  (abstentions and clarification answers). They cannot contain an unsupported
  claim, so their exclusion cannot hide one.
* **`_mark_contested` and `_enforce_abstentions` are not ablated.** They flag and
  add rather than cut, so the diff design does not reach them. The abstention
  path's own defect is measured separately in EXP-2026-08-007 A-1.
* **Two design errors were found by checking provenance, not by the numbers**
  (PROTOCOL §6). Both produced a plausible zero. The reported zero survives only
  because `composer_used` is now counted per answer and reads
  `deterministic` for all 137.
