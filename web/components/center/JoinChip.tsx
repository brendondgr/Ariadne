import type { JoinPair } from "@/lib/types";
import { ACCENT } from "@/lib/ui";
import { SHADOW } from "@/lib/ui";

/** A cross-source connector chip: `CAPEC-549 ⇄ T1047`. */
export function JoinChip({ pair }: { pair: JoinPair }) {
  return (
    <span
      className="inline-flex items-center gap-[7px] rounded-full bg-bg px-[11px] py-[5px] font-mono text-[11.5px] text-text"
      style={{ boxShadow: SHADOW.lightRing }}
    >
      <span style={{ color: ACCENT[pair.leftAccent].fg }}>{pair.left}</span>⇄
      <span style={{ color: ACCENT[pair.rightAccent].fg }}>{pair.right}</span>
    </span>
  );
}
