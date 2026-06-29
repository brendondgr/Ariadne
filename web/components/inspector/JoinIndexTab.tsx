import type { JoinCandidate } from "@/lib/types";
import { ACCENT, SHADOW } from "@/lib/ui";
import { ArrowRight } from "@/components/ui/icons";

const CONFIDENCE_ACCENT = { high: "teal", medium: "amber", low: "sage" } as const;

/** Cross-source join candidates aligned on the shared key. */
export function JoinIndexTab({ candidates, joinKey }: { candidates: JoinCandidate[]; joinKey: string }) {
  return (
    <div>
      <div className="mb-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
        Join index · key {joinKey} · {candidates.length} candidates
      </div>
      <div className="flex flex-col gap-[9px]">
        {candidates.map((c, i) => (
          <div
            key={i}
            className="rounded-[10px] bg-bg p-3.5"
            style={{ boxShadow: SHADOW.lightRing }}
          >
            <div className="mb-[9px] flex items-center justify-center gap-3">
              <span className="font-mono text-[13px]" style={{ color: ACCENT[c.leftAccent].fg }}>
                {c.left}
              </span>
              <span className="text-text-muted">
                <ArrowRight />
              </span>
              <span className="font-mono text-[13px]" style={{ color: ACCENT[c.rightAccent].fg }}>
                {c.right}
              </span>
            </div>
            <div className="text-center font-mono text-[10.5px] text-text-muted">
              matched on {c.matchedOn} · confidence{" "}
              <span style={{ color: ACCENT[CONFIDENCE_ACCENT[c.confidence]].fg }}>{c.confidence}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
