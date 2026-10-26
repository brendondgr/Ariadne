# Documentation reorganization — two eras (2026-10-26)

**Status: executed on 2026-10-26.** This reasoning was written and committed before anything
moved; the four commits that carried it out are listed in
[`changelog.jsonl`](changelog.jsonl) under 2026-10-26, each with the gates it ran. The
resulting map is [`structure.md`](structure.md) and the front door is
[`README.md`](README.md). Paths in sections 2 and 3 are the paths as they were before the
change.

## 1. Why

Ariadne's documents describe two different projects, and nothing told a reader which one
they were reading.

- **Era 1, finished: the Innovation Challenge.** The year-one ReliaQuest award (June 8 to
  October 23, 2026) paid for a federated, provenance-checked query prototype over ATT&CK
  and CAPEC and a research programme to measure it: the arm comparisons, the question
  banks, judging, experiments `EXP-2026-07-001` to `EXP-2026-09-029`, the September
  showcase and the October pitch. All of that was done *for* the pitch.
- **Era 2, current: the expansion.** From the ReliaQuest year-two award onward, Ariadne
  becomes an embeddable, graph-universal, exact retrieval agent that other systems call.

Before this change the two were mixed in the same folders (`docs/prompts/` held both;
`docs/proposal/` held the year-one proposal and the October ARA drafts), and several
era-1 documents still read as current: `goals.md` marked pitch preparation as "underway",
and `RESULTS.md` described "the two most recent" experiments and the "open work" as if
the programme were still running.

## 2. Where the line is, and how it was found

**The line is the October pitch: 2026-10-19.**

| Evidence | What it says |
|---|---|
| `docs/pitch/october-pitch-plan.md`, first line | "ReliaQuest Innovation Challenge pitch, FSU Discovery Days, October 19, 2026" |
| `docs/showcase/README.md` | The showcase deck was built on 2026-09-15 for the same challenge |
| `git log` | The last research commit is 2026-09-23; the 2026-10-15 commits only rewrote the README and cleaned the root for outside readers; the next commit, `37cace55` (2026-10-26), opens the post-pitch section |
| First post-pitch documents | `docs/prompts/2026-10-20-plug-and-play-retrieval.md` and the ARA drafts are dated 2026-10-20, the day after the pitch |
| `docs/expansion/README.md` | Places the research programme before the pitch and the new direction after it |

The repository holds the plan for the event, not a record of it; the date comes from the
plan and agrees with the owner's account (about a week before 2026-10-26).

**Rule used to classify a document:** era 1 if it was written for, or reports on, the work
up to the pitch; era 2 if it was written from 2026-10-20 for the new direction; timeless if
it describes the system or how to run, extend or trust it, which both eras rely on.

## 3. Audit

### Timeless — stays where it is, unchanged

| Document | Why timeless |
|---|---|
| `README.md` (root) | The project's front page: what Ariadne is and how to run it. Gains links to the two eras and to the docs front door (section 5). Its Team & Funding section names only the year-one award (section 8) |
| `CONTRIBUTING.md`, `CITATION.cff`, `LICENSE`, `NOTICE`, `images/` | Workflow, citation, licences, README images |
| `docs/ARCHITECTURE.md` | Describes the shipped pipeline, which is what era 2 starts from |
| `docs/commands.md`, `docs/source_cards.md`, `docs/agent-interfaces.md`, `docs/query-safety.md`, `docs/migration-guide.md` | How to run, extend, integrate with and trust the system. Some mention when they were written ("frozen since Wk 10–11", "Proposal Deliverable #6"); the contracts they describe still hold |
| `docs/CHANGELOG.md`, `docs/changelog.jsonl` | One append-only log across both eras |
| `docs/structure.md` | The repository map; rewritten for the new layout (section 5) |
| `docs/assets/`, `docs/skills/` | Architecture figure; agent instructions |
| `docs/research/datasets/`, `docs/research/templates/`, `docs/research/AGENT_INSTRUCTIONS.md` | Dataset cards and the record's own contract and templates |

No stray top-level folder is a document: the 2026-10-15 cleanup already moved
`scratchpad/` and `data-identity/`.

### Era 1 — finished

| Document or folder | Reason | Reads as current? |
|---|---|---|
| `docs/pitch/` (deck, script, preview, plan, numbers audit, zip) | The October pitch itself | No: dated and event-specific |
| `docs/showcase/` (deck, brief, figures, zip) | September showcase for the same challenge | **Yes, mildly:** its README lists an "open item" (re-record a clip) that the pitch made moot |
| `docs/proposal/proposal.md` | The funded year-one ReliaQuest proposal | No |
| `docs/goals.md` | The year-one roadmap and deliverables | **Yes:** the pitch-prep row is marked `[~]` "underway as of September 2026" |
| `docs/RESULTS.md` | The research results, moved out of the README on 2026-10-15 | **Yes:** its Status section speaks of "the two most recent" experiments and "the item that now leads" open work, and counts 52 experiments where the record holds 62 |
| `docs/plans/` (32 dated plans and `robustness/`) | Every plan is dated 2026-08-05 to 2026-09-16 | No individual plan does, but the folder gave no sign that it is closed |
| `docs/evaluation/` | Raw artifacts of the era-1 experiments | Its README already says which runs are superseded; nothing says the store is closed |
| `docs/prompts/2026-09-05-positioning-sweep.md`, `2026-09-06-venue-selection.md` | Publication-positioning prompts | Mixed into one folder with era-2 prompts |
| `docs/research/experiments/` (62 folders, `EXP-2026-07-001` to `EXP-2026-09-029`) | The research programme | No: dated, append-only |
| `docs/research/reports/` up to `2026-09-14-…` | Era-1 synthesis reports | Mixed into one table with the era-2 report |
| `docs/research/paper/`, `audit-2026-08-03.md`, `audit-2026-08-31.md`, `history/`, `figures/`, `tables/` | Paper draft, venue analysis, external audits and publication figures from August and September | `paper/venue-targets.md` lists deadlines as plans; whether the paper programme continues is an owner decision (section 8) |
| `docs/research/top-tier-programme-2026-09.md` | A September plan for the paper | **Name collision:** it is titled "Phase 2 — the top-tier programme", which a reader could take for the post-pitch phase |

### Era 2 — current direction

| Document or folder | Reason |
|---|---|
| `docs/expansion/` (`README.md`, `decision-model-tests.md`) | Written 2026-10-26 as the seed of the post-pitch section |
| `docs/proposal/ara-fall-2026-one-pager.md`, `ara-deep-research-prompt.md` | Amazon Research Awards drafts, 2026-10-20 |
| `docs/prompts/2026-10-20-plug-and-play-retrieval.md`, `2026-10-26-agentic-loop-*.md` | The post-pitch research prompts |
| `docs/research/reports/2026-10-26-agentic-loop/` | Four external reports, the synthesis, pointers and the latency probe |

### Spanning both eras — the research record's living ledgers

`docs/research/CLAIMS.md`, `CURRENT.md`, `INDEX.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`,
`RELATED_WORK.md` and `research/README.md` stay the single record for both eras. Every
figure in them today comes from an era-1 experiment, but each is still the latest
measurement of its kind, and era 2 states that it starts from them
(`docs/expansion/README.md`, "What it starts from"). They are therefore **not** stale, and
they are not relabelled; `research/README.md` gains a section saying which parts belong to
which era.

## 4. The layout

```
docs/
  README.md               NEW  front door: the two eras, then the timeless reference
  REORGANIZATION-2026-10.md    this file
  era-1-challenge/        NEW  Era 1, finished: "what we started with"
    README.md             NEW  what era 1 was, where all of it lives, what carries over
    pitch/                MOVED from docs/pitch/
    showcase/             MOVED from docs/showcase/
    proposal.md           MOVED from docs/proposal/proposal.md
  era-2-expansion/        RENAMED from docs/expansion/: "where we're going"
    README.md                  the direction, requirements and research trail (content kept)
    decision-model-tests.md
    proposals/            MOVED from docs/proposal/ara-*.md
  research/               STAYS  the single record, both eras; era section added to its README
  evaluation/             STAYS  era-1 raw artifacts; banner
  plans/                  STAYS  era-1 plans, closed; README added
  prompts/                STAYS  both eras, dated filenames; README with one section per era
  goals.md, RESULTS.md    STAY   era 1; banner at the top
  ARCHITECTURE.md, commands.md, source_cards.md, agent-interfaces.md,
  query-safety.md, migration-guide.md, structure.md, CHANGELOG.md,
  changelog.jsonl, assets/, skills/      STAY  timeless
```

The names say *Era 1* and *Era 2*, not "phase": "Phase 1/Phase 2" already mean other
things in `top-tier-programme-2026-09.md`, in `EXP-2026-08-013` and in two plans. The
suffixes (`challenge`, `expansion`) are the names the owner already uses: the Innovation
Challenge, and the commit that opened "the post-pitch expansion section".

`docs/proposal/` ceases to exist: its era-1 file and its era-2 files go to their eras.

## 5. Every move and relabel, with its reason

### Moves (all `git mv`, content unchanged unless stated)

| From | To | Reason | Who cites the old path, and what is done |
|---|---|---|---|
| `docs/expansion/` | `docs/era-2-expansion/` | It is the era-2 section; the name now says so and sorts after era 1 | Only `changelog.jsonl` (append-only, left as is). Relative links inside keep working: same depth |
| `docs/proposal/ara-fall-2026-one-pager.md`, `ara-deep-research-prompt.md` | `docs/era-2-expansion/proposals/` | Post-pitch proposal drafts belong to era 2 | Cited only by `changelog.jsonl` and the expansion README (updated). The one-pager's three relative links (two to the record, one to the year-one proposal, which moves to era 1) are re-pointed (path only) |
| `docs/pitch/` | `docs/era-1-challenge/pitch/` | The pitch is the end point of era 1 | `scripts/verify_paper_numbers.py` scans the pitch plan for stale figures: its path is updated so `make check-docs` keeps scanning it. `goals.md` cites it in backticks (updated; the docs-contract test checks it). Six files under `docs/plans/` and `changelog.jsonl` keep the old path, by the 2026-10-15 precedent: dated records cite the tree as it was, and `structure.md` records the move. `numbers-audit-2026-09-10.md` has one relative link to `../research/CURRENT.md`, which gains one `../` (path only; no words change) |
| `docs/showcase/` | `docs/era-1-challenge/showcase/` | Built for the challenge showcase | Cited by nothing |
| `docs/proposal/proposal.md` | `docs/era-1-challenge/proposal.md` | The funded year-one proposal defines era 1's scope | Cited only by `audit-2026-08-03.md`, a dated snapshot excluded from link checks, which keeps the old path; `structure.md` records the move |

### Relabels (in place)

| Document | Change | Reason |
|---|---|---|
| `docs/goals.md` | Banner: the year-one roadmap, complete; the pitch happened on 2026-10-19; era 2's goal is in `era-2-expansion/`. The pitch-prep row goes from `[~]` to `[x]` with the date and its cited path updated | It read as a live roadmap. Ticking a delivered row in a living status table records a fact; no task's wording changes |
| `docs/RESULTS.md` | Banner: the era-1 results as the record stood at the pitch; the Status section is September's view and its experiment count is that date's; figures come from `research/CURRENT.md`; where the work goes next is era 2 | Its Status section read as current. A banner says so without rewriting what was measured |
| `docs/evaluation/README.md` | Banner: era-1 raw-artifact store; era-2 runs will be recorded through new experiments | Nothing said the store was closed |
| `docs/plans/README.md` (new) | Index: every plan here is era 1 and closed; why the folder stays at its path | The folder had no index, and the plans cannot move (section 6) |
| `docs/prompts/README.md` (new) | Index with one section per era | The folder mixes both eras and cannot be split safely (section 6) |
| `docs/research/README.md` | New section "Two eras in one record": which experiments, reports, paper files and audits are era 1; that era-2 work enters the same record; that `top-tier-programme-2026-09.md`'s "Phase 2" is an era-1 paper plan | The record serves both eras, so it has to say which part is which |
| `docs/research/reports/INDEX.md` | The one table becomes two, era 1 and era 2; rows unchanged | The era-2 report sat in the same list as the September overnights |
| `docs/era-2-expansion/README.md` | Era-1 dates corrected to "June 8 to October 19, 2026" (was "July to mid-October"); proposal link updated; contents table added | The award started on June 8 and the pitch date is now established; content otherwise kept |

### Navigation

| Document | Change |
|---|---|
| `docs/README.md` (new) | The front door of `docs/`: the two eras side by side, then the timeless reference and the research record |
| `docs/era-1-challenge/README.md` (new) | What era 1 was, where every part lives (moved or in place), what carries into era 2 |
| `docs/structure.md` | The `docs/` table regrouped as timeless / era 1 / era 2 / shared record; "Start here" points at the eras; a "Moved paths" table lists every path this change moved |
| `README.md` (root) | The "More" links name the eras (what we started with, where we're going) and the docs front door. No other change; it stays lean |
| `utils/specialists/tests/test_docs_contracts.py` | The three navigation READMEs join `DOCS`, so their links and cited paths are checked on every run |
| `scripts/verify_paper_numbers.py` | *Added during execution:* `docs/era-2-expansion/README.md` joins the `make check-docs` scan, because it quotes era 2's starting figures from the record (it passed with 0 stale quotes before being added) |

## 6. What stays put, and why

| Path | Why it does not move |
|---|---|
| `docs/research/` (all of it) | It is the single, CI-enforced record. Experiment folders carry manifests, sealed banks with SHA-256 pins and protocols that cite paths; `INDEX.md` and `CURRENT.md` are generated; reports are dated snapshots. It serves era 2 as well, so moving it into an era folder would be wrong as well as risky |
| `docs/evaluation/` | About 44,000 raw artifacts whose directories are hash-pinned in experiments' `data/POINTERS.md`; `holdout-v1/` belongs to the `freeze/holdout-v1` isolation guarantee |
| `docs/plans/` | Cited by 48 files inside experiment folders (one manifest, `EXP-2026-09-002`, records a plan as its `config.path`), by docstrings in seven files under `utils/` and six scripts, by `.gitignore`, `.env.example` and the agent rules; `robustness/_overnight/` is hash-pinned by eight manifests |
| `docs/prompts/` | The era-2 prompts are linked from `reports/2026-10-26-agentic-loop/POINTERS.md` and `SYNTHESIS.md`, and the era-1 prompts from `research/paper/` files, all of which the docs-contract test link-checks. The prompts are verbatim records of what was sent out, and moving them would mean editing their links. Filenames already carry the date; the README separates the eras |
| `docs/goals.md`, `docs/RESULTS.md` | Both are in the docs-contract test's `DOCS` list and in the `make check-docs` scan, and are cited by the root README, scripts, `utils/` docstrings and the agent rules. Banners make the era plain without breaking any of that |
| `docs/research/top-tier-programme-2026-09.md`, `DECISIONS.md`, `CLAIMS.md`, reports, experiments | Never edited: dated or append-only. The "Phase 2" collision is explained in `research/README.md`, not by retitling the file |

## 7. Risks and how each is handled

| Risk | Handling |
|---|---|
| A move breaks a citation | Only folders with few citers move. Living citers are updated; dated records keep the old path and `structure.md` lists the move. A link check over every markdown file outside `docs/evaluation/` runs before and after (zero unresolved links before) |
| A move breaks a hash pin or the validator | Nothing under `docs/research/`, `docs/evaluation/` or `docs/plans/` moves. `make validate-research` output is compared before and after; it must be identical. (In this worktree the validator reports 80 pointer-hash mismatches before any change, because the hashed artifact directories hold gitignored files that a worktree does not have: one directory has 852 files in the main checkout and 568 here. They are unrelated to this change.) |
| The stale-figure gate stops scanning the pitch plan | `scripts/verify_paper_numbers.py` gets the new path, and `make check-docs` must report the same number of scanned documents |
| Generated files edited by hand | `INDEX.md` and `CURRENT.md` are not touched; `make index` must leave no diff |
| Rewriting the past | Content edits to existing files are limited to those listed in section 5: banners, one status tick, path-only link fixes, the era-2 README's date correction, and the reports index split with rows unchanged |
| Untracked files left behind | The main checkout has an untracked, git-ignored `docs/showcase/build/` (the deck generators). Git does not move it on merge; it should be moved by hand to `docs/era-1-challenge/showcase/build/` |
| Active work at the old paths | The ARA proposal (due 2026-11-04) is being drafted in `docs/proposal/`. Git's rename detection carries edits made on `main` across the move when this branch merges; anyone drafting should switch to `docs/era-2-expansion/proposals/` |
| `freeze/holdout-v1`, sealed banks, byte-identical isolation inputs | Not touched |

## 8. Decisions left to the owner

1. **Where era-2 plans go.** *Decided 2026-10-26 by the operator: era-2 plans stay in
   `docs/plans/`, next to the era-1 plans, so the agent rule needs no change.* `docs/skills/global-project-rules/SKILL.md` says plans go in
   `docs/plans/`. That folder is now closed as era 1. The proposal is
   `docs/era-2-expansion/plans/`; the rule is agent configuration and is left for the
   owner to change.
2. **The year-two award in the root README.** Team & Funding names only the year-one award
   period. The repository holds no date or amount for the year-two award, so none was
   written.
3. **Whether the paper programme continues.** *Assessed 2026-10-26 in
   [`plans/2026-10-26-era-2-roadmap.md`](plans/2026-10-26-era-2-roadmap.md): treat the TMLR draft as
   era 1's publication, not an era-2 programme; submitting it is the operator's call.* `research/paper/` and
   `top-tier-programme-2026-09.md` are labelled era 1. If the TMLR draft is still meant to
   be submitted, say so, and it can be listed under era 2 as a carried item.
4. **Experiment numbering for era 2.** New experiments will be `EXP-2026-10-…` and later,
   which already separates them by date. An `era` field in the manifest schema, shown as a
   column in the generated `INDEX.md`, would make it explicit; that is a change to the
   validator and generator, so it was not made.
