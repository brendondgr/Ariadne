# Latency probe — one controller step on the local stack (2026-10-26)

**A probe, not an experiment.** One question, three repeats per condition, one user,
warm GPU, no concurrency. It times how long each kind of model call takes. It does
**not** measure accuracy. Run before any controller was built, to replace the deep-research
reports' assumed "several seconds per call" with a measured figure.

- Relay `http://localhost:9090/v1`, alias `default-model`. `scripts/model_identity.py`
  reported **`minicpmv47-35b`** on 2026-10-26, not the `qwen38-27B-v2` the September
  record names. Every figure below belongs to that model only.
- Decision model: GAIFA's `decide` mod on `:5107`, d3-lite at revision `03560c26`.
- Scripts: [`latency_probe.py`](latency_probe.py) and [`probe2.py`](probe2.py), run with
  `python3 -I <script> data/source_cards/attack.json`.

## The controller call

The prompt holds the ATT&CK card's label and relation glosses, the question "How do I defend
against T1176?", and one observation (the anchor and its relation counts). The tool is
`expand(anchor_id, relation, direction, target_label)` with `relation` and `target_label` as
enums taken from the card. The tool call came back with the same arguments in all nine runs:
`{"anchor_id": "T1176", "relation": "MITIGATES", "direction": "in", "target_label": "Mitigation"}`.

| Condition | Prompt tokens | Completion tokens | Seconds (3 runs) |
|---|---|---|---|
| Tool call, thinking off | 953 | 140–146 | 0.66, 0.74, 0.70 |
| Tool call, thinking budget 512 | 951 | 287–339 | 1.47, 1.42, 1.27 |
| Tool call, thinking budget 2048 | 951 | 291–581 | 1.52, 1.16, 2.38 |
| Pick from a four-option menu, thinking off | 577 | 7 | 0.41, 0.33, 0.30 |

## Prompt size

Two copies of the full ATT&CK card JSON (27,353 prompt tokens) with a four-token answer:
**2.50 s** on the first call and **0.60 s** on the second, when the relay could reuse the
cached prefix. A stable prompt prefix (cards first, in a fixed order) is worth about 2 s per call.

## The decision model

One request with two questions: a four-way relation choice (MITIGATES / DETECTS / USES /
NONE, each with a one-line gloss) and a yes/no on whether "the Chrome add-on technique" means
T1176 Browser Extensions.

| Run | Seconds | Server ms | Relation (p) | Entity (p) |
|---|---|---|---|---|
| 0 (model load) | 7.17 | 7,160.3 | MITIGATES (0.614) | yes (0.791) |
| 1 | 0.09 | 85.8 | MITIGATES (0.614) | yes (0.791) |
| 2 | 0.08 | 79.3 | MITIGATES (0.614) | yes (0.791) |
| 3 | 0.08 | 82.9 | MITIGATES (0.614) | yes (0.791) |

Deterministic: the same probabilities on every run. The right answer won both questions, but
the relation margin is modest (0.614), so calibration on Ariadne's banks has to come before any
threshold is chosen.

## For comparison (from the record, not re-measured)

`EXP-2026-09-016` A-3, single user, 20 questions: hand-written templates **0.006 s** median;
model writes the query **182.0 s** median. That arm ran a different model, with large thinking
budgets, and had the model write whole queries. Today's controller-step figures are not
comparable with it and do not replace it.
