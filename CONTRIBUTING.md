# Contributing

Agent workflow rules — read first:
[`docs/skills/global-project-rules/SKILL.md`](docs/skills/global-project-rules/SKILL.md).
Command reference: [`docs/commands.md`](docs/commands.md). Repository map:
[`docs/structure.md`](docs/structure.md).

## Running an experiment

1. `make new-experiment SLUG=<slug>` — scaffolds the folder from templates,
   allocating the next ID and capturing the git commit, branch, and dirty-tree
   status automatically.
2. Fill `PROTOCOL.md` **before** running anything. A protocol written after the
   numbers are in is not a protocol.
3. Run via the recorded entrypoint so the manifest reflects what actually ran.
4. Fill `RESULTS.md`, regenerate figures, and run `make validate-research`.
5. Commit the experiment folder in the same commit as any code change it
   depends on.

```bash
./scripts/install_hooks.sh  # once — regenerates INDEX.md and validates on commit
make new-experiment SLUG=my-experiment
make validate-research      # schema, linkage, figure, and pointer checks
make index                  # regenerate docs/research/INDEX.md
make figures                # regenerate every promoted figure and table
make test-research          # the research-record test suite
```

Regenerating figures needs `rsvg-convert` (`librsvg2-tools` on Fedora,
`librsvg2-bin` on Debian/Ubuntu). Everything else is pure Python.

The full contract is [`docs/research/AGENT_INSTRUCTIONS.md`](docs/research/AGENT_INSTRUCTIONS.md).

### The rules that get enforced

CI and the pre-commit hook fail on all of these, so it is cheaper to know them:

- A missing `manifest.yaml`, `PROTOCOL.md`, or `RESULTS.md`.
- `status: complete` with empty `metrics.values`.
- A figure listed in the manifest with no file, or a figure file not listed.
- A figure folder with no generating script.
- A `data/POINTERS.md` row without a hash.
- A `supports_claims` ID that is not in `docs/research/CLAIMS.md`.
- A stale `INDEX.md`, or a promoted figure its generator no longer reproduces.

### Things that are not negotiable

- **Failed and abandoned runs are recorded, not deleted.** Set `status: failed`
  or `superseded` and use
  [`docs/research/templates/negative_result.md`](docs/research/templates/negative_result.md).
- **Never hand-edit a figure, and never hardcode a number in a plotting script.**
  Figures read from `data/metrics.json`.
- **Do not fabricate manifest fields.** `unknown` is a valid value; a guess is
  not. Three known fields beat ten invented ones.
- **Completed experiment folders are append-only.** Corrections go in a new
  experiment or an appended `AMENDMENTS` section, never a silent edit.
- **If asked to "just quickly check" a number, still create the experiment
  folder.**

## General changes

1. **Commit at every step.** After a step's changes pass validation, commit
   immediately — do not batch steps. **Do not `git push`** unless explicitly
   asked; this repository is worked locally.
2. **Every change gets a `docs/changelog.jsonl` entry** — code, docs, config,
   tests, skills, no exceptions. Two to four sentences on what changed and why.
3. **Web changes require `npm run build`** to verify compilation.
4. **Never duplicate agent instructions** outside `docs/skills/`. The `.claude/`,
   `.agents/`, and `.cursor/` folders are pointers only.
5. Leave a branch merged and the tree clean when everything is functional.

## Tests

```bash
uv run pytest utils/research_record/tests -q          # the research record
uv run pytest utils/specialists/tests -q              # specialists + docs contracts
ORCH_MAX_HOPS=5 uv run pytest                         # full suite
```

`ORCH_MAX_HOPS=5` is required for the full suite: the local `.env` pins it to
`1`, which fails the API event-order test.
