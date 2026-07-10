"use client";

import { useState } from "react";
import type { WorkbenchRun } from "@/lib/types";
import { Pill } from "@/components/ui/Pill";
import { buildChatExport, buildFullHistoryExport } from "@/lib/export";

interface ThreadHeaderProps {
  title: string;
  run: WorkbenchRun;
  /** Every turn in the thread, for the Export action. */
  runs: WorkbenchRun[];
}

/** The two things "Export" can copy: the conversation alone, or the whole
 *  conversation plus each turn's step-by-step pipeline trace. */
const EXPORT_OPTIONS = [
  {
    key: "chat" as const,
    label: "Chat Only",
    hint: "Questions and replies",
    build: buildChatExport,
  },
  {
    key: "full" as const,
    label: "Full History",
    hint: "Step-by-step of what each turn did",
    build: buildFullHistoryExport,
  },
];

/** Center-pane title strip: conversation title + the run's mode/drafter tag,
 *  with an Export menu (Chat Only / Full History) pinned to the right edge. */
export function ThreadHeader({ title, run, runs }: ThreadHeaderProps) {
  const modeLabel = run.mode === "query" ? "Full answer" : "Plan only";
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const canExport = runs.length > 0;

  const copyExport = async (build: (title: string, runs: WorkbenchRun[]) => string) => {
    setOpen(false);
    if (!canExport) return;
    try {
      await navigator.clipboard?.writeText(build(title, runs));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard blocked — leave state as-is.
    }
  };

  return (
    <div
      className="flex flex-[0_0_auto] items-center gap-2.5 px-[22px] py-[13px]"
      style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
    >
      {/* Align the title strip with the centered ~60% conversation column. */}
      <div className="mx-auto flex w-full items-center gap-2.5 lg:w-[60%]">
      <span className="truncate text-sm font-semibold">{title}</span>
      <Pill accent="teal" className="shrink-0 px-2 py-0.5 text-[9.5px] tracking-[0.06em]">
        {modeLabel} · {run.drafter}
      </Pill>
      <div className="relative ml-auto shrink-0">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          disabled={!canExport}
          title="Copy the conversation as Markdown"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label="Export conversation as Markdown"
          className="flex shrink-0 items-center gap-1.5 rounded-[8px] border border-[rgba(235,230,220,0.12)] px-2.5 py-1 font-mono text-[10.5px] tracking-[0.04em] text-text-muted transition-colors hover:border-[rgba(78,158,150,0.5)] hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ExportIcon />
          {copied ? "Copied" : "Export"}
          <CaretIcon />
        </button>

        {open && (
          <>
            {/* Click-away backdrop */}
            <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} aria-hidden="true" />
            <div
              role="menu"
              aria-label="Export options"
              className="absolute right-0 top-full z-30 mt-1 flex min-w-[208px] flex-col gap-0.5 rounded-md bg-console p-1.5"
              style={{
                boxShadow: "rgba(235,230,220,0.12) 0 0 0 1px, rgba(0,0,0,0.35) 0 6px 18px",
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
              }}
            >
              {EXPORT_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  role="menuitem"
                  onClick={() => copyExport(opt.build)}
                  className="flex flex-col items-start rounded px-2 py-1.5 text-left transition-colors hover:bg-surface"
                >
                  <span className="font-mono text-[12px] text-text-soft">{opt.label}</span>
                  <span className="font-mono text-[10px] text-text-muted">{opt.hint}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      </div>
    </div>
  );
}

function CaretIcon() {
  return (
    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ExportIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      <polyline points="8 8 12 4 16 8" />
      <line x1="12" y1="4" x2="12" y2="16" />
    </svg>
  );
}
