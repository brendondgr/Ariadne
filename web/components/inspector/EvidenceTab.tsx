"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { CodeLang, EvidenceRow } from "@/lib/types";
import { ACCENT, CONSOLE_BG, SHADOW } from "@/lib/ui";
import { collapse } from "@/lib/motion";
import { CodeBlock } from "@/components/ui/CodeBlock";

const INITIAL_PAGE = 60;
const PAGE_SIZE = 60;

function langForBackend(backend: string): CodeLang {
  if (backend === "neo4j") return "cypher";
  if (backend === "gremlin") return "gremlin";
  return "text";
}

function EvidenceRowCard({ row }: { row: EvidenceRow }) {
  const [open, setOpen] = useState(false);
  const queryLang = langForBackend(row.backend);

  return (
    <div
      className="overflow-hidden rounded-[9px] bg-bg"
      style={{ boxShadow: SHADOW.lightRing }}
    >
      {/* Collapsed header — always visible */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 border-0 bg-transparent px-3.5 py-[11px] text-left"
      >
        <span className="font-mono text-xs" style={{ color: ACCENT[row.accent].fg }}>
          {row.id}
        </span>
        <span
          className="rounded-full px-1.5 py-px font-mono text-[9px] text-text-muted"
          style={{ background: ACCENT.sage.tintBg }}
        >
          {row.label}
        </span>
        <span className="flex-1 truncate text-[12.5px] text-text">{row.name}</span>
        <span
          className="text-[9px] text-text-muted transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        >
          ▶
        </span>
      </button>

      {/* Expanded body */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            variants={collapse}
            initial="hidden"
            animate="show"
            exit="hidden"
            className="overflow-hidden"
          >
            <div className="px-3.5 pb-3.5">
              {/* Provenance meta line */}
              <div className="mb-2 font-mono text-[10px] text-text-muted">
                {row.provenanceMeta}
              </div>

              {/* Full record JSON */}
              <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
                Record
              </div>
              <CodeBlock
                code={row.fullJson}
                lang="json"
                className="mb-3 text-[10.5px] leading-[1.6]"
              />

              {/* Provenance query */}
              {row.provenanceQuery && (
                <>
                  <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
                    query:
                  </div>
                  <CodeBlock
                    code={row.provenanceQuery}
                    lang={queryLang}
                    emphasis
                    className="text-[10.5px] leading-[1.6]"
                  />
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Normalized evidence records across all sub-questions. */
export function EvidenceTab({ evidence }: { evidence: EvidenceRow[] }) {
  const [filter, setFilter] = useState("");
  const [revealed, setRevealed] = useState(INITIAL_PAGE);

  const normalizedFilter = filter.trim().toLowerCase();
  const filtered =
    normalizedFilter === ""
      ? evidence
      : evidence.filter(
          (row) =>
            row.id.toLowerCase().includes(normalizedFilter) ||
            row.name.toLowerCase().includes(normalizedFilter) ||
            row.label.toLowerCase().includes(normalizedFilter),
        );

  // Reset reveal count when filter changes
  const handleFilterChange = (value: string) => {
    setFilter(value);
    setRevealed(INITIAL_PAGE);
  };

  const visible = filtered.slice(0, revealed);
  const remaining = filtered.length - visible.length;

  return (
    <div>
      {/* Header row */}
      <div className="mb-2 flex items-center gap-3">
        <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          Normalized evidence
        </div>
        <div className="font-mono text-[10px] text-text-muted">
          (showing {visible.length} of {filtered.length}
          {normalizedFilter && ` · filtered from ${evidence.length}`})
        </div>
      </div>

      {/* Filter input */}
      <div className="mb-3 flex items-center gap-2">
        <input
          type="text"
          value={filter}
          onChange={(e) => handleFilterChange(e.target.value)}
          placeholder="Filter by id, name, or label…"
          aria-label="Filter evidence records"
          className="h-8 flex-1 rounded-lg border-0 bg-bg px-3 font-mono text-[11.5px] text-text placeholder:text-text-muted focus:outline-none focus:ring-1"
          style={{
            boxShadow: SHADOW.lightRing,
            background: CONSOLE_BG,
          }}
        />
        {normalizedFilter && (
          <button
            type="button"
            onClick={() => handleFilterChange("")}
            className="font-mono text-[10px] text-text-muted hover:text-text"
            aria-label="Clear filter"
          >
            ✕
          </button>
        )}
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div
          className="rounded-[9px] px-3.5 py-4 font-mono text-[11px] text-text-muted"
          style={{ boxShadow: SHADOW.hairline, background: CONSOLE_BG }}
        >
          No records match &ldquo;{filter}&rdquo;.
        </div>
      )}

      {/* Record list */}
      <div className="flex flex-col gap-[7px]">
        {visible.map((row) => (
          <EvidenceRowCard key={row.id} row={row} />
        ))}
      </div>

      {/* Show more */}
      {remaining > 0 && (
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setRevealed((r) => r + PAGE_SIZE)}
            className="rounded-lg px-3 py-1.5 font-mono text-[11px] text-text-muted hover:text-text"
            style={{ boxShadow: SHADOW.hairline, background: CONSOLE_BG }}
          >
            Show {Math.min(PAGE_SIZE, remaining)} more
          </button>
          <button
            type="button"
            onClick={() => setRevealed(filtered.length)}
            className="font-mono text-[11px] text-text-muted hover:text-text"
          >
            Show all ({filtered.length})
          </button>
        </div>
      )}
    </div>
  );
}
