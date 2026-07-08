"use client";

import { followUpPrompt } from "@/lib/references";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

/** An inline, in-prose CAPEC / ATT&CK identifier rendered as a clickable link.
 *  Clicking seeds a follow-up question ("Could you provide me more details on
 *  {id}?") into the composer below and focuses it — it does not auto-send. This
 *  is the lightweight in-text counterpart to {@link ProvenanceChip} (which is a
 *  pill that jumps the inspector); here we keep the reading flow intact and only
 *  tint + underline the identifier. Sized in `em` so it scales with whichever
 *  answer surface renders it (final answer, claims, claim table, evidence). */
export function ReferenceLink({ id }: { id: string }) {
  const { setComposerDraft } = useWorkbench();
  return (
    <button
      type="button"
      onClick={() => setComposerDraft(followUpPrompt(id))}
      title={`Ask a follow-up about ${id}`}
      aria-label={`Ask a follow-up about ${id}`}
      className="cursor-pointer border-0 bg-transparent p-0 align-baseline font-mono text-[0.92em] text-primary underline decoration-dotted decoration-primary/40 underline-offset-2 transition-colors hover:text-[#5bb0a7] hover:decoration-primary"
    >
      {id}
    </button>
  );
}
