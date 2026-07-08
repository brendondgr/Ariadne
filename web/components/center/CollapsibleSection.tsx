"use client";

import { useState, type ReactNode } from "react";
import { SHADOW } from "@/lib/ui";
import { ChevronRight } from "@/components/ui/icons";

/** A Woven-Dusk disclosure for one answer-card section.
 *
 *  Renders the section label with a count badge (so a closed section still
 *  tells the analyst how much it holds) and a chevron that rotates when open.
 *  The body mounts only while open. `accessory` sits beside the count for a
 *  section that carries an inline status (e.g. the verification pill). */
export function CollapsibleSection({
  label,
  count,
  defaultOpen = false,
  accessory,
  children,
}: {
  label: string;
  /** Shown as the closed-state summary (e.g. `"1/3"`, `12`, `"8 nodes · 5 links"`). */
  count?: ReactNode;
  defaultOpen?: boolean;
  accessory?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div style={{ boxShadow: SHADOW.insetBottom }}>
      <button
        type="button"
        onClick={(e) => {
          // Don't let the toggle also select the turn (TurnBlock's onClick).
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        aria-expanded={open}
        className="flex w-full items-center gap-2 border-0 bg-transparent px-[18px] py-[13px] text-left transition-colors hover:bg-[rgba(235,230,220,0.02)]"
      >
        <span
          className="text-text-muted transition-transform duration-150"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        >
          <ChevronRight size={12} />
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          {label}
        </span>
        {count != null && (
          <span
            className="inline-flex items-center rounded-full px-2 py-px font-mono text-[10px] text-text-muted"
            style={{ boxShadow: SHADOW.hairline }}
          >
            {count}
          </span>
        )}
        {accessory && <span className="ml-1">{accessory}</span>}
      </button>
      {open && <div className="px-[18px] pb-[15px]">{children}</div>}
    </div>
  );
}
