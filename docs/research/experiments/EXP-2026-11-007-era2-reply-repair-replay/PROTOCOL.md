# PROTOCOL — EXP-2026-11-007 Era 2 Step 2: replaying the reply-repair layer over the kill-test replies

Written 2026-11-15, before the replay was run. The repair code (`utils/llm/repair.py`) and its
unit tests were written first. Its fixtures are synthetic, and no saved reply was inspected
to tune it. The one fix made after the tests ran (no closing at an inner `}`) came from a
synthetic fixture.

## Question

The era-2 model layer adds logged repairs for replies that are nearly but not quite well
formed. Over every reply saved by the typed kill tests (EXP-2026-11-004, -005, -006), we ask:

- How many replies does the layer recover that the kill tests' own parser rejected?
- Does it ever change a reply that the old parser read?
- Does it ever repair something without logging an event?
- Could any recovered reply have changed a kill-test verdict?

## Hypothesis

- **H1 (gate, from the v2 plan): zero silent repairs.** Take every reply whose extracted
  object differs from a plain `json.loads` of the reply text. Each such reply carries at least
  one repair event.
- **H2 (gate): no changed readings.** Where the old parser
  (`utils.killtests.typed.prompts.extract_request`) returned an object, the new layer
  (`utils.llm.repair.extract_json_object`) returns the identical object.
- **E1 (expectation): Gemma's capped replies stay invalid.** Gemma's part-C replies that hit
  the token cap stay unrecovered. They are expected to hold no closable JSON; only the token
  policy can help them.
- **E2 (expectation): few rescues.** At most 2% of the typed replies in any one cache file.
- **E3 (expectation): no verdict changes.** Rescues can only raise typed-arm scores, so only
  hypotheses that failed can flip.
  - For each failed typed-favouring hypothesis, the upper bound is the number of rescued
    replies in that arm divided by n. That bound is smaller than the margin the verdict
    missed by.
  - Margins:
    - EXP-005 part B H2 missed by 0.110 (n = 390);
    - EXP-006 part C H2 missed by 0.222 for Gemma and 0.129 for Qwen (n = 450);
    - EXP-006 part C H3 missed by about 0.40.

## Setup

- **The system:** `utils/llm/repair.py` at the commit that records this experiment.
- **No model calls.** The replay reads saved replies only.
- **The old parser** is imported unchanged from `utils/killtests/typed/prompts.py`.

## Data

Every line of every saved-generation cache:

| Cache (`logs/killtests-2026-11/`) | Experiment |
|---|---|
| `typed/cache/generate.jsonl` | EXP-004 |
| `exp005/cache/{A,B}-generate.jsonl`, `{A,B}-repair.jsonl`, `B-generate.qwen-xhigh-archive.jsonl` | EXP-005 |
| `exp006/cache/{A,B,C}-generate.jsonl`, `{A,B,C}-repair.jsonl` | EXP-006 |

- Keys are `qid|arm|model`.
- **Typed arms** are those whose arm starts with `typed`. They get both parsers.
- **Free-query arms** (`cypher-*`, `gremlin-*`) only get their status classified: ok, empty,
  or cut off at the cap. The JSON repairs do not apply to them.
- The xhigh archive is the superseded EXP-005 Qwen run. It is reported on its own row and is
  not used for E3.
- Saved replies are the last 6,000 characters of the content (`c.text[-6000:]`). A reply
  longer than that is truncated at its start. This is a known limit on what can be recovered.

## Metrics

All are per cache file, model and arm family (typed or free):

- `n`: the number of replies;
- `capped`: `finish_reason == "length"`;
- `empty`: content is blank after thinking is split off;
- `old_ok`: `extract_request` returned an object;
- `new_ok`: `extract_json_object` returned an object;
- `rescued`: `new_ok and not old_ok`, broken down by repair kind;
- `changed`: `old_ok and new_ok and old != new` (gate H2: must be 0);
- `silent`: the new object differs from a plain `json.loads(reply.strip())` but carries no
  events (gate H1: must be 0);
- `still_invalid`: `not new_ok`;
- `capped_rescued`: rescued replies that were capped (E1).

## Baselines

The kill tests' own parser, run over the same replies.

## Procedure

```bash
uv run python scripts/era2_repair_replay.py \
    --out docs/research/experiments/EXP-2026-11-007-era2-reply-repair-replay/data
```

The script writes `data/replay.json` (per-cell counts, plus up to 5 example keys per rescue
kind) and `data/rescued.jsonl` (every rescued reply's key, repair kinds and recovered object).

If the E3 bound is not met for any failed hypothesis, the rescued requests in that arm are
validated against their card and executed, and the arm is re-scored before anything is
concluded. This is decided now, not after seeing the bound.

## What would falsify this

- **H1 fails:** any `silent > 0`. The layer repairs without saying so, and Step 2's gate
  fails. Fix before committing.
- **H2 fails:** any `changed > 0`. The layer reads well-formed replies differently from the
  baseline parser, which would move graded numbers. Fix before committing.
- **E1 and E2** are expectations. A miss is reported as is.
- **E3:** if re-scoring flips a verdict, EXP-2026-11-004 to -006 get an erratum, and the
  era-2 plan's §1.2 is revisited.
