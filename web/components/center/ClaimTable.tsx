"use client";

import type { SynthesisView } from "@/lib/types";
import { SHADOW } from "@/lib/ui";
import { ProvenanceChip } from "./ProvenanceChip";
import { CollapsibleSection } from "./CollapsibleSection";

/** Deliverable #4 — the analyst-facing table.
 *
 *  A scannable, structured view of the same verified claims the prose block
 *  renders: one row per supported claim (kind, the sentence, and its citation
 *  chips). Cut claims and abstentions stay in `SynthesisBlock`'s audit trail —
 *  the table only tabulates what the verifier let through, so it never presents
 *  unverified topology as fact.
 *
 *  Renders nothing when there are no supported claims (an abstention-only or
 *  fully-cut answer has nothing to tabulate). */
export function ClaimTable({ synthesis }: { synthesis: SynthesisView }) {
  if (synthesis.claims.length === 0) return null;

  return (
    <CollapsibleSection label="Claim table" count={synthesis.claims.length}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr>
              <th
                scope="col"
                className="whitespace-nowrap pb-1.5 pr-3 align-bottom font-mono text-[9.5px] uppercase tracking-[0.06em] font-normal text-text-muted"
              >
                Type
              </th>
              <th
                scope="col"
                className="pb-1.5 pr-3 align-bottom font-mono text-[9.5px] uppercase tracking-[0.06em] font-normal text-text-muted"
              >
                Claim
              </th>
              <th
                scope="col"
                className="pb-1.5 align-bottom font-mono text-[9.5px] uppercase tracking-[0.06em] font-normal text-text-muted"
              >
                Provenance
              </th>
            </tr>
          </thead>
          <tbody>
            {synthesis.claims.map((claim, i) => (
              <tr key={`row-${i}`} style={{ boxShadow: SHADOW.insetBottom }}>
                <td className="whitespace-nowrap py-2 pr-3 align-top">
                  <span className="font-mono text-[10px] uppercase tracking-[0.06em] text-text-muted">
                    {claim.kind === "correlation" ? "corr" : "fact"}
                  </span>
                </td>
                <td className="py-2 pr-3 align-top text-[12.5px] leading-[1.5] text-text-soft">
                  {claim.text}
                </td>
                <td className="py-2 align-top">
                  <span className="flex flex-wrap gap-1">
                    {claim.chips.map((chip, j) => (
                      <ProvenanceChip key={j} refData={chip} />
                    ))}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CollapsibleSection>
  );
}
