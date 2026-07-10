"use client";

import { Children, Fragment, isValidElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { tokenizeReferences } from "@/lib/references";
import { ReferenceLink } from "./ReferenceLink";

/**
 * Recursively linkify inline CAPEC / ATT&CK identifiers inside a markdown node's
 * children. Every string leaf is split via {@link tokenizeReferences} into plain
 * text + clickable {@link ReferenceLink}s; non-string nodes (already-rendered
 * elements like <strong>, <em>, <a>) are walked so identifiers nested inside
 * emphasis still linkify. Elements that must not contain a nested <button>
 * (anchors) or should stay verbatim (code) are handled by the caller, which
 * simply doesn't route their children through here.
 */
function linkifyChildren(children: ReactNode): ReactNode {
  return Children.map(children, (child, i) => {
    if (typeof child === "string") {
      const tokens = tokenizeReferences(child);
      if (tokens.length === 0) return child;
      return (
        <Fragment key={i}>
          {tokens.map((t, j) =>
            t.kind === "ref" ? (
              <ReferenceLink key={j} id={t.id} />
            ) : (
              <Fragment key={j}>{t.text}</Fragment>
            ),
          )}
        </Fragment>
      );
    }
    // Recurse into element children (e.g. bold text wrapping an identifier), but
    // never into anchors/code — those are re-rendered by their own overrides.
    if (isValidElement(child)) {
      const props = child.props as { children?: ReactNode };
      if (child.type === "a" || child.type === "code") return child;
      if (props?.children != null) {
        return { ...child, props: { ...props, children: linkifyChildren(props.children) } };
      }
    }
    return child;
  });
}

/** Markdown component overrides styled to the Woven Dusk chat surface. Text-
 *  bearing blocks route their children through `linkifyChildren` so inline
 *  references stay clickable; `a`/`code`/`pre` render verbatim. */
const components: Components = {
  p: ({ children }) => (
    <p className="m-0 mb-2 last:mb-0 text-sm leading-[1.62] text-text-soft">{linkifyChildren(children)}</p>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline decoration-primary/40 underline-offset-2 transition-colors hover:decoration-primary"
    >
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-text">{linkifyChildren(children)}</strong>,
  em: ({ children }) => <em className="italic">{linkifyChildren(children)}</em>,
  del: ({ children }) => <del className="text-text-muted">{linkifyChildren(children)}</del>,
  ul: ({ children }) => (
    <ul className="my-2 list-disc space-y-1 pl-5 text-sm leading-[1.62] text-text-soft marker:text-text-muted">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 list-decimal space-y-1 pl-5 text-sm leading-[1.62] text-text-soft marker:text-text-muted">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-0.5">{linkifyChildren(children)}</li>,
  h1: ({ children }) => (
    <h1 className="mb-2 mt-3 text-[15px] font-semibold text-text first:mt-0">{linkifyChildren(children)}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1.5 mt-3 text-[14px] font-semibold text-text first:mt-0">{linkifyChildren(children)}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-2.5 text-[13px] font-semibold text-text-soft first:mt-0">{linkifyChildren(children)}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="mb-1 mt-2 text-[12.5px] font-semibold text-text-soft first:mt-0">{linkifyChildren(children)}</h4>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-border pl-3 text-sm italic leading-[1.6] text-text-muted">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    // Inline code (no language class from a fenced block): render as a pill.
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return <code className={`${className ?? ""} font-mono text-[12.5px]`}>{children}</code>;
    }
    return (
      <code className="rounded-[4px] bg-surface-deep px-1.5 py-0.5 font-mono text-[12px] text-text">{children}</code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-[8px] bg-surface-deep p-3 text-[12.5px] leading-[1.5] text-text-soft">
      {children}
    </pre>
  ),
  hr: () => <hr className="my-3 border-0 border-t border-border" />,
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-sm text-text-soft">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-border px-2 py-1 text-left font-semibold text-text">{linkifyChildren(children)}</th>
  ),
  td: ({ children }) => <td className="border border-border px-2 py-1">{linkifyChildren(children)}</td>,
};

/**
 * Render an assistant reply string as GitHub-flavored markdown on the chat
 * surface. Supports bold/italic/strikethrough, ordered & unordered lists,
 * headings, links, inline & fenced code, blockquotes, tables, and hard line
 * breaks (single `\n` → `<br>` via remark-breaks — chat prose rarely uses the
 * two-space markdown convention). Inline CAPEC/ATT&CK identifiers remain
 * clickable {@link ReferenceLink}s, matching the prior `RefText` behavior.
 */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
