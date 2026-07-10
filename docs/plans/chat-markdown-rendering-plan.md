# Chat Markdown Rendering Plan

## Introduction

The chat surface renders assistant replies and user questions as **plain text**.
`ReplyMessage.tsx` puts `run.reply.text` inside a `<p>` via `RefText`, which only
tokenizes CAPEC/ATT&CK identifiers into clickable `ReferenceLink`s — it does no
markdown parsing. `UserMessage.tsx` renders `{text}` raw. As a result:

- Newlines collapse (HTML whitespace folding).
- `**bold**`, `_italic_`, bullet/numbered lists, headings, code, blockquotes,
  and links render as literal syntax instead of formatted output.

Goal: render assistant replies as GitHub-flavored markdown while **preserving**
the existing inline CAPEC/ATT&CK reference-link behavior, and preserve newlines
in user-typed questions. Match Woven Dusk design tokens.

## Gaps / Assumptions

- **Assumption:** Assistant replies get full markdown (bold/italic/lists/code/
  links/headings/blockquote/tables via GFM). Single `\n` should become a line
  break (chat expectation) → use `remark-breaks`.
- **Assumption:** User questions are analyst-typed; do NOT parse them as markdown
  (a stray `*` shouldn't italicize). Instead preserve their newlines with
  `whitespace-pre-wrap`. (Low risk, reversible.)
- **Assumption:** Inline reference linkification must survive inside markdown
  text nodes, but NOT inside markdown `<a>` anchors (nested `<button>` in `<a>`
  is invalid HTML) or inside `code`/`pre`.
- **Library choice:** `react-markdown` + `remark-gfm` + `remark-breaks` — the
  standard, well-maintained React 19-compatible stack. Recorded per ui-frontend
  skill rule (every lib has a job + changelog entry).

## Steps

### Step 1 — Add dependencies
- `cd web && npm install react-markdown remark-gfm remark-breaks`
- **Validate:** packages appear in `web/package.json`; `npm run build` still compiles.

### Step 2 — Build a reusable `Markdown` renderer
- New file `web/components/center/Markdown.tsx` (client component).
- Renders `react-markdown` with `[remarkGfm, remarkBreaks]`.
- Component overrides styled with Woven Dusk tokens (`text-text-soft`,
  `text-primary`, spacing, `font-mono` for code) for: `p, a, strong, em, ul, ol,
  li, h1-h4, blockquote, code, pre, hr, table/th/td, del`.
- A `linkifyChildren` helper recursively walks children; every string leaf is run
  through `tokenizeReferences` → text + `<ReferenceLink>`. Applied in text-bearing
  overrides; skipped for `a`, `code`, `pre`.
- **Validate:** typecheck / lint clean.

### Step 3 — Wire assistant replies to `Markdown`
- In `ReplyMessage.tsx`, replace the `<p className="...">` + `<RefText>` block with
  `<Markdown text={reply.text} />` wrapped in a prose container keeping the current
  `text-sm leading-[1.62] text-text-soft` typography.
- **Validate:** `npm run build`; visual check via preview (bold, list, newline,
  reference link still clickable → seeds composer).

### Step 4 — Preserve newlines in user questions
- In `UserMessage.tsx`, add `whitespace-pre-wrap break-words` to the bubble.
- **Validate:** build; multi-line question keeps line breaks.

### Step 5 — Tests
- Add `web/lib/__tests__/` or component-level assertion where practical; at minimum
  keep `references.test.ts` green (tokenizer unchanged). Run `npm test`.
- **Validate:** `npm test` passes; `npm run lint` clean; `npm run build` succeeds.

### Step 6 — Changelog + commit (NO push — per user directive)
- Append one `docs/changelog.jsonl` entry.
- Commit only the files touched by this change (leave unrelated pre-existing
  `data/versions.json` and `ViewToggle.tsx` edits unstaged).

## Deliverables

| Deliverable | Location |
|-------------|----------|
| Markdown renderer | `web/components/center/Markdown.tsx` |
| Assistant reply wiring | `web/components/center/ReplyMessage.tsx` |
| User newline preservation | `web/components/center/UserMessage.tsx` |
| Dependencies | `web/package.json`, `web/package-lock.json` |
| Changelog | `docs/changelog.jsonl` |
| This plan | `docs/plans/chat-markdown-rendering-plan.md` |

## Validation Summary

- `cd web && npm run build` compiles.
- `cd web && npm test` passes.
- `cd web && npm run lint` clean.
- Preview: assistant markdown renders (bold/italic/lists/newlines), reference
  links still clickable; user multi-line questions keep line breaks.
- Committed locally, not pushed.
