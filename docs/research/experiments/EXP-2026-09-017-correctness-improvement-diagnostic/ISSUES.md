# Scope and provenance

- Retrospective analysis only. `n_runs: 1` refers to each source arm's historical system run, not a new execution. No seeds were introduced; grading positions are not independent runs.
- `code.commit` identifies the repository inspected. `dirty: true` records that the analysis scripts and report were being authored during the analysis; their exact source is committed with this record. No application code changed.
- No LLM calls were made. Original qwen scores are reused, with known rubric and gold limitations.
- Hardware, elapsed compute and a fully locked plotting environment were not collected. Matplotlib version is pinned in the reproduction command; the figure dependency is kept outside project dependencies.
- The D6 retrieval reversal in earlier prose does not describe judged correctness. Both instruments are explicitly separated in RESULTS.
- Qualitative examples were selected from low-scoring development answers and cannot establish prevalence.
