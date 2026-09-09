# AGENT_INSTRUCTIONS §9–§10 — the one-time migration (completed 6 August 2026)

Moved out of the live contract on 2026-09-09 because the retrofit it describes is
done. Kept verbatim; a dated record, never edited.

## 9. Migration procedure for an existing repository

Execute in order; open a plan for approval before step 3.

1. **Inventory.** Find every existing result: notebooks with output cells, `results/` dirs, `.csv`/`.json` metric dumps, plots in `assets/` or `images/`, benchmark numbers quoted in README or issues, evaluation numbers in commit messages, prior chat/report exports.
2. **Triage.** For each: does it support a claim you intend to make? If yes → back-fill. If no → leave in place and note it.
3. **Back-fill.** Create an experiment folder per recovered result. Mark unknown provenance honestly: `status: superseded`, `code.commit: unknown`, and an `ISSUES.md` line stating what could not be recovered. **Do not fabricate manifest fields.** A back-filled experiment with three known fields is more useful than one with ten invented ones.
4. **Re-run what matters.** Any result destined for the paper that cannot be traced to a commit and a seed should be re-run under the new protocol. Everything else stays as historical record.
5. **Install structure + templates + automation** (sections 2, 3, 7).
6. **Amend docs** (section 6).
7. **Seed `CLAIMS.md`** with the paper's intended claims, most marked unsupported. This immediately surfaces the real experiment backlog.
8. **Turn on CI** and let it fail loudly on the next PR.

---

## 10. Acceptance criteria

The retrofit is complete when all of the following hold:

- [ ] `docs/research/` exists with the full structure from section 2.
- [ ] `make new-experiment SLUG=x` scaffolds a valid, validator-passing experiment.
- [ ] `make validate-research` passes and fails correctly on a deliberately broken folder.
- [ ] `make figures` regenerates every promoted figure with no diff.
- [ ] `INDEX.md` is generated and current.
- [ ] `CLAIMS.md` lists every intended paper claim with its evidence status.
- [ ] At least one real experiment is fully recorded end to end as a worked example.
- [ ] All pre-existing results are either back-filled or explicitly noted as unrecoverable.
- [ ] README, CONTRIBUTING, and the agent instruction file point at `docs/research/`, with no other documentation rewritten.
- [ ] CI enforces validation on every PR.

---

