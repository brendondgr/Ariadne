# ISSUES — EXP-2026-07-010

## 2026-08-06 — Back-filled and superseded; provenance largely unrecoverable

**Impact:** `code.commit` unknown, seeds unrecorded, no lockfile. Additionally,
the exact pipeline configuration graded here cannot be reconstructed: eight
defects have since been fixed and the truncation profile has changed.

**Cause:** The run predates the research record by weeks.

**Resolution:** Not resolvable, and not worth resolving — this experiment's
value is as a historical "before", not as a reproducible measurement. Marked
`status: superseded` with `superseded_by: EXP-2026-07-001` rather than deleted.

**Paper implication:** Cite only as the pre-fix baseline, always with the date
and the fact that eight defects were fixed after it.

## 2026-07-20 — Judge comparison is not like-for-like on groundedness

**Impact:** The independent judge scored groundedness **higher** than the
self-judge (0.9575 vs 0.9342), which looks like the independent judge being
lenient.

**Cause:** It is not. The two judges were shown different evidence — the Sonnet
grader received the related-neighbour descriptions that skynet's judge had
stripped.

**Resolution:** Documented rather than corrected; re-running the self-judge with
matched inputs was not worth the compute.

**Paper implication:** Do not present the independent-vs-self groundedness delta
as evidence about judge behaviour. It is evidence about judge *inputs*.
