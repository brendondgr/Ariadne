# Plan — Clickable CAPEC / ATT&CK References in Chat Answers

## 1. Introduction

The analyst workbench renders assistant answers as prose that frequently names cybersecurity
identifiers inline — e.g. *"CAPEC-98 (Phishing) maps to two ATT&CK techniques. These include
T1566, known as Phishing, and T1598, known as Phishing for Information."* Today those identifiers
are plain text; only the separate provenance **chips** (`T1566 · attack/neo4j`) are interactive,
and they jump the inspector, not the conversation. Analysts have no fast way to ask a follow-up
about a specific entity they just read.

This plan makes every CAPEC / ATT&CK identifier that appears **inside assistant answer prose**
clickable. Clicking one pre-fills the composer (the chat box below) with a follow-up question —
*"Could you provide me more details on CAPEC-98?"* — and focuses it, so the analyst can review,
edit, and send. The work is web-only (`web/`), split into a pure, unit-tested tokenizer, a small
piece of context plumbing to drive the composer, an inline link component, and wiring into the
four answer-prose render sites. No backend, API, or data changes.

## 2. Gaps & Unanswered Questions

- **Click behaviour — prefill vs. auto-send.** The request says the click should make *"the chat
  box below … ask 'Could you provide me more details on this specific topic'"*. *Assumption:*
  clicking **pre-fills and focuses** the composer (does not auto-submit), letting the analyst edit
  mode/drafter and confirm. This is the more interactable, lower-risk reading and matches "in the
  chat box below."
- **Follow-up wording.** *Assumption:* `Could you provide me more details on {ID}?` (e.g.
  `Could you provide me more details on CAPEC-98?`). The friendly name in parentheses is not
  reliably parseable from arbitrary prose, so we key on the ID only.
- **Which identifiers.** *Assumption:* reuse the existing `classifyEntity` vocabulary in
  `web/lib/synthesisGraph.ts` — CAPEC patterns (`CAPEC-###`), ATT&CK techniques
  (`T####` / `T####.###` sub-techniques), and ATT&CK mitigations (`M####`) — so detection stays
  consistent with the network plot. Tactics/groups/software are out of scope (they don't appear in
  current answers and risk false positives).
- **Which surfaces.** *Assumption:* only **assistant** answer prose — the final answer paragraph,
  the verified-claim sentences, the claim-table sentences, and the evidence paragraphs. User
  messages and the provenance/join chips (already interactive) are left unchanged.
- **Worktree vs. branch.** The change is self-contained to `web/`. *Assumption:* work on a feature
  branch in the main checkout (not a separate git worktree) to avoid the documented Ariadne
  worktree data-symlink / real-`npm install` overhead, then merge to local `main`. Steps are
  strictly sequential/dependent, so a parallel Agent-Workflow fan-out is not used; implementation
  is done directly.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Reference tokenizer utility + unit tests
- **Locations:**
  - New `web/lib/references.ts` — `tokenizeReferences(text: string)` returning an ordered array of
    `{ kind: "text"; text }` and `{ kind: "ref"; id; scheme: "capec" | "technique" | "mitigation" }`
    tokens; a `followUpPrompt(id: string)` helper returning the follow-up question string. The scan
    regex mirrors the anchored patterns in `web/lib/synthesisGraph.ts` `classifyEntity` (inline,
    with `\b` word boundaries so `T1566` matches but `ST1566`/`CAPEC-98x` do not).
  - New `web/lib/__tests__/references.test.ts` — Vitest cases pinning: CAPEC/technique/sub-technique/
    mitigation detection, mixed prose (the example sentence) split into the right token sequence,
    no-match prose returns a single text token, boundary non-matches, case-insensitivity, and the
    `followUpPrompt` output.
- **Rationale:** A pure function isolated in `lib/` is directly unit-testable (matching the existing
  `lib/__tests__/*` pattern) and keeps regex/format decisions in one audited place before any React
  wiring depends on it.
- **Action:** Undergo the verification/tests/validation process for this phase (`cd web && npm test`).
  Once validated, commit to GitHub stating: Clickable References (1/4) Complete: added the
  `tokenizeReferences`/`followUpPrompt` utility and its unit tests.

### Step 2: Composer prefill plumbing in the workbench context
- **Locations:**
  - `web/components/workbench/WorkbenchContext.tsx` — add a `composerDraft: { text: string;
    nonce: number } | null` state plus a `setComposerDraft(text: string)` action (nonce increments
    every call so repeat clicks on the same id still re-trigger). Expose both on `WorkbenchState`
    and the `useMemo` value.
  - `web/components/center/Composer.tsx` — consume `composerDraft`; a `useEffect` keyed on
    `composerDraft?.nonce` sets the local `question` state and focuses the textarea (via a `useRef`
    on the `<textarea>`), scrolling it into view. Existing send/toggle behaviour is untouched.
- **Rationale:** The composer owns its input state locally; a nonce-stamped context channel is the
  minimal way for a click anywhere in the answer to drive that input without lifting all composer
  state or coupling components directly.
- **Action:** Undergo the verification/tests/validation process for this phase (`npm test`,
  `npm run lint`). Once validated, commit to GitHub stating: Clickable References (2/4) Complete:
  added the `composerDraft` context channel and wired the composer to accept pre-filled follow-ups.

### Step 3: Inline reference-link component + prose renderer, wired into all answer surfaces
- **Locations:**
  - New `web/components/center/ReferenceLink.tsx` — an inline `<button>` styled as a subtle
    in-text link (Woven Dusk teal, underline-on-hover, `font-mono`), `aria-label`
    "Ask a follow-up about {ID}"; `onClick` calls `setComposerDraft(followUpPrompt(id))` from
    `useWorkbench()`.
  - New `web/components/center/RefText.tsx` — a `RefText({ text })` component that runs
    `tokenizeReferences(text)` and renders text tokens verbatim and ref tokens as `<ReferenceLink>`.
  - `web/components/center/AnswerCard.tsx` — replace the raw string renders with `<RefText>`:
    the final-answer `<p>` (`syn.narrative || syn.headline`, ~line 322), each `claim.text` in
    `SynthesisBody` (~line 88), and the `seg.kind === "text"` branch of `Paragraph` (~line 34).
  - `web/components/center/ClaimTable.tsx` — wrap `claim.text` in the claim column (~line 54) with
    `<RefText>`.
- **Rationale:** One renderer applied at every assistant-prose site guarantees consistent behaviour
  and styling; splitting the clickable atom (`ReferenceLink`) from the tokenizing wrapper (`RefText`)
  keeps each testable/reusable and mirrors the existing `ProvenanceChip` pattern.
- **Action:** Undergo the verification/tests/validation process for this phase (`npm test`,
  `npm run lint`, `npm run build`). Once validated, commit to GitHub stating: Clickable References
  (3/4) Complete: inline `ReferenceLink`/`RefText` renderers make CAPEC/ATT&CK ids in answer prose
  pre-fill a follow-up into the composer.

### Step 4: Full validation, live verification, changelog, merge to main
- **Locations:** `web/` (build + lint + tests), running app via `python app.py` (or preview),
  `docs/changelog.jsonl` (final consolidated entry if not already appended per step), local `main`.
- **Rationale:** The webfront rule requires `npm run build` to pass; a live click-through confirms
  the end-to-end interaction (click id → composer pre-filled + focused → editable → sends) that unit
  tests can't cover. Merging only after everything is green satisfies the "100% functional" gate.
- **Action:** Undergo the verification/tests/validation process for this phase (`npm test`,
  `npm run lint`, `npm run build`, and a live click-through). Once validated, commit any remaining
  changes and merge the feature branch into local `main`, stating: Clickable References (4/4)
  Complete: validated (tests + lint + build + live click-through) and merged to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Reference tokenizer | `tokenizeReferences` + `followUpPrompt` pure helpers | `web/lib/references.ts` |
| Tokenizer unit tests | Vitest cases over detection, boundaries, mixed prose, prompt text | `web/lib/__tests__/references.test.ts` |
| Composer prefill channel | `composerDraft` state + `setComposerDraft` action | `web/components/workbench/WorkbenchContext.tsx` |
| Composer prefill consumer | Effect that fills + focuses the textarea from `composerDraft` | `web/components/center/Composer.tsx` |
| Reference link atom | Inline clickable link that pre-fills a follow-up | `web/components/center/ReferenceLink.tsx` |
| Prose renderer | Tokenizes a string and renders links inline | `web/components/center/RefText.tsx` |
| Answer-surface wiring | `<RefText>` applied to final answer, claims, claim table, evidence prose | `web/components/center/AnswerCard.tsx`, `web/components/center/ClaimTable.tsx` |
| Changelog entries | One entry per shipped step | `docs/changelog.jsonl` |
