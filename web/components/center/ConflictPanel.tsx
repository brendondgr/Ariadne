"use client";

import type { ConflictView } from "@/lib/types";
import { ACCENT } from "@/lib/ui";

const KIND_LABEL: Record<ConflictView["kind"], string> = {
  name: "name disagreement",
  status: "deprecated yet referenced",
};

/** The "Conflicting sources" surface: the consistency axis of trust.
 *
 *  Groundedness proves each claim traces to a real record; reconciliation
 *  catches when two sources both carry a canonical join value yet assert
 *  incompatible facts about it. Both records are real, so nothing is cut —
 *  instead the disagreement is shown side by side, with the authoritative
 *  source (the one that owns the id's scheme) marked. Renders nothing when the
 *  sources agree. */
export function ConflictPanel({ conflicts }: { conflicts: ConflictView[] }) {
  if (conflicts.length === 0) return null;

  return (
    <div className="mb-2">
      <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.06em] text-secondary">
        Conflicting sources · {conflicts.length}
      </div>
      {conflicts.map((c, i) => (
        <div
          key={`conflict-${i}`}
          className="mb-2 rounded-[8px] px-3 py-2.5"
          style={{
            boxShadow: "rgba(201,146,74,0.45) 0 0 0 1px",
            background: "rgba(201,146,74,0.06)",
          }}
        >
          <div className="mb-1.5 flex items-baseline gap-2">
            <span className="font-mono text-[11px] text-secondary">{c.joinValue}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.06em] text-text-muted">
              {KIND_LABEL[c.kind]}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            {c.values.map((v, j) => {
              const a = ACCENT[v.accent];
              return (
                <div key={j} className="flex items-baseline gap-2 text-[12.5px] leading-[1.5]">
                  <span
                    className="shrink-0 rounded-full px-[7px] py-px font-mono text-[10.5px]"
                    style={{ color: a.fg, background: a.tintBg, boxShadow: `${a.ring} 0 0 0 1px` }}
                  >
                    {v.source}
                    {v.authoritative ? " · authoritative" : ""}
                  </span>
                  <span className="text-text-soft">{v.value}</span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/** A small inline "contested" badge for a claim whose id the sources disagree
 *  about — the flag that keeps a real-but-contested claim honest at the point
 *  of reading. */
export function ContestedBadge({ ids }: { ids: string[] }) {
  if (ids.length === 0) return null;
  return (
    <span
      title={`sources disagree about ${ids.join(", ")}`}
      className="ml-1 inline-flex items-center rounded-full px-[6px] py-px align-middle font-mono text-[9.5px] uppercase tracking-[0.05em]"
      style={{
        color: "#c9924a",
        background: "rgba(201,146,74,0.1)",
        boxShadow: "rgba(201,146,74,0.4) 0 0 0 1px",
      }}
    >
      contested
    </span>
  );
}
