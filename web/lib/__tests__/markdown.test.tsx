import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Markdown } from "@/components/center/Markdown";

/**
 * The chat reply surface renders assistant prose as GitHub-flavored markdown.
 * These render the component to static HTML (no DOM needed) and assert the
 * markdown syntax the analyst reported as broken — bold, italic, lists, and
 * single-newline line breaks — actually produces formatted elements instead of
 * literal characters. Reference linkification (identifiers → clickable links)
 * is covered by references.test.ts; here we only prove the markdown pipeline.
 */
describe("Markdown chat renderer", () => {
  it("renders bold and italic emphasis as elements, not literal syntax", () => {
    const html = renderToStaticMarkup(<Markdown text="This is **bold** and _italic_ text." />);
    expect(html).toContain("<strong");
    expect(html).toContain("bold");
    expect(html).toContain("<em");
    expect(html).toContain("italic");
    // The raw markdown markers must not survive into the output.
    expect(html).not.toContain("**bold**");
    expect(html).not.toContain("_italic_");
  });

  it("renders unordered and ordered lists", () => {
    const html = renderToStaticMarkup(<Markdown text={"- alpha\n- beta\n\n1. one\n2. two"} />);
    expect(html).toContain("<ul");
    expect(html).toContain("<ol");
    expect((html.match(/<li/g) ?? []).length).toBe(4);
    expect(html).toContain("alpha");
    expect(html).toContain("two");
  });

  it("turns single newlines into hard line breaks (remark-breaks)", () => {
    const html = renderToStaticMarkup(<Markdown text={"line one\nline two"} />);
    expect(html).toContain("<br");
    expect(html).toContain("line one");
    expect(html).toContain("line two");
  });

  it("renders headings and inline code", () => {
    const html = renderToStaticMarkup(<Markdown text={"# Title\n\nUse `code` here."} />);
    expect(html).toContain("<h1");
    expect(html).toContain("Title");
    expect(html).toContain("<code");
    expect(html).toContain("code");
  });
});
