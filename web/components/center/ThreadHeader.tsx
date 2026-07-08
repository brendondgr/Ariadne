"use client";

import { useState } from "react";
import type { WorkbenchRun } from "@/lib/types";
import { Pill } from "@/components/ui/Pill";
import { buildChatExport } from "@/lib/export";

interface ThreadHeaderProps {
  title: string;
  run: WorkbenchRun;
  /** Every turn in the thread, for the Export action. */
  runs: WorkbenchRun[];
}

/** Center-pane title strip: conversation title + the run's mode/drafter tag,
 *  with an Export-chat action pinned to the right edge. */
export function ThreadHeader({ title, run, runs }: ThreadHeaderProps) {
  const modeLabel = run.mode === "query" ? "Full answer" : "Plan only";
  const [copied, setCopied] = useState(false);
  const canExport = runs.length > 0;

  const exportChat = async () => {
    if (!canExport) return;
    try {
      await navigator.clipboard?.writeText(buildChatExport(title, runs));
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
      <span className="truncate text-sm font-semibold">{title}</span>
      <Pill accent="teal" className="shrink-0 px-2 py-0.5 text-[9.5px] tracking-[0.06em]">
        {modeLabel} · {run.drafter}
      </Pill>
      <button
        type="button"
        onClick={exportChat}
        disabled={!canExport}
        title="Copy the whole conversation as Markdown"
        aria-label="Export chat as Markdown"
        className="ml-auto flex shrink-0 items-center gap-1.5 rounded-[8px] border border-[rgba(235,230,220,0.12)] px-2.5 py-1 font-mono text-[10.5px] tracking-[0.04em] text-text-muted transition-colors hover:border-[rgba(78,158,150,0.5)] hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
      >
        <ExportIcon />
        {copied ? "Copied" : "Export chat"}
      </button>
    </div>
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
