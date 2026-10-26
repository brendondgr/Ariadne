# Agentic retrieval loop — 2026-10-26

**The four numbered reports were not produced by this repository's pipeline.** They are
external deep-research reports, one per prompt in
[`docs/prompts/2026-10-26-agentic-loop-README.md`](../../../prompts/2026-10-26-agentic-loop-README.md),
copied here unchanged from the operator's downloads. No number in them comes from an experiment
of ours, and their figures keep the reports' own read-status tags.

| File | What it is |
|---|---|
| [`SYNTHESIS.md`](SYNTHESIS.md) | Reads across the four reports, the GAIFA agent loop and the probe, and sets out the revised design, the test plan and the open research areas |
| [`1-controller.md`](1-controller.md) … [`4-embedding.md`](4-embedding.md) | The external reports |
| [`probe/RESULTS.md`](probe/RESULTS.md) | Per-call latency of the local model and d3-lite, measured 2026-10-26: a probe, not an experiment |

Nothing here changes a claim in [`CLAIMS.md`](../../CLAIMS.md). The test plan in `SYNTHESIS.md`
§6 is a proposal; each step becomes an experiment only through `make new-experiment`.
