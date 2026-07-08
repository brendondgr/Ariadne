"use client";

import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { SHADOW } from "@/lib/ui";

export interface TabDef {
  id: string;
  label: string;
  /** Small count shown beside the label (e.g. claim count, node count). */
  badge?: ReactNode;
  content: ReactNode;
}

/** A tabbed container for the answer-card sections.
 *
 *  Only *available* tabs are passed in, so tabs appear progressively as the
 *  pipeline extracts information. Exactly one panel is open at a time; clicking
 *  the active tab again closes everything, collapsing to just the thin tab
 *  strip. Until the analyst touches a tab, the panel auto-follows: it opens the
 *  preferred tab (Network Plot) once available, and falls back to a streaming
 *  tab (Logs) while the answer is still being built. */
export function SectionTabs({
  tabs,
  preferredId,
  streamingFallbackId,
}: {
  tabs: TabDef[];
  preferredId: string;
  streamingFallbackId?: string;
}) {
  // `"auto"` means "no manual choice yet" — the panel follows the pipeline:
  // it opens the preferred tab (Network Plot) once available, falling back to a
  // streaming tab (Logs) while the answer is still building. Any click pins the
  // choice (an id, or `null` to collapse everything to the strip).
  const [choice, setChoice] = useState<string | null | "auto">("auto");
  const ids = tabs.map((t) => t.id);

  // Prefer the Network Plot; if it isn't available, open the first meaningful
  // tab (not Logs); while only Logs exists (streaming) open that.
  const auto =
    (ids.includes(preferredId) && preferredId) ||
    tabs.find((t) => t.id !== streamingFallbackId)?.id ||
    (streamingFallbackId && ids.includes(streamingFallbackId) ? streamingFallbackId : null);
  const active = choice === "auto" ? auto : choice;

  const toggle = (id: string) => setChoice(active === id ? null : id);

  const activeTab = tabs.find((t) => t.id === active) ?? null;

  return (
    <div style={{ boxShadow: SHADOW.insetBottom }}>
      {/* The thin tab strip — the only thing visible when everything is closed. */}
      <div className="flex flex-wrap items-center gap-1.5 px-[14px] py-2">
        {tabs.map((t) => {
          const on = t.id === active;
          return (
            <motion.button
              key={t.id}
              type="button"
              layout
              initial={{ opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }}
              onClick={(e) => {
                e.stopPropagation();
                toggle(t.id);
              }}
              aria-pressed={on}
              className="inline-flex items-center gap-1.5 rounded-full border-0 px-2.5 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.05em] transition-colors"
              style={
                on
                  ? { color: "#4E9E96", background: "rgba(78,158,150,0.12)", boxShadow: "rgba(78,158,150,0.4) 0 0 0 1px" }
                  : { color: "var(--color-text-muted)", background: "transparent", boxShadow: SHADOW.hairline }
              }
            >
              {t.label}
              {t.badge != null && (
                <span className="text-text-soft" style={on ? { color: "#4E9E96" } : undefined}>
                  {t.badge}
                </span>
              )}
            </motion.button>
          );
        })}
      </div>

      <AnimatePresence initial={false}>
        {activeTab && (
          <motion.div
            key={activeTab.id}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.24 }}
            className="overflow-hidden"
          >
            <div className="px-[18px] pb-[15px] pt-1">{activeTab.content}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
