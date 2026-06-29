import type { EvidenceRow } from "@/lib/types";
import { ACCENT, SHADOW } from "@/lib/ui";

/** Normalized evidence records across all sub-questions. */
export function EvidenceTab({ evidence }: { evidence: EvidenceRow[] }) {
  return (
    <div>
      <div className="mb-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
        Normalized evidence · {evidence.length} records
      </div>
      <div className="flex flex-col gap-[7px]">
        {evidence.map((row) => (
          <div
            key={row.id}
            className="rounded-[9px] bg-bg px-3.5 py-[11px]"
            style={{ boxShadow: SHADOW.lightRing }}
          >
            <div className="mb-[5px] flex items-center gap-2">
              <span className="font-mono text-xs" style={{ color: ACCENT[row.accent].fg }}>
                {row.id}
              </span>
              <span
                className="rounded-full px-1.5 py-px font-mono text-[9px] text-text-muted"
                style={{ background: ACCENT.sage.tintBg }}
              >
                {row.label}
              </span>
            </div>
            <div className="mb-1 text-[13px] text-text">{row.name}</div>
            <div className="font-mono text-[10.5px] text-text-muted">{row.meta}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
