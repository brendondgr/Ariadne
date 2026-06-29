"use client";

import { Fragment } from "react";
import type { AnswerParagraph, WorkbenchRun } from "@/lib/types";
import { SHADOW } from "@/lib/ui";
import { CopyIcon, ExportIcon, LinkIcon } from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { MiniStepper } from "./MiniStepper";
import { ProvenanceChip } from "./ProvenanceChip";
import { JoinChip } from "./JoinChip";

function Paragraph({ paragraph }: { paragraph: AnswerParagraph }) {
  return (
    <p className="m-0 mb-3 last:mb-0">
      {paragraph.segments.map((seg, i) => {
        if (seg.kind === "text") return <Fragment key={i}>{seg.text}</Fragment>;
        if (seg.kind === "mono")
          return (
            <span key={i} className="font-mono text-[12px] text-[#c9c6bd]">
              {seg.text}
            </span>
          );
        return <ProvenanceChip key={i} refData={seg.ref} />;
      })}
    </p>
  );
}

/** The structured assistant turn: status stepper, grounded prose with inline
 *  provenance chips, and a footer of join candidates + evidence actions. */
export function AnswerCard({ run }: { run: WorkbenchRun }) {
  const { setActiveTab, setInspectorOpen } = useWorkbench();

  const openRawJson = () => {
    setActiveTab("raw");
    setInspectorOpen(true);
  };
  const copyEvidence = () => {
    void navigator.clipboard?.writeText(JSON.stringify(run.federated, null, 2));
  };

  return (
    <div
      className="max-w-[92%] overflow-hidden rounded-[4px_13px_13px_13px] bg-surface"
      style={{ boxShadow: SHADOW.answerCard }}
    >
      <MiniStepper steps={run.stepper} status={run.status} exitCode={run.exitCode} />

      <div className="px-[18px] pb-4 pt-[18px] text-sm leading-[1.62] text-text-soft">
        {run.answer.paragraphs.map((p, i) => (
          <Paragraph key={i} paragraph={p} />
        ))}
      </div>

      <div className="px-[18px] py-[13px]" style={{ boxShadow: SHADOW.insetBottom }}>
        <div className="mb-[9px] font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          Cross-source join candidates
        </div>
        <div className="mb-3.5 flex flex-wrap gap-2">
          {run.answer.joinPairs.map((pair, i) => (
            <JoinChip key={i} pair={pair} />
          ))}
        </div>
        <div className="flex items-center gap-3.5">
          <button
            type="button"
            onClick={openRawJson}
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-primary"
          >
            <LinkIcon />
            View full evidence JSON
          </button>
          <button
            type="button"
            onClick={copyEvidence}
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-text-muted transition-colors hover:text-text"
          >
            <CopyIcon />
            Copy
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-text-muted transition-colors hover:text-text"
          >
            <ExportIcon />
            Export
          </button>
        </div>
      </div>
    </div>
  );
}
