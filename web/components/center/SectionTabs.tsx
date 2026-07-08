"use client";

import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { SHADOW } from "@/lib/ui";

export interface TabDef {
  id: string;
  label: string;
  /** Leading icon for the tab (matches the section). */
  icon?: ReactNode;
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
      {/* The tab bar — sits on a baseline hairline; the only thing visible when
          all panels are closed. Active tab is tinted with a teal underline. */}
      <div
        className="flex flex-wrap items-stretch gap-0.5 px-[10px] pt-1.5"
        style={{ boxShadow: SHADOW.insetBottom }}
        role="tablist"
      >
        {tabs.map((t) => {
          const on = t.id === active;
          return (
            <motion.button
              key={t.id}
              type="button"
              role="tab"
              layout
              initial={{ opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }}
              onClick={(e) => {
                e.stopPropagation();
                toggle(t.id);
              }}
              aria-selected={on}
              className="relative inline-flex items-center gap-1.5 rounded-t-[7px] border-0 bg-transparent px-3 py-2 font-mono text-[10.5px] uppercase tracking-[0.05em] transition-colors hover:text-text"
              style={{
                color: on ? "#4E9E96" : "var(--color-text-muted)",
                background: on ? "rgba(78,158,150,0.08)" : "transparent",
              }}
            >
              {t.icon && <span className="flex shrink-0 items-center">{t.icon}</span>}
              {t.label}
              {t.badge != null && (
                <span
                  className="rounded-full px-1.5 py-px text-[9.5px] leading-none"
                  style={{
                    color: on ? "#4E9E96" : "var(--color-text-soft)",
                    background: on ? "rgba(78,158,150,0.15)" : "rgba(235,230,220,0.06)",
                  }}
                >
                  {t.badge}
                </span>
              )}
              {on && (
                <motion.span
                  aria-hidden
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="absolute inset-x-2 -bottom-px h-[2px] rounded-full"
                  style={{ background: "#4E9E96" }}
                />
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
            <div className="px-[18px] pb-[15px] pt-3">{activeTab.content}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
