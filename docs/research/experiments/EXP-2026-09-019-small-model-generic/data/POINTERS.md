# POINTERS — EXP-2026-09-019

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — a path alone does not say whether the
directory still holds what it held when the number was computed.

Every answer directory below is gitignored raw run output (D-033). The
committed derivatives are `data/metrics.json` (the 2x2, both seams and the
latency sample, all folded into one file so no manifest number is typed
rather than read), `data/endpoint.json` and `data/planner_cost.json`.

Hashes are over each directory's files in sorted path order, judgment
sidecars excluded — a sidecar beside its input is how `EXP-2026-09-016` A-8
double-counted a grading pass.

| Artifact | Path (repo-relative) | Files | Bytes | SHA-256 | Mean gold coverage | What it is |
|---|---|---:|---:|---|---:|---|
| generic_narrator_off | `docs/evaluation/experiments/small-model-generic-2026-09-13/twobytwo/generic_narrator_off/answers` | 284 | 8662032 | `sha256:f9abd9331c53c66b4593b399d5b50aaa4b4d825365933f2ddc606bb690ae79d1` | 0.8611 | 2x2 cell: authored plan, no model |
| generic_local_narrator | `docs/evaluation/experiments/small-model-generic-2026-09-13/narrator-full/generic_local_narrator/answers` | 284 | 8593084 | `sha256:45983ddfff092d1368deb44fd3b4bf7fb086117b34fd0016a95b4f92757083eb` | 0.8611 | 2x2 cell: authored plan, 2B narrator (Step 3's full pass) |
| generic_planned | `docs/evaluation/experiments/small-model-generic-2026-09-13/twobytwo/generic_planned/answers` | 284 | 5964435 | `sha256:5b378e592da30af9b87bc19fc76e175df47840a33789c0911b35ebbcf44e85b2` | 0.4797 | 2x2 cell: real planner, no model (Step 2's treatment arm) |
| generic_planned_local | `docs/evaluation/experiments/small-model-generic-2026-09-13/twobytwo/generic_planned_local/answers` | 284 | 5907108 | `sha256:fceddd8eeccd250ca542d313f296f44edb30a5d4b34c5437012ac3970baa3f56` | 0.4824 | 2x2 cell: real planner, 2B narrator — the cell nobody had run |
| generic_narrator_off | `docs/evaluation/experiments/small-model-generic-2026-09-13/narrator-full/generic_narrator_off/answers` | 284 | 8662055 | `sha256:3d68478c6bb6863d3eddfa3d237e01b72eb666345a438219b4f00f6139745987` | 0.8611 | Step 3's control, same root as its narrator arm |
| generic_composed | `docs/evaluation/experiments/small-model-generic-2026-09-13/planner-cost/generic_composed/answers` | 284 | 8654333 | `sha256:9fd5ef6dabd59b4ff59b1c1b9151e2064d41dbb489b38471ec65c535ddd100c2` | 0.8611 | Step 2's original control; superseded as a control by generic_narrator_off (I-8), kept because the published -0.3814 was computed against it |
| generic_local_full | `docs/evaluation/experiments/small-model-generic-2026-09-13/specialist-dry/generic_local_full/answers` | 9 | 45717 | `sha256:0c818780fa8ae5254b63d282181d027b3642c59171bd153c0b73b7364b1eb9ae` | 0.0000 | Step 4 gate, 4096-token budget |
| generic_local_full | `docs/evaluation/experiments/small-model-generic-2026-09-13/specialist-bigbudget/generic_local_full/answers` | 9 | 46982 | `sha256:0dcfcdfdb0c8f93e7d52ed405eb9cc3e59428a7ad3545d9fa6ef79ca8796027f` | 0.0000 | Step 4 gate, 16384-token budget |
| generic_local_narrator | `docs/evaluation/experiments/small-model-generic-2026-09-13/latency-1worker/generic_local_narrator/answers` | 9 | 118084 | `sha256:cbca8e3c7c558d8392bbae43eaa0981c91199b668acd50579b078cd445b0ad68` | 0.8095 | single-user latency, 1 worker |

## Inputs

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| development bank | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | the 284 questions every cell answers |
