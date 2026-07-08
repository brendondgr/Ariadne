"use client";

import { Fragment } from "react";
import { tokenizeReferences } from "@/lib/references";
import { ReferenceLink } from "./ReferenceLink";

/** Render a prose string with any inline CAPEC / ATT&CK identifiers turned into
 *  clickable {@link ReferenceLink}s. Plain text is emitted verbatim, so this is
 *  a drop-in replacement for rendering a raw `{text}` string anywhere an
 *  assistant answer's prose appears. When the text has no identifiers it renders
 *  exactly one text run (no wrappers, no behaviour change). */
export function RefText({ text }: { text: string }) {
  const tokens = tokenizeReferences(text);
  return (
    <>
      {tokens.map((t, i) =>
        t.kind === "ref" ? (
          <ReferenceLink key={i} id={t.id} />
        ) : (
          <Fragment key={i}>{t.text}</Fragment>
        ),
      )}
    </>
  );
}
