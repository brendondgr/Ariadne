/**
 * references.ts — Detect CAPEC / ATT&CK identifiers inside answer prose and
 * split it into an ordered run of plain-text and reference tokens.
 *
 * The provenance **chips** already make citations interactive, but the same
 * identifiers appear inline in the natural-language answer as plain text
 * ("CAPEC-98 maps to T1566 …"). `tokenizeReferences` finds those inline mentions
 * so the UI can render each as a clickable link that pre-fills a follow-up
 * question into the composer.
 *
 * The detected vocabulary mirrors `classifyEntity` in `synthesisGraph.ts` — CAPEC
 * patterns, ATT&CK techniques (incl. sub-techniques `T####.###`), and ATT&CK
 * mitigations (`M####`) — so what the plot types as a node is exactly what the
 * prose links. No React here: a pure function, unit-testable in isolation.
 */

/** The identifier families we linkify (matches `classifyEntity`'s `kind`s). */
export type ReferenceScheme = "capec" | "technique" | "mitigation";

export type ReferenceToken =
  | { kind: "text"; text: string }
  | { kind: "ref"; id: string; scheme: ReferenceScheme };

/**
 * Inline scan pattern — the anchored `classifyEntity` regexes made global and
 * bounded so they match mid-sentence but not inside a larger token:
 *   - `CAPEC-\d+`            CAPEC pattern ids
 *   - `T\d{4}(?:\.\d{3})?`   ATT&CK technique / sub-technique ids
 *   - `M\d{4}`               ATT&CK mitigation ids
 *
 * Boundaries: a preceding non-word/non-hyphen lookbehind and a trailing
 * non-word (letter/digit) lookahead keep `ST1566`, `T15660`, and `CAPEC-98x`
 * from matching while still allowing trailing punctuation (`T1566,`, `(T1566)`,
 * and a sentence-ending `T1566.`). The optional `(?:\.\d{3})?` sub-technique
 * group — not the boundary — is what keeps `T1566.001` a single token, so the
 * lookahead deliberately permits a following `.`.
 */
const REFERENCE_RE =
  /(?<![\w-])(CAPEC-\d+|T\d{4}(?:\.\d{3})?|M\d{4})(?![\w])/gi;

function schemeOf(id: string): ReferenceScheme {
  const upper = id.toUpperCase();
  if (upper.startsWith("CAPEC-")) return "capec";
  if (upper.startsWith("M")) return "mitigation";
  return "technique";
}

/**
 * Split `text` into an ordered array of plain-text and reference tokens. Prose
 * with no identifiers returns a single text token; adjacent runs of text are
 * preserved verbatim (whitespace and punctuation included) so re-joining the
 * `text`/`id` fields reproduces the input exactly.
 */
export function tokenizeReferences(text: string): ReferenceToken[] {
  const tokens: ReferenceToken[] = [];
  let lastIndex = 0;
  // Fresh lastIndex per call — the shared regex object is stateful with /g.
  REFERENCE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = REFERENCE_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ kind: "text", text: text.slice(lastIndex, match.index) });
    }
    const id = match[0];
    tokens.push({ kind: "ref", id, scheme: schemeOf(id) });
    lastIndex = match.index + id.length;
  }
  if (lastIndex < text.length) {
    tokens.push({ kind: "text", text: text.slice(lastIndex) });
  }
  // Empty input → no tokens; keep the caller's map a no-op rather than emit "".
  return tokens;
}

/** True when `text` contains at least one linkable identifier. */
export function hasReference(text: string): boolean {
  REFERENCE_RE.lastIndex = 0;
  return REFERENCE_RE.test(text);
}

/**
 * The follow-up question a reference click pre-fills into the composer. Keyed on
 * the identifier only — the friendly name in prose ("CAPEC-98 (Phishing)") is
 * not reliably parseable, and the id is the unambiguous handle the pipeline
 * resolves.
 */
export function followUpPrompt(id: string): string {
  return `Could you provide me more details on ${id}?`;
}
