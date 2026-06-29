import type { SpecialistLane as Lane } from "@/lib/types";
import { ACCENT, SHADOW } from "@/lib/ui";
import { Pill } from "@/components/ui/Pill";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { MicroStepPill } from "./MicroStepPill";
import { LaneRecordRow } from "./LaneRecordRow";

/** One source-specific specialist lane: backend badge, row/timing, the eight
 *  micro-step checkpoints, the validated query, and normalized records. */
export function SpecialistLane({ lane }: { lane: Lane }) {
  return (
    <div
      id={lane.id}
      className="mb-3 overflow-hidden rounded-[11px] bg-bg"
      style={{ boxShadow: SHADOW.lightRing }}
    >
      <div
        className="flex items-center gap-[9px] px-[13px] py-[11px]"
        style={{ boxShadow: SHADOW.insetTop }}
      >
        <Pill accent={lane.accent} className="px-2 py-0.5 text-[9.5px] tracking-[0.06em]">
          {lane.badge}
        </Pill>
        <span className="flex-1 text-[12.5px] font-semibold">{lane.title}</span>
        <span className="font-mono text-[11px]" style={{ color: ACCENT.teal.fg }}>
          {lane.rows} rows · {lane.ms}ms
        </span>
      </div>

      <div className="px-[13px] pb-[13px] pt-2.5">
        <div className="mb-[11px] flex flex-wrap gap-1.5">
          {lane.steps.map((step) => (
            <MicroStepPill key={step.key} step={step} />
          ))}
        </div>

        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
          Validated query
        </div>
        <CodeBlock code={lane.query} lang={lane.language} emphasis className="mb-[11px] leading-[1.6]" />

        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
          Evidence records
        </div>
        <div className="flex flex-col gap-[5px]">
          {lane.records.map((record) => (
            <LaneRecordRow key={record.id} record={record} />
          ))}
        </div>
      </div>
    </div>
  );
}
