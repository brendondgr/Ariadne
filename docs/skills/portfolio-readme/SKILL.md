---
name: portfolio-readme
description: Use when writing, improving, or auditing GitHub portfolio material — profile READMEs, project READMEs, or repo pinning/organization strategy. Applies whenever the user asks to write docs for a project, clean up a repo before an application, make something "portfolio-ready," or asks what to pin. Ask whether the target is general SWE hiring or research-track (PhD/research-lab internship) roles before writing, since the structure differs.
---

# Portfolio README

Canonical instructions. The `.claude/`, `.agents/`, and `.cursor/` copies are
pointers to this file.

## Step 0 — Track

Two audiences need different treatment:

- **Standard track**: SWE / new-grad hiring. Lead with live demos, UX polish, deployment proof.
- **Research track**: PhD / research-lab internships. Lead with architecture, literature-gap framing, and a coherent thesis across projects rather than a highlight reel.

If ambiguous, ask before writing — don't guess silently.

## Step 1 — Gather real context

Read the repo (package manifest, file structure, existing docs) before asking the user anything. Get: what it does, real tech stack, deployment status, 1–2 genuine technical challenges. Never invent metrics, stars, or demo links — leave a `[TODO]` marker instead.

For this repository specifically, verify claims against the code before writing them: the README's accuracy is itself a maintained property enforced by `utils/specialists/tests/test_docs_contracts.py` (see `docs/research/DECISIONS.md` D-012), and the "What actually runs" table in `README.md` is the pattern to follow — every architectural sentence traceable to a named file.

## Step 2 — Project README structure

1. One-paragraph overview (what + why)
2. Tech stack (specific, not exhaustive — 3–5 architecturally significant items)
3. Live demo link near the top, if applicable
4. Screenshot/GIF if UI-relevant
5. Setup instructions (real, tested commands + env vars)
6. 3–5 key features, not a changelog
7. Challenges & design decisions (1–2 genuine ones)
8. Architecture note/diagram (research track: prioritize this over screenshots)

Keep it scannable — short paragraphs, headers, whitespace. No emoji walls, no "Built with ❤️" filler.

Research track additionally: state what the evaluation does **and does not** show. A limitations section that names the missing baseline, the absent holdout, and the judge's own nature reads as rigour, not weakness.

## Step 3 — Profile README (if requested)

Repo named exactly the GitHub username, README.md at root. One-line bio (what they build, not a title), 3–5 core technologies, 3–6 featured repos each with a real one-line description, one current-project line, one deliberate outbound link. Skip animated badge carousels.

## Step 4 — Curation advice

Recommend pinning 3–6 repos for variety + relevance, not just "best." Flag tutorial clones or assignment-named repos (`lab-3`, `hw2`) for archiving. For research track, lead with the 1–2 repos that compose into a coherent narrative rather than pinning every active project equally.

## Output

If editing files directly, write the README to the file and summarize the diff. If asked for advice only, respond in chat. Never fabricate demo links, star counts, or challenges the user hasn't confirmed.
