"use client";

import type { ProvenanceRef } from "@/lib/types";
import { ACCENT } from "@/lib/ui";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

/** Inline citation chip (`T1047 · ATT&CK/neo4j`). Clicking jumps the inspector
 *  to the evidence/stage that backs the claim. */
export function ProvenanceChip({ refData }: { refData: ProvenanceRef }) {
  const { focusStage } = useWorkbench();
  const a = ACCENT[refData.accent];
  return (
    <button
      type="button"
      onClick={() => refData.target && focusStage(refData.target)}
      className="inline-flex cursor-pointer items-center gap-[5px] rounded-full border-0 px-[7px] py-px align-middle font-mono text-[11px] transition-transform hover:scale-[1.03]"
      style={{ color: a.fg, background: a.tintBg, boxShadow: `${a.ring} 0 0 0 1px` }}
    >
      {refData.id} · {refData.source}
    </button>
  );
}
