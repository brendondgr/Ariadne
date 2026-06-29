"use client";

import type { PlannerStage } from "@/lib/types";
import { ACCENT, statusAccent } from "@/lib/ui";
import { CheckIcon, ShieldIcon } from "@/components/ui/icons";
import { Pill } from "@/components/ui/Pill";
import { CodeBlock } from "@/components/ui/CodeBlock";

interface TraceStageProps {
  stage: PlannerStage;
  open: boolean;
  onToggle: () => void;
}

function SummaryLine({ stage }: { stage: PlannerStage }) {
  if (stage.liveSources?.length) {
    return (
      <span>
        {stage.liveSources.map((s, i) => (
          <span key={s.backend}>
            {i > 0 && " · "}
            {s.backend}{" "}
            <span style={{ color: ACCENT.teal.fg }}>
              {s.status.toUpperCase()} · {s.nodes?.toLocaleString()}
            </span>
          </span>
        ))}
      </span>
    );
  }
  return <>{stage.summary}</>;
}

/** A planner-loop stage in the inspector timeline. Marker punches through the
 *  vertical thread; gate carries a shield. */
export function TraceStage({ stage, open, onToggle }: TraceStageProps) {
  const accent = ACCENT[statusAccent(stage.status)];
  const summaryColor = stage.shield ? ACCENT.teal.fg : "var(--color-text-muted)";

  return (
    <div id={stage.id} className="relative mb-[9px]">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-start gap-3 border-0 bg-transparent p-0 text-left"
      >
        <span
          aria-hidden
          className="mt-px flex h-[17px] w-[17px] flex-[0_0_auto] items-center justify-center rounded-full text-bg"
          style={{ background: accent.fg, boxShadow: "0 0 0 3px var(--color-surface)" }}
        >
          {stage.shield ? <ShieldIcon size={10} /> : <CheckIcon size={9} />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-[7px]">
            <span
              className="inline-block text-[10px] text-text-muted transition-transform"
              style={{ transform: open ? "rotate(90deg)" : "none" }}
            >
              ▶
            </span>
            <span className="font-mono text-[11px] tracking-[0.05em] text-text-muted">{stage.index}</span>
            <span className="text-[13px] font-semibold">{stage.title}</span>
            {stage.tag && (
              <Pill accent="teal" className="px-1.5 py-px text-[9px] tracking-[0.06em]">
                {stage.tag}
              </Pill>
            )}
          </span>
          <span className="mt-0.5 block pl-[18px] text-[11.5px]" style={{ color: summaryColor }}>
            <SummaryLine stage={stage} />
          </span>
        </span>
      </button>
      {open && (
        <div className="ml-[29px] mt-2">
          <CodeBlock code={stage.code} lang={stage.codeLang} emphasis={stage.codeEmphasis} />
        </div>
      )}
    </div>
  );
}
