import { describe, expect, it } from "vitest";
import {
  followUpPrompt,
  hasReference,
  tokenizeReferences,
  type ReferenceToken,
} from "../references";

/** Compact assertion helper: the tokens as `[kind, value]` pairs. */
function pairs(tokens: ReferenceToken[]): [string, string][] {
  return tokens.map((t) => (t.kind === "ref" ? ["ref", t.id] : ["text", t.text]));
}

describe("tokenizeReferences", () => {
  it("returns a single text token when there are no identifiers", () => {
    const out = tokenizeReferences("No identifiers here, just prose.");
    expect(out).toEqual([{ kind: "text", text: "No identifiers here, just prose." }]);
  });

  it("returns no tokens for an empty string", () => {
    expect(tokenizeReferences("")).toEqual([]);
  });

  it("detects a CAPEC pattern id", () => {
    expect(tokenizeReferences("See CAPEC-98 today.")).toEqual([
      { kind: "text", text: "See " },
      { kind: "ref", id: "CAPEC-98", scheme: "capec" },
      { kind: "text", text: " today." },
    ]);
  });

  it("detects ATT&CK techniques, sub-techniques, and mitigations with schemes", () => {
    expect(tokenizeReferences("T1566")).toEqual([
      { kind: "ref", id: "T1566", scheme: "technique" },
    ]);
    expect(tokenizeReferences("T1566.001")).toEqual([
      { kind: "ref", id: "T1566.001", scheme: "technique" },
    ]);
    expect(tokenizeReferences("M1049")).toEqual([
      { kind: "ref", id: "M1049", scheme: "mitigation" },
    ]);
  });

  it("splits the example sentence into the right ordered token sequence", () => {
    const text =
      "CAPEC-98 (Phishing) maps to two ATT&CK techniques. These include T1566, " +
      "known as Phishing, and T1598, known as Phishing for Information.";
    expect(pairs(tokenizeReferences(text))).toEqual([
      ["ref", "CAPEC-98"],
      ["text", " (Phishing) maps to two ATT&CK techniques. These include "],
      ["ref", "T1566"],
      ["text", ", known as Phishing, and "],
      ["ref", "T1598"],
      ["text", ", known as Phishing for Information."],
    ]);
  });

  it("is case-insensitive but preserves the matched casing in the id", () => {
    expect(tokenizeReferences("capec-11 and t1055")).toEqual([
      { kind: "ref", id: "capec-11", scheme: "capec" },
      { kind: "text", text: " and " },
      { kind: "ref", id: "t1055", scheme: "technique" },
    ]);
  });

  it("respects boundaries — no match inside a larger token", () => {
    // Leading word char, trailing digit, and trailing letter must all block.
    expect(tokenizeReferences("ST1566")).toEqual([{ kind: "text", text: "ST1566" }]);
    expect(tokenizeReferences("T15660")).toEqual([{ kind: "text", text: "T15660" }]);
    expect(tokenizeReferences("CAPEC-98x")).toEqual([{ kind: "text", text: "CAPEC-98x" }]);
  });

  it("matches identifiers adjacent to punctuation", () => {
    expect(pairs(tokenizeReferences("(T1566), and CAPEC-98."))).toEqual([
      ["text", "("],
      ["ref", "T1566"],
      ["text", "), and "],
      ["ref", "CAPEC-98"],
      ["text", "."],
    ]);
  });

  it("does not treat a technique's trailing dot as a sub-technique boundary break", () => {
    // "T1566." (end of sentence) is the id T1566 followed by a period, not T1566.<none>.
    expect(pairs(tokenizeReferences("ends with T1566."))).toEqual([
      ["text", "ends with "],
      ["ref", "T1566"],
      ["text", "."],
    ]);
  });

  it("round-trips: re-joining token text/id reproduces the input", () => {
    const text = "CAPEC-98 maps to T1566.001 mitigated by M1049 here.";
    const joined = tokenizeReferences(text)
      .map((t) => (t.kind === "ref" ? t.id : t.text))
      .join("");
    expect(joined).toBe(text);
  });
});

describe("hasReference", () => {
  it("is true only when a linkable id is present", () => {
    expect(hasReference("CAPEC-98 here")).toBe(true);
    expect(hasReference("nothing linkable")).toBe(false);
    // Repeated calls must not be affected by the shared /g regex's lastIndex.
    expect(hasReference("T1566")).toBe(true);
    expect(hasReference("T1566")).toBe(true);
  });
});

describe("followUpPrompt", () => {
  it("builds the composer follow-up keyed on the id", () => {
    expect(followUpPrompt("CAPEC-98")).toBe("Could you provide me more details on CAPEC-98?");
    expect(followUpPrompt("T1566")).toBe("Could you provide me more details on T1566?");
  });
});
