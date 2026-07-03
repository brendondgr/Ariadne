"use client";

import { useCallback } from "react";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

const SEGMENTS = [
  { value: "chat", label: "Chat" },
  { value: "graphs", label: "Graphs" },
] as const;

/** App-wide segmented view toggle: Chat | Graphs.
 *
 *  Accessibility: role="radiogroup" container; each segment is a
 *  role="radio" button. ArrowLeft/ArrowRight move between segments.
 */
export function ViewToggle() {
  const { view, setView } = useWorkbench();

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const idx = SEGMENTS.findIndex((s) => s.value === view);
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        const next = SEGMENTS[(idx + 1) % SEGMENTS.length];
        setView(next.value);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        const prev = SEGMENTS[(idx - 1 + SEGMENTS.length) % SEGMENTS.length];
        setView(prev.value);
      }
    },
    [view, setView],
  );

  return (
    <div
      role="radiogroup"
      aria-label="View"
      onKeyDown={handleKeyDown}
      className="inline-flex items-center gap-0.5 rounded-lg p-0.5 shadow-border"
    >
      {SEGMENTS.map((seg) => {
        const active = view === seg.value;
        return (
          <button
            key={seg.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setView(seg.value)}
            className={[
              "rounded-md px-2.5 py-1 font-mono text-xs uppercase tracking-[0.04em] transition-[color,box-shadow]",
              active
                ? "bg-surface-deep text-text shadow-border"
                : "text-text-muted hover:text-primary",
            ].join(" ")}
          >
            {seg.label}
          </button>
        );
      })}
    </div>
  );
}
